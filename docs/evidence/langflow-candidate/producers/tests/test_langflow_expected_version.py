import argparse
import sys

import httpx
import pytest

from scripts import bootstrap_langflow as bootstrap


def test_version_argument_defaults_to_current_runtime_and_restricts_candidate():
    parser = argparse.ArgumentParser()
    bootstrap.add_expected_langflow_version_argument(parser)
    assert parser.parse_args([]).expected_langflow_version == "1.11.6"
    assert parser.parse_args(
        ["--expected-langflow-version", "1.13.1"]
    ).expected_langflow_version == "1.13.1"
    with pytest.raises(SystemExit):
        parser.parse_args(["--expected-langflow-version", "latest"])


def test_observed_version_must_match_default_or_explicit_candidate():
    assert bootstrap.require_langflow_version({"info": {"version": "1.11.6"}}) == "1.11.6"
    with pytest.raises(AssertionError, match="expected Langflow 1.11.6"):
        bootstrap.require_langflow_version({"info": {"version": "1.13.1"}})
    assert bootstrap.require_langflow_version(
        {"info": {"version": "1.13.1"}}, "1.13.1"
    ) == "1.13.1"
    for malformed in ({}, {"info": None}, {"info": {"version": "1.13.1rc2"}}):
        with pytest.raises(AssertionError):
            bootstrap.require_langflow_version(malformed, "1.13.1")


def test_bootstrap_refuses_mismatch_before_component_or_flow_writes(monkeypatch):
    calls = []

    def handle(request):
        calls.append((request.method, request.url.path))
        if request.url.path == "/api/v1/login":
            return httpx.Response(200, json={"access_token": "synthetic-only"})
        if request.url.path == "/openapi.json":
            return httpx.Response(200, json={"info": {"version": "1.13.1"}})
        raise AssertionError("No component discovery or Flow publication before version check")

    client = httpx.Client(base_url="http://candidate.test", transport=httpx.MockTransport(handle))
    monkeypatch.setattr(bootstrap.httpx, "Client", lambda **kwargs: client)
    monkeypatch.setattr(sys, "argv", ["bootstrap_langflow.py", "--upload"])
    with pytest.raises(AssertionError, match="Runtime version mismatch"):
        bootstrap.main()
    assert calls == [("POST", "/api/v1/login"), ("GET", "/openapi.json")]
