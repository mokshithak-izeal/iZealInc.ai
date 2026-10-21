import pytest
from google.genai import errors

from app.agents import gemini_retry


def api_error(code):
    return errors.APIError(code=code, response_json={})


def test_with_retry_retries_transient_errors_and_returns_result(monkeypatch):
    calls = []
    delays = []
    monkeypatch.setattr(gemini_retry.time, "sleep", delays.append)

    def call():
        calls.append(None)
        if len(calls) < 3:
            raise api_error(503)
        return "success"

    assert gemini_retry.with_retry(call, delay=2) == "success"
    assert len(calls) == 3
    assert delays == [2, 4]


def test_with_retry_does_not_retry_non_transient_errors(monkeypatch):
    delays = []
    monkeypatch.setattr(gemini_retry.time, "sleep", delays.append)

    with pytest.raises(errors.APIError) as raised:
        gemini_retry.with_retry(lambda: (_ for _ in ()).throw(api_error(400)))

    assert raised.value.code == 400
    assert delays == []


def test_with_retry_raises_after_last_transient_error(monkeypatch):
    calls = []
    delays = []
    monkeypatch.setattr(gemini_retry.time, "sleep", delays.append)

    def call():
        calls.append(None)
        raise api_error(429)

    with pytest.raises(errors.APIError) as raised:
        gemini_retry.with_retry(call, attempts=2, delay=1)

    assert raised.value.code == 429
    assert len(calls) == 2
    assert delays == [1]
