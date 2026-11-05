"""Create and check one isolated synthetic Flow for an opt-in GUI editor probe."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from api.app.langflow_client import graph_hash  # noqa: E402
from scripts.bootstrap_langflow import login, require_langflow_version  # noqa: E402
from scripts.candidate_runtime_guard import CandidateRuntimeGuard  # noqa: E402
from scripts.verify_langflow_migration import published_url_matches  # noqa: E402

NAMES = ("Document Review Intake", "Document Review Decision")


def items(client: httpx.Client, headers: dict) -> list:
    response = client.get("/api/v1/flows/", headers=headers)
    response.raise_for_status()
    result = response.json()
    return result.get("items", []) if isinstance(result, dict) else result


def selected(client: httpx.Client, headers: dict) -> dict:
    listed = items(client, headers)
    selected = {}
    for name in NAMES:
        matching = [f for f in listed if f.get("name") == name]
        if len(matching) != 1:
            raise RuntimeError("Expected exactly one original business Flow: " + name)
        response = client.get("/api/v1/flows/" + matching[0]["id"], headers=headers)
        response.raise_for_status()
        flow = response.json()
        selected[name] = {"id": flow["id"], "graph_sha256": graph_hash(flow["data"])}
    return selected


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["prepare", "verify"])
    parser.add_argument("--state", type=Path, required=True)
    args = parser.parse_args()
    base = os.environ.get("ARC_LF_BASE_URL", "http://localhost:7860")
    parsed = urlparse(base)
    if parsed.scheme not in ("http", "https") or parsed.hostname not in ("localhost", "127.0.0.1"):
        raise ValueError("Only isolated loopback runtime is permitted")
    project = os.environ.get("COMPOSE_PROJECT_NAME", "")
    compose = os.environ.get("ARC_CANDIDATE_COMPOSE_FILE", "")
    if not compose:
        raise ValueError("ARC_CANDIDATE_COMPOSE_FILE is required")
    guard = CandidateRuntimeGuard(project, Path(compose), "1.13.1", "http://127.0.0.1:8000", 5433)
    guard.validate()
    if not published_url_matches(base, guard.running["langflow"], "7860/tcp"):
        raise ValueError("Editor URL is not the guarded Langflow container")
    runtime_identity = {"project": project, "langflow_image": guard.running["langflow"]["Image"]}
    with httpx.Client(base_url=base, timeout=30) as client:
        headers = login(
            client,
            os.environ.get("LANGFLOW_SUPERUSER", "review-admin"),
            os.environ.get("LANGFLOW_SUPERUSER_PASSWORD", "synthetic-demo-change-me"),
        )
        response = client.get("/openapi.json", headers=headers)
        response.raise_for_status()
        require_langflow_version(response.json(), "1.13.1")
        if args.action == "prepare":
            if args.state.exists():
                raise ValueError("State must not already exist")
            before = selected(client, headers)
            original = client.get("/api/v1/flows/" + before[NAMES[0]]["id"], headers=headers)
            original.raise_for_status()
            data = original.json()["data"]
            if not data.get("nodes") or not data.get("edges"):
                raise ValueError("Synthetic copy requires a graph with nodes and edges")
            name = "ARC Synthetic Editor " + uuid4().hex[:10]
            payload = {
                "name": name,
                "description": "Synthetic editor verification only",
                "endpoint_name": None,
                "is_component": False,
                "tags": ["synthetic-data"],
                "data": data,
            }
            created = client.post("/api/v1/flows/", headers=headers, json=payload)
            created.raise_for_status()
            flow = created.json()
            if flow["id"] in {x["id"] for x in before.values()}:
                raise RuntimeError("Synthetic flow ID collides with original")
            state = {
                "runtime_identity": runtime_identity,
                "synthetic_id": flow["id"],
                "original_name": name,
                "edited_name": name + " Edited",
                "originals_before": before,
                "synthetic_nodes": len(data["nodes"]),
                "synthetic_edges": len(data["edges"]),
                "version": "1.13.1",
            }
            with args.state.open("x", encoding="utf-8") as out:
                json.dump(state, out, ensure_ascii=False, indent=2)
            print(json.dumps(state))
        else:
            state = json.loads(args.state.read_text(encoding="utf-8"))
            if state["runtime_identity"] != runtime_identity:
                raise RuntimeError("Candidate runtime identity changed since preparation")
            before = state["originals_before"]
            after = selected(client, headers)
            if after != before:
                raise RuntimeError("Original business Flow identity or graph changed")
            response = client.get("/api/v1/flows/" + state["synthetic_id"], headers=headers)
            response.raise_for_status()
            actual = response.json()
            if actual["name"] != state["edited_name"]:
                raise RuntimeError("Synthetic UI edit was not persisted")
            print(
                json.dumps(
                    {
                        "synthetic_id": state["synthetic_id"],
                        "persisted_name": actual["name"],
                        "synthetic_graph_sha256": graph_hash(actual["data"]),
                        "originals_before": before,
                        "originals_after": after,
                    }
                )
            )


if __name__ == "__main__":
    main()
