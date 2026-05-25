"""
Centralized error handling utilities.
"""

from typing import Optional, Callable, TypeVar, Any
from functools import wraps
import logging
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
from openai import RateLimitError, APIConnectionError

logger = logging.getLogger(__name__)

T = TypeVar("T")


class VTOError(Exception):
    """Base exception cho VTO application"""

    pass


class FaceDetectionError(VTOError):
    """Face detection failed"""

    pass


class AnonymizationError(VTOError):
    """Face anonymization failed"""

    pass


class OpenAIError(VTOError):
    """OpenAI API error"""

    pass


def handle_errors(fallback_value: Optional[Any] = None, error_class: type = VTOError):
    """
    Decorator cho graceful error handling.
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> T:
            try:
                return await func(*args, **kwargs)
            except error_class as e:
                logger.error(f"{func.__name__} failed: {e}")
                if fallback_value is not None:
                    return fallback_value
                raise

        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> T:
            try:
                return func(*args, **kwargs)
            except error_class as e:
                logger.error(f"{func.__name__} failed: {e}")
                if fallback_value is not None:
                    return fallback_value
                raise

        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


def retry_on_rate_limit(max_attempts: int = 3):
    """
    Decorator cho retry logic with exponential backoff on rate limits.
    """
    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((RateLimitError, APIConnectionError)),
        before_sleep=lambda retry_state: logger.warning(
            f"Rate limit hit, retrying in {retry_state.next_action.sleep} seconds..."
        ),
    )
