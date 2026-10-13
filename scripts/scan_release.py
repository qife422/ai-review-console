"""Bounded, metadata-based release evidence; never exports images or modifies packages.

All output belongs to compliance/upgrade, not the historical compliance/sbom.
Use an explicitly created system temporary root. Image inventory uses new, no-network,
read-only, no-mount containers and binds results to immutable local image IDs.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import re
import subprocess
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "compliance/upgrade"
LIMIT = 256 * 1024 * 1024
WARN = 200 * 1024 * 1024
INVENTORY_CODE = r"""
import importlib.metadata as m, json, sys
packages=[]
for d in m.distributions():
    h=d.metadata
    packages.append({"name":h.get("Name",""), "version":d.version,
        "license_expression":h.get("License-Expression",""),
        "license":h.get("License","")[:4096],
        "classifiers":h.get_all("Classifier") or [],
        "location":str(d._path)})
print(json.dumps({"interpreter":sys.executable,"python_version":sys.version,
    "packages":packages},sort_keys=True))
"""
OS_COMMAND = r"""
printf '===os-release===\n'
if [ -r /etc/os-release ]; then cat /etc/os-release; fi
printf '\n===apk===\n'
if [ -r /lib/apk/db/installed ]; then cat /lib/apk/db/installed; fi
printf '\n===dpkg===\n'
if command -v dpkg-query >/dev/null 2>&1; then
 dpkg_fmt='${binary:Package}\t${Version}\t${Architecture}'
 dpkg_fmt="$dpkg_fmt"'\t${source:Package}\t${source:Version}\n'
 dpkg-query -W -f="$dpkg_fmt"
fi
printf '\n===dpkg-licenses===\n'
for copyright_path in /usr/share/doc/*/copyright; do
 [ -r "$copyright_path" ] || continue
 package_path=${copyright_path%/copyright}
 printf '%s\t' "${package_path##*/}"
 awk '/^License:/ {gsub(/\t/, " "); printf "%s;", $0}' "$copyright_path"
 printf '\n'
done
printf '\n===rpm===\n'
if command -v rpm >/dev/null 2>&1; then
 rpm -qa --qf '%{NAME}\t%{VERSION}-%{RELEASE}\t%{ARCH}\t%{LICENSE}\n'
fi
"""


def now() -> str:
    return datetime.now(UTC).isoformat()


def fingerprint(path: Path) -> dict[str, object]:
    data = path.read_bytes()
    return {
        "path": str(path.relative_to(ROOT)),
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def write_json(name: str, data: object) -> None:
    (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def tree_bytes(path: Path) -> int:
    return sum(p.stat().st_size for p in path.rglob("*") if p.is_file())


class Runner:
    def __init__(self, temporary: Path):
        self.temporary = temporary.resolve()
        if not str(self.temporary).startswith("/private/tmp/arc-release-scan."):
            raise ValueError("Use mktemp -d /private/tmp/arc-release-scan.XXXXXX")
        if not self.temporary.is_dir():
            raise ValueError("Temporary directory must already exist")
        OUT.mkdir(parents=True, exist_ok=True)
        self.records: list[dict[str, object]] = []
        self.environment = os.environ | {
            "TMPDIR": str(self.temporary),
            "DOCKER_SCOUT_CACHE_DIR": str(self.temporary / "scout"),
            "DOCKER_SCOUT_NO_CACHE": "true",
            "DOCKER_SCOUT_NEW_VERSION_WARN": "false",
            "DOCKER_SCOUT_EXPERIMENTAL_WARN": "false",
            "npm_config_cache": str(self.temporary / "npm"),
            "PIP_CACHE_DIR": str(self.temporary / "pip"),
            "PYTHONDONTWRITEBYTECODE": "1",
        }

    def run(
        self, label: str, command: list[str], *, cwd: Path = ROOT, timeout: int = 180
    ) -> tuple[int, str]:
        if tree_bytes(self.temporary) >= WARN or tree_bytes(OUT) >= 100 * 1024 * 1024:
            raise RuntimeError("Capacity guard triggered; preserve and inventory, do not clean")
        stdout = OUT / f"{label}.stdout"
        stderr = OUT / f"{label}.stderr"
        if stdout.exists() or stderr.exists():
            raise FileExistsError(f"Evidence already exists: {label}; do not overwrite")
        start = now()
        reason = None
        with stdout.open("xb") as out, stderr.open("xb") as err:
            proc = subprocess.Popen(
                command,
                cwd=cwd,
                env=self.environment,
                stdout=out,
                stderr=err,
                start_new_session=True,
            )
            deadline = time.monotonic() + timeout
            while proc.poll() is None:
                if time.monotonic() > deadline:
                    reason = "bounded_timeout"
                if tree_bytes(self.temporary) >= WARN:
                    reason = "bounded_capacity"
                if tree_bytes(OUT) >= 90 * 1024 * 1024:
                    reason = "bounded_evidence_capacity"
                if reason:
                    proc.terminate()
                    try:
                        proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                    break
                time.sleep(0.1)
            code = proc.wait()
        self.records.append(
            {
                "label": label,
                "command": command,
                "cwd": str(cwd),
                "started_at": start,
                "ended_at": now(),
                "exit_code": code,
                "stop_reason": reason,
                "temporary_bytes_after": tree_bytes(self.temporary),
                "stdout": stdout.name,
                "stderr": stderr.name,
            }
        )
        if tree_bytes(self.temporary) > LIMIT:
            raise RuntimeError("256 MiB temporary limit exceeded; no further generation")
        return code, stdout.read_text(errors="replace")


def normalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def python_license(name: str, version: str, inventory: list[dict]) -> dict:
    matches = [
        p for p in inventory if normalize(p["name"]) == normalize(name) and p["version"] == version
    ]
    if not matches:
        return {"identifiers": [], "source": "matching installed metadata unavailable"}
    p = matches[0]
    identifiers = [p.get("license_expression", "")]
    if p.get("license"):
        identifiers.append(p["license"])
    identifiers.extend(c for c in p.get("classifiers", []) if c.startswith("License ::"))
    return {
        "identifiers": [v for v in identifiers if v],
        "source": "installed METADATA of exact name/version",
        "location": p["location"],
    }


def licenses_report(components: list[dict]) -> dict:
    restricted = re.compile(r"AGPL|GPL|LGPL|SSPL|Commons Clause|BUSL|Business Source|Elastic", re.I)
    rows = []
    for p in components:
        values = p.get("license", {}).get("identifiers", [])
        useful = [v for v in values if v and v.upper() not in {"UNKNOWN", "NOASSERTION", "NONE"}]
        state = "unknown" if not useful else "recorded"
        if restricted.search(" ".join(useful)):
            state = "review_required_copyleft_or_restricted_match"
        rows.append(p | {"license_check": state})
    return {
        "generated_at": now(),
        "method": "metadata identifier inventory; conservative text matching",
        "legal_conclusion": "none; unknown/restricted metadata requires distribution review",
        "summary": {
            s: sum(p["license_check"] == s for p in rows)
            for s in ["recorded", "unknown", "review_required_copyleft_or_restricted_match"]
        },
        "packages": rows,
    }


def dependencies(runner: Runner, online: bool = False) -> dict:
    lock = ROOT / "requirements.lock"
    command = [
        str(ROOT / ".venv/bin/pip-audit"),
        "--requirement",
        str(lock),
        "--no-deps",
        "--disable-pip",
        "--strict",
        "--timeout",
        "30",
        "--progress-spinner",
        "off",
        "--cache-dir",
        str(runner.temporary / "pip-audit"),
    ]
    py_code = None
    if online:
        py_code, py_raw = runner.run(
            "python-audit", command + ["--format", "cyclonedx-json"], timeout=180
        )
        try:
            py_bom = json.loads(py_raw) if py_code in (0, 1) else {}
        except json.JSONDecodeError:
            py_bom = {}
    else:
        py_bom = {
            "bomFormat": "CycloneDX",
            "specVersion": "1.5",
            "version": 1,
            "serialNumber": "urn:uuid:" + str(uuid.uuid4()),
            "metadata": {
                "timestamp": now(),
                "tools": [
                    {"vendor": "AI Review Console", "name": "scan_release.py", "version": "1"}
                ],
                "properties": [
                    {"name": "arc:source", "value": "requirements.lock exact pins"},
                    {
                        "name": "arc:vulnerability-state",
                        "value": "not_scanned_external_authorization",
                    },
                ],
            },
            "components": [
                {
                    "type": "library",
                    "name": name,
                    "version": version,
                    "purl": f"pkg:pypi/{normalize(name)}@{quote(version, safe='')}",
                }
                for name, version in re.findall(r"^([\w.-]+)==([^\s;]+)", lock.read_text(), re.M)
            ],
        }
        runner.environment["npm_config_offline"] = "true"
    if py_bom.get("bomFormat") == "CycloneDX":
        write_json("python.cdx.json", py_bom)
    node_code, node_raw = runner.run(
        "node-sbom",
        ["npm", "sbom", "--package-lock-only", "--sbom-format=cyclonedx"],
        cwd=ROOT / "frontend",
    )
    if node_code == 0:
        write_json("node.cdx.json", json.loads(node_raw))
    full_code = runtime_code = None
    full_raw = runtime_raw = ""
    if online:
        full_code, full_raw = runner.run(
            "node-audit-all",
            ["npm", "audit", "--package-lock-only", "--json", "--ignore-scripts"],
            cwd=ROOT / "frontend",
        )
        runtime_code, runtime_raw = runner.run(
            "node-audit-runtime",
            ["npm", "audit", "--package-lock-only", "--omit=dev", "--json", "--ignore-scripts"],
            cwd=ROOT / "frontend",
        )
    local_inventory = []
    for d in importlib.metadata.distributions():
        h = d.metadata
        local_inventory.append(
            {
                "name": h.get("Name", ""),
                "version": d.version,
                "license_expression": h.get("License-Expression", ""),
                "license": h.get("License", "")[:4096],
                "classifiers": h.get_all("Classifier") or [],
                "location": str(d._path),
            }
        )
    py_licenses = []
    for name, version in re.findall(r"^([\w.-]+)==([^\s;]+)", lock.read_text(), re.M):
        py_licenses.append(
            {
                "name": name,
                "version": version,
                "license": python_license(name, version, local_inventory),
            }
        )
    write_json("python-licenses.json", licenses_report(py_licenses))
    node_lock = json.loads((ROOT / "frontend/package-lock.json").read_text())
    node_licenses = [
        {
            "name": path.rsplit("node_modules/", 1)[-1],
            "version": p.get("version", ""),
            "dev": p.get("dev", False),
            "license": {
                "identifiers": [p["license"]] if p.get("license") else [],
                "source": "frontend/package-lock.json package license field",
            },
        }
        for path, p in node_lock["packages"].items()
        if path
    ]
    write_json("node-licenses.json", licenses_report(node_licenses))

    def npm_result(raw: str) -> dict:
        try:
            d = json.loads(raw)
            return d.get("metadata", {}).get("vulnerabilities", {}) or {"error": d.get("error")}
        except json.JSONDecodeError:
            return {"error": "invalid/no JSON result"}

    result = {
        "python": {
            "exit_code": py_code,
            "components": len(py_bom.get("components", [])),
            "vulnerabilities": len(py_bom.get("vulnerabilities", []))
            if py_bom and online
            else None,
            "service": "pip-audit PyPI JSON API",
            "database_snapshot_date": "not exposed by service",
        },
        "node_sbom_exit_code": node_code,
        "node_all": {"exit_code": full_code, "counts": npm_result(full_raw) if online else None},
        "node_runtime": {
            "exit_code": runtime_code,
            "counts": npm_result(runtime_raw) if online else None,
        },
        "vulnerability_state": "queried" if online else "not_scanned_external_authorization",
        "node_service": "configured npm registry audit API",
        "node_database_snapshot_date": "not exposed by registry",
    }
    write_json("dependencies-summary.json", result)
    return result


def os_packages(raw: str) -> tuple[dict, list[dict]]:
    sections = dict(re.findall(r"===([^=]+)===\n(.*?)(?=\n===|\Z)", raw, re.S))
    release = dict(re.findall(r'^([A-Z_]+)="?([^"\n]*)"?$', sections.get("os-release", ""), re.M))
    rows = []
    deb_licenses = {}
    for line in sections.get("dpkg-licenses", "").strip().splitlines():
        if "\t" in line:
            name, identifiers = line.split("\t", 1)
            deb_licenses[name] = sorted(
                {v.removeprefix("License:").strip() for v in identifiers.split(";") if v.strip()}
            )
    for entry in sections.get("apk", "").strip().split("\n\n"):
        fields = dict(line.split(":", 1) for line in entry.splitlines() if ":" in line)
        if fields.get("P"):
            rows.append(
                {
                    "name": fields["P"],
                    "version": fields.get("V", ""),
                    "type": "apk",
                    "arch": fields.get("A", ""),
                    "source_name": fields.get("o", fields["P"]),
                    "license": {
                        "identifiers": [fields["L"]] if fields.get("L") else [],
                        "source": "/lib/apk/db/installed L field",
                    },
                }
            )
    for line in sections.get("dpkg", "").strip().splitlines():
        f = line.split("\t")
        if len(f) >= 3:
            rows.append(
                {
                    "name": f[0].split(":")[0],
                    "version": f[1],
                    "type": "deb",
                    "arch": f[2],
                    "source_name": f[3] if len(f) > 3 else f[0],
                    "source_version": f[4] if len(f) > 4 else f[1],
                    "license": {
                        "identifiers": deb_licenses.get(f[0].split(":")[0], []),
                        "source": "/usr/share/doc/<binary-package>/copyright License fields",
                    },
                }
            )
    for line in sections.get("rpm", "").strip().splitlines():
        f = line.split("\t")
        if len(f) == 4:
            rows.append(
                {
                    "name": f[0],
                    "version": f[1],
                    "type": "rpm",
                    "arch": f[2],
                    "license": {"identifiers": [f[3]], "source": "rpm LICENSE header"},
                }
            )
    return release, rows


def package_purl(p: dict, distro: dict) -> str:
    kind = p["type"]
    namespace = (distro.get("ID", "") + "/") if kind in {"deb", "apk", "rpm"} else ""
    name = normalize(p["name"]) if kind == "pypi" else p["name"]
    url = f"pkg:{kind}/{namespace}{quote(name, safe='')}@{quote(p['version'], safe='')}"
    if kind in {"deb", "apk", "rpm"}:
        distro_id = distro.get("ID", "") + "-" + distro.get("VERSION_ID", "")
        url += f"?arch={quote(p.get('arch', ''), safe='')}&distro={quote(distro_id, safe='')}"
    return url


def image_bom(name: str, identity: dict, packages: list[dict], distro: dict) -> tuple[dict, dict]:
    components = []
    spdx_packages = []
    for index, p in enumerate(packages):
        purl = package_purl(p, distro)
        license_values = p.get("license", {}).get("identifiers", [])
        components.append(
            {
                "type": "library",
                "name": p["name"],
                "version": p["version"],
                "bom-ref": purl,
                "purl": purl,
                "properties": [
                    {"name": "arc:metadata:package-type", "value": p["type"]},
                    {
                        "name": "arc:metadata:license-source",
                        "value": p.get("license", {}).get("source", ""),
                    },
                    {"name": "arc:metadata:license-raw", "value": json.dumps(license_values)},
                ],
            }
        )
        spdx_packages.append(
            {
                "name": p["name"],
                "SPDXID": f"SPDXRef-Package-{index}",
                "versionInfo": p["version"],
                "downloadLocation": "NOASSERTION",
                "filesAnalyzed": False,
                "licenseConcluded": "NOASSERTION",
                "licenseDeclared": "NOASSERTION",
                "copyrightText": "NOASSERTION",
                "externalRefs": [
                    {
                        "referenceCategory": "PACKAGE-MANAGER",
                        "referenceType": "purl",
                        "referenceLocator": purl,
                    }
                ],
            }
        )
    timestamp = now()
    properties = [
        {"name": "arc:image:id", "value": identity["id"]},
        {"name": "arc:image:platform", "value": identity["os"] + "/" + identity["architecture"]},
        {
            "name": "arc:inventory:scope",
            "value": "installed package-manager metadata, not full filesystem",
        },
        {"name": "arc:os-release", "value": json.dumps(distro, sort_keys=True)},
    ]
    cdx = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "version": 1,
        "serialNumber": "urn:uuid:" + str(uuid.uuid4()),
        "metadata": {
            "timestamp": timestamp,
            "tools": [{"vendor": "AI Review Console", "name": "scan_release.py", "version": "1"}],
            "component": {
                "type": "container",
                "name": name,
                "version": identity["id"],
                "properties": properties,
            },
        },
        "components": components,
    }
    spdx = {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": name + " metadata inventory",
        "documentNamespace": "https://ai-review-console.invalid/sbom/" + str(uuid.uuid4()),
        "creationInfo": {
            "created": timestamp.split(".")[0] + "Z",
            "creators": ["Tool: scan_release.py-1"],
        },
        "documentComment": json.dumps(
            {
                "identity": identity,
                "os-release": distro,
                "scope": "installed package-manager metadata; no complete filesystem traversal",
            },
            sort_keys=True,
        ),
        "packages": spdx_packages,
        "relationships": [
            {
                "spdxElementId": "SPDXRef-DOCUMENT",
                "relationshipType": "DESCRIBES",
                "relatedSpdxElement": p["SPDXID"],
            }
            for p in spdx_packages
        ],
    }
    return cdx, spdx


def images(
    runner: Runner, targets: list[str], online: bool = False, record: str = "images"
) -> dict:
    results = {}
    for target in targets:
        name, image_id = target.split("=", 1)
        label_prefix = record + "-" + name
        if not re.fullmatch(r"[a-z][a-z0-9-]*", name) or not re.fullmatch(
            r"sha256:[a-f0-9]{64}", image_id
        ):
            raise ValueError("Images must be NAME=sha256:<full immutable ID>")
        fmt = (
            '{"id":{{json .Id}},"created":{{json .Created}},"size":{{json .Size}},'
            '"os":{{json .Os}},"architecture":{{json .Architecture}},'
            '"repo_digests":{{json .RepoDigests}},"layers":{{json .RootFS.Layers}}}'
        )
        code, raw = runner.run(
            label_prefix + "-identity", ["docker", "image", "inspect", "--format", fmt, image_id]
        )
        if code != 0:
            results[name] = {"state": "identity_failed"}
            continue
        identity = json.loads(raw)
        if identity["id"] != image_id:
            raise ValueError("Resolved image ID mismatch")
        base = [
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            "--read-only",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            "--pids-limit",
            "64",
            "--memory",
            "256m",
            "--cpus",
            "1",
            "--env",
            "PYTHONDONTWRITEBYTECODE=1",
        ]
        os_code, os_raw = runner.run(
            label_prefix + "-os-metadata",
            base + ["--entrypoint", "/bin/sh", image_id, "-c", OS_COMMAND],
        )
        distro, packages = os_packages(os_raw)
        py_code = None
        raw_distribution_count = unique_distribution_count = 0
        if name != "web":
            py_code, py_raw = runner.run(
                label_prefix + "-python-metadata",
                base + ["--entrypoint", "python", image_id, "-c", INVENTORY_CODE],
            )
            if py_code == 0:
                inventory = json.loads(py_raw)["packages"]
                raw_distribution_count = len(inventory)
                unique = {}
                for p in inventory:
                    unique.setdefault((normalize(p["name"]), p["version"]), p)
                inventory = list(unique.values())
                unique_distribution_count = len(inventory)
                packages += [
                    {
                        "name": p["name"],
                        "version": p["version"],
                        "type": "pypi",
                        "license": python_license(p["name"], p["version"], inventory),
                    }
                    for p in inventory
                ]
        derived_names = [
            name + "-image.cdx.json",
            name + "-image.spdx.json",
            name + "-image-licenses.json",
        ]
        previous = [fingerprint(OUT / p) for p in derived_names if (OUT / p).exists()]
        previous_identity = None
        if (OUT / derived_names[0]).exists():
            previous_identity = (
                json.loads((OUT / derived_names[0]).read_text())
                .get("metadata", {})
                .get("component", {})
                .get("version")
            )
        cdx, spdx = image_bom(name, identity, packages, distro)
        write_json(name + "-image.cdx.json", cdx)
        write_json(name + "-image.spdx.json", spdx)
        write_json(name + "-image-licenses.json", licenses_report(packages))
        scan_code = None
        scan_raw = ""
        if online:
            scan_code, scan_raw = runner.run(
                label_prefix + "-image-cves",
                [
                    "docker",
                    "scout",
                    "cves",
                    "sbom://" + str(OUT / (name + "-image.spdx.json")),
                    "--format",
                    "sarif",
                    "--exit-code",
                ],
                timeout=180,
            )
        try:
            sarif = json.loads(scan_raw)
            scan_results = [v for run in sarif.get("runs", []) for v in run.get("results", [])]
            count = len(scan_results)
        except json.JSONDecodeError:
            count = None
        results[name] = {
            "identity": identity,
            "os_release": distro,
            "packages": len(packages),
            "python_distributions_raw": raw_distribution_count,
            "python_distributions_unique": unique_distribution_count,
            "deduplication_method": "Python normalized name/version dedup; lib/lib64 aliases",
            "candidate_revision": {
                "previous_image_id": previous_identity,
                "previous_derived_fingerprints": previous,
                "current_derived_fingerprints": [fingerprint(OUT / p) for p in derived_names],
                "raw_metadata_preserved": True,
                "historical_sbom_unchanged": True,
            },
            "os_metadata_exit_code": os_code,
            "python_metadata_exit_code": py_code,
            "cve_scan_exit_code": scan_code,
            "sarif_findings": count,
            "vulnerability_state": "queried" if online else "not_scanned_external_authorization",
            "inventory_scope": (
                "installed package-manager metadata only; "
                "excludes undiscovered/static binaries and full file tree"
            ),
            "service": "Docker Scout vulnerability service",
            "database_snapshot_date": "not exposed by service",
        }
    write_json(record + "-summary.json", results)
    return results


def validate_evidence(runtime_record: str = "final-runtime") -> dict:
    """Normalize unsealed candidates; retain raw inventories and before/after hashes."""
    from cyclonedx.schema import SchemaVersion
    from cyclonedx.validation.json import JsonStrictValidator

    revisions = []
    node_raw_name = (
        "verified-node-sbom.stdout"
        if (OUT / "verified-node-sbom.stdout").exists()
        else "node-sbom.stdout"
    )
    node_path = OUT / "node.cdx.json"
    before = fingerprint(node_path)
    node = json.loads(node_path.read_text())
    original_components = len(node["components"])
    original_dependencies = len(node["dependencies"])
    unique_components = {}
    for component in node["components"]:
        unique_components.setdefault(component["bom-ref"], component)
    graph = {}
    for dependency in node["dependencies"]:
        graph.setdefault(dependency["ref"], set()).update(dependency["dependsOn"])
    node["components"] = list(unique_components.values())
    node["dependencies"] = [
        {"ref": ref, "dependsOn": sorted(edges)} for ref, edges in graph.items()
    ]
    write_json("node.cdx.json", node)
    revisions.append(
        {
            "file": "node.cdx.json",
            "before": before,
            "after": fingerprint(node_path),
            "raw_source": fingerprint(OUT / node_raw_name),
            "method": "dedup duplicate npm bom-ref; union dependsOn edges per ref",
            "components_before": original_components,
            "components_after": len(node["components"]),
            "dependencies_before": original_dependencies,
            "dependencies_after": len(node["dependencies"]),
        }
    )

    py_license_path = OUT / "python-licenses.json"
    before = fingerprint(py_license_path)
    py_licenses = json.loads(py_license_path.read_text())["packages"]
    api_inventory = json.loads(
        (OUT / (runtime_record + "-api-python-metadata.stdout")).read_text()
    )["packages"]
    api_id = json.loads((OUT / (runtime_record + "-summary.json")).read_text())["api"]["identity"][
        "id"
    ]
    for package in py_licenses:
        if not package["license"]["identifiers"]:
            package["license"] = python_license(package["name"], package["version"], api_inventory)
            package["license"]["source"] += "; isolated final API image " + api_id
    write_json("python-licenses.json", licenses_report(py_licenses))
    revisions.append(
        {
            "file": "python-licenses.json",
            "before": before,
            "after": fingerprint(py_license_path),
            "raw_source": fingerprint(OUT / (runtime_record + "-api-python-metadata.stdout")),
            "method": "fill missing license using exact locked package version in final API image",
        }
    )

    validations = []
    for path in sorted(OUT.glob("*.cdx.json")):
        raw = path.read_text()
        bom = json.loads(raw)
        errors = list(
            JsonStrictValidator(SchemaVersion.from_version(bom["specVersion"])).validate_str(
                raw, all_errors=True
            )
            or []
        )
        refs = [p["bom-ref"] for p in bom["components"] if "bom-ref" in p]
        validations.append(
            {
                "file": path.name,
                "sha256": fingerprint(path)["sha256"],
                "schema": "CycloneDX strict " + bom["specVersion"],
                "schema_valid": not errors,
                "bom_refs_unique": len(refs) == len(set(refs)),
                "errors": [
                    {"path": e.data.json_path, "validator": e.data.validator} for e in errors
                ],
            }
        )
    for path in sorted(OUT.glob("*.spdx.json")):
        doc = json.loads(path.read_text())
        ids = [p["SPDXID"] for p in doc["packages"]]
        validations.append(
            {
                "file": path.name,
                "sha256": fingerprint(path)["sha256"],
                "schema": "SPDX structural checks only, not full SPDX schema validation",
                "package_ids_unique": len(ids) == len(set(ids)),
                "document_relationships_valid": all(
                    r["relatedSpdxElement"] in ids for r in doc["relationships"]
                ),
            }
        )
    for manifest_name in [
        "dependencies-manifest.json",
        "langflow-web-manifest.json",
        "final-runtime-manifest.json",
        runtime_record + "-manifest.json",
    ]:
        path = OUT / manifest_name
        original = json.loads(path.read_text())
        original["candidate_state"] = (
            "superseded_candidate_do_not_use"
            if manifest_name in {"langflow-web-manifest.json", "final-runtime-manifest.json"}
            and manifest_name != runtime_record + "-manifest.json"
            else "unsealed_candidate_reviewed"
        )
        if manifest_name == "dependencies-manifest.json" and node_raw_name != "node-sbom.stdout":
            original["candidate_state"] = "superseded_node_input_use_node_refresh_manifest"
            original["current_node_input_record"] = "node-refresh-manifest.json"
        original["candidate_revisions"] = revisions
        original["current_file_fingerprints"] = [
            fingerprint(OUT / p["path"].split("/")[-1]) for p in original["files"]
        ]
        original["current_runtime_record"] = runtime_record + "-manifest.json"
        original["historical_file_fingerprints_preserved"] = True
        write_json(manifest_name, original)
    result = {
        "created_at": now(),
        "revisions": revisions,
        "validations": validations,
        "jsonschema": importlib.metadata.version("jsonschema"),
        "online_vulnerability_audit": "not_executed_authorization_pending",
        "no_additional_tool_downloads": True,
    }
    write_json("sbom-validation.json", result)
    return result


def audit_existing(runner: Runner, record: str, runtime_record: str = "final-runtime") -> dict:
    """Online service queries only; inventory and image files are never regenerated."""
    result = {}
    py_code, py_raw = runner.run(
        record + "-python-vulnerabilities",
        [
            str(ROOT / ".venv/bin/pip-audit"),
            "--requirement",
            str(ROOT / "requirements.lock"),
            "--no-deps",
            "--disable-pip",
            "--strict",
            "--timeout",
            "30",
            "--progress-spinner",
            "off",
            "--cache-dir",
            str(runner.temporary / "pip-audit"),
            "--format",
            "json",
        ],
        timeout=180,
    )
    try:
        data = json.loads(py_raw)
        packages = data.get("dependencies", [])
        findings = sum(len(p.get("vulns", [])) for p in packages)
    except json.JSONDecodeError:
        packages, findings = [], None
    result["python"] = {
        "exit_code": py_code,
        "packages": len(packages),
        "findings": findings,
        "service": "PyPI/PyPA vulnerability JSON API",
        "database_snapshot_date": "not exposed by service",
    }
    for name, extra in [("node-all", []), ("node-runtime", ["--omit=dev"])]:
        code, raw = runner.run(
            record + "-" + name + "-vulnerabilities",
            [
                "npm",
                "audit",
                "--package-lock-only",
                "--json",
                "--ignore-scripts",
                "--registry=https://registry.npmjs.org",
                *extra,
            ],
            cwd=ROOT / "frontend",
        )
        try:
            data = json.loads(raw)
            counts = data.get("metadata", {}).get("vulnerabilities")
        except json.JSONDecodeError:
            counts = None
        result[name] = {
            "exit_code": code,
            "counts": counts,
            "service": "https://registry.npmjs.org audit API",
            "database_snapshot_date": "not exposed by service",
        }
    identities = json.loads((OUT / (runtime_record + "-summary.json")).read_text())
    for name in ["api", "langflow", "web"]:
        source = OUT / (name + "-image.spdx.json")
        code, raw = runner.run(
            record + "-" + name + "-vulnerabilities",
            [
                "docker",
                "scout",
                "cves",
                "sbom://" + str(source),
                "--format",
                "sarif",
                "--exit-code",
            ],
            timeout=180,
        )
        try:
            data = json.loads(raw)
            runs = data["runs"]
            findings = sum(len(run.get("results", [])) for run in runs)
        except (json.JSONDecodeError, KeyError):
            findings = None
        result[name] = {
            "exit_code": code,
            "findings": findings,
            "image_id": identities[name]["identity"]["id"],
            "input_sbom": fingerprint(source),
            "inventory_scope": "installed package-manager metadata, not full filesystem",
            "service": "Docker Scout vulnerability service",
            "database_snapshot_date": "not exposed by service",
        }
    write_json(record + "-summary.json", result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=["dependencies", "images", "validate", "audit"])
    parser.add_argument("--temporary-root", type=Path, required=True)
    parser.add_argument("--image", action="append", default=[])
    parser.add_argument("--record", help="Distinct stage record name; preserves previous manifests")
    parser.add_argument(
        "--runtime-record",
        default="final-runtime",
        help="Runtime record supplying current final image identities",
    )
    parser.add_argument(
        "--allow-online-audit",
        action="store_true",
        help="Requires explicit authority to send package name/version metadata to audit services",
    )
    args = parser.parse_args()
    record = args.record or args.stage
    if not re.fullmatch(r"[a-z][a-z0-9-]*", record):
        raise ValueError("Record name must be lowercase letters/numbers/hyphens")
    if not re.fullmatch(r"[a-z][a-z0-9-]*", args.runtime_record):
        raise ValueError("Runtime record must be lowercase letters/numbers/hyphens")
    if (OUT / (record + "-manifest.json")).exists():
        raise FileExistsError("Existing manifest is immutable; choose a distinct record")
    runner = Runner(args.temporary_root)
    if args.stage == "dependencies":
        result = dependencies(runner, args.allow_online_audit)
    elif args.stage == "images":
        result = images(runner, args.image, args.allow_online_audit, record)
    elif args.stage == "validate":
        result = validate_evidence(args.runtime_record)
    else:
        if not args.allow_online_audit:
            raise ValueError("Online audit needs explicit external-sending authorization")
        result = audit_existing(runner, record, args.runtime_record)
    inputs = [
        "requirements.lock",
        "frontend/package-lock.json",
        "pyproject.toml",
        "frontend/package.json",
        "docker/api.Dockerfile",
        "docker/langflow.Dockerfile",
        "docker/web.Dockerfile",
        "docker-compose.yml",
        "docs/UPGRADE_SPEC.md",
        "docs/spec-baseline.json",
        "scripts/scan_release.py",
        "THIRD_PARTY_NOTICES.md",
    ]
    manifest = {
        "contract": "ARC-UPGRADE@0.1.0",
        "acceptance": ["RELEASE-001", "AC-19"],
        "stage": args.stage,
        "created_at": now(),
        "producer": "scripts/scan_release.py",
        "temporary_root": str(runner.temporary),
        "temporary_bytes": tree_bytes(runner.temporary),
        "temporary_limit_bytes": LIMIT,
        "source_inputs": [fingerprint(ROOT / p) for p in inputs],
        "tools": {
            "python": os.sys.version,
            "pip-audit": importlib.metadata.version("pip-audit"),
            "cyclonedx-python-lib": importlib.metadata.version("cyclonedx-python-lib"),
            "npm": subprocess.check_output(["npm", "--version"], text=True).strip(),
            "docker_scout": "1.18.1; locally probed before scanning",
        },
        "commands": runner.records,
        "result": result,
        "limitations": [
            "Remote vulnerability services do not expose reproducible database snapshot dates.",
            "Metadata SBOM is not a complete filesystem/static-binary scan.",
            "License metadata is not legal approval; unknown/restricted licenses need review.",
            "P0/P1 local release evidence does not establish production readiness.",
        ],
        "files": [
            fingerprint(p)
            for p in sorted(OUT.iterdir())
            if p.is_file() and not p.name.endswith("manifest.json")
        ],
    }
    write_json(record + "-manifest.json", manifest)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
