"""Read-only preflight for the new Debian/aarch64 guest; never probes host endpoints."""

import hashlib
import json
import os
import platform
import subprocess
import sys
from pathlib import Path

MAX_OUTPUT = 128 * 1024


def command(args, accepted=(0,)):
    result = subprocess.run(
        args,
        capture_output=True,
        timeout=8,
        env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LC_ALL": "C"},
    )
    if len(result.stdout) + len(result.stderr) > MAX_OUTPUT:
        raise RuntimeError("preflight command output limit")
    if result.returncode not in accepted:
        raise RuntimeError("preflight command failed: " + args[0])
    return result.stdout.decode().strip(), result.returncode


def small(path, maximum=4096):
    value = Path(path)
    if value.is_symlink():
        if str(value) != "/etc/os-release" or value.resolve() != Path("/usr/lib/os-release"):
            raise RuntimeError("unexpected guest metadata symlink")
        value = value.resolve()
    if not value.is_file() or value.stat().st_size > maximum:
        raise RuntimeError("invalid bounded guest metadata file")
    with value.open("rb") as stream:
        raw = stream.read(maximum + 1)
    if len(raw) > maximum:
        raise RuntimeError("guest metadata bound")
    return raw.decode().strip()


def inspect_guest():
    if platform.system() != "Linux" or platform.machine() != "aarch64":
        raise RuntimeError("requires the new Linux aarch64 guest, never the macOS host")
    release = dict(
        line.split("=", 1) for line in small("/etc/os-release").splitlines() if "=" in line
    )
    if (
        release.get("ID", "").strip('"') != "debian"
        or release.get("VERSION_ID", "").strip('"') != "12"
    ):
        raise RuntimeError("requires the selected Debian 12 guest")
    mounts = json.loads(
        command(
            ["/usr/bin/findmnt", "--json", "--list", "--output", "TARGET,SOURCE,FSTYPE,OPTIONS"]
        )[0]
    )["filesystems"]
    forbidden_types = {"9p", "virtiofs", "fuse.sshfs", "sshfs"}
    forbidden_paths = (
        "/Users/",
        "/Applications/",
        "Docker.raw",
        "/private/tmp/arc-linux-vm",
        "com.docker.docker",
        "/hosthome",
        "/hostUsers",
    )
    for mount in mounts:
        description = str(mount.get("target", "")) + " " + str(mount.get("source", ""))
        if mount.get("fstype") in forbidden_types or any(
            text in description for text in forbidden_paths
        ):
            raise RuntimeError("host/shared/history mount detected; refusing guest work")
    if not any(
        mount.get("target") == "/sys/fs/cgroup" and mount.get("fstype") == "cgroup2"
        for mount in mounts
    ):
        raise RuntimeError("requires unified cgroup v2")
    controllers = small("/sys/fs/cgroup/cgroup.controllers").split()
    if not {"cpu", "memory", "pids"}.issubset(controllers):
        raise RuntimeError("required cgroup controllers unavailable")
    dependencies = {}
    for package, minimum in (("libc6", "2.34"), ("libseccomp2", "2.5.0"), ("libsystemd0", None)):
        value, _ = command(
            ["/usr/bin/dpkg-query", "-W", "-f=${Status}|${Version}|${Architecture}", package]
        )
        status, version, architecture = value.split("|")
        if status != "install ok installed" or architecture != "arm64":
            raise RuntimeError("required native dependency is not installed")
        if minimum:
            command(["/usr/bin/dpkg", "--compare-versions", version, "ge", minimum])
        dependencies[package] = {
            "version": version,
            "architecture": architecture,
            "minimum": minimum,
        }
    iptables, status = command(
        ["/usr/bin/dpkg-query", "-W", "-f=${Status}|${Version}", "iptables"], (0, 1)
    )
    # Engine networking is disabled; absent iptables is reported, never installed.
    dependencies["iptables"] = {"query_exit_code": status, "installed_metadata": iptables}
    filesystem = os.statvfs("/var/lib")
    free = filesystem.f_bavail * filesystem.f_frsize
    if free < 768 * 1024 * 1024:
        raise RuntimeError("guest free-space floor below 768 MiB")
    return {
        "result": "passed",
        "system": platform.system(),
        "architecture": platform.machine(),
        "kernel": platform.release(),
        "hostname": platform.node(),
        "uid": os.getuid(),
        "boot_id": small("/proc/sys/kernel/random/boot_id"),
        "machine_id_sha256": hashlib.sha256(small("/etc/machine-id").encode()).hexdigest(),
        "cgroup_controllers": controllers,
        "mounts": mounts,
        "dependencies": dependencies,
        "guest_available_bytes": free,
        "desktop_boundary": "not probed; no host socket/network connection is attempted; "
        "absence of shared mounts is checked, network unreachability is not claimed",
        "not_checked": [
            "host VM allocated-byte ceiling, monitored by host",
            "binary signatures/hashes",
            "full dependency closure or executable loading",
            "Docker Desktop state",
        ],
    }


if __name__ == "__main__":
    try:
        print(json.dumps(inspect_guest(), separators=(",", ":")))
    except Exception as error:
        print(
            json.dumps(
                {"result": "failed", "error_type": type(error).__name__, "detail": str(error)}
            )
        )
        sys.exit(1)
