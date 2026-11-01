"""Scan exact local image package metadata with the public OSV API, without a DB cache.

This is a package-manager inventory scan, not a filesystem/binary scanner. Only
package names/versions are sent to OSV. Existing images, containers and volumes
are never modified. Output is bounded and never overwrites an existing record.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import re
import subprocess
import sys
import threading
import urllib.error
import urllib.request
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote

try:
    from scripts.scan_release import (
        INVENTORY_CODE,
        OS_COMMAND,
        image_bom,
        licenses_report,
        normalize,
        os_packages,
        python_license,
    )
except ModuleNotFoundError:
    from scan_release import (  # type: ignore[no-redef]
        INVENTORY_CODE,
        OS_COMMAND,
        image_bom,
        licenses_report,
        normalize,
        os_packages,
        python_license,
    )

API = "https://api.osv.dev/v1"
LIMIT = 40 * 1024 * 1024
MAX_FILES = 200
MAX_RESPONSE = 4 * 1024 * 1024
MAX_PAGES = 10


def now() -> str:
    return datetime.now(UTC).isoformat()


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def encoded(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode()


class Output:
    def __init__(self, path: Path):
        if path.is_symlink():
            raise ValueError("Output root must not be a symlink")
        self.path = path.resolve()
        if self.path.exists() and (not self.path.is_dir() or any(self.path.iterdir())):
            raise ValueError("Output root must be absent or empty")
        self.path.mkdir(parents=True, exist_ok=True)
        self.files: list[dict] = []

    def write(self, name: str, raw: bytes) -> None:
        if not re.fullmatch(r"[a-zA-Z0-9_.-]+", name):
            raise ValueError("Unsafe output name")
        # Reserve 1 MiB and one file for the final manifest/error record.
        cap = LIMIT if name == "manifest.json" else LIMIT - 1024 * 1024
        if sum(r["bytes"] for r in self.files) + len(raw) > cap:
            raise RuntimeError("40 MiB output guard; preserve outputs, do not clean")
        if len(self.files) >= MAX_FILES - (name != "manifest.json"):
            raise RuntimeError("200 file output guard")
        with (self.path / name).open("xb") as stream:
            stream.write(raw)
        self.files.append({"path": name, "bytes": len(raw), "sha256": digest(raw)})

    def json(self, name: str, value: object) -> None:
        self.write(name, encoded(value))


def query_for(package: dict, distro: dict) -> dict | None:
    """Use distribution source packages, not binary names or upstream versions."""
    kind = package["type"]
    if kind == "pypi":
        ecosystem, name, version = "PyPI", normalize(package["name"]), package["version"]
    elif kind == "deb" and distro.get("ID") == "debian":
        release = distro.get("VERSION_ID", "")
        if not re.fullmatch(r"\d+", release):
            return None
        ecosystem = "Debian:" + release
        name, version = package.get("source_name"), package.get("source_version")
    elif kind == "apk" and distro.get("ID") == "alpine":
        release = distro.get("VERSION_ID", "")
        match = re.fullmatch(r"(\d+\.\d+)(?:\.\d+)?", release)
        if not match:
            return None
        ecosystem = "Alpine:v" + match[1]
        name, version = package.get("source_name"), package.get("version")
    else:
        return None
    if not name or not version:
        return None
    return {"package": {"ecosystem": ecosystem, "name": name}, "version": version}


def key_for(query: dict) -> str:
    return json.dumps(query, sort_keys=True, separators=(",", ":"))


def batch_queries(queries: list[dict], request) -> list[dict]:
    """Preserve per-query completeness; malformed/error/pagination limits are unknown."""
    outcomes = [{"query": q, "status": "pending", "vulnerability_ids": []} for q in queries]
    for offset in range(0, len(queries), 100):
        pending = [(i, dict(queries[i])) for i in range(offset, min(offset + 100, len(queries)))]
        seen_tokens: dict[int, set[str]] = {}
        for page in range(MAX_PAGES):
            if not pending:
                break
            try:
                response = request(API + "/querybatch", {"queries": [q for _, q in pending]})
                results = response.get("results")
                if not isinstance(results, list) or len(results) != len(pending):
                    raise ValueError("querybatch result length mismatch")
            except Exception as exc:
                for index, _ in pending:
                    outcomes[index].update(status="unknown", error=str(exc))
                break
            following = []
            for (index, query), result in zip(pending, results, strict=True):
                try:
                    if not isinstance(result, dict) or "error" in result:
                        raise ValueError("invalid/error query result")
                    matches = result.get("vulns", [])
                    if not isinstance(matches, list) or any(
                        not isinstance(v, dict) or not isinstance(v.get("id"), str)
                        or not v["id"] for v in matches
                    ):
                        raise ValueError("invalid vulnerability identifiers")
                    outcomes[index]["vulnerability_ids"] = sorted(set(
                        outcomes[index]["vulnerability_ids"] + [v["id"] for v in matches]
                    ))
                    token = result.get("next_page_token")
                    if token is not None and (not isinstance(token, str) or len(token) > 8192):
                        raise ValueError("invalid pagination token")
                    if token:
                        tokens = seen_tokens.setdefault(index, set())
                        if token in tokens:
                            raise ValueError("repeated pagination token")
                        tokens.add(token)
                        if page + 1 == MAX_PAGES:
                            raise ValueError("pagination limit reached before completion")
                        following.append((index, query | {"page_token": token}))
                    else:
                        outcomes[index]["status"] = "queried"
                except Exception as exc:
                    outcomes[index].update(status="unknown", error=str(exc))
            pending = following
    return outcomes


class HTTP:
    def __init__(self):
        self.records: list[dict] = []
        self.lock = threading.Lock()
        self.total_bytes = 0

    def __call__(self, url: str, payload: dict | None = None) -> dict:
        data = json.dumps(payload).encode() if payload is not None else None
        record = {"url": url, "method": "POST" if data else "GET", "request": payload,
                  "started_at": now()}
        request = urllib.request.Request(url, data=data, headers={
            "Content-Type": "application/json", "User-Agent": "arc-release-metadata-scan/1"
        })
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                raw = response.read(MAX_RESPONSE + 1)
                record["status_code"] = response.status
            with self.lock:
                self.total_bytes += len(raw)
                if len(raw) > MAX_RESPONSE or self.total_bytes > 24 * 1024 * 1024:
                    raise RuntimeError("bounded HTTP response capacity exceeded")
            record.update(response_bytes=len(raw), response_sha256=digest(raw))
            parsed = json.loads(raw)
            if not isinstance(parsed, dict):
                raise ValueError("OSV response must be an object")
            # Batch raw responses are small and preserve pagination evidence. Full
            # vulnerability documents are stored once in vulnerabilities.json.
            if payload is not None:
                record["response"] = parsed
            return parsed
        except (OSError, ValueError, RuntimeError) as exc:
            record["error"] = str(exc)
            raise
        finally:
            record["ended_at"] = now()
            with self.lock:
                self.records.append(record)


def command(out: Output, label: str, argv: list[str], records: list) -> str:
    started = now()
    proc = subprocess.run(argv, capture_output=True, timeout=120, check=False)
    if len(proc.stdout) + len(proc.stderr) > 8 * 1024 * 1024:
        raise RuntimeError("8 MiB command output capacity exceeded")
    out.write(label + ".stdout", proc.stdout)
    out.write(label + ".stderr", proc.stderr)
    records.append({"argv": argv, "started_at": started, "ended_at": now(),
                    "exit_code": proc.returncode, "stdout_sha256": digest(proc.stdout),
                    "stderr_sha256": digest(proc.stderr)})
    if proc.returncode:
        raise RuntimeError(f"{label} failed with exit {proc.returncode}")
    return proc.stdout.decode()


def inventory(out: Output, name: str, image_id: str, records: list) -> dict:
    fmt = ('{"id":{{json .Id}},"os":{{json .Os}},'
           '"architecture":{{json .Architecture}},"size":{{.Size}},'
           '"repo_digests":{{json .RepoDigests}}}')
    identity = json.loads(command(out, name + "-identity", [
        "docker", "image", "inspect", "--format", fmt, image_id
    ], records))
    if identity["id"] != image_id:
        raise ValueError("Docker returned a different image ID")
    base = ["docker", "run", "--rm", "--network", "none", "--read-only",
            "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
            "--pids-limit", "64", "--memory", "512m"]
    raw = command(out, name + "-os", base + ["--entrypoint", "sh", image_id,
                                            "-c", OS_COMMAND], records)
    distro, packages = os_packages(raw)
    probe = (
        'if command -v python >/dev/null 2>&1; then exec python -c "$1"; '
        'elif command -v python3 >/dev/null 2>&1; then exec python3 -c "$1"; '
        'else printf \'%s\\n\' \'{"packages": [], "interpreter": null}\'; fi'
    )
    text = command(out, name + "-python", base + ["--entrypoint", "sh", image_id,
                                                 "-c", probe, "arc-inventory", INVENTORY_CODE],
                   records)
    python_inventory = json.loads(text)["packages"]
    unique = {(normalize(p["name"]), p["version"]): p for p in python_inventory}
    packages += [{"name": p["name"], "version": p["version"], "type": "pypi",
                  "license": python_license(p["name"], p["version"], python_inventory)}
                 for p in unique.values()]
    if not packages:
        raise ValueError("No package metadata collected; cannot claim empty scan")
    out.json(name + "-inventory.json", {"identity": identity, "distro": distro,
                                      "packages": packages})
    cdx, spdx = image_bom(name, identity, packages, distro)
    out.json(name + ".cdx.json", cdx)
    out.json(name + ".spdx.json", spdx)
    out.json(name + "-licenses.json", licenses_report(packages))
    return {"identity": identity, "distro": distro, "packages": packages}


def validate_image(value: str) -> tuple[str, str]:
    match = re.fullmatch(r"([a-z][a-z0-9-]{0,31})=(sha256:[0-9a-f]{64})", value)
    if not match:
        raise argparse.ArgumentTypeError("Use name=sha256:<64 lowercase hex>, never a mutable tag")
    return match[1], match[2]


def run(args) -> int:
    if not 1 <= len(args.image) <= 4 or len({n for n, _ in args.image}) != len(args.image):
        raise ValueError("Supply 1..4 images with unique names")
    out = Output(args.output_dir)
    records: list = []
    started = now()
    manifest = {"contract": "ARC-UPGRADE@0.1.0", "acceptance": ["RELEASE-001", "AC-19"],
                "producer": "scripts/scan_images_osv.py", "started_at": started,
                "service": API, "database_snapshot_date": None,
                "online_package_metadata_sending": True, "result": "incomplete"}
    http = HTTP()
    try:
        inventories = {name: inventory(out, name, image_id, records)
                       for name, image_id in args.image}
        queries: dict[str, dict] = {}
        mappings = []
        for name, inv in inventories.items():
            for package in inv["packages"]:
                query = query_for(package, inv["distro"])
                key = key_for(query) if query else None
                if query:
                    queries[key] = query
                mappings.append({"image": name, "package": package, "query_key": key,
                                 "mapping_status": "mapped" if query else "unsupported_unknown"})
        keys = sorted(queries)
        outcomes = batch_queries([queries[k] for k in keys], http)
        by_key = dict(zip(keys, outcomes, strict=True))
        out.json("package-mappings.json", {"mappings": mappings,
                                          "deduplicated_queries": outcomes})
        ids = sorted({v for row in outcomes for v in row["vulnerability_ids"]})
        if len(ids) > 4000:
            raise RuntimeError("4000 vulnerability detail capacity exceeded")

        def detail(identifier: str) -> tuple[str, dict]:
            try:
                value = http(API + "/vulns/" + quote(identifier, safe=""))
                if value.get("id") != identifier:
                    raise ValueError("vulnerability detail ID mismatch")
                return identifier, {"status": "queried", "document": value}
            except Exception as exc:
                return identifier, {"status": "unknown", "error": str(exc)}

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            details = dict(executor.map(detail, ids))
        out.json("vulnerabilities.json", details)
        summaries = {}
        for name, inv in inventories.items():
            rows = [r for r in mappings if r["image"] == name]
            matched = []
            unknown = 0
            for row in rows:
                result = by_key.get(row["query_key"])
                if result is None or result["status"] != "queried":
                    unknown += 1
                if result and result["vulnerability_ids"]:
                    matched.append({"package": row["package"]["name"],
                                    "version": row["package"]["version"],
                                    "query": result["query"],
                                    "vulnerability_ids": result["vulnerability_ids"]})
            found = {v for r in matched for v in r["vulnerability_ids"]}
            severities = Counter()
            for identifier in found:
                doc = details[identifier].get("document", {})
                # Keep upstream labels only. CVSS vectors are retained in documents,
                # never turned into invented severity labels here.
                label = doc.get("database_specific", {}).get("severity")
                severities[label if isinstance(label, str) and label else "unknown"] += 1
            summaries[name] = {"image_id": inv["identity"]["id"],
                               "inventory_packages": len(rows), "unknown_packages": unknown,
                               "matched_binary_or_python_packages": len(matched),
                               "observed_unique_advisory_ids": len(found),
                               "detail_unknown": sum(details[v]["status"] != "queried"
                                                     for v in found),
                               "upstream_severity_labels": dict(severities),
                               "findings": matched}
        manifest.update(result="queried_with_findings" if ids else "queried_no_match",
                        images=summaries, unique_queries=len(keys),
                        observed_unique_advisory_ids=len(ids),
                        mapping_unknown=sum(r["query_key"] is None for r in mappings),
                        query_unknown=sum(r["status"] != "queried" for r in outcomes),
                        detail_unknown=sum(v["status"] != "queried" for v in details.values()))
        out.json("summary.json", manifest)
    except Exception as exc:
        manifest.update(result="incomplete_unknown", error=str(exc))
    finally:
        out.json("http-records.json", http.records)
        manifest.update(ended_at=now(), commands=records,
                        source_inputs=[{"path": p, "sha256": digest(Path(p).read_bytes())}
                                       for p in ["scripts/scan_images_osv.py",
                                                 "scripts/scan_release.py"]],
                        limitations=[
                            "No full filesystem/static binary/native embedded library scan.",
                            "Only Debian/Alpine source packages and Python METADATA are mapped.",
                            "Unsupported mapping/errors/incomplete pages remain unknown, not zero.",
                            "No match is a service query result, not proof of absolute safety.",
                            "OSV service exposes no reproducible database snapshot date.",
                            "License inventory metadata is not distribution approval.",
                            "Severity is upstream metadata; absent severity remains unknown.",
                        ], output_limit_bytes=LIMIT, output_limit_files=MAX_FILES,
                        files=out.files.copy())
        out.json("manifest.json", manifest)
    print(json.dumps({k: manifest.get(k) for k in [
        "result", "error", "unique_queries", "observed_unique_advisory_ids", "query_unknown",
        "detail_unknown"]}))
    return 2 if (manifest["result"] == "incomplete_unknown" or manifest.get("mapping_unknown")
                 or manifest.get("query_unknown")
                 or manifest.get("detail_unknown")) else 1 if manifest.get(
                     "observed_unique_advisory_ids") else 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", action="append", type=validate_image, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    sys.exit(run(parser.parse_args()))


if __name__ == "__main__":
    main()
