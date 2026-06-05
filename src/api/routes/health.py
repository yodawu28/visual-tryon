"""
Health check endpoints.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import httpx
from fastapi import APIRouter, Response, status

from src.config.settings import get_settings
from src.modules.kiosk_tryon.garment_registry import GarmentRegistry
from src.modules.kiosk_tryon.size_chart_registry import SizeChartRegistry
from src.schemas.responses import (
    HealthResponse,
    ReadinessCheckResponse,
    ReadinessResponse,
)

router = APIRouter(prefix="/api/v1", tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint.
    Returns status và available modules.
    """
    return HealthResponse(
        status="healthy", modules=["privacy_guard", "semantic_parser"]
    )


@router.get("/readiness", response_model=ReadinessResponse)
async def readiness_check(response: Response) -> ReadinessResponse:
    """
    Deployment readiness check for kiosk API dependencies.

    This endpoint avoids expensive model calls. It verifies local storage,
    SQLite catalogs, job queue paths, and provider configuration so deploys can
    fail fast before a user starts a kiosk flow.
    """

    settings = get_settings()
    _ensure_kiosk_sqlite_schemas(settings)
    checks = {
        "storage": _check_writable_directory(settings.temp_storage_dir),
        "garment_registry": _check_sqlite_database(
            settings.temp_storage_dir / "garments" / "garments.sqlite3",
            required_table="garments",
        ),
        "size_chart_registry": _check_sqlite_database(
            settings.temp_storage_dir / "size_charts" / "size_charts.sqlite3",
            required_table="size_charts",
        ),
        "job_queue": _check_writable_directory(settings.job_queue_dir),
        "ollama_analyzer_config": _check_ollama_analyzer_config(settings),
        "replicate_preview_config": _check_replicate_preview_config(settings),
    }

    overall_status = (
        "ready"
        if all(check.status == "ready" for check in checks.values())
        else "not_ready"
    )
    if overall_status != "ready":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return ReadinessResponse(status=overall_status, checks=checks)


def _ensure_kiosk_sqlite_schemas(settings: Any) -> None:
    garment_dir = settings.temp_storage_dir / "garments"
    GarmentRegistry(
        db_path=garment_dir / "garments.sqlite3",
        image_dir=garment_dir / "images",
    )
    SizeChartRegistry(
        db_path=settings.temp_storage_dir / "size_charts" / "size_charts.sqlite3"
    )


def _check_writable_directory(path: Path) -> ReadinessCheckResponse:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe_path = path / ".readiness_probe"
        probe_path.write_text("ok", encoding="utf-8")
        probe_path.unlink(missing_ok=True)
    except Exception as exc:
        return ReadinessCheckResponse(
            status="not_ready",
            message=f"Directory is not writable: {path}",
            details={"path": str(path), "error": str(exc)},
        )
    return ReadinessCheckResponse(
        status="ready",
        message="Directory is writable",
        details={"path": str(path)},
    )


def _check_sqlite_database(
    db_path: Path,
    *,
    required_table: str,
) -> ReadinessCheckResponse:
    if not required_table.isidentifier():
        return ReadinessCheckResponse(
            status="not_ready",
            message=f"SQLite table name is invalid: {required_table}",
            details={"db_path": str(db_path), "required_table": required_table},
        )
    try:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(db_path) as conn:
            row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
                (required_table,),
            ).fetchone()
            if row is None:
                return ReadinessCheckResponse(
                    status="not_ready",
                    message=f"SQLite table is missing: {required_table}",
                    details={
                        "db_path": str(db_path),
                        "required_table": required_table,
                    },
                )
            conn.execute(f"SELECT COUNT(*) FROM {required_table}").fetchone()
    except Exception as exc:
        return ReadinessCheckResponse(
            status="not_ready",
            message=f"SQLite database is not readable: {db_path}",
            details={
                "db_path": str(db_path),
                "required_table": required_table,
                "error": str(exc),
            },
        )
    return ReadinessCheckResponse(
        status="ready",
        message="SQLite database is readable",
        details={"db_path": str(db_path), "required_table": required_table},
    )


def _check_ollama_analyzer_config(settings: Any) -> ReadinessCheckResponse:
    model = str(settings.tryon_analyzer_ollama_model or "").strip()
    base_url = str(settings.ollama_base_url or "").strip()
    if not model:
        return ReadinessCheckResponse(
            status="not_ready",
            message="TRYON_ANALYZER_OLLAMA_MODEL is not configured",
            details={"ollama_base_url": base_url},
        )
    if not base_url:
        return ReadinessCheckResponse(
            status="not_ready",
            message="OLLAMA_BASE_URL is not configured",
            details={"model": model},
        )
    tags_url = f"{base_url.rstrip('/')}/api/tags"
    try:
        response = httpx.get(tags_url, timeout=3.0)
        response.raise_for_status()
        model_names = _extract_ollama_model_names(response.json())
    except (httpx.HTTPError, ValueError) as exc:
        return ReadinessCheckResponse(
            status="not_ready",
            message="Ollama analyzer runtime is not reachable",
            details={
                "ollama_base_url": base_url,
                "model": model,
                "tags_url": tags_url,
                "error": str(exc),
            },
        )
    if model not in model_names:
        return ReadinessCheckResponse(
            status="not_ready",
            message="Ollama analyzer model is not installed",
            details={
                "ollama_base_url": base_url,
                "model": model,
                "available_models": model_names[:20],
            },
        )
    return ReadinessCheckResponse(
        status="ready",
        message="Ollama analyzer runtime and model are ready",
        details={
            "ollama_base_url": base_url,
            "model": model,
            "model_count": len(model_names),
        },
    )


def _extract_ollama_model_names(payload: Any) -> list[str]:
    if not isinstance(payload, dict):
        raise ValueError("Ollama /api/tags response must be a JSON object")
    models = payload.get("models")
    if not isinstance(models, list):
        raise ValueError("Ollama /api/tags response is missing models list")

    model_names: list[str] = []
    for item in models:
        if not isinstance(item, dict):
            continue
        name = item.get("name") or item.get("model")
        if isinstance(name, str) and name.strip():
            model_names.append(name.strip())
    return model_names


def _check_replicate_preview_config(settings: Any) -> ReadinessCheckResponse:
    model = str(settings.replicate_preview_model or "").strip()
    token = str(settings.replicate_api_token or "").strip()
    if not model:
        return ReadinessCheckResponse(
            status="not_ready",
            message="REPLICATE_PREVIEW_MODEL is not configured",
            details={},
        )
    if not token:
        return ReadinessCheckResponse(
            status="not_ready",
            message="REPLICATE_API_TOKEN is not configured",
            details={"model": model},
        )
    return ReadinessCheckResponse(
        status="ready",
        message="Replicate preview config is present",
        details={
            "model": model,
            "token_configured": True,
            "input_mapping": settings.replicate_preview_input_mapping,
        },
    )
