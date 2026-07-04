"""
Run a cheap kiosk deployment preflight against the running API.

The preflight calls GET /api/v1/readiness and prints a compact operator-facing
summary. It does not run model inference.
"""

from __future__ import annotations

import argparse
import json
import os
from typing import Any

import httpx


DEFAULT_BASE_URL = "http://127.0.0.1:8080"


def default_base_url() -> str:
    port = os.getenv("PORT", "8080").strip() or "8080"
    return f"http://127.0.0.1:{port}"


def run_preflight(
    *, base_url: str | None = None, timeout: float = 5.0
) -> dict[str, Any]:
    if base_url is None:
        base_url = default_base_url()
    endpoint = f"{base_url.rstrip('/')}/api/v1/readiness"
    try:
        response = httpx.get(endpoint, timeout=timeout)
    except httpx.HTTPError as exc:
        return {
            "success": False,
            "status": "unreachable",
            "endpoint": endpoint,
            "message": "Kiosk API readiness endpoint is not reachable.",
            "error": str(exc),
        }

    try:
        readiness_payload = response.json()
    except ValueError as exc:
        return {
            "success": False,
            "status": "invalid_response",
            "status_code": response.status_code,
            "endpoint": endpoint,
            "message": "Kiosk API readiness endpoint did not return JSON.",
            "error": str(exc),
        }

    readiness_status = str(readiness_payload.get("status", "unknown"))
    return {
        "success": response.status_code == 200 and readiness_status == "ready",
        "status": readiness_status,
        "status_code": response.status_code,
        "endpoint": endpoint,
        "checks": readiness_payload.get("checks", {}),
    }


def exit_code_for_result(result: dict[str, Any]) -> int:
    if result.get("success") is True:
        return 0
    if result.get("status") in {"unreachable", "invalid_response"}:
        return 2
    return 1


def format_human_summary(result: dict[str, Any]) -> str:
    lines = [
        f"Kiosk preflight: {'READY' if result.get('success') else 'NOT READY'}",
        f"Endpoint: {result.get('endpoint')}",
    ]
    if "status_code" in result:
        lines.append(f"HTTP status: {result['status_code']}")
    lines.append(f"Readiness status: {result.get('status')}")

    message = result.get("message")
    if message:
        lines.append(f"Message: {message}")
    error = result.get("error")
    if error:
        lines.append(f"Error: {error}")

    checks = result.get("checks")
    if isinstance(checks, dict) and checks:
        lines.append("")
        lines.append("Checks:")
        for name, check in checks.items():
            if not isinstance(check, dict):
                continue
            check_status = check.get("status", "unknown")
            check_message = check.get("message", "")
            lines.append(f"- {name}: {check_status} - {check_message}")
            if check_status != "ready":
                details = check.get("details") or {}
                if details:
                    details_json = json.dumps(details, sort_keys=True)
                    lines.append(f"  details: {details_json}")
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url",
        default=default_base_url(),
        help="Base URL for the running kiosk API.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=5.0,
        help="HTTP timeout in seconds.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON instead of a human summary.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = run_preflight(base_url=args.base_url, timeout=args.timeout)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(format_human_summary(result))
    return exit_code_for_result(result)


if __name__ == "__main__":
    raise SystemExit(main())
