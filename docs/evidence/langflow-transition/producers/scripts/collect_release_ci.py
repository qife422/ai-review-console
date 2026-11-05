"""Collect bounded release evidence from this CI job's already running images.

This does not approve a release. Vulnerability findings, scan gaps and license
obligations remain in the recorded manifests for review. No build, pull, database
write, mount, package installation or historical-artifact cleanup is performed.
Short-lived read-only helper containers use their normal removal lifecycle.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import platform
import re
import shlex
import shutil
import signal
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

LIMIT = 60 * 1024 * 1024
FILE_LIMIT = 600
SYSTEM_LIMIT = 4 * 1024 * 1024
SYSTEM_PRODUCER = b"""import base64,hashlib,json,stat
from pathlib import Path
root=Path("/usr/share/arc-system-maintenance")
assert not root.is_symlink() and root.is_dir()
paths=sorted(root.iterdir())
assert len(paths)<=32
files=[];total=0
for p in paths:
    assert not p.is_symlink() and stat.S_ISREG(p.stat().st_mode)
    total+=p.stat().st_size
    assert total<=4*1024*1024+65536
    data=p.read_bytes()
    files.append({"path":p.name,"bytes":len(data),"sha256":hashlib.sha256(data).hexdigest(),"base64":base64.b64encode(data).decode()})
print(json.dumps({"files":files},separators=(",",":")))
"""


def extract_system_records(raw: str, destination: Path) -> dict:
    """Validate the entire bounded export before writing any selected image bytes."""
    if destination.exists() or destination.is_symlink():
        raise ValueError("System evidence output must not exist")
    records = json.loads(raw)["files"]
    if not isinstance(records, list) or len(records) > 32:
        raise ValueError("System record count limit")
    selected = {}
    total = 0
    for record in records:
        name = record["path"]
        if name != "manifest.json" and not re.fullmatch(r"[a-z-]+\.(stdout|stderr)", name):
            raise ValueError("Unexpected system record path")
        if name in selected:
            raise ValueError("Duplicate system record")
        data = base64.b64decode(record["base64"], validate=True)
        total += len(data)
        if total > SYSTEM_LIMIT + 65536:
            raise ValueError("System record byte limit")
        if len(data) != record["bytes"] or hashlib.sha256(data).hexdigest() != record["sha256"]:
            raise ValueError("System transport integrity mismatch")
        selected[name] = data
    manifest = json.loads(selected["manifest.json"])
    if manifest["status"] != "completed":
        raise ValueError("System update did not complete")
    declared = {f["path"]: f for f in manifest["files"]}
    if set(declared) != set(selected) - {"manifest.json"}:
        raise ValueError("System manifest file set mismatch")
    for name, entry in declared.items():
        data = selected[name]
        if entry["bytes"] != len(data) or entry["sha256"] != hashlib.sha256(data).hexdigest():
            raise ValueError("System manifest integrity mismatch")
    if not {"rpm-before.stdout", "rpm-after.stdout", "update.stdout"} <= set(selected):
        raise ValueError("Missing system transaction records")
    destination.mkdir()
    for name, data in selected.items():
        with (destination / name).open("xb") as stream:
            stream.write(data)
    return {"files": len(selected), "bytes": total, "status": manifest["status"]}


def verify_os_release(raw: str, profile: str) -> dict:
    fields = {}
    for line in raw.splitlines():
        if not line or line.startswith("#"):
            continue
        key, sep, value = line.partition("=")
        if not sep or not re.fullmatch(r"[A-Z][A-Z0-9_]*", key) or key in fields:
            raise ValueError("Invalid os-release record")
        parts = shlex.split(value, comments=False, posix=True)
        if len(parts) != 1:
            raise ValueError("Invalid os-release value")
        fields[key] = parts[0]
    expected = {"rhel": "rhel", "debian": "debian"}[profile]
    if fields.get("ID") != expected or (profile == "debian" and fields.get("VERSION_ID") != "12"):
        raise ValueError("Expected OS profile mismatch: " + profile)
    if not fields.get("VERSION_ID"):
        raise ValueError("OS version missing")
    return {
        "profile": profile,
        "id": fields["ID"],
        "version_id": fields["VERSION_ID"],
        "source": "/etc/os-release",
    }


def collect_native_for_profile(profile: str, system: str, machine: str) -> bool:
    if profile == "complete":
        return True
    if profile == "prior-materials":
        return False
    if profile == "arm-backend" and system == "Linux" and machine in {"aarch64", "arm64"}:
        return False
    raise ValueError("The native-budget skip profile is only for the Linux ARM backend job")


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
        if not re.fullmatch(r"arc-ci-[0-9]+(?:-(?:amd64|arm64))?", project):
            raise ValueError("This collector only reads the current arc-ci-<run_id> project")
        if root.is_symlink() or (root.exists() and (not root.is_dir() or any(root.iterdir()))):
            raise ValueError("Output must be absent or empty, never replace existing evidence")
        self.root = root.resolve()
        if shutil.disk_usage(self.root.parent).free < 6 * 1024**3:
            raise RuntimeError("CI evidence collection requires 6 GiB free; stop before generation")
        self.root.mkdir(parents=True, exist_ok=True)
        self.project = project
        self.commands: list[dict] = []

    def run(
        self,
        label: str,
        argv: list[str],
        timeout: int = 240,
        *,
        payload: bytes | None = None,
        max_stdout_bytes: int = 2 * 1024 * 1024,
    ) -> tuple[int, str]:
        if not re.fullmatch(r"[a-z0-9-]+", label):
            raise ValueError("Invalid record label")
        if payload is not None and len(payload) > 64 * 1024:
            raise ValueError("Bounded probe stdin exceeds 64 KiB")
        if not 0 < max_stdout_bytes <= 6 * 1024 * 1024:
            raise ValueError("Command summary limit exceeds 6 MiB")
        stdout = self.root / (label + ".stdout")
        stderr = self.root / (label + ".stderr")
        started = now()
        begin = time.monotonic()
        stop = None
        with stdout.open("xb") as out, stderr.open("xb") as err:
            proc = subprocess.Popen(
                argv,
                stdin=subprocess.PIPE if payload is not None else subprocess.DEVNULL,
                stdout=out,
                stderr=err,
                start_new_session=True,
                env=os.environ | {"PYTHONDONTWRITEBYTECODE": "1"},
            )
            if payload is not None:
                assert proc.stdin is not None
                proc.stdin.write(payload)
                proc.stdin.close()
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
                "stdin_bytes": len(payload) if payload is not None else 0,
                "max_stdout_bytes": max_stdout_bytes,
                "stdin_sha256": hashlib.sha256(payload).hexdigest()
                if payload is not None
                else None,
                "stdout": stdout.name,
                "stderr": stderr.name,
            }
        )
        if stop:
            raise RuntimeError(stop)
        if stdout.stat().st_size > max_stdout_bytes:
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
    parser.add_argument(
        "--native-profile",
        choices=["complete", "arm-backend", "prior-materials"],
        default="complete",
    )
    parser.add_argument("--os-profile", choices=["rhel", "debian"], default="rhel")
    args = parser.parse_args()
    collect_native = collect_native_for_profile(
        args.native_profile, platform.system(), platform.machine()
    )
    collector = Collector(args.output_dir, os.environ.get("COMPOSE_PROJECT_NAME", ""))
    result = {
        "contract": "ARC-UPGRADE@0.1.0",
        "acceptance": ["AC-19", "RELEASE-001"],
        "started_at": now(),
        "producer": "scripts/collect_release_ci.py",
        "release_acceptance": "pending_review_not_granted_by_collection",
        "project": collector.project,
        "historical_or_user_artifact_cleanup": False,
        "runner_system": platform.system(),
        "runner_machine": platform.machine(),
        "native_materials_profile": args.native_profile,
        "os_profile": args.os_profile,
    }
    try:
        targets = collector.images()
        result["images"] = targets
        code, raw = collector.run(
            "langflow-os-release",
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
                "128m",
                "--pids-limit",
                "32",
                "--entrypoint",
                "python",
                targets["langflow"],
                "-c",
                "from pathlib import Path; print(Path('/etc/os-release').read_text())",
            ],
            timeout=60,
            max_stdout_bytes=65536,
        )
        if code:
            raise RuntimeError("OS identity read failed")
        result["os_identity"] = verify_os_release(raw, args.os_profile) | {
            "image": targets["langflow"]
        }
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
        probe = Path("scripts/verify_dependency_compatibility.py").read_bytes()
        code, _ = collector.run(
            "dependency-compatibility",
            [
                "docker",
                "run",
                "--rm",
                "--network",
                "none",
                "--read-only",
                "--tmpfs",
                "/tmp:rw,noexec,nosuid,size=32m",
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
                "-i",
                "--entrypoint",
                "python",
                targets["langflow"],
                "-B",
                "-",
                *(["--candidate-1-13-1"] if args.os_profile == "debian" else []),
            ],
            timeout=90,
            payload=probe,
        )
        if code:
            raise RuntimeError("Offline dependency compatibility contract failed")
        if args.os_profile == "rhel":
            code, raw = collector.run(
                "system-materials",
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
                    "128m",
                    "--pids-limit",
                    "32",
                    "--env",
                    "PYTHONDONTWRITEBYTECODE=1",
                    "-i",
                    "--entrypoint",
                    "python",
                    targets["langflow"],
                    "-B",
                    "-",
                ],
                timeout=60,
                payload=SYSTEM_PRODUCER,
                max_stdout_bytes=6 * 1024 * 1024,
            )
            if code:
                raise RuntimeError("System maintenance evidence export failed")
            result["system_materials"] = extract_system_records(raw, collector.root / "system")
        else:
            result["system_materials"] = {
                "state": "not_applicable",
                "reason": (
                    "RHEL transaction export does not apply to Debian; "
                    "primary image inventory remains required."
                ),
            }
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
        if args.os_profile == "rhel":
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
        else:
            audits["redhat_supplement"] = {
                "state": "not_applicable",
                "reason": "Verified Debian 12 image",
            }
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
        if collect_native:
            continuation = Path("compliance/native-baseline.json")
            native_command = [
                sys.executable,
                "scripts/verify_native_materials.py",
                "--image",
                "api=" + targets["api"],
                "--image",
                "langflow=" + targets["langflow"],
                "--output-dir",
                str(collector.root / "native"),
            ]
            if continuation.is_file():
                native_command += ["--followup", "--baseline-manifest", str(continuation)]
                result["native_scope"] = "remaining_budget_from_fixed_prior_batch"
            code, _ = collector.run(
                "native-materials",
                native_command,
                timeout=240,
            )
            if code:
                raise RuntimeError("Native material collector failed")
        elif args.native_profile == "prior-materials":
            result["native_materials"] = {
                "state": "not_collected_this_image",
                "prior_evidence": (
                    "docs/evidence/runtime-maintenance/ci/native-close/selection.json"
                ),
                "prior_ci_run": 41760412382,
                "prior_langflow_image": (
                    "sha256:fd6d66658d49008b53095d2669de17f88360038cbfc8238aa509ffd2e1aaa02c"
                ),
                "limitation": (
                    "Prior sealed native materials concern their original images; "
                    "no current image native body was read or established by this profile."
                ),
                "legal_approval": False,
                "distribution_approval": False,
            }
        else:
            result["native_materials"] = {
                "state": "not_collected_on_arm_backend",
                "reason": "This round's shared targeted-native input budget is reserved for AMD64.",
                "distribution_approval": False,
            }
        result.update(
            collection_state="collected",
            audits=audits,
            note=(
                "Exit 1 means findings; 2 means unknown/incomplete. "
                "RHEL RPM coverage is supplemented separately when applicable. No result accepts "
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
                    "scripts/verify_dependency_compatibility.py",
                    "scripts/apply_system_updates.py",
                    "scripts/verify_native_materials.py",
                    "compliance/native-baseline.json",
                    "docs/evidence/runtime-maintenance/ci/native-close/selection.json",
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
