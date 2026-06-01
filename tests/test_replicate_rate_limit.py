from unittest.mock import Mock

import pytest
from replicate.exceptions import ReplicateError

from src.modules.image_generator import replicate_rate_limit
from src.modules.image_generator.replicate_rate_limit import (
    create_prediction_with_rate_limit_retry,
)


def test_create_prediction_retries_replicate_429_with_reset_hint(monkeypatch):
    sleep = Mock()
    monkeypatch.setattr(replicate_rate_limit.time, "sleep", sleep)
    create_prediction = Mock(
        side_effect=[
            ReplicateError(status=429, detail="rate limit resets in ~4s."),
            "prediction",
        ]
    )

    result = create_prediction_with_rate_limit_retry(create_prediction)

    assert result == "prediction"
    assert create_prediction.call_count == 2
    sleep.assert_called_once_with(5.0)


def test_create_prediction_retries_replicate_429_with_fallback_delay(monkeypatch):
    sleep = Mock()
    monkeypatch.setattr(replicate_rate_limit.time, "sleep", sleep)
    create_prediction = Mock(
        side_effect=[
            ReplicateError(status=429, detail="throttled"),
            "prediction",
        ]
    )

    result = create_prediction_with_rate_limit_retry(
        create_prediction,
        fallback_delay_seconds=2.0,
    )

    assert result == "prediction"
    sleep.assert_called_once_with(2.0)


def test_create_prediction_does_not_retry_non_rate_limit_errors(monkeypatch):
    sleep = Mock()
    monkeypatch.setattr(replicate_rate_limit.time, "sleep", sleep)
    create_prediction = Mock(
        side_effect=ReplicateError(status=500, detail="server error")
    )

    with pytest.raises(ReplicateError):
        create_prediction_with_rate_limit_retry(create_prediction)

    assert create_prediction.call_count == 1
    sleep.assert_not_called()
