"""
Run a kiosk end-to-end baseline with local storage.

The default run exercises the control plane without paid image generation:
garment registry, session, captures, MediaPipe analysis, and Fit Intelligence.
Pass --run-visual-preview to enqueue and process one visual preview job through
the local worker. That mode can call the configured image generation provider.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.config.settings import get_settings
from src.modules.avatar_preview.tryon_analyzer import OllamaTryOnAnalyzer
from src.modules.image_generator.replicate_avatar_preview_generator import (
    ReplicateAvatarPreviewGenerator,
)
from src.modules.jobs.queue import JobService, LocalJobQueueBackend
from src.modules.jobs.worker import JobWorker
from src.modules.kiosk_tryon.capture_analyzer import MediaPipeKioskCaptureAnalyzer
from src.modules.kiosk_tryon.fit_intelligence import (
    KioskFitIntelligenceService,
    OllamaFitAnalyzer,
)
from src.modules.kiosk_tryon.garment_registry import GarmentRegistry
from src.modules.kiosk_tryon.job_handlers import (
    KIOSK_VISUAL_PREVIEW_JOB_TYPE,
    KIOSK_VISUAL_PREVIEW_QUEUE,
    KioskVisualPreviewJobHandler,
)
from src.modules.kiosk_tryon.service import KioskTryOnService
from src.modules.kiosk_tryon.visual_tryon import KioskVisualTryOnService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run kiosk E2E baseline")
    parser.add_argument("--front-image", required=True, type=Path)
    parser.add_argument("--side-image", type=Path)
    parser.add_argument("--garment-image", required=True, type=Path)
    parser.add_argument(
        "--garment-category",
        default="tops",
        choices=["tops", "bottoms", "one_pieces"],
    )
    parser.add_argument("--garment-type", default="shirt")
    parser.add_argument("--garment-name", default="baseline garment")
    parser.add_argument("--preferred-fit", default="regular")
    parser.add_argument(
        "--size-chart-json",
        type=Path,
        help="Optional JSON file containing a list of size chart rows",
    )
    parser.add_argument(
        "--body-measurements-json",
        type=Path,
        help="Optional JSON file containing body measurements in cm/kg",
    )
    parser.add_argument(
        "--use-ai-fit-analysis",
        action="store_true",
        help="Call the configured Ollama multimodal fit analyzer",
    )
    parser.add_argument(
        "--run-visual-preview",
        action="store_true",
        help="Enqueue and process one visual preview job; can call paid/provider model",
    )
    parser.add_argument(
        "--visual-preview-size",
        default="1024x1024",
        help="Requested visual preview size",
    )
    parser.add_argument(
        "--visual-preview-max-attempts",
        type=int,
        default=1,
        help="Max worker attempts for the visual preview job",
    )
    parser.add_argument(
        "--force-after-capture-fail",
        action="store_true",
        help="Continue report generation when capture analysis fails",
    )
    parser.add_argument(
        "--output-report",
        type=Path,
        help="Output report path. Defaults to data/e2e/kiosk-baseline-<timestamp>.json",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    settings = get_settings()
    output_report = args.output_report or _default_report_path(
        settings.temp_storage_dir
    )

    for input_path in [args.front_image, args.side_image, args.garment_image]:
        if input_path is not None and not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")

    garment_registry = _build_garment_registry(settings.temp_storage_dir)
    session_service = _build_session_service(
        settings.temp_storage_dir,
        garment_registry=garment_registry,
    )
    fit_service = _build_fit_service(
        settings.temp_storage_dir,
        use_ai_fit_analysis=args.use_ai_fit_analysis,
    )
    job_service = JobService(
        backend=LocalJobQueueBackend(job_dir=settings.job_queue_dir),
    )

    garment_image = args.garment_image.read_bytes()
    front_image = args.front_image.read_bytes()
    side_image = args.side_image.read_bytes() if args.side_image else None

    garment = garment_registry.create_garment(
        image_bytes=garment_image,
        category=args.garment_category,
        name=args.garment_name,
        garment_type=args.garment_type,
        original_filename=args.garment_image.name,
        max_size_bytes=settings.max_upload_size_bytes,
    )
    session = session_service.create_session(garment_id=garment.garment_id)
    session = session_service.add_user_capture(
        session_id=session.session_id,
        front_image=front_image,
        side_image=side_image,
    )
    session = session_service.analyze_user_capture(session_id=session.session_id)

    report: dict[str, Any] = {
        "started_at": datetime.now(UTC).isoformat(),
        "mode": {
            "use_ai_fit_analysis": args.use_ai_fit_analysis,
            "run_visual_preview": args.run_visual_preview,
            "force_after_capture_fail": args.force_after_capture_fail,
        },
        "inputs": {
            "front_image": str(args.front_image),
            "side_image": str(args.side_image) if args.side_image else None,
            "garment_image": str(args.garment_image),
            "garment_category": args.garment_category,
            "garment_type": args.garment_type,
            "preferred_fit": args.preferred_fit,
        },
        "garment": asdict(garment),
        "session": asdict(session),
        "fit": None,
        "visual_preview_job": None,
        "visual_preview_result": None,
        "status": (
            "capture_analysis_passed"
            if session.capture_analysis
            and session.capture_analysis.get("passed") is True
            else "capture_analysis_failed"
        ),
    }

    capture_passed = bool(
        session.capture_analysis and session.capture_analysis.get("passed") is True
    )
    if not capture_passed and not args.force_after_capture_fail:
        report["message"] = "Capture analysis failed; downstream model calls skipped."
        return _write_report(output_report, report)

    if capture_passed:
        fit = fit_service.analyze_fit(
            session_id=session.session_id,
            garment_id=garment.garment_id,
            garment_category=garment.category,
            garment_type=garment.garment_type,
            capture_analysis=session.capture_analysis or {},
            front_image=front_image,
            side_image=side_image,
            garment_image=garment_image,
            size_chart=_load_json_list(args.size_chart_json),
            preferred_fit=args.preferred_fit,
            body_measurements=_load_json_object(args.body_measurements_json),
            use_ai_analysis=args.use_ai_fit_analysis,
        )
        session = session_service.mark_fit_analysis_ready(
            session_id=session.session_id,
            fit_analysis_key=fit.fit_analysis_key,
        )
        report["fit"] = _fit_result_to_dict(fit)
        report["session"] = asdict(session)

    if args.run_visual_preview and capture_passed:
        job = job_service.create_job(
            queue_name=KIOSK_VISUAL_PREVIEW_QUEUE,
            job_type=KIOSK_VISUAL_PREVIEW_JOB_TYPE,
            payload={
                "session_id": session.session_id,
                "garment_id": garment.garment_id,
                "garment_category": garment.category,
                "garment_type": garment.garment_type,
                "capture_keys": session.capture_keys,
                "use_multimodal_analysis": True,
                "size": args.visual_preview_size,
            },
            max_attempts=args.visual_preview_max_attempts,
        )
        report["visual_preview_job"] = asdict(job)

        worker = _build_visual_preview_worker(
            settings.temp_storage_dir,
            job_service=job_service,
            garment_registry=garment_registry,
            session_service=session_service,
            settings=settings,
        )
        worker_result = worker.run_once(queue_name=KIOSK_VISUAL_PREVIEW_QUEUE)
        loaded_job = job_service.get_job(job.job_id)
        session = session_service.get_session(session.session_id)
        report["visual_preview_result"] = {
            "worker_result": asdict(worker_result),
            "job": asdict(loaded_job),
        }
        report["session"] = asdict(session)
        report["status"] = (
            "visual_preview_succeeded"
            if loaded_job.status == "succeeded"
            else "visual_preview_failed"
        )

    report["finished_at"] = datetime.now(UTC).isoformat()
    return _write_report(output_report, report)


def _build_garment_registry(data_dir: Path) -> GarmentRegistry:
    garment_dir = data_dir / "garments"
    return GarmentRegistry(
        db_path=garment_dir / "garments.sqlite3",
        image_dir=garment_dir / "images",
    )


def _build_session_service(
    data_dir: Path,
    *,
    garment_registry: GarmentRegistry,
) -> KioskTryOnService:
    return KioskTryOnService(
        session_dir=data_dir / "kiosk_sessions",
        capture_analyzer=MediaPipeKioskCaptureAnalyzer(),
        garment_registry=garment_registry,
    )


def _build_fit_service(
    data_dir: Path,
    *,
    use_ai_fit_analysis: bool,
) -> KioskFitIntelligenceService:
    settings = get_settings()
    analyzer = (
        OllamaFitAnalyzer(
            model=settings.tryon_analyzer_ollama_model,
            base_url=settings.ollama_base_url,
            timeout=settings.tryon_analyzer_timeout,
        )
        if use_ai_fit_analysis
        else None
    )
    return KioskFitIntelligenceService(
        fit_dir=data_dir / "kiosk_fit",
        fit_analyzer=analyzer,
    )


def _build_visual_preview_worker(
    data_dir: Path,
    *,
    job_service: JobService,
    garment_registry: GarmentRegistry,
    session_service: KioskTryOnService,
    settings: Any,
) -> JobWorker:
    visual_tryon_service = KioskVisualTryOnService(
        tryon_dir=data_dir / "kiosk_tryons",
        generator=_build_visual_preview_generator(settings),
        tryon_analyzer=OllamaTryOnAnalyzer(
            model=settings.tryon_analyzer_ollama_model,
            base_url=settings.ollama_base_url,
            timeout=settings.tryon_analyzer_timeout,
        ),
    )
    return JobWorker(
        job_service=job_service,
        stale_running_seconds=1800,
        handlers={
            KIOSK_VISUAL_PREVIEW_JOB_TYPE: KioskVisualPreviewJobHandler(
                session_service=session_service,
                garment_registry=garment_registry,
                visual_tryon_service=visual_tryon_service,
            )
        },
    )


def _build_visual_preview_generator(settings: Any) -> Any:
    provider = (
        str(
            getattr(settings, "kiosk_visual_preview_provider", "disabled") or "disabled"
        )
        .strip()
        .lower()
    )
    if provider == "replicate_qwen":
        return ReplicateAvatarPreviewGenerator()
    raise RuntimeError(
        "Kiosk visual preview provider is disabled. Production kiosk visual "
        "preview requires a self-hosted GPU engine; use "
        "KIOSK_VISUAL_PREVIEW_PROVIDER=replicate_qwen only for benchmark/debug."
    )


def _load_json_list(path: Path | None) -> list[dict[str, Any]]:
    if path is None:
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"Expected JSON list: {path}")
    return [dict(item) for item in payload]


def _load_json_object(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return dict(payload)


def _fit_result_to_dict(fit: Any) -> dict[str, Any]:
    payload = asdict(fit)
    payload["fit_analysis_path"] = str(fit.fit_analysis_path)
    return payload


def _default_report_path(data_dir: Path) -> Path:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return data_dir / "e2e" / f"kiosk-baseline-{timestamp}.json"


def _write_report(path: Path, report: dict[str, Any]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(f"Report written to {path}")
    print(json.dumps({"status": report.get("status"), "report_path": str(path)}))
    return 0 if str(report.get("status", "")).endswith("succeeded") else 0


if __name__ == "__main__":
    raise SystemExit(main())
