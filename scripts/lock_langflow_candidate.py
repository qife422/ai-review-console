#!/usr/bin/env python3
"""Fail-closed candidate lock creation from an ephemeral pip resolver report.

The report is not evidence: only the bounded lock and receipt are retained.
Installation must use pip --require-hashes (without --no-deps) in a fresh env.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from urllib.parse import urlsplit

BASELINE = Path("docs/evidence/langflow-candidate/ci/candidate/second/inventory.json")
BASELINE_SHA256 = "8afd65b961c8772146dad70e64894911a8b5edb951178d5c5f13d7d5fabf1e41"
PINS = Path("compliance/langflow-candidate.in")
MAX_REPORT = 64 * 1024 * 1024
MAX_OUTPUT = 512 * 1024


def canonical(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def read_pins(path: Path) -> dict[str, str]:
    pins = {}
    for line in path.read_text().splitlines():
        if not line or line.startswith("#"):
            continue
        match = re.fullmatch(r"([a-z0-9]+(?:-[a-z0-9]+)*)==([A-Za-z0-9][A-Za-z0-9.!+_-]*)", line)
        if not match or match[1] in pins:
            raise ValueError("pins must be unique canonical names with exact versions")
        pins[match[1]] = match[2]
    if not pins:
        raise ValueError("empty pins")
    return pins


def baseline_pins(path: Path) -> dict[str, str]:
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != BASELINE_SHA256:
        raise ValueError("baseline fingerprint mismatch")
    data = json.loads(raw)
    pins = {canonical(p["name"]): p["version"] for p in data["packages"]}
    if data["python"] != "3.12.16" or len(pins) != 334 or len(data["packages"]) != 334:
        raise ValueError("baseline identity mismatch")
    return pins


def target(environment: dict) -> None:
    if (
        environment.get("python_full_version") != "3.12.16"
        or environment.get("sys_platform") != "linux"
        or environment.get("platform_machine") != "x86_64"
        or environment.get("implementation_name") != "cpython"
    ):
        raise ValueError("requires CPython 3.12.16 Linux x86_64")


def lock_from_report(data: dict, pins: dict[str, str]) -> tuple[str, list]:
    if data.get("version") != "1":
        raise ValueError("unsupported pip report format")
    target(data["environment"])
    selected = {}
    for item in data["install"]:
        meta = item["metadata"]
        name, version = canonical(meta["name"]), meta["version"]
        if name in selected or pins.get(name) != version:
            raise ValueError("duplicate or unexpected resolved package: " + name)
        if item.get("is_direct") or item.get("is_yanked"):
            raise ValueError("direct or yanked requirement: " + name)
        info = item["download_info"]
        url = urlsplit(info["url"])
        if (
            url.scheme != "https"
            or url.hostname != "files.pythonhosted.org"
            or url.netloc != "files.pythonhosted.org"
            or url.query
            or url.fragment
            or not url.path.startswith("/packages/")
        ):
            raise ValueError("archive must use official HTTPS files.pythonhosted.org")
        digest = info.get("archive_info", {}).get("hashes", {}).get("sha256", "")
        if not re.fullmatch("[0-9a-f]{64}", digest):
            raise ValueError("missing archive SHA256: " + name)
        kind = "wheel" if url.path.endswith(".whl") else "sdist"
        if kind == "sdist" and not url.path.endswith(
            (".tar.gz", ".zip", ".tar.bz2", ".tar.xz", ".tgz")
        ):
            raise ValueError("unsupported source archive: " + name)
        selected[name] = {
            "name": name,
            "version": version,
            "sha256": digest,
            "kind": kind,
            "url": info["url"],
        }
    if set(selected) != set(pins):
        raise ValueError("resolved package set differs from complete baseline")
    archives = [selected[name] for name in sorted(selected)]
    lock = "# Candidate CPython 3.12.16 Linux x86_64; install with --require-hashes\n"
    lock += "".join(f"{a['name']}=={a['version']} --hash=sha256:{a['sha256']}\n" for a in archives)
    return lock, archives


def encode(data: dict) -> bytes:
    return (json.dumps(data, indent=2, sort_keys=True) + "\n").encode()


def write_outputs(outputs: list[tuple[Path, bytes]]) -> None:
    if sum(len(content) for _, content in outputs) > MAX_OUTPUT:
        raise ValueError("combined output exceeds 512KiB")
    paths = [path.resolve() for path, _ in outputs]
    if len(set(paths)) != len(paths) or any(p.exists() or p.is_symlink() for p, _ in outputs):
        raise ValueError("outputs must be distinct absent paths; nothing overwritten")
    for path, content in outputs:
        with path.open("xb") as handle:
            handle.write(content)


def verify_python(python: str, pins: dict) -> dict:
    subprocess.run([python, "-m", "pip", "check"], check=True, timeout=120)
    code = """import importlib.metadata as m,json,platform,sys
print(json.dumps({
    'environment': {
        'python_full_version': platform.python_version(),
        'sys_platform': sys.platform,
        'platform_machine': platform.machine(),
        'implementation_name': sys.implementation.name,
    },
    'packages': [{'name': d.metadata['Name'], 'version': d.version}
                 for d in m.distributions()],
}))"""
    result = subprocess.run(
        [python, "-c", code], check=True, capture_output=True, text=True, timeout=120
    )
    data = json.loads(result.stdout)
    target(data["environment"])
    actual = {}
    for package in data["packages"]:
        name = canonical(package["name"])
        if name in actual:
            raise ValueError("duplicate installed distribution: " + name)
        actual[name] = package["version"]
    if actual != pins:
        raise ValueError("installed package set/versions differ from complete baseline")
    return {
        "environment": data["environment"],
        "package_count": len(actual),
        "pip_check": "passed",
        "installed_set_matches_pins": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("generate", "verify"):
        p = sub.add_parser(command)
        p.add_argument("--pins", type=Path, default=PINS)
        p.add_argument("--baseline", type=Path, default=BASELINE)
        p.add_argument("--receipt", type=Path, required=True)
        if command == "generate":
            p.add_argument("--report", type=Path, required=True)
            p.add_argument("--lock", type=Path, required=True)
        else:
            p.add_argument("--python", required=True)
    args = parser.parse_args()
    pins = read_pins(args.pins)
    if pins != baseline_pins(args.baseline):
        raise ValueError("pins differ from fixed baseline")
    receipt = {
        "baseline_sha256": BASELINE_SHA256,
        "pins_sha256": hashlib.sha256(args.pins.read_bytes()).hexdigest(),
    }
    if args.command == "generate":
        if args.report.stat().st_size > MAX_REPORT:
            raise ValueError("ephemeral pip report exceeds 64MiB")
        raw = args.report.read_bytes()
        lock, archives = lock_from_report(json.loads(raw), pins)
        receipt.update(
            {
                "report_sha256": hashlib.sha256(raw).hexdigest(),
                "lock_sha256": hashlib.sha256(lock.encode()).hexdigest(),
                "package_count": len(pins),
                "archives": archives,
                "sdist_count": sum(a["kind"] == "sdist" for a in archives),
                "scope": "resolver selection; not installation or runtime verification",
            }
        )
        write_outputs([(args.lock, lock.encode()), (args.receipt, encode(receipt))])
    else:
        receipt.update(verify_python(args.python, pins))
        write_outputs([(args.receipt, encode(receipt))])


if __name__ == "__main__":
    main()
