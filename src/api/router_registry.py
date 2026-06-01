"""
API router profiles for deployment-specific Swagger surfaces.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from typing import Any

from fastapi import FastAPI


@dataclass(frozen=True)
class RouterSpec:
    name: str
    module: str
    attribute: str = "router"


KIOSK_ROUTER_SPECS: tuple[RouterSpec, ...] = (
    RouterSpec(name="health", module="src.api.routes.health"),
    RouterSpec(name="avatar_preview", module="src.api.routes.avatar_preview"),
    RouterSpec(name="kiosk_tryon", module="src.api.routes.kiosk_tryon"),
)

FULL_ROUTER_SPECS: tuple[RouterSpec, ...] = (
    RouterSpec(name="health", module="src.api.routes.health"),
    RouterSpec(name="privacy", module="src.api.routes.privacy"),
    RouterSpec(name="analysis", module="src.api.routes.analysis"),
    RouterSpec(name="generation", module="src.api.routes.generation"),
    RouterSpec(
        name="manual_generation",
        module="src.api.routes.generation",
        attribute="manual_router",
    ),
    RouterSpec(name="products", module="src.api.routes.products"),
    RouterSpec(name="avatar_preview", module="src.api.routes.avatar_preview"),
    RouterSpec(name="kiosk_tryon", module="src.api.routes.kiosk_tryon"),
)

API_PROFILE_ROUTER_SPECS: dict[str, tuple[RouterSpec, ...]] = {
    "kiosk": KIOSK_ROUTER_SPECS,
    "full": FULL_ROUTER_SPECS,
}


def get_router_specs_for_profile(profile: str) -> tuple[RouterSpec, ...]:
    normalized_profile = profile.strip().lower()
    try:
        return API_PROFILE_ROUTER_SPECS[normalized_profile]
    except KeyError as exc:
        supported = ", ".join(sorted(API_PROFILE_ROUTER_SPECS))
        raise ValueError(
            f"Unsupported API_PROFILE: {profile}. Supported: {supported}"
        ) from exc


def include_routers_for_profile(app: FastAPI, profile: str) -> None:
    for spec in get_router_specs_for_profile(profile):
        app.include_router(_load_router(spec))


def _load_router(spec: RouterSpec) -> Any:
    module = import_module(spec.module)
    return getattr(module, spec.attribute)
