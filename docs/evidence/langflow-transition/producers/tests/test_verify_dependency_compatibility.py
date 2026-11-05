import importlib.metadata

import pytest

from scripts.verify_dependency_compatibility import dependency_versions


def test_candidate_only_allows_datamodel_absence_for_exact_versions(monkeypatch):
    versions = {
        "langflow-base": "1.13.1",
        "lfx": "1.13.1",
        "oauthlib": "4.0.0",
        "opentelemetry-api": "1.45.1",
        "opentelemetry-sdk": "1.45.1",
        "opentelemetry-instrumentation": "0.66b1",
    }

    def version(name):
        if name not in versions:
            raise importlib.metadata.PackageNotFoundError(name)
        return versions[name]

    monkeypatch.setattr(importlib.metadata, "version", version)
    assert dependency_versions(True)["datamodel-code-generator"] is None
    with pytest.raises(importlib.metadata.PackageNotFoundError):
        dependency_versions(False)
    versions["lfx"] = "1.13.0"
    with pytest.raises(ValueError, match="1.13.1"):
        dependency_versions(True)
    versions["lfx"] = "1.13.1"
    del versions["oauthlib"]
    with pytest.raises(importlib.metadata.PackageNotFoundError):
        dependency_versions(True)
    versions["oauthlib"] = "4.0.0"
    versions["datamodel-code-generator"] = "0.42.0"
    assert dependency_versions(False)["datamodel-code-generator"] == "0.42.0"
    assert dependency_versions(True)["datamodel-code-generator"] == "0.42.0"


def test_candidate_reports_absent_datamodel_and_runs_other_probes(monkeypatch, capsys):
    import json
    import sys

    from scripts import verify_dependency_compatibility as probe

    monkeypatch.setattr(sys, "argv", ["probe", "--candidate-1-13-1"])
    monkeypatch.setattr(probe, "dependency_versions", lambda _: {"datamodel-code-generator": None})
    monkeypatch.setattr(probe, "oauth_probe", lambda baseline: {"checked": not baseline})
    monkeypatch.setattr(probe, "otel_probe", lambda baseline: {"checked": not baseline})
    monkeypatch.setattr(probe, "datamodel_probe", lambda _: pytest.fail("must not run"))
    probe.main()
    result = json.loads(capsys.readouterr().out)
    assert result["datamodel"] == {"status": "not_installed"}
    assert result["versions"]["datamodel-code-generator"] is None
    assert result["oauthlib"]["checked"] and result["otel"]["checked"]
