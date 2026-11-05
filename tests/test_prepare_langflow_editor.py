import httpx
import pytest

from scripts import prepare_langflow_editor as probe


def error(status, retry_after=None):
    request = httpx.Request("POST", "http://localhost/api/v1/login")
    headers = {"Retry-After": retry_after} if retry_after is not None else {}
    response = httpx.Response(status, request=request, headers=headers)
    return httpx.HTTPStatusError("test", request=request, response=response)


def test_429_waits_for_retry_after_and_records_retry_count(monkeypatch):
    clock = [0.0]
    calls = []
    monkeypatch.setattr(probe.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(probe.time, "sleep", lambda n: clock.__setitem__(0, clock[0] + n))

    def login(*_):
        calls.append(clock[0])
        if len(calls) == 1:
            raise error(429, "37")
        return {"Authorization": "secret"}

    monkeypatch.setattr(probe, "login", login)
    headers, retries = probe.login_with_retry(httpx.Client(), "u", "p")
    assert headers["Authorization"] == "secret" and retries == 1 and calls == [0, 37]


def test_non_429_fails_without_retry(monkeypatch):
    calls = []

    def login(*_):
        calls.append(1)
        raise error(401)

    monkeypatch.setattr(probe, "login", login)
    with pytest.raises(httpx.HTTPStatusError):
        probe.login_with_retry(httpx.Client(), "u", "p")
    assert len(calls) == 1


def test_retry_after_beyond_deadline_fails_without_sleep(monkeypatch):
    monkeypatch.setattr(probe.time, "monotonic", lambda: 0)
    monkeypatch.setattr(probe.time, "sleep", lambda _: pytest.fail("must not retry early"))
    monkeypatch.setattr(probe, "login", lambda *_: (_ for _ in ()).throw(error(429, "91")))
    with pytest.raises(TimeoutError, match="deadline"):
        probe.login_with_retry(httpx.Client(), "u", "p")


def test_missing_retry_after_uses_30_seconds_and_three_attempt_limit(monkeypatch):
    clock = [0.0]
    calls = []
    monkeypatch.setattr(probe.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(probe.time, "sleep", lambda n: clock.__setitem__(0, clock[0] + n))

    def login(*_):
        calls.append(clock[0])
        raise error(429)

    monkeypatch.setattr(probe, "login", login)
    with pytest.raises(httpx.HTTPStatusError):
        probe.login_with_retry(httpx.Client(), "u", "p")
    assert calls == [0, 30, 60]
