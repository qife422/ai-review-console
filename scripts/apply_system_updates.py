"""Update only the pinned Langflow image's public UBI10 repositories during build.

This runs inside the new image, never against host caches or historical images.
The captured transaction is evidence of what happened, not release acceptance.
"""

from __future__ import annotations

import argparse
import configparser
import hashlib
import json
import os
import re
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

LIMIT = 4 * 1024 * 1024
KEY = Path("/etc/pki/rpm-gpg/RPM-GPG-KEY-redhat-release")
RPM_FORMAT = "%{NAME}\t%{EPOCHNUM}:%{VERSION}-%{RELEASE}\t%{ARCH}\t%{RSAHEADER:pgpsig}\n"


def now() -> str:
    return datetime.now(UTC).isoformat()


def check_os(text: str) -> dict[str, str]:
    fields = {}
    for line in text.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            fields[key] = value.strip('"')
    if fields.get("ID") != "rhel" or fields.get("VERSION_ID", "").split(".")[0] != "10":
        raise ValueError("Only the existing RHEL10 Langflow base is supported")
    return fields


def repositories(paths: list[Path]) -> list[dict[str, str]]:
    selected = []
    seen = set()
    for path in paths:
        if path.is_symlink() or path.stat().st_size > 128 * 1024:
            raise ValueError("Unexpected repository configuration")
        raw = path.read_bytes()
        config = configparser.ConfigParser(interpolation=None)
        config.read_string(raw.decode())
        for name in config.sections():
            if not config.getboolean(name, "enabled", fallback=True):
                continue
            match = re.fullmatch(
                r"ubi-10-(?:for-(?:\$basearch|x86_64|aarch64)-)?(baseos|appstream)-rpms", name
            )
            if not match:
                continue  # All other repositories are explicitly disabled in every command.
            if name in seen:
                raise ValueError("Duplicate enabled UBI repository")
            seen.add(name)
            url = config.get(name, "baseurl", fallback="").strip().rstrip("/")
            parsed = urlsplit(url)
            expected = (
                r"/content/public/ubi/dist/ubi10/(?:10|\$releasever)/"
                r"(?:\$basearch|x86_64|aarch64)/" + match[1] + r"/os"
            )
            if (
                parsed.scheme != "https"
                or parsed.netloc != "cdn-ubi.redhat.com"
                or parsed.query
                or parsed.fragment
                or not re.fullmatch(expected, parsed.path)
                or config.get(name, "mirrorlist", fallback="").strip()
                or config.get(name, "metalink", fallback="").strip()
                or not config.getboolean(name, "gpgcheck", fallback=False)
                or not config.getboolean(name, "sslverify", fallback=True)
                or config.get(name, "gpgkey", fallback="").strip() != "file://" + str(KEY)
            ):
                raise ValueError(
                    "UBI repository origin, TLS or package signature policy mismatch: " + name
                )
            selected.append(
                {
                    "id": name,
                    "baseurl": url,
                    "gpgkey": "file://" + str(KEY),
                    "gpgcheck": "1",
                    "sslverify": "1",
                    "config_path": str(path),
                    "config_sha256": hashlib.sha256(raw).hexdigest(),
                    "component": match[1],
                }
            )
    if {r["component"] for r in selected} != {"baseos", "appstream"}:
        raise ValueError("Both default public UBI10 BaseOS and AppStream are required")
    return sorted(selected, key=lambda item: item["id"])


def manager_args(repos: list[dict[str, str]]) -> list[str]:
    return [
        "microdnf",
        "--disablerepo=*",
        *["--enablerepo=" + r["id"] for r in repos],
        "--setopt=gpgcheck=1",
        "--setopt=sslverify=1",
        "--setopt=install_weak_deps=0",
        "--setopt=keepcache=0",
    ]


class Recorder:
    def __init__(self, root: Path):
        if root.is_symlink() or root.exists():
            raise ValueError("Never replace previous system-maintenance records")
        root.mkdir(parents=True, mode=0o755)
        self.root = root
        self.commands: list[dict] = []

    def run(self, label: str, argv: list[str], timeout: int = 600) -> str:
        outpath = self.root / (label + ".stdout")
        errpath = self.root / (label + ".stderr")
        started = now()
        stop = None
        with outpath.open("xb") as out, errpath.open("xb") as err:
            proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=out, stderr=err)
            begin = time.monotonic()
            while proc.poll() is None:
                if time.monotonic() - begin > timeout:
                    stop = "timeout"
                if sum(p.stat().st_size for p in self.root.iterdir() if p.is_file()) > LIMIT:
                    stop = "output_capacity"
                if stop:
                    proc.terminate()
                    try:
                        proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                    break
                time.sleep(0.2)
            code = proc.wait()
        if sum(p.stat().st_size for p in self.root.iterdir() if p.is_file()) > LIMIT:
            stop = "output_capacity"
        self.commands.append(
            {
                "argv": argv,
                "started_at": started,
                "ended_at": now(),
                "exit_code": code,
                "stop_reason": stop,
                "stdout": outpath.name,
                "stderr": errpath.name,
            }
        )
        if code or stop:
            raise RuntimeError(f"{label} failed: exit={code}, stop={stop}")
        return outpath.read_text()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise ValueError("System updates run only as root inside the new build image")
    record = Recorder(args.output_dir)
    result = {
        "started_at": now(),
        "scope": "new_image_public_UBI10_only",
        "release_acceptance": "pending",
        "producer": "scripts/apply_system_updates.py",
    }
    try:
        result["os_before"] = check_os(Path("/etc/os-release").read_text())
        repos = repositories(sorted(Path("/etc/yum.repos.d").glob("*.repo")))
        result["repositories"] = repos
        result["redhat_release_key_sha256"] = hashlib.sha256(KEY.read_bytes()).hexdigest()
        record.run("rpm-before", ["rpm", "-qa", "--qf", RPM_FORMAT])
        record.run(
            "trusted-keys",
            ["rpm", "-q", "gpg-pubkey", "--qf", "%{NAME}-%{VERSION}-%{RELEASE}\n"],
        )
        manager = manager_args(repos)
        record.run("repositories", [*manager, "repolist"])
        record.run("metadata-refresh", [*manager, "--refresh", "makecache"])
        record.run("update", [*manager, "--refresh", "update", "-y"])
        record.run("rpm-after", ["rpm", "-qa", "--qf", RPM_FORMAT])
        result["os_after"] = check_os(Path("/etc/os-release").read_text())
        # Only this newly built image's package-manager cache lifecycle is affected.
        record.run("image-cache-clean", [*manager, "clean", "all"])
        result["status"] = "completed"
    except Exception as exc:
        result["status"] = "failed"
        result["error"] = type(exc).__name__ + ": " + str(exc)
        raise
    finally:
        result["ended_at"] = now()
        result["commands"] = record.commands
        result["files"] = [
            {
                "path": p.name,
                "bytes": p.stat().st_size,
                "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
            }
            for p in sorted(record.root.iterdir())
            if p.is_file()
        ]
        (record.root / "manifest.json").write_text(json.dumps(result, indent=2) + "\n")
        if result["status"] == "failed":
            print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()
