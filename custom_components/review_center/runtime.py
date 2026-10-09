"""Small shared validators for trusted, per-execution component inputs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def execution_context(value: str) -> dict[str, Any]:
    if not value or not value.strip():
        raise ValueError("runtime_input_missing: an explicit per-run input is required")
    context = json.loads(value)
    if not isinstance(context, dict):
        raise ValueError("runtime_input_invalid: expected an object")
    required = (
        "case_id",
        "document_version_id",
        "job_id",
        "execution_token",
        "payload_hash",
        "flow_id",
        "flow_hash",
    )
    if any(not isinstance(context.get(key), str) or not context[key] for key in required):
        raise ValueError("runtime_input_invalid: execution identity is incomplete")
    return context


def controlled_source(context: dict[str, Any], directory: str = "/app/documents") -> Path:
    root = Path(directory).resolve()
    source = Path(str(context.get("source_path", ""))).resolve(strict=True)
    expected_parent = root / str(context["document_version_id"])
    if source.parent != expected_parent or not source.name.startswith("source."):
        raise ValueError("source_path_invalid: source is outside its document version")
    return source


def envelope_context(context: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "case_id",
        "document_version_id",
        "job_id",
        "execution_token",
        "source_sha256",
        "payload_hash",
        "flow_id",
        "flow_hash",
        "config_hash",
        "ruleset_version",
        "ruleset_hash",
        "redaction_policy_version",
        "redaction_policy_hash",
    )
    return {"schema_version": "1.0", **{key: context[key] for key in keys}}
