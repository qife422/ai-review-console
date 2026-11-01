"""Offline synthetic compatibility probes for the patched Langflow dependencies.

Run via stdin in an immutable image with no network, a read-only root and a
32MiB /tmp tmpfs. The probe's own scratch is limited to 8MiB/50 files. Baseline
mode reports the old security behavior without declaring the upgrade accepted.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import importlib.util
import inspect
import json
import os
import socket
import sys
import tempfile
from pathlib import Path
from urllib.parse import parse_qs, urlparse

LIMIT_BYTES = 8 * 1024 * 1024
LIMIT_FILES = 50
SCHEMA = {
    "title": "SyntheticReview",
    "type": "object",
    "description": "SYNTHETIC TEST ONLY; no business or personal data",
    "properties": {
        "case_id": {"type": "string"},
        "score": {"type": "integer", "minimum": 0, "maximum": 100},
        "decision": {"type": "string", "enum": ["approve", "reject", "request_changes"]},
    },
    "required": ["case_id", "score", "decision"],
    "additionalProperties": False,
}


def scratch_inventory(root: Path) -> dict:
    files = []
    for path in root.rglob("*"):
        if path.is_symlink():
            raise RuntimeError("Probe scratch contains a symlink")
        if path.is_file():
            files.append(path)
    size = sum(p.stat().st_size for p in files)
    if len(files) > LIMIT_FILES or size > LIMIT_BYTES:
        raise RuntimeError("8MiB/50 file probe scratch guard")
    return {"files": len(files), "bytes": size}


def validate_model(model) -> dict:
    from pydantic import ValidationError

    valid = {"case_id": "SYNTHETIC-ONLY", "score": 42, "decision": "approve"}
    assert model.model_validate(valid).model_dump(mode="json") == valid
    rejected = 0
    for invalid in [
        valid | {"score": 101},
        valid | {"decision": "automatic"},
        {"case_id": "SYNTHETIC-ONLY", "score": 42},
    ]:
        try:
            model.model_validate(invalid)
        except ValidationError:
            rejected += 1
    assert rejected == 3, "Generated model no longer rejects bounded invalid inputs"
    return {"valid_payloads": 1, "rejected_payloads": rejected}


def oauth_probe(baseline: bool) -> dict:
    from oauthlib.oauth2 import MismatchingStateError, WebApplicationClient
    from requests_oauthlib import OAuth2Session

    client = WebApplicationClient("synthetic-client", scope=["review:read"])
    verifier = "s" * 64
    challenge = client.create_code_challenge(verifier, "S256")
    uri = client.prepare_request_uri(
        "https://provider.invalid/authorize",
        redirect_uri="https://client.invalid/callback",
        state="synthetic-state",
        code_challenge=challenge,
        code_challenge_method="S256",
    )
    query = parse_qs(urlparse(uri).query)
    assert query["code_challenge"] == [challenge]
    assert query["state"] == ["synthetic-state"]
    parsed = client.parse_request_uri_response(
        "https://client.invalid/callback?code=synthetic-code&state=synthetic-state",
        state="synthetic-state",
    )
    assert parsed["code"] == "synthetic-code"
    try:
        client.parse_request_uri_response(
            "https://client.invalid/callback?code=synthetic-code&state=wrong",
            state="synthetic-state",
        )
    except MismatchingStateError:
        pass
    else:
        raise AssertionError("Mismatched OAuth state was accepted")
    body = parse_qs(
        client.prepare_request_body(
            code="synthetic-code",
            redirect_uri="https://client.invalid/callback",
            code_verifier=verifier,
        )
    )
    assert body["grant_type"] == ["authorization_code"]
    assert body["code_verifier"] == [verifier]
    token = client.parse_request_body_response(
        json.dumps(
            {
                "access_token": "synthetic-token",
                "token_type": "Bearer",
                "expires_in": 3600,
                "scope": "review:read",
            }
        )
    )
    assert token["access_token"] == "synthetic-token"
    _, _, revocation_body = client.prepare_token_revocation_request(
        "https://provider.invalid/revoke",
        token="synthetic-token",
        token_type_hint="access_token",
    )
    assert parse_qs(revocation_body)["token"] == ["synthetic-token"]
    session = OAuth2Session("synthetic-client", token=token)
    prepared = session.prepare_request(
        __import__("requests").Request("GET", "https://provider.invalid/resource")
    )
    assert prepared.url == "https://provider.invalid/resource"
    jsonp_removed = (
        "callback" not in inspect.signature(client.prepare_token_revocation_request).parameters
    )
    if not baseline:
        assert jsonp_removed, "OAuthlib4 JSONP revocation parameter still present"
    return {
        "pkce_request": "passed",
        "state_rejection": "passed",
        "token_and_revocation": "passed",
        "requests_oauthlib_prepare": "passed",
        "jsonp_parameter_removed": jsonp_removed,
        "baseline_old_jsonp_expected": baseline and not jsonp_removed,
    }


def datamodel_probe(root: Path) -> dict:
    from datamodel_code_generator import DataModelType, InputFileType, generate

    destination = root / "synthetic_model.py"
    os.environ["BLACK_CACHE_DIR"] = str(root / "black-cache")
    generate(
        json.dumps(SCHEMA),
        input_file_type=InputFileType.JsonSchema,
        output=destination,
        output_model_type=DataModelType.PydanticV2BaseModel,
        disable_timestamp=True,
    )
    scratch_inventory(root)
    spec = importlib.util.spec_from_file_location("arc_synthetic_generated", destination)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
        result = validate_model(module.SyntheticReview)
    finally:
        sys.modules.pop(spec.name, None)
    return result | {
        "generated_sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
        "fixed_schema_sha256": hashlib.sha256(
            json.dumps(SCHEMA, sort_keys=True).encode()
        ).hexdigest(),
    }


def propagation_length_probe(
    propagator, read_context, traceparent: str, expected_trace_id: int, baseline: bool
) -> dict:
    """Test the inbound cap at extract(), where upstream actually enforces it.

    TraceState.from_header is a lower-level linear parser; its valid 32-member
    input may exceed the inbound cap. The combined-header guard belongs to the
    propagator, before calling that parser (upstream v1.45.1 tracecontext.py).
    """
    members = [f"k{i:02d}=" + "a" * 256 for i in range(32)]
    single = ",".join(members)
    split = [",".join(members[:16]), ",".join(members[16:])]

    class HeaderGetter:
        def get(self, carrier, key):
            value = carrier.get(key)
            return value if isinstance(value, list) else [value] if value is not None else None

        def keys(self, carrier):
            return list(carrier)

    results = []
    for name, headers in [("single", [single]), ("split", split)]:
        combined = sum(len(h) for h in headers) + len(headers) - 1
        assert combined == 8351 and combined > 8192
        if name == "split":
            assert all(len(h) <= 8192 for h in headers)
        context = read_context(
            propagator.extract(
                {"traceparent": traceparent, "tracestate": headers},
                getter=HeaderGetter(),
            )
        )
        assert context.is_valid and context.trace_id == expected_trace_id
        discarded = len(context.trace_state) == 0
        if not baseline:
            assert discarded, f"Oversized {name} inbound tracestate was retained"
        results.append(
            {
                "case": name,
                "header_fields": len(headers),
                "combined_bytes": combined,
                "discarded": discarded,
                "trace_id_preserved": True,
            }
        )
    return {
        "entrypoint": "TraceContextTextMapPropagator.extract",
        "limit_bytes": 8192,
        "cases": results,
        "all_discarded": all(r["discarded"] for r in results),
    }


def otel_probe(baseline: bool) -> dict:
    import importlib
    import threading

    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from opentelemetry import trace
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.threading import ThreadingInstrumentor
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
    from opentelemetry.trace import TraceState
    from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

    modules = ["requests", "urllib3", "sqlalchemy", "logging", "redis", "asgi", "fastapi"]
    for name in modules:
        importlib.import_module("opentelemetry.instrumentation." + name)
    for name in ["otlp.proto.grpc.trace_exporter", "otlp.proto.http.trace_exporter", "prometheus"]:
        importlib.import_module("opentelemetry.exporter." + name)
    exporter = InMemorySpanExporter()
    provider = TracerProvider(shutdown_on_exit=False)
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer("arc-synthetic-compatibility")
    instrumentor = ThreadingInstrumentor()
    instrumentor.instrument()
    try:
        with tracer.start_as_current_span("synthetic-parent") as parent:
            carrier = {}
            propagator = TraceContextTextMapPropagator()
            propagator.inject(carrier)
            restored = trace.get_current_span(propagator.extract(carrier)).get_span_context()
            assert restored.trace_id == parent.get_span_context().trace_id
            seen = []

            def child():
                with tracer.start_as_current_span("synthetic-thread-child") as span:
                    seen.append(span.get_span_context().trace_id)

            thread = threading.Thread(target=child)
            thread.start()
            thread.join(timeout=3)
            assert not thread.is_alive() and seen == [parent.get_span_context().trace_id]
        app = FastAPI()

        @app.get("/synthetic")
        def synthetic():
            return {"synthetic": True}

        FastAPIInstrumentor.instrument_app(app, tracer_provider=provider)
        try:
            with TestClient(app) as client:
                response = client.get("/synthetic")
                assert response.status_code == 200 and response.json() == {"synthetic": True}
        finally:
            FastAPIInstrumentor.uninstrument_app(app)
        spans = exporter.get_finished_spans()
        assert any(s.name == "synthetic-parent" for s in spans)
        assert any("/synthetic" in s.name for s in spans)
        length_result = propagation_length_probe(
            propagator,
            lambda value: trace.get_current_span(value).get_span_context(),
            carrier["traceparent"],
            restored.trace_id,
            baseline,
        )
        long_header = ",".join(f"k{i:02d}=" + "a" * 256 for i in range(32))
        direct_entries = len(TraceState.from_header([long_header]))
        module_sources = []
        for name in ["opentelemetry.trace.span", "opentelemetry.trace.propagation.tracecontext"]:
            module = importlib.import_module(name)
            path = Path(module.__file__)
            module_sources.append(
                {
                    "module": name,
                    "path": str(path),
                    "resolved_path": str(path.resolve()),
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                }
            )
        return {
            "in_memory_spans": len(spans),
            "propagation": "passed",
            "thread_context": "passed",
            "fastapi_instrumentation": "passed",
            "instrumentor_modules": modules,
            "oversized_tracestate_bytes": len(long_header),
            "oversized_tracestate_discarded": length_result["all_discarded"],
            "tracestate_ingress": length_result,
            "direct_low_level_parser_entries_observed": direct_entries,
            "actual_imported_sources": module_sources,
            "baseline_old_tracestate_expected": baseline and not length_result["all_discarded"],
        }
    finally:
        instrumentor.uninstrument()
        provider.shutdown()


def prohibit_network(*args, **kwargs):
    raise RuntimeError("Dependency compatibility probe forbids network connections")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", action="store_true")
    args = parser.parse_args()
    sys.dont_write_bytecode = True
    socket.socket.connect = prohibit_network
    socket.socket.connect_ex = prohibit_network
    socket.create_connection = prohibit_network
    with tempfile.TemporaryDirectory(prefix="arc-dependency-compat-", dir="/tmp") as temporary:
        root = Path(temporary)
        result = {
            "synthetic_only": True,
            "baseline_mode": args.baseline,
            "network": "forbidden",
            "scratch_limit_bytes": LIMIT_BYTES,
            "scratch_limit_files": LIMIT_FILES,
            "versions": {
                n: importlib.metadata.version(n)
                for n in [
                    "oauthlib",
                    "datamodel-code-generator",
                    "opentelemetry-api",
                    "opentelemetry-sdk",
                    "opentelemetry-instrumentation",
                ]
            },
            "oauthlib": oauth_probe(args.baseline),
            "datamodel": datamodel_probe(root),
            "otel": otel_probe(args.baseline),
            "scratch": scratch_inventory(root),
            "scope": "Fixed offline dependency behavior; real Langflow Flow remains separate.",
        }
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
