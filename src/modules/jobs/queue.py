"""
Backend-neutral job queue primitives.

The local backend is intentionally small and file-backed. Redis/Kafka backends can
implement the same protocol without changing kiosk route contracts.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass(frozen=True)
class JobRecord:
    job_id: str
    queue_name: str
    job_type: str
    status: str
    payload: dict[str, Any]
    result: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
    attempts: int = 0
    max_attempts: int = 1
    created_at: str = field(default_factory=lambda: _now_iso())
    updated_at: str = field(default_factory=lambda: _now_iso())
    started_at: str | None = None
    finished_at: str | None = None


class JobQueueBackend(Protocol):
    def enqueue(self, record: JobRecord) -> JobRecord:
        """Persist a queued job."""

    def get(self, job_id: str) -> JobRecord:
        """Load one job by id."""

    def update(self, job_id: str, **fields: Any) -> JobRecord:
        """Update fields for one job."""

    def lease_next(
        self,
        *,
        queue_name: str,
        job_types: set[str] | None = None,
    ) -> JobRecord | None:
        """Claim the next queued job for a worker."""

    def requeue_stale_running(
        self,
        *,
        queue_name: str,
        stale_after_seconds: int,
    ) -> list[JobRecord]:
        """Move old running jobs back to queued or failed."""


class LocalJobQueueBackend:
    """
    Local JSON-file backend for development and single-node deployments.

    This backend is not meant to provide distributed locking. Redis/Kafka should
    be used once multiple workers or multiple API instances are active.
    """

    def __init__(self, *, job_dir: Path) -> None:
        self.job_dir = Path(job_dir)
        self.metadata_dir = self.job_dir / "metadata"
        self.metadata_dir.mkdir(parents=True, exist_ok=True)

    def enqueue(self, record: JobRecord) -> JobRecord:
        path = self._job_path(record.job_id)
        if path.exists():
            raise ValueError(f"Job already exists: {record.job_id}")
        self._write_record(record)
        return record

    def get(self, job_id: str) -> JobRecord:
        path = self._job_path(job_id)
        if not path.exists():
            raise FileNotFoundError(f"Job not found: {job_id}")
        return self._read_record(path)

    def update(self, job_id: str, **fields: Any) -> JobRecord:
        record = self.get(job_id)
        updated = replace(record, **_jsonable(fields), updated_at=_now_iso())
        self._write_record(updated)
        return updated

    def lease_next(
        self,
        *,
        queue_name: str,
        job_types: set[str] | None = None,
    ) -> JobRecord | None:
        candidates = []
        for path in self.metadata_dir.glob("*.json"):
            record = self._read_record(path)
            if record.queue_name != queue_name:
                continue
            if record.status != JobStatus.QUEUED.value:
                continue
            if job_types is not None and record.job_type not in job_types:
                continue
            candidates.append(record)

        if not candidates:
            return None

        candidates.sort(key=lambda item: item.created_at)
        record = candidates[0]
        return self.update(
            record.job_id,
            status=JobStatus.RUNNING.value,
            attempts=record.attempts + 1,
            started_at=_now_iso(),
            error=None,
        )

    def requeue_stale_running(
        self,
        *,
        queue_name: str,
        stale_after_seconds: int,
    ) -> list[JobRecord]:
        if stale_after_seconds <= 0:
            raise ValueError("stale_after_seconds must be positive")

        cutoff = datetime.now(timezone.utc) - timedelta(seconds=stale_after_seconds)
        updated_records: list[JobRecord] = []

        for path in self.metadata_dir.glob("*.json"):
            record = self._read_record(path)
            if record.queue_name != queue_name:
                continue
            if record.status != JobStatus.RUNNING.value:
                continue
            if record.started_at is None:
                continue
            if _parse_iso(record.started_at) > cutoff:
                continue

            error = {
                "message": "Job lease expired before completion",
                "error_type": "JobLeaseExpired",
                "attempts": record.attempts,
                "max_attempts": record.max_attempts,
            }
            if record.attempts < record.max_attempts:
                updated_records.append(
                    self.update(
                        record.job_id,
                        status=JobStatus.QUEUED.value,
                        error=error,
                        started_at=None,
                    )
                )
            else:
                updated_records.append(
                    self.update(
                        record.job_id,
                        status=JobStatus.FAILED.value,
                        error=error,
                        finished_at=_now_iso(),
                    )
                )

        return updated_records

    def _job_path(self, job_id: str) -> Path:
        return self.metadata_dir / f"{_safe_id(job_id)}.json"

    def _write_record(self, record: JobRecord) -> None:
        path = self._job_path(record.job_id)
        path.write_text(
            json.dumps(_jsonable(asdict(record)), indent=2, sort_keys=True),
            "utf-8",
        )

    def _read_record(self, path: Path) -> JobRecord:
        payload = json.loads(path.read_text("utf-8"))
        return JobRecord(**payload)


class JobService:
    def __init__(self, *, backend: JobQueueBackend) -> None:
        self.backend = backend

    def create_job(
        self,
        *,
        queue_name: str,
        job_type: str,
        payload: dict[str, Any],
        max_attempts: int = 1,
    ) -> JobRecord:
        if not queue_name:
            raise ValueError("queue_name is required")
        if not job_type:
            raise ValueError("job_type is required")
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")

        record = JobRecord(
            job_id=f"job:v1:{uuid4().hex}",
            queue_name=queue_name,
            job_type=job_type,
            status=JobStatus.QUEUED.value,
            payload=dict(payload),
            max_attempts=max_attempts,
        )
        return self.backend.enqueue(record)

    def get_job(self, job_id: str) -> JobRecord:
        return self.backend.get(job_id)

    def lease_next(
        self,
        *,
        queue_name: str,
        job_types: set[str] | None = None,
    ) -> JobRecord | None:
        return self.backend.lease_next(queue_name=queue_name, job_types=job_types)

    def mark_succeeded(
        self,
        *,
        job_id: str,
        result: dict[str, Any] | None = None,
    ) -> JobRecord:
        return self.backend.update(
            job_id,
            status=JobStatus.SUCCEEDED.value,
            result=result or {},
            error=None,
            finished_at=_now_iso(),
        )

    def mark_failed(
        self,
        *,
        job_id: str,
        error: dict[str, Any],
    ) -> JobRecord:
        return self.backend.update(
            job_id,
            status=JobStatus.FAILED.value,
            error=dict(error),
            finished_at=_now_iso(),
        )

    def mark_attempt_failed(
        self,
        *,
        job_id: str,
        error: dict[str, Any],
    ) -> JobRecord:
        record = self.get_job(job_id)
        if record.attempts < record.max_attempts:
            return self.backend.update(
                job_id,
                status=JobStatus.QUEUED.value,
                error=dict(error),
                started_at=None,
            )
        return self.mark_failed(job_id=job_id, error=error)

    def requeue_stale_running(
        self,
        *,
        queue_name: str,
        stale_after_seconds: int,
    ) -> list[JobRecord]:
        return self.backend.requeue_stale_running(
            queue_name=queue_name,
            stale_after_seconds=stale_after_seconds,
        )


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_id(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in value)


def _jsonable(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    return value


def _parse_iso(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
