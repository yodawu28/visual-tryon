from datetime import datetime, timedelta, timezone

from src.modules.jobs.queue import JobService, JobStatus, LocalJobQueueBackend


def test_local_job_queue_creates_leases_and_completes_job(tmp_path):
    service = JobService(backend=LocalJobQueueBackend(job_dir=tmp_path / "jobs"))

    created = service.create_job(
        queue_name="gpu.visual_preview",
        job_type="kiosk_visual_preview",
        payload={"session_id": "kiosk-session:v1:test"},
        max_attempts=2,
    )

    assert created.job_id.startswith("job:v1:")
    assert created.status == JobStatus.QUEUED.value
    assert created.attempts == 0

    loaded = service.get_job(created.job_id)
    assert loaded.payload == {"session_id": "kiosk-session:v1:test"}

    leased = service.lease_next(queue_name="gpu.visual_preview")
    assert leased is not None
    assert leased.job_id == created.job_id
    assert leased.status == JobStatus.RUNNING.value
    assert leased.attempts == 1
    assert leased.started_at is not None

    assert service.lease_next(queue_name="gpu.visual_preview") is None

    completed = service.mark_succeeded(
        job_id=created.job_id,
        result={"personalized_tryon_key": "kiosk-tryon:v1:test"},
    )
    assert completed.status == JobStatus.SUCCEEDED.value
    assert completed.finished_at is not None
    assert completed.result == {"personalized_tryon_key": "kiosk-tryon:v1:test"}
    assert completed.error is None


def test_local_job_queue_marks_failure(tmp_path):
    service = JobService(backend=LocalJobQueueBackend(job_dir=tmp_path / "jobs"))
    created = service.create_job(
        queue_name="gpu.fit",
        job_type="kiosk_fit_analysis",
        payload={"session_id": "kiosk-session:v1:test"},
    )

    failed = service.mark_failed(
        job_id=created.job_id,
        error={"message": "worker unavailable"},
    )

    assert failed.status == JobStatus.FAILED.value
    assert failed.error == {"message": "worker unavailable"}
    assert failed.finished_at is not None


def test_local_job_queue_requeues_stale_running_job_when_attempts_remain(tmp_path):
    backend = LocalJobQueueBackend(job_dir=tmp_path / "jobs")
    service = JobService(backend=backend)
    created = service.create_job(
        queue_name="gpu.visual_preview",
        job_type="kiosk_visual_preview",
        payload={"session_id": "kiosk-session:v1:test"},
        max_attempts=2,
    )
    leased = service.lease_next(queue_name="gpu.visual_preview")
    assert leased is not None

    stale_started_at = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    backend.update(created.job_id, started_at=stale_started_at)

    recovered = service.requeue_stale_running(
        queue_name="gpu.visual_preview",
        stale_after_seconds=60,
    )

    assert len(recovered) == 1
    assert recovered[0].status == JobStatus.QUEUED.value
    assert recovered[0].attempts == 1
    assert recovered[0].started_at is None
    assert recovered[0].error is not None
    assert recovered[0].error["error_type"] == "JobLeaseExpired"


def test_local_job_queue_fails_stale_running_job_after_max_attempts(tmp_path):
    backend = LocalJobQueueBackend(job_dir=tmp_path / "jobs")
    service = JobService(backend=backend)
    created = service.create_job(
        queue_name="gpu.visual_preview",
        job_type="kiosk_visual_preview",
        payload={"session_id": "kiosk-session:v1:test"},
        max_attempts=1,
    )
    leased = service.lease_next(queue_name="gpu.visual_preview")
    assert leased is not None

    stale_started_at = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    backend.update(created.job_id, started_at=stale_started_at)

    recovered = service.requeue_stale_running(
        queue_name="gpu.visual_preview",
        stale_after_seconds=60,
    )

    assert len(recovered) == 1
    assert recovered[0].status == JobStatus.FAILED.value
    assert recovered[0].finished_at is not None
    assert recovered[0].error is not None
    assert recovered[0].error["error_type"] == "JobLeaseExpired"
