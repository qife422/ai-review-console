from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from api.app.langflow_client import canonical_hash, graph_hash  # noqa: E402
from review_core.redaction import REDACTION_POLICY_HASH, REDACTION_POLICY_VERSION  # noqa: E402
from review_core.risk import RULESET_HASH, RULESET_VERSION  # noqa: E402

COMPONENTS = (
    "SyntheticDocumentParser",
    "DeterministicPIIRedactor",
    "ExplainableRiskScorer",
    "ApprovalTaskGateway",
    "DecisionReportExporter",
)


def login(client: httpx.Client, username: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/login", data={"username": username, "password": password})
    response.raise_for_status()
    payload = response.json()
    token = payload.get("access_token")
    return {"Authorization": f"Bearer {token}"} if token else {}


def find_template(payload: object, component_type: str) -> dict[str, Any] | None:
    if isinstance(payload, dict):
        direct = payload.get(component_type)
        if isinstance(direct, dict):
            return copy.deepcopy(direct.get("node", direct))
        if payload.get("name") == component_type or payload.get("type") == component_type:
            return copy.deepcopy(payload.get("node", payload))
        for value in payload.values():
            found = find_template(value, component_type)
            if found:
                return found
    elif isinstance(payload, list):
        for value in payload:
            found = find_template(value, component_type)
            if found:
                return found
    return None


def set_input(template: dict[str, Any], name: str, value: object) -> None:
    field = template.get("template", {}).get(name)
    if isinstance(field, dict):
        field["value"] = value


def node(component_type: str, template: dict[str, Any], index: int) -> dict[str, Any]:
    node_id = f"{component_type}-review"
    return {
        "id": node_id,
        "type": "genericNode",
        "position": {"x": 120 + index * 360, "y": 180},
        "data": {
            "id": node_id,
            "type": component_type,
            "display_name": template.get("display_name", component_type),
            "description": template.get("description", ""),
            "node": template,
        },
    }


def encoded_handle(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).replace('"', "œ")


def edge(source: dict[str, Any], target: dict[str, Any], target_field: str) -> dict[str, Any]:
    source_type = source["data"]["type"]
    source_id = source["id"]
    target_id = target["id"]
    outputs = source["data"]["node"].get("outputs", [])
    output = outputs[0]
    target_template = target["data"]["node"].get("template", {}).get(target_field, {})
    source_handle = {
        "dataType": source_type,
        "id": source_id,
        "name": output.get("name"),
        "output_types": output.get("types", ["Data"]),
    }
    target_handle = {
        "fieldName": target_field,
        "id": target_id,
        "inputTypes": target_template.get("input_types", ["Data"]),
        "type": target_template.get("type", "other"),
    }
    encoded_source = encoded_handle(source_handle)
    encoded_target = encoded_handle(target_handle)
    return {
        "id": f"reactflow__edge-{source_id}{encoded_source}-{target_id}{encoded_target}",
        "source": source_id,
        "target": target_id,
        "sourceHandle": encoded_source,
        "targetHandle": encoded_target,
        "data": {"sourceHandle": source_handle, "targetHandle": target_handle},
        "animated": False,
        "selected": False,
        "className": "",
    }


def flow_payload(
    name: str, description: str, nodes: list[dict[str, Any]], edges: list[dict[str, Any]]
) -> dict[str, Any]:
    return {
        "name": name,
        "description": description,
        "endpoint_name": None,
        "is_component": False,
        "tags": ["synthetic-data", "document-review", "built-on-langflow"],
        "data": {"nodes": nodes, "edges": edges, "viewport": {"x": 0, "y": 0, "zoom": 0.8}},
    }


def build_flows(component_index: object) -> list[dict[str, Any]]:
    templates: dict[str, dict[str, Any]] = {}
    for component_type in COMPONENTS:
        template = find_template(component_index, component_type)
        if template is None:
            raise RuntimeError(f"Langflow did not expose trusted component {component_type}")
        templates[component_type] = template

    set_input(templates["SyntheticDocumentParser"], "runtime_json", "")
    set_input(templates["DecisionReportExporter"], "runtime_json", "")
    set_input(templates["ApprovalTaskGateway"], "review_api_url", "http://api:8000")
    intake_nodes = [
        node("SyntheticDocumentParser", templates["SyntheticDocumentParser"], 0),
        node("DeterministicPIIRedactor", templates["DeterministicPIIRedactor"], 1),
        node("ExplainableRiskScorer", templates["ExplainableRiskScorer"], 2),
        node("ApprovalTaskGateway", templates["ApprovalTaskGateway"], 3),
    ]
    intake_edges = [
        edge(intake_nodes[0], intake_nodes[1], "document"),
        edge(intake_nodes[1], intake_nodes[2], "document"),
        edge(intake_nodes[2], intake_nodes[3], "assessment"),
    ]
    decision_nodes = [node("DecisionReportExporter", templates["DecisionReportExporter"], 0)]
    return [
        flow_payload(
            "Document Review Intake",
            "Synthetic parsing, redaction, explainable scoring and asynchronous human approval.",
            intake_nodes,
            intake_edges,
        ),
        flow_payload(
            "Document Review Decision",
            "Export a synthetic human decision as a deterministic report.",
            decision_nodes,
            [],
        ),
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--upload", action="store_true")
    parser.add_argument("--write", type=Path)
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()
    base_url = os.getenv("LANGFLOW_URL", "http://localhost:7860").rstrip("/")
    username = os.getenv("LANGFLOW_SUPERUSER", "review-admin")
    password = os.getenv("LANGFLOW_SUPERUSER_PASSWORD", "")
    with httpx.Client(base_url=base_url, timeout=30) as client:
        headers = login(client, username, password)
        response = client.get("/api/v1/all", headers=headers)
        response.raise_for_status()
        flows = build_flows(response.json())
        if args.write:
            args.write.mkdir(parents=True, exist_ok=True)
            for flow in flows:
                path = args.write / f"{flow['name'].lower().replace(' ', '-')}.json"
                path.write_text(json.dumps(flow, ensure_ascii=False, indent=2), encoding="utf-8")
                print(f"Wrote {path}")
        published: dict[str, Any] = {}
        if args.upload:
            existing_payload = client.get("/api/v1/flows/", headers=headers).json()
            existing = (
                existing_payload.get("items", [])
                if isinstance(existing_payload, dict)
                else existing_payload
            )
            existing_by_name = {
                item.get("name"): item
                for item in existing
                if isinstance(item, dict) and item.get("name")
            }
            for flow in flows:
                current = existing_by_name.get(flow["name"])
                if current:
                    updated = client.patch(
                        f"/api/v1/flows/{current['id']}", headers=headers, json=flow
                    )
                    updated.raise_for_status()
                    published[flow["name"]] = updated.json()
                    print(f"Updated Flow: {flow['name']}")
                    continue
                created = client.post("/api/v1/flows/", headers=headers, json=flow)
                created.raise_for_status()
                published[flow["name"]] = created.json()
                print(f"Created Flow: {flow['name']}")
        if args.manifest:
            if not args.upload:
                raise RuntimeError("--manifest requires --upload to record actual published IDs")
            component_root = Path(__file__).resolve().parents[1] / "custom_components/review_center"
            project_root = component_root.parents[1]
            core_inputs = sorted((project_root / "review_core").glob("*.py"))
            core_inputs.extend(sorted((project_root / "review_core/assets").glob("*")))
            core_inputs.append(project_root / "requirements.lock")
            configuration = {
                "ruleset_version": RULESET_VERSION,
                "ruleset_hash": RULESET_HASH,
                "redaction_policy_version": REDACTION_POLICY_VERSION,
                "redaction_policy_hash": REDACTION_POLICY_HASH,
                "components": {
                    path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                    for path in sorted(component_root.glob("*.py"))
                },
                "runtime_inputs": {
                    str(path.relative_to(project_root)): hashlib.sha256(
                        path.read_bytes()
                    ).hexdigest()
                    for path in core_inputs
                    if path.is_file()
                },
            }
            digest = canonical_hash(configuration)
            manifest = {
                "schema_version": "1.0",
                "langflow_version": "1.11.6",
                "config_hash": digest,
                "configuration": configuration,
                "flows": {},
            }
            for kind, name in (
                ("intake", "Document Review Intake"),
                ("report", "Document Review Decision"),
            ):
                actual = published[name]
                if not actual.get("id") or not actual.get("data"):
                    raise RuntimeError("Flow publication response omitted its trusted graph")
                manifest["flows"][kind] = {
                    "id": str(actual["id"]),
                    "name": name,
                    "flow_hash": graph_hash(actual["data"]),
                    "config_hash": digest,
                    "runtime_node_id": "SyntheticDocumentParser-review"
                    if kind == "intake"
                    else "DecisionReportExporter-review",
                }
            args.manifest.parent.mkdir(parents=True, exist_ok=True)
            args.manifest.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            print(f"Published trusted Flow manifest: {args.manifest}")


if __name__ == "__main__":
    main()
