"""
Run the local kiosk worker.

Example:
    python -m scripts.run_kiosk_worker --once
"""

from __future__ import annotations

import argparse
import logging

from src.config.settings import get_settings
from src.modules.avatar_preview.tryon_analyzer import OllamaTryOnAnalyzer
from src.modules.image_generator.local_leffa_kiosk_generator import (
    LocalLeffaKioskGenerator,
)
from src.modules.image_generator.replicate_avatar_preview_generator import (
    ReplicateAvatarPreviewGenerator,
)
from src.modules.jobs.queue import JobService, LocalJobQueueBackend
from src.modules.jobs.worker import JobWorker
from src.modules.kiosk_tryon.capture_analyzer import MediaPipeKioskCaptureAnalyzer
from src.modules.kiosk_tryon.garment_registry import GarmentRegistry
from src.modules.kiosk_tryon.job_handlers import (
    KIOSK_VISUAL_PREVIEW_JOB_TYPE,
    KIOSK_VISUAL_PREVIEW_QUEUE,
    KioskVisualPreviewJobHandler,
)
from src.modules.kiosk_tryon.service import KioskTryOnService
from src.modules.kiosk_tryon.visual_tryon import KioskVisualTryOnService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run kiosk local job worker")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Process at most one queued job and exit",
    )
    parser.add_argument(
        "--queue-name",
        default=KIOSK_VISUAL_PREVIEW_QUEUE,
        help="Queue name to poll",
    )
    parser.add_argument(
        "--poll-interval-seconds",
        type=float,
        default=2.0,
        help="Sleep interval when no job is available",
    )
    parser.add_argument(
        "--stale-running-seconds",
        type=int,
        default=1800,
        help=(
            "Recover running jobs older than this many seconds before polling. "
            "Use 0 to disable stale job recovery."
        ),
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    return parser.parse_args()


def build_worker(*, stale_running_seconds: int | None = 1800) -> JobWorker:
    settings = get_settings()
    if settings.job_queue_backend.strip().lower() != "local":
        raise RuntimeError(
            "scripts.run_kiosk_worker currently supports JOB_QUEUE_BACKEND=local"
        )

    garment_dir = settings.temp_storage_dir / "garments"
    garment_registry = GarmentRegistry(
        db_path=garment_dir / "garments.sqlite3",
        image_dir=garment_dir / "images",
    )
    session_service = KioskTryOnService(
        session_dir=settings.temp_storage_dir / "kiosk_sessions",
        capture_analyzer=MediaPipeKioskCaptureAnalyzer(),
        garment_registry=garment_registry,
    )
    visual_tryon_service = KioskVisualTryOnService(
        tryon_dir=settings.temp_storage_dir / "kiosk_tryons",
        generator=_build_kiosk_visual_generator(settings),
        tryon_analyzer=OllamaTryOnAnalyzer(
            model=settings.tryon_analyzer_ollama_model,
            base_url=settings.ollama_base_url,
            timeout=settings.tryon_analyzer_timeout,
        ),
    )
    job_service = JobService(
        backend=LocalJobQueueBackend(job_dir=settings.job_queue_dir),
    )

    return JobWorker(
        job_service=job_service,
        stale_running_seconds=stale_running_seconds,
        handlers={
            KIOSK_VISUAL_PREVIEW_JOB_TYPE: KioskVisualPreviewJobHandler(
                session_service=session_service,
                garment_registry=garment_registry,
                visual_tryon_service=visual_tryon_service,
            )
        },
    )


def _build_kiosk_visual_generator(settings):
    provider = (
        str(
            getattr(settings, "kiosk_visual_preview_provider", "disabled") or "disabled"
        )
        .strip()
        .lower()
    )
    if provider == "replicate_qwen":
        return ReplicateAvatarPreviewGenerator()
    if provider in {"local_leffa", "leffa"}:
        return LocalLeffaKioskGenerator(
            work_dir=settings.temp_storage_dir / "kiosk_tryons" / "leffa_work",
            leffa_root=settings.local_leffa_root,
            repo_url=settings.local_leffa_repo_url,
            model_repo_id=settings.local_leffa_model_repo_id,
            checkpoint_dir=settings.local_leffa_checkpoint_dir,
            python_executable=settings.local_leffa_python,
            hf_home=settings.local_leffa_hf_home,
            torch_home=settings.local_leffa_torch_home,
            xdg_cache_home=settings.local_leffa_xdg_cache_home,
            no_clone=bool(settings.local_leffa_no_clone),
            size=settings.local_leffa_size,
            device=settings.local_leffa_device,
            dtype=settings.local_leffa_dtype,
            vt_model_type=settings.local_leffa_vt_model_type,
            steps=int(settings.local_leffa_steps),
            guidance_scale=float(settings.local_leffa_guidance_scale),
            seed=int(settings.local_leffa_seed),
            ref_acceleration=bool(settings.local_leffa_ref_acceleration),
            repaint=bool(settings.local_leffa_repaint),
            preprocess_garment=bool(settings.local_leffa_preprocess_garment),
            timeout_seconds=int(settings.local_leffa_timeout),
            execution_mode=settings.local_visual_engine_mode,
            service_url=settings.local_visual_engine_service_url,
            service_ready_timeout_seconds=int(
                settings.local_visual_engine_service_ready_timeout
            ),
            service_request_timeout_seconds=int(
                settings.effective_local_visual_engine_service_request_timeout
            ),
        )
    raise RuntimeError(
        "Kiosk visual preview provider is disabled. Production kiosk visual "
        "preview requires a self-hosted GPU engine; Replicate Qwen is available "
        "only by explicitly setting KIOSK_VISUAL_PREVIEW_PROVIDER=replicate_qwen "
        "for benchmark/debug."
    )


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    stale_running_seconds = (
        None if args.stale_running_seconds == 0 else args.stale_running_seconds
    )
    worker = build_worker(stale_running_seconds=stale_running_seconds)
    if args.once:
        result = worker.run_once(queue_name=args.queue_name)
        if result.processed:
            logging.info("Processed job_id=%s status=%s", result.job_id, result.status)
        else:
            logging.info("No queued job found for queue=%s", args.queue_name)
        return 0

    worker.run_forever(
        queue_name=args.queue_name,
        poll_interval_seconds=args.poll_interval_seconds,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
