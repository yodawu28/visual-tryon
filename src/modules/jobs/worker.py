"""
Small worker loop for backend-neutral jobs.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Protocol

from src.modules.jobs.queue import JobRecord, JobService

logger = logging.getLogger(__name__)


class JobHandler(Protocol):
    def handle(self, job: JobRecord) -> dict[str, Any]:
        """Run one job and return a JSON-serializable result payload."""


@dataclass(frozen=True)
class JobWorkerResult:
    processed: bool
    job_id: str | None = None
    status: str | None = None
    error: dict[str, Any] | None = None


class JobWorker:
    """
    Polling worker for local and future queue backends.

    The worker only depends on JobService. Queue-specific behavior belongs in
    the backend implementation.
    """

    def __init__(
        self,
        *,
        job_service: JobService,
        handlers: dict[str, JobHandler],
        stale_running_seconds: int | None = None,
    ) -> None:
        self.job_service = job_service
        self.handlers = dict(handlers)
        self.stale_running_seconds = stale_running_seconds

    def run_once(self, *, queue_name: str) -> JobWorkerResult:
        if self.stale_running_seconds is not None:
            requeued = self.job_service.requeue_stale_running(
                queue_name=queue_name,
                stale_after_seconds=self.stale_running_seconds,
            )
            if requeued:
                logger.warning(
                    "Recovered %s stale running job(s) for queue=%s",
                    len(requeued),
                    queue_name,
                )

        job = self.job_service.lease_next(
            queue_name=queue_name,
            job_types=set(self.handlers),
        )
        if job is None:
            return JobWorkerResult(processed=False)

        handler = self.handlers.get(job.job_type)
        if handler is None:
            unsupported_error: dict[str, Any] = {
                "message": f"Unsupported job_type: {job.job_type}",
                "job_type": job.job_type,
            }
            failed = self.job_service.mark_failed(
                job_id=job.job_id,
                error=unsupported_error,
            )
            return JobWorkerResult(
                processed=True,
                job_id=failed.job_id,
                status=failed.status,
                error=unsupported_error,
            )

        try:
            logger.info("Running job %s (%s)", job.job_id, job.job_type)
            started = time.perf_counter()
            result = handler.handle(job)
        except Exception as exc:  # pragma: no cover - covered via public behavior
            duration_seconds = time.perf_counter() - started
            logger.exception(
                "Job %s failed after %.2fs",
                job.job_id,
                duration_seconds,
            )
            error: dict[str, Any] = {
                "message": str(exc),
                "error_type": type(exc).__name__,
                "attempts": job.attempts,
                "max_attempts": job.max_attempts,
            }
            failed = self.job_service.mark_attempt_failed(
                job_id=job.job_id,
                error=error,
            )
            return JobWorkerResult(
                processed=True,
                job_id=failed.job_id,
                status=failed.status,
                error=error,
            )

        completed = self.job_service.mark_succeeded(job_id=job.job_id, result=result)
        duration_seconds = time.perf_counter() - started
        logger.info(
            "Job %s completed with status=%s in %.2fs",
            completed.job_id,
            completed.status,
            duration_seconds,
        )
        return JobWorkerResult(
            processed=True,
            job_id=completed.job_id,
            status=completed.status,
        )

    def run_forever(
        self,
        *,
        queue_name: str,
        poll_interval_seconds: float,
    ) -> None:
        if poll_interval_seconds <= 0:
            raise ValueError("poll_interval_seconds must be positive")

        logger.info("Starting worker loop for queue=%s", queue_name)
        while True:
            result = self.run_once(queue_name=queue_name)
            if not result.processed:
                time.sleep(poll_interval_seconds)
