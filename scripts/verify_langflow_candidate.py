"""Bounded evidence for one fresh, explicitly isolated Langflow candidate."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.bootstrap_langflow import COMPONENTS, find_template  # noqa: E402

VERSION = "1.13.1"
FORBIDDEN = {
    "langflow",
    "lfx-ibm",
    "lfx-bundles",
    "zep-python",
    "zep-cloud",
    "ibm-db",
    "psycopg-binary",
    "psycopg2-binary",
    "chromadb",
    "couchbase",
}
PRODUCER = r"""
import importlib.metadata as m, json, platform, sysconfig
from pathlib import Path
import psycopg
from psycopg import pq
rows=[]
for d in m.distributions():
    rows.append({"name":d.metadata["Name"],"version":d.version,
        "license_expression":d.metadata.get("License-Expression"),
        "license_metadata":(d.metadata.get("License") or "")[:160]})
roots=sorted({str(Path(sysconfig.get_path(k)).resolve()) for k in ("purelib","platlib")})
print(json.dumps({"python":platform.python_version(),
    "packages":sorted(rows,key=lambda x:x["name"].lower()),
    "psycopg_implementation":pq.__impl__,"libpq_runtime_version":pq.version(),
    "clidriver_known_paths":[
        {"path":str(Path(r)/"clidriver"),"exists":(Path(r)/"clidriver").exists()}
        for r in roots],
    "scope":("Installed distribution metadata and known clidriver paths only; "
        "no full filesystem absence or corresponding-source proof.")}))
"""


def run(argv: list[str], timeout: int = 60) -> str:
    result = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, check=False)
    if len(result.stdout.encode()) > 1024 * 1024 or len(result.stderr.encode()) > 64 * 1024:
        raise RuntimeError("Command output cap exceeded")
    if result.returncode:
        raise RuntimeError(f"Command {argv[0]} failed with exit {result.returncode}")
    return result.stdout


def write(directory: Path, name: str, data: object) -> None:
    raw = (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode()
    if len(raw) > 256 * 1024:
        raise RuntimeError("Selected evidence member exceeds256KiB")
    with (directory / name).open("xb") as stream:
        stream.write(raw)


def canonical(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    output = args.output_dir
    if output.exists():
        raise RuntimeError("Never overwrite candidate evidence")
    output.mkdir(parents=True)
    project = os.environ.get("COMPOSE_PROJECT_NAME", "")
    if not re.fullmatch(r"arc-ci-[0-9]+-amd64", project):
        raise RuntimeError("Only isolated CI candidate project is allowed")
    container = run(["docker", "compose", "ps", "-q", "langflow"]).strip()
    identity = json.loads(run(["docker", "inspect", container]))[0]
    labels = identity["Config"]["Labels"]
    if labels.get("com.docker.compose.project") != project:
        raise RuntimeError("Compose project identity mismatch")
    if labels.get("com.docker.compose.service") != "langflow":
        raise RuntimeError("Compose service identity mismatch")
    image_id = identity["Image"]
    if not re.fullmatch(r"sha256:[a-f0-9]{64}", image_id):
        raise RuntimeError("Immutable image ID required")
    base = [
        "docker",
        "run",
        "--rm",
        "--network",
        "none",
        "--read-only",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--memory",
        "512m",
        "--pids-limit",
        "64",
        "--env",
        "PYTHONDONTWRITEBYTECODE=1",
        "--entrypoint",
        "python",
        image_id,
    ]
    pip_check = run([*base, "-m", "pip", "check"])
    inventory = json.loads(run([*base, "-c", PRODUCER]))
    packages = {canonical(p["name"]): p["version"] for p in inventory["packages"]}
    write(
        output,
        "identity.json",
        {
            "source": os.getenv("GITHUB_SHA"),
            "project": project,
            "image_id": image_id,
            "service": "langflow",
            "expected_runtime": VERSION,
        },
    )
    write(output, "inventory.json", inventory)

    denied = sorted(FORBIDDEN.intersection(packages))
    expected = {"langflow-base": VERSION, "lfx": VERSION, "psycopg": "3.3.5"}
    if denied or any(packages.get(k) != v for k, v in expected.items()):
        raise RuntimeError(f"Candidate dependency identity/absence check failed: {denied}")
    if inventory["psycopg_implementation"] != "python":
        raise RuntimeError("Candidate must use pure Python Psycopg with system libpq")
    if any(item["exists"] for item in inventory["clidriver_known_paths"]):
        raise RuntimeError("Known clidriver directory remains installed")
    url = os.getenv("LANGFLOW_URL", "http://localhost:7860").rstrip("/")
    if httpx.URL(url).host not in {"localhost", "127.0.0.1"}:
        raise RuntimeError("Only loopback candidate HTTP verification is allowed")
    with httpx.Client(base_url=url, timeout=30) as client:
        anonymous = client.get("/api/v1/flows/")
        if anonymous.status_code not in {401, 403}:
            raise RuntimeError("Anonymous Flow access was not rejected")
        login = client.post(
            "/api/v1/login",
            data={
                "username": os.getenv("LANGFLOW_SUPERUSER", "review-admin"),
                "password": os.environ["LANGFLOW_SUPERUSER_PASSWORD"],
            },
        )
        login.raise_for_status()
        token = login.json().get("access_token")
        if not token:
            raise RuntimeError("Login did not return an access token")
        client.headers["Authorization"] = f"Bearer {token}"
        schema = client.get("/openapi.json")
        schema.raise_for_status()
        observed = schema.json().get("info", {}).get("version")
        if observed != VERSION:
            raise RuntimeError(f"Expected runtime{VERSION}; observed{observed}")
        components = client.get("/api/v1/all")
        components.raise_for_status()
        missing = [n for n in COMPONENTS if not find_template(components.json(), n)]
        if missing:
            raise RuntimeError(f"Trusted components missing:{missing}")
        flows = client.get("/api/v1/flows/")
        flows.raise_for_status()
        data = flows.json()
        items = data.get("items", []) if isinstance(data, dict) else data
        names = {item.get("name") for item in items}
        required = {"Document Review Intake", "Document Review Decision"}
        if not required.issubset(names):
            raise RuntimeError("Required published Flows are missing")
        page = client.get("/")
        page.raise_for_status()
        if "text/html" not in page.headers.get("content-type", ""):
            raise RuntimeError("Packaged management UI did not return HTML")
        api = {
            "runtime_version": observed,
            "anonymous_flows_http": anonymous.status_code,
            "authenticated_login": True,
            "token_recorded": False,
            "components": list(COMPONENTS),
            "flows": sorted(required),
            "openapi_sha256": hashlib.sha256(schema.content).hexdigest(),
            "component_index_sha256": hashlib.sha256(components.content).hexdigest(),
            "frontend_html_sha256": hashlib.sha256(page.content).hexdigest(),
            "frontend_content_type": page.headers.get("content-type"),
            "gui_browser_result": "separate GUI CLI probe; HTTP HTML alone is insufficient",
        }
    write(output, "api.json", api)
    write(
        output,
        "summary.json",
        {
            "at": datetime.now(UTC).isoformat(),
            "result": "passed",
            "producer_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "image_id": image_id,
            "distribution_count": len(packages),
            "denied_present": denied,
            "pip_check": pip_check.strip(),
            "default_runtime_changed": False,
            "acceptance": ("Isolated candidate observations; "
                           "not default upgrade or release acceptance"),
            "native_qualification": inventory["scope"],
        },
    )
    print(json.dumps({"image_id": image_id, "result": "passed", "packages": len(packages)}))


if __name__ == "__main__":
    main()
