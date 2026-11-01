"""Collect bounded release evidence from this CI job's already running images.

This does not approve a release. Vulnerability findings, scan gaps and license
obligations remain in the recorded manifests for review. No build, pull, database
write, mount, package installation or historical-artifact cleanup is performed.
Short-lived read-only helper containers use their normal removal lifecycle.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

LIMIT = 60 * 1024 * 1024
FILE_LIMIT = 600


def now() -> str:
    return datetime.now(UTC).isoformat()


def identity(raw: str, project: str, service: str) -> str:
    fields = raw.strip().split()
    if len(fields) != 3 or fields[1:] != [project, service]:
        raise ValueError("Container project/service identity mismatch")
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", fields[0]):
        raise ValueError("Expected immutable full image ID")
    return fields[0]


def usage(root: Path) -> tuple[int, int]:
    files = [p for p in root.rglob("*") if p.is_file()]
    if any(p.is_symlink() for p in root.rglob("*")):
        raise ValueError("Unexpected symlink in collector output")
    return sum(p.stat().st_size for p in files), len(files)


class Collector:
    def __init__(self, root: Path, project: str):
        if not re.fullmatch(r"arc-ci-[0-9]+", project):
            raise ValueError("This collector only reads the current arc-ci-<run_id> project")
        if root.is_symlink() or (root.exists() and (not root.is_dir() or any(root.iterdir()))):
            raise ValueError("Output must be absent or empty, never replace existing evidence")
        self.root = root.resolve()
        if shutil.disk_usage(self.root.parent).free < 6 * 1024**3:
            raise RuntimeError("CI evidence collection requires 6 GiB free; stop before generation")
        self.root.mkdir(parents=True, exist_ok=True)
        self.project = project
        self.commands: list[dict] = []

    def run(self, label: str, argv: list[str], timeout: int = 240) -> tuple[int, str]:
        if not re.fullmatch(r"[a-z0-9-]+", label):
            raise ValueError("Invalid record label")
        stdout = self.root / (label + ".stdout")
        stderr = self.root / (label + ".stderr")
        started = now()
        begin = time.monotonic()
        stop = None
        with stdout.open("xb") as out, stderr.open("xb") as err:
            proc = subprocess.Popen(
                argv,
                stdout=out,
                stderr=err,
                start_new_session=True,
                env=os.environ | {"PYTHONDONTWRITEBYTECODE": "1"},
            )
            while proc.poll() is None:
                size, count = usage(self.root)
                if time.monotonic() - begin > timeout:
                    stop = "bounded_timeout"
                if size >= LIMIT - 1024 * 1024 or count >= FILE_LIMIT - 5:
                    stop = "bounded_output_capacity"
                if shutil.disk_usage(self.root).free < 5 * 1024**3:
                    stop = "CI_disk_headroom"
                if stop:
                    os.killpg(proc.pid, signal.SIGTERM)
                    try:
                        proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        os.killpg(proc.pid, signal.SIGKILL)
                    break
                time.sleep(0.4)
            code = proc.wait()
        self.commands.append(
            {
                "argv": argv,
                "started_at": started,
                "ended_at": now(),
                "exit_code": code,
                "stop_reason": stop,
                "stdout": stdout.name,
                "stderr": stderr.name,
            }
        )
        if stop:
            raise RuntimeError(stop)
        if stdout.stat().st_size > 2 * 1024 * 1024:
            raise RuntimeError("Unexpectedly large command summary")
        return code, stdout.read_text()

    def images(self) -> dict[str, str]:
        targets = {}
        for service in ["api", "langflow", "web", "postgres"]:
            code, raw = self.run(service + "-container", ["docker", "compose", "ps", "-q", service])
            container = raw.strip()
            if code or not re.fullmatch(r"[0-9a-f]{64}", container):
                raise ValueError("Exactly one running container per expected service is required")
            fmt = (
                '{{.Image}} {{index .Config.Labels "com.docker.compose.project"}} '
                '{{index .Config.Labels "com.docker.compose.service"}}'
            )
            code, raw = self.run(
                service + "-image", ["docker", "inspect", "--format", fmt, container]
            )
            if code:
                raise ValueError("Image identity read failed")
            targets[service] = identity(raw, self.project, service)
        return targets


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    collector = Collector(args.output_dir, os.environ.get("COMPOSE_PROJECT_NAME", ""))
    result = {
        "contract": "ARC-UPGRADE@0.1.0",
        "acceptance": ["AC-19", "RELEASE-001"],
        "started_at": now(),
        "producer": "scripts/collect_release_ci.py",
        "release_acceptance": "pending_review_not_granted_by_collection",
        "project": collector.project,
        "historical_or_user_artifact_cleanup": False,
    }
    try:
        targets = collector.images()
        result["images"] = targets
        for name in ["api", "langflow"]:
            code, _ = collector.run(
                name + "-pip-check",
                [
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
                    targets[name],
                    "-m",
                    "pip",
                    "check",
                ],
            )
            if code:
                raise RuntimeError(name + " installed dependency consistency failed")
        audits = {}
        command = [
            sys.executable,
            "scripts/scan_images_osv.py",
            "--output-dir",
            str(collector.root / "images"),
        ]
        for name, image in targets.items():
            command += ["--image", name + "=" + image]
        code, _ = collector.run("image-audit", command, timeout=600)
        audits["package_scan_exit_code"] = code
        if code not in {0, 1, 2} or not (collector.root / "images/manifest.json").is_file():
            raise RuntimeError("Image scanner failed to produce a valid record")
        code, _ = collector.run(
            "rhel-audit",
            [
                sys.executable,
                "scripts/scan_images_osv.py",
                "--redhat-only",
                "--image",
                "langflow=" + targets["langflow"],
                "--output-dir",
                str(collector.root / "rhel"),
            ],
            timeout=360,
        )
        audits["redhat_supplement_exit_code"] = code
        if code not in {0, 1, 2} or not (collector.root / "rhel/manifest.json").is_file():
            raise RuntimeError("Red Hat supplement did not produce a valid record")
        code, _ = collector.run(
            "image-licenses",
            [
                sys.executable,
                "scripts/verify_image_licenses.py",
                "--output-dir",
                str(collector.root / "licenses"),
                *[
                    value
                    for name in ["api", "langflow", "web"]
                    for value in ["--image", name + "=" + targets[name]]
                ],
            ],
            timeout=240,
        )
        if code:
            raise RuntimeError(
                "License collector failed; missing license remains a separate finding"
            )
        result.update(
            collection_state="collected",
            audits=audits,
            note=(
                "Exit 1 means findings; 2 means unknown/incomplete. "
                "RPM coverage is supplemented separately. No result accepts "
                "residual risk or grants binary redistribution."
            ),
        )
    except Exception as exc:
        result.update(collection_state="failed", error=str(exc))
    finally:
        result.update(
            ended_at=now(),
            commands=collector.commands,
            limits={"bytes": LIMIT, "files": FILE_LIMIT},
            source_inputs=[
                {"path": path, "sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest()}
                for path in [
                    "scripts/collect_release_ci.py",
                    "scripts/scan_images_osv.py",
                    "scripts/scan_release.py",
                    "scripts/verify_image_licenses.py",
                    "docs/UPGRADE_SPEC.md",
                ]
                if Path(path).is_file()
            ],
            files=[
                {
                    "path": str(p.relative_to(collector.root)),
                    "bytes": p.stat().st_size,
                    "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                }
                for p in sorted(collector.root.rglob("*"))
                if p.is_file()
            ],
        )
        with (collector.root / "manifest.json").open("x") as output:
            output.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: result.get(k) for k in ["collection_state", "error", "images", "audits"]}))
    raise SystemExit(0 if result["collection_state"] == "collected" else 1)


if __name__ == "__main__":
    main()
