import pytest

from meeting_assistant.utils.retry import with_retry


def test_retry_succeeds_and_is_bounded() -> None:
    calls = 0

    def flaky() -> str:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise TimeoutError
        return "ok"

    result = with_retry(
        flaky, attempts=3, retryable=lambda exc: isinstance(exc, TimeoutError), sleep=lambda _: None
    )
    assert result == "ok"
    assert calls == 3


def test_non_retryable_stops_immediately() -> None:
    with pytest.raises(ValueError):
        with_retry(
            lambda: (_ for _ in ()).throw(ValueError("bad")),
            attempts=4,
            retryable=lambda _: False,
            sleep=lambda _: None,
        )
