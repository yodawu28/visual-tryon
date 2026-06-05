from src.modules.jobs.queue import JobService, JobStatus, LocalJobQueueBackend
from src.modules.jobs.worker import JobWorker


class EchoHandler:
    def handle(self, job):
        return {"echo": job.payload["value"]}


class FailingHandler:
    def handle(self, job):
        raise ValueError(f"bad job: {job.job_id}")


class FlakyHandler:
    def __init__(self):
        self.calls = 0

    def handle(self, job):
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("temporary provider failure")
        return {"ok": True}


def test_job_worker_runs_one_job_successfully(tmp_path):
    service = JobService(backend=LocalJobQueueBackend(job_dir=tmp_path / "jobs"))
    created = service.create_job(
        queue_name="gpu.visual_preview",
        job_type="echo",
        payload={"value": "ok"},
    )
    worker = JobWorker(job_service=service, handlers={"echo": EchoHandler()})

    result = worker.run_once(queue_name="gpu.visual_preview")

    assert result.processed is True
    assert result.job_id == created.job_id
    assert result.status == JobStatus.SUCCEEDED.value

    loaded = service.get_job(created.job_id)
    assert loaded.status == JobStatus.SUCCEEDED.value
    assert loaded.result == {"echo": "ok"}


def test_job_worker_marks_handler_exception_as_failed(tmp_path):
    service = JobService(backend=LocalJobQueueBackend(job_dir=tmp_path / "jobs"))
    created = service.create_job(
        queue_name="gpu.visual_preview",
        job_type="failing",
        payload={"value": "bad"},
    )
    worker = JobWorker(job_service=service, handlers={"failing": FailingHandler()})

    result = worker.run_once(queue_name="gpu.visual_preview")

    assert result.processed is True
    assert result.job_id == created.job_id
    assert result.status == JobStatus.FAILED.value
    assert result.error is not None
    assert result.error["error_type"] == "ValueError"

    loaded = service.get_job(created.job_id)
    assert loaded.status == JobStatus.FAILED.value
    assert loaded.error is not None
    assert "bad job" in loaded.error["message"]


def test_job_worker_requeues_failed_attempt_when_retry_remains(tmp_path):
    service = JobService(backend=LocalJobQueueBackend(job_dir=tmp_path / "jobs"))
    created = service.create_job(
        queue_name="gpu.visual_preview",
        job_type="flaky",
        payload={"value": "retry"},
        max_attempts=2,
    )
    handler = FlakyHandler()
    worker = JobWorker(job_service=service, handlers={"flaky": handler})

    first = worker.run_once(queue_name="gpu.visual_preview")

    assert first.processed is True
    assert first.job_id == created.job_id
    assert first.status == JobStatus.QUEUED.value

    retried = service.get_job(created.job_id)
    assert retried.status == JobStatus.QUEUED.value
    assert retried.attempts == 1
    assert retried.error is not None
    assert retried.error["error_type"] == "RuntimeError"

    second = worker.run_once(queue_name="gpu.visual_preview")

    assert second.processed is True
    assert second.job_id == created.job_id
    assert second.status == JobStatus.SUCCEEDED.value
    completed = service.get_job(created.job_id)
    assert completed.attempts == 2
    assert completed.result == {"ok": True}


def test_job_worker_returns_not_processed_when_queue_is_empty(tmp_path):
    service = JobService(backend=LocalJobQueueBackend(job_dir=tmp_path / "jobs"))
    worker = JobWorker(job_service=service, handlers={"echo": EchoHandler()})

    result = worker.run_once(queue_name="gpu.visual_preview")

    assert result.processed is False
    assert result.job_id is None
