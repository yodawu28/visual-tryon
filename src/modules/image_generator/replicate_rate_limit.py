"""
Helpers for Replicate prediction creation retry behavior.
"""

from __future__ import annotations

import logging
import re
import time
from collections.abc import Callable
from typing import Any

from replicate.exceptions import ReplicateError

logger = logging.getLogger(__name__)


def create_prediction_with_rate_limit_retry(
    create_prediction: Callable[[], Any],
    *,
    max_attempts: int = 3,
    fallback_delay_seconds: float = 5.0,
) -> Any:
    """Retry Replicate prediction creation when account-level 429 throttling occurs."""
    for attempt_index in range(max_attempts):
        try:
            return create_prediction()
        except ReplicateError as exc:
            is_last_attempt = attempt_index == max_attempts - 1
            if exc.status != 429 or is_last_attempt:
                raise

            sleep_seconds = _rate_limit_sleep_seconds(
                detail=exc.detail,
                fallback_delay_seconds=fallback_delay_seconds,
                attempt_index=attempt_index,
            )
            logger.warning(
                "Replicate prediction creation throttled; retrying in %.1fs "
                "(attempt %s/%s)",
                sleep_seconds,
                attempt_index + 2,
                max_attempts,
            )
            time.sleep(sleep_seconds)

    raise RuntimeError("unreachable")


def _rate_limit_sleep_seconds(
    *,
    detail: str | None,
    fallback_delay_seconds: float,
    attempt_index: int,
) -> float:
    if detail:
        match = re.search(r"resets in ~?(\d+(?:\.\d+)?)s", detail)
        if match:
            return float(match.group(1)) + 1.0

    return fallback_delay_seconds * (attempt_index + 1)
