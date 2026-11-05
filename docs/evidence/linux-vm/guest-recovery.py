"""New-guest-only, retained synthetic Docker restart-policy experiment.

No package install, pull, host socket, host mount, manual container removal,
volume deletion, VM lifecycle action or fallback is implemented.
"""

import argparse
import hashlib
import io
import json
import os
import re
import signal
import stat
import subprocess
import sys
import tarfile
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from importlib.util import module_from_spec, spec_from_file_location

spec = spec_from_file_location(
    "arc_guest_prerequisites", Path(__file__).with_name("guest-prerequisites.py")
)
prerequisites = module_from_spec(spec)
spec.loader.exec_module(prerequisites)

ENGINE = Path("/opt/arc-engine/usr/bin")
INPUTS = Path("/opt/arc-inputs")
ALPINE = INPUTS / "alpine-minirootfs-3.22.1-aarch64.tar.gz"
ALPINE_SHA = "188416d41f9f0c9a6e9427b75149e43ccf3a89587b2d27c9ad506e7ffca78d1c"
DEBS = {
    "docker-ce_28.3.2-1~debian.12~bookworm_arm64.deb": (
        16992264,
        "b16fdb4305323e1da85e50c1784049f57d7360c339f1483d01013c8df630aeec",
    ),
    "docker-ce-cli_28.3.2-1~debian.12~bookworm_arm64.deb": (
        14932020,
        "29d54c7e2cf57fa2f0a8619346cb1ee2e74e1af628d2dd608bd561b5d80c51c7",
    ),
    "containerd.io_1.7.27-1_arm64.deb": (
        22766596,
        "18f49ec1dd1ba34ae76c52fe8c52edaed24f2b72fd3a0e5528546c9705f08ef5",
    ),
}
ENV = {"PATH": str(ENGINE) + ":/usr/sbin:/usr/bin:/sbin:/bin", "LC_ALL": "C", "HOME": "/root"}
MAX_LOG = 1024 * 1024
MAX_EVIDENCE = 2 * 1024 * 1024
POLICIES = (
    ("always-running", "always", False),
    ("unless-running", "unless-stopped", False),
    ("onfailure-running", "on-failure", False),
    ("always-manual", "always", True),
    ("unless-manual", "unless-stopped", True),
)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def bounded_file(path, expected_size=None, expected_sha=None):
    path = Path(path)
    if any(item.is_symlink() for item in (path, *path.parents)) or not path.is_file():
        raise RuntimeError("nonregular/symlink input or executable")
    if expected_size is not None and path.stat().st_size != expected_size:
        raise RuntimeError("fixed input size mismatch")
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(block)
    if expected_sha and hasher.hexdigest() != expected_sha:
        raise RuntimeError("fixed input digest mismatch")
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": hasher.hexdigest()}


def owned_directory_chain(path, leaf_mode=None):
    path = Path(path)
    for item in reversed((path, *path.parents)):
        if not item.exists() and not item.is_symlink():
            continue
        info = item.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or stat.S_IMODE(info.st_mode) & 0o022:
            raise RuntimeError("directory ancestor is linked, non-root-owned or writable by others")
    if leaf_mode is not None and stat.S_IMODE(path.lstat().st_mode) != leaf_mode:
        raise RuntimeError("owned directory mode mismatch")


def bind_deb_binaries():
    """Stream verified DEBs through dpkg-deb; hash exact members without extraction."""
    selected = {
        "docker-ce_28.3.2-1~debian.12~bookworm_arm64.deb": {"dockerd"},
        "docker-ce-cli_28.3.2-1~debian.12~bookworm_arm64.deb": {"docker"},
        "containerd.io_1.7.27-1_arm64.deb": {
            "containerd",
            "ctr",
            "runc",
            "containerd-shim-runc-v2",
        },
    }
    result = {}
    for filename, names in selected.items():
        package = INPUTS / filename
        bounded_file(package, *DEBS[filename])
        process = subprocess.Popen(
            ["/usr/bin/dpkg-deb", "--fsys-tarfile", str(package)],
            env=ENV,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        timer = threading.Timer(60, process.kill)
        timer.start()
        found = set()
        try:
            expanded = 0
            with tarfile.open(fileobj=process.stdout, mode="r|") as archive:
                for member in archive:
                    expanded += member.size
                    if expanded > 512 * 1024 * 1024:
                        raise RuntimeError("verified DEB expanded-size bound")
                    normalized = member.name.removeprefix("./")
                    for name in names:
                        if normalized != "usr/bin/" + name:
                            continue
                        if name in found or not member.isfile() or member.size > 128 * 1024 * 1024:
                            raise RuntimeError("ambiguous/nonregular owned binary DEB member")
                        hasher = hashlib.sha256()
                        source = archive.extractfile(member)
                        count = 0
                        for block in iter(lambda source=source: source.read(1024 * 1024), b""):
                            count += len(block)
                            hasher.update(block)
                        if count != member.size:
                            raise RuntimeError("DEB binary member truncated")
                        path = ENGINE / name
                        owned_directory_chain(path.parent)
                        info = path.lstat()
                        if (
                            not stat.S_ISREG(info.st_mode)
                            or info.st_uid != 0
                            or stat.S_IMODE(info.st_mode) & 0o022
                            or not info.st_mode & 0o111
                        ):
                            raise RuntimeError("owned binary mode/ownership mismatch")
                        binary = bounded_file(path, member.size, hasher.hexdigest())
                        with path.open("rb") as executable:
                            header = executable.read(64)
                        if (
                            len(header) < 20
                            or header[:4] != b"\x7fELF"
                            or header[4:6] != b"\x02\x01"
                            or int.from_bytes(header[18:20], "little") != 183
                        ):
                            raise RuntimeError("owned binary is not ELF64 little-endian aarch64")
                        result[name] = {
                            **binary,
                            "source_deb": filename,
                            "member": normalized,
                            "member_sha256": hasher.hexdigest(),
                            "elf_machine": 183,
                        }
                        found.add(name)
            process.stdout.close()
            if process.wait(timeout=8) != 0 or found != names:
                raise RuntimeError("DEB streaming failed or required binary member absent")
        finally:
            timer.cancel()
            if process.poll() is None:
                process.kill()
                process.wait(timeout=8)
            process.stdout.close()
    return result


class Experiment:
    def __init__(self, args, preflight):
        self.args = args
        self.preflight = preflight
        self.root = Path("/var/lib/arc-engine/probe") / args.run_id
        self.runroot = Path("/run/arc-engine") / args.run_id
        owned_directory_chain(self.root)
        owned_directory_chain(self.runroot)
        if self.root.exists() or self.runroot.exists():
            raise RuntimeError("experiment paths must be absent; never reuse existing state")
        for parent in (self.root.parent, self.runroot.parent):
            if parent.is_symlink():
                raise RuntimeError("unsafe experiment parent")
            parent.mkdir(mode=0o700, exist_ok=True)
            if parent.stat().st_uid != 0 or stat.S_IMODE(parent.stat().st_mode) != 0o700:
                raise RuntimeError("experiment parent ownership/mode mismatch")
        self.root.mkdir(mode=0o700)
        self.runroot.mkdir(mode=0o700)
        owned_directory_chain(self.root, 0o700)
        owned_directory_chain(self.runroot, 0o700)
        self.records = []
        self.groups = []
        self.owned_groups = []
        self.evidence_bytes = 0
        self.counter = 0
        self.processes = []
        self.log_monitors = []
        self.log_errors = []
        self.log_threads = []
        self.inputs = {}
        self.result = {
            "run_id": args.run_id,
            "result": "failed",
            "groups": self.groups,
            "guest_identity": {
                key: preflight[key] for key in ("hostname", "boot_id", "machine_id_sha256")
            },
            "not_tested": [
                "original Desktop or historical data",
                "VM reboot or original VM restoration",
                "containerd/daemon simultaneous crash",
                "production workloads",
            ],
            "retention": "all experiment directories, data-roots and evidence retained; no cleanup",
        }

    def capacity(self):
        value = os.statvfs(self.root)
        if value.f_bavail * value.f_frsize < 512 * 1024 * 1024:
            raise RuntimeError("guest free-space floor below 512 MiB; stop growth")
        total = 0
        for path in self.root.rglob("*"):
            if path.is_symlink():
                continue
            if path.is_file():
                total += path.stat().st_blocks * 512
            if total > 256 * 1024 * 1024:
                raise RuntimeError("experiment allocated-data ceiling exceeds 256 MiB")
        if self.log_errors:
            raise RuntimeError("owned daemon exceeded retained-log limit")
        for path in self.log_monitors:
            if path.exists() and path.stat().st_size > MAX_LOG:
                raise RuntimeError("daemon log exceeded 1 MiB; stop owned services")

    def save(self, name, value):
        data = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
        if len(data) > 256 * 1024 or self.evidence_bytes + len(data) > MAX_EVIDENCE:
            raise RuntimeError("retained JSON evidence exceeds bound")
        destination = self.root / name
        with destination.open("xb") as stream:
            stream.write(data)
        self.evidence_bytes += len(data)
        return {"path": str(destination), "bytes": len(data), "sha256": sha(data)}

    def command(self, argv, *, timeout=30, accepted=(0,), maximum=256 * 1024):
        self.capacity()
        result = subprocess.run(
            [str(value) for value in argv], env=ENV, capture_output=True, timeout=timeout
        )
        if len(result.stdout) + len(result.stderr) > maximum:
            raise RuntimeError("owned command output bound")
        self.records.append(
            {
                "argv": [str(value) for value in argv],
                "exit_code": result.returncode,
                "stdout_sha256": sha(result.stdout),
                "stderr_sha256": sha(result.stderr),
            }
        )
        if result.returncode not in accepted:
            raise RuntimeError("owned command failed; raw output is retained only by hash")
        return result

    def own_process(self, process, executable, token):
        if process.poll() is not None:
            return False
        executable_path = os.readlink(f"/proc/{process.pid}/exe")
        argv = Path(f"/proc/{process.pid}/cmdline").read_bytes().split(b"\x00")
        if executable_path != str(ENGINE / executable) or token.encode() not in argv:
            raise RuntimeError("PID executable/namespace binding mismatch; refusing signal")
        return True

    def spawn(self, argv, log, executable, token):
        self.capacity()
        stream = log.open("xb")
        process = subprocess.Popen(
            [str(value) for value in argv],
            env=ENV,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        self.processes.append((process, executable, token))
        self.log_monitors.append(log)

        def collect():
            count = 0
            try:
                with stream:
                    while True:
                        block = process.stdout.read(4096)
                        if not block:
                            break
                        remaining = MAX_LOG - count
                        stream.write(block[:remaining])
                        count += len(block)
                        if count > MAX_LOG:
                            self.log_errors.append(process.pid)
                            if self.own_process(process, executable, token):
                                process.send_signal(signal.SIGTERM)
                            break
            except Exception:
                self.log_errors.append(process.pid)
            finally:
                process.stdout.close()

        thread = threading.Thread(target=collect, daemon=True)
        thread.start()
        self.log_threads.append(thread)
        if not self.own_process(process, executable, token):
            raise RuntimeError("owned daemon exited during startup")
        return process

    def wait_until(self, predicate, timeout=30):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self.capacity()
            try:
                if predicate():
                    return
            except (ConnectionError, FileNotFoundError):
                pass
            time.sleep(0.25)
        raise RuntimeError("owned service/expected state did not become ready")

    def docker(self, group, *args, **kwargs):
        socket = group["socket"]
        if not str(socket).startswith(str(self.runroot) + "/"):
            raise RuntimeError("non-owned Docker socket")
        if socket.exists() and (
            not stat.S_ISSOCK(socket.lstat().st_mode) or socket.lstat().st_uid != 0
        ):
            raise RuntimeError("Docker socket ownership/type mismatch")
        return self.command([ENGINE / "docker", "--host", "unix://" + str(socket), *args], **kwargs)

    def create_group(self, name):
        root, run = self.root / name, self.runroot / name
        owned_directory_chain(root)
        owned_directory_chain(run)
        root.mkdir(mode=0o700)
        run.mkdir(mode=0o700)
        owned_directory_chain(root, 0o700)
        owned_directory_chain(run, 0o700)
        group = {
            "name": name,
            "root": root,
            "run": run,
            "socket": run / "docker.sock",
            "ctnd_socket": run / "containerd.sock",
            "containers": [],
            "started": [],
        }
        self.owned_groups.append(group)
        self.groups.append({"name": name, "result": "pending", "containers": []})
        group["summary"] = self.groups[-1]
        config = root / "containerd.toml"
        with config.open("x") as stream:
            stream.write(
                "version = 2\nroot = "
                + json.dumps(str(root / "containerd"))
                + "\nstate = "
                + json.dumps(str(run / "containerd"))
                + '\ndisabled_plugins = ["io.containerd.grpc.v1.cri"]\n[grpc]\n  address = '
                + json.dumps(str(group["ctnd_socket"]))
                + "\n"
            )
        group["ctnd"] = self.spawn(
            [ENGINE / "containerd", "--config", config],
            root / "containerd.log",
            "containerd",
            str(config),
        )
        self.wait_until(
            lambda: (
                group["ctnd_socket"].exists()
                and self.command(
                    [ENGINE / "ctr", "--address", group["ctnd_socket"], "version"], accepted=(0, 1)
                ).returncode
                == 0
            )
        )
        return group

    def start_docker(self, group, restart, live_restore=False):
        self.counter += 1
        config = group["root"] / f"daemon-{self.counter}.json"
        with config.open("x") as stream:
            json.dump(
                {
                    "restart": restart,
                    "live-restore": live_restore,
                    "bridge": "none",
                    "iptables": False,
                    "ip6tables": False,
                    "ip-forward": False,
                    "ip-masq": False,
                    "userland-proxy": False,
                },
                stream,
            )
        argv = [
            ENGINE / "dockerd",
            "--config-file",
            config,
            "--host",
            "unix://" + str(group["socket"]),
            "--data-root",
            group["root"] / "docker",
            "--exec-root",
            group["run"] / "exec",
            "--pidfile",
            group["run"] / "dockerd.pid",
            "--containerd",
            group["ctnd_socket"],
            "--containerd-namespace",
            "moby",
            "--containerd-plugins-namespace",
            "plugins.moby",
            "--add-runtime",
            "arc-runc=" + str(ENGINE / "runc"),
            "--default-runtime",
            "arc-runc",
        ]
        process = self.spawn(
            argv, group["root"] / f"dockerd-{self.counter}.log", "dockerd", str(config)
        )
        group["dockerd"] = process
        group["dockerd_token"] = str(config)
        self.wait_until(
            lambda: (
                self.docker(group, "info", "--format", "{{json .}}", accepted=(0, 1)).returncode
                == 0
            )
        )
        information = json.loads(self.docker(group, "info", "--format", "{{json .}}").stdout)
        if information.get("ServerVersion") != "28.3.2" or information.get("DockerRootDir") != str(
            group["root"] / "docker"
        ):
            raise RuntimeError("new daemon version/data-root mismatch")
        if bool(information.get("LiveRestoreEnabled")) != live_restore:
            raise RuntimeError("daemon live-restore configuration mismatch")
        if self.docker(group, "ps", "-aq").stdout.strip() and not group["containers"]:
            raise RuntimeError("unexpected pre-existing containers in supposedly fresh data-root")
        group["started"].append(
            {
                "restart": restart,
                "live_restore": live_restore,
                "pid": process.pid,
                "config_sha256": bounded_file(config)["sha256"],
            }
        )

    def stop_daemon(self, group, *, kill=False):
        process = group["dockerd"]
        if not self.own_process(process, "dockerd", group["dockerd_token"]):
            raise RuntimeError("owned daemon already exited unexpectedly")
        process.send_signal(signal.SIGKILL if kill else signal.SIGTERM)
        process.wait(timeout=30)
        if not kill and process.returncode != 0:
            raise RuntimeError("owned daemon did not shut down cleanly")

    def snapshot(self, group, phase):
        expected = set(group["containers"])
        listed = set(self.docker(group, "ps", "-aq", "--no-trunc").stdout.decode().split())
        if listed != expected:
            raise RuntimeError("unexpected missing/additional containers in owned daemon")
        result = {}
        for identity in group["containers"]:
            item = json.loads(self.docker(group, "inspect", identity).stdout)[0]
            if (
                item["Id"] != identity
                or item["Config"]["Labels"].get("arc.experiment") != self.args.run_id
                or item["Config"]["Labels"].get("arc.group") != group["name"]
                or item["HostConfig"]["NetworkMode"] != "none"
                or item.get("Mounts")
            ):
                raise RuntimeError("container labels/identity/network/mount mismatch")
            result[identity] = item
        self.save(f"{group['name']}-{phase}-inspect.json", result)
        return result

    def marker(self, group, identity, expected):
        archive = self.docker(group, "cp", identity + ":/arc-marker", "-", maximum=64 * 1024).stdout
        with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as tar:
            members = tar.getmembers()
            if len(members) != 1 or not members[0].isfile() or members[0].size > 1024:
                raise RuntimeError("unexpected marker archive")
            content = tar.extractfile(members[0]).read(1025)
        if content.decode() != expected:
            raise RuntimeError("synthetic marker changed")
        return {"bytes": len(content), "sha256": sha(content)}

    def import_probe(self, group):
        name = "arc-probe:" + group["name"]
        identity = self.docker(group, "import", ALPINE, name).stdout.decode().strip()
        image = json.loads(self.docker(group, "image", "inspect", identity).stdout)[0]
        if image["Architecture"] != "arm64" or image["Os"] != "linux":
            raise RuntimeError("imported probe architecture mismatch")
        return name

    def create_probe(self, group, image, case, policy="no", autoremove=False):
        marker = self.args.run_id + ":" + group["name"] + ":" + case
        self.save(
            group["name"] + "-" + case + "-expected-marker.json",
            {"text": marker, "sha256": sha(marker.encode())},
        )
        args = [
            "run",
            "--pull=never",
            "-d",
            "--network",
            "none",
            "--memory",
            "32m",
            "--pids-limit",
            "16",
            "--cpus",
            "0.1",
            "--label",
            "arc.experiment=" + self.args.run_id,
            "--label",
            "arc.group=" + group["name"],
            "--label",
            "arc.case=" + case,
        ]
        if autoremove:
            args += ["--rm"]
        else:
            args += ["--restart", policy]
        args += [
            image,
            "/bin/sh",
            "-c",
            "printf '%s' \"$1\" > /arc-marker; exec sleep 86400",
            "arc",
            marker,
        ]
        identity = self.docker(group, *args).stdout.decode().strip()
        if not re.fullmatch(r"[a-f0-9]{64}", identity):
            raise RuntimeError("unexpected synthetic container identity")
        group["containers"].append(identity)
        self.wait_until(
            lambda: (
                self.docker(
                    group, "exec", identity, "/bin/sh", "-c", "test -f /arc-marker", accepted=(0, 1)
                ).returncode
                == 0
            )
        )
        return identity, marker

    def pre_restore(self, group, probes, before, restart):
        rows, conditions = {}, {}
        for case, identity, _marker in probes:
            policy, manual = next((p, m) for c, p, m in POLICIES if c == case)
            path = group["root"] / "docker/containers" / identity / "config.v2.json"
            owned_directory_chain(path.parent)
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            try:
                info = os.fstat(fd)
                if (
                    not stat.S_ISREG(info.st_mode)
                    or info.st_uid != 0
                    or info.st_mode & 0o022
                    or info.st_size > 65536
                ):
                    raise RuntimeError("persisted container metadata ownership/size mismatch")
                raw = os.read(fd, 65537)
            finally:
                os.close(fd)
            if len(raw) != info.st_size:
                raise RuntimeError("persisted container metadata read changed")
            data = json.loads(raw)
            state, initial = data["State"], before[identity]
            if (
                data["ID"] != identity
                or state["Running"]
                or state["ExitCode"] != 137
                or data["HasBeenManuallyStopped"] is not manual
                or state["StartedAt"] != initial["State"]["StartedAt"]
                or data["RestartCount"] != initial["RestartCount"]
                or initial["HostConfig"]["RestartPolicy"]["Name"] != policy
            ):
                raise RuntimeError(
                    "fixed pre-restore policy/exit/manual/chronology precondition failed"
                )
            expected = restart and (
                policy == "always"
                or policy == "on-failure"
                or (policy == "unless-stopped" and not manual)
            )
            rows[case] = {
                "id": identity,
                "metadata_sha256": sha(raw),
                "State": state,
                "HasBeenManuallyStopped": data["HasBeenManuallyStopped"],
                "policy": policy,
                "RestartCount": data["RestartCount"],
                "expected_running": expected,
            }
            conditions[case] = [137, manual, policy, initial["State"]["Running"]]
        self.save(group["name"] + "/pre-restore.json", rows)
        if getattr(self, "policy_preconditions", conditions) != conditions:
            raise RuntimeError("two groups do not have matching fixed policy preconditions")
        self.policy_preconditions = conditions
        return {case for case, row in rows.items() if row["expected_running"]}

    def strategies(self, name, restart):
        group = self.create_group(name)
        self.start_docker(group, True)
        image = self.import_probe(group)
        probes = []
        for case, policy, manual in POLICIES:
            identity, marker = self.create_probe(group, image, case, policy)
            probes.append((case, identity, marker))
            if manual:
                self.docker(group, "stop", "--time", "2", identity)
        before = self.snapshot(group, "before")
        for case, identity, marker in probes:
            if before[identity]["State"]["Running"] != (not case.endswith("manual")):
                raise RuntimeError("initial policy/manual-stop state mismatch")
            self.marker(group, identity, marker)
        self.stop_daemon(group)
        expected_running = self.pre_restore(group, probes, before, restart)
        self.start_docker(group, restart)
        self.snapshot(group, "after-start")

        def settled():
            states = self.snapshot_state(group)
            return all(
                states[identity] == (case in expected_running) for case, identity, marker in probes
            )

        try:
            self.wait_until(settled, timeout=30)
        finally:
            self.snapshot(group, "settled-observation")
        after = self.snapshot(group, "after")
        time.sleep(3)
        repeated = self.snapshot(group, "repeated")
        rows = []
        for case, identity, marker in probes:
            if after[identity]["State"]["Running"] != repeated[identity]["State"]["Running"]:
                raise RuntimeError("restart state was not stable")
            chronology = {
                phase: {
                    "StartedAt": item[identity]["State"]["StartedAt"],
                    "RestartCount": item[identity]["RestartCount"],
                }
                for phase, item in (("before", before), ("after", after), ("repeated", repeated))
            }
            if not restart and (
                chronology["before"] != chronology["after"]
                or chronology["after"] != chronology["repeated"]
            ):
                raise RuntimeError(
                    "restart=false container briefly started or restart counter changed"
                )
            if restart:
                for observed in (chronology["after"], chronology["repeated"]):
                    old_time, new_time = chronology["before"]["StartedAt"], observed["StartedAt"]
                    if (case in expected_running and not new_time > old_time) or (
                        case not in expected_running and new_time != old_time
                    ):
                        raise RuntimeError(
                            "positive-control StartedAt differs from preregistered expectation"
                        )
            rows.append(
                {
                    "chronology": chronology,
                    "case": case,
                    "id": identity,
                    "running": repeated[identity]["State"]["Running"],
                    "marker": self.marker(group, identity, marker),
                    "policy": repeated[identity]["HostConfig"]["RestartPolicy"],
                }
            )
        group["summary"].update(
            result="passed",
            restart=restart,
            cases=rows,
            daemon_starts=group["started"],
            expectation_source=[
                "https://github.com/moby/moby/blob/v28.3.2/container/container.go#L497-L501",
                "https://github.com/moby/moby/blob/v28.3.2/restartmanager/restartmanager.go#L75-L85",
            ],
        )
        self.finish_group(group)

    def snapshot_state(self, group):
        result = {}
        for identity in group["containers"]:
            item = json.loads(self.docker(group, "inspect", identity).stdout)[0]
            if item["Config"]["Labels"].get("arc.experiment") != self.args.run_id:
                raise RuntimeError("unexpected container ownership")
            result[identity] = item["State"]["Running"]
        return result

    def live_tasks(self):
        group = self.create_group("live-restore")
        self.start_docker(group, True, True)
        image = self.import_probe(group)
        probes = [
            self.create_probe(group, image, "retained"),
            self.create_probe(group, image, "autoremove", autoremove=True),
        ]
        before = self.snapshot(group, "before")
        for identity, marker in probes:
            self.marker(group, identity, marker)
        self.stop_daemon(group)
        tasks = self.command(
            [
                ENGINE / "ctr",
                "--address",
                group["ctnd_socket"],
                "--namespace",
                "moby",
                "tasks",
                "list",
            ]
        ).stdout.decode()
        self.save(
            "live-restore-daemon-down-tasks.json", {"output": tasks, "sha256": sha(tasks.encode())}
        )
        for identity, _marker in probes:
            pid = before[identity]["State"]["Pid"]
            if identity not in tasks or not Path(f"/proc/{pid}").exists():
                raise RuntimeError("live-restore did not leave the existing task running")
        self.start_docker(group, False, True)
        after = self.snapshot(group, "after-reconnect")
        rows = []
        for identity, marker in probes:
            if (
                not after[identity]["State"]["Running"]
                or after[identity]["State"]["Pid"] != before[identity]["State"]["Pid"]
                or after[identity]["State"]["StartedAt"] != before[identity]["State"]["StartedAt"]
                or after[identity]["RestartCount"] != before[identity]["RestartCount"]
            ):
                raise RuntimeError("live task was restarted/lost instead of reattached")
            rows.append(
                {"id": identity, "same_pid": True, "marker": self.marker(group, identity, marker)}
            )
        autoremove = probes[1][0]
        if not after[autoremove]["HostConfig"]["AutoRemove"]:
            raise RuntimeError("AutoRemove precondition missing")
        self.docker(group, "stop", "--time", "2", autoremove)
        self.wait_until(
            lambda: self.docker(group, "inspect", autoremove, accepted=(0, 1)).returncode == 1
        )
        missing = self.docker(group, "inspect", autoremove, accepted=(1,))
        self.save(
            "live-restore-autoremove-after.json",
            {
                "id": autoremove,
                "exit_code": missing.returncode,
                "stdout": missing.stdout.decode(),
                "stderr": missing.stderr.decode(),
                "expected_marker": probes[1][1],
                "removal": "daemon AutoRemove after stopping owned synthetic task",
            },
        )
        group["containers"].remove(autoremove)
        self.snapshot(group, "retained-after-autoremove")
        group["summary"].update(
            result="passed",
            restart_false_does_not_stop_live_tasks=True,
            cases=rows,
            autoremove_observed=True,
            daemon_starts=group["started"],
        )
        self.finish_group(group)

    def finish_group(self, group):
        for identity in group["containers"]:
            item = json.loads(self.docker(group, "inspect", identity).stdout)[0]
            if item["Config"]["Labels"].get("arc.experiment") != self.args.run_id:
                raise RuntimeError("refusing stop of foreign synthetic container")
            if item["State"]["Running"]:
                self.docker(group, "stop", "--time", "2", identity)
        if self.docker(group, "ps", "-q").stdout.strip():
            raise RuntimeError("owned data-root still has running containers")
        group["tasks_confirmed_stopped"] = True
        self.stop_daemon(group)
        process = group["ctnd"]
        if self.own_process(process, "containerd", str(group["root"] / "containerd.toml")):
            process.send_signal(signal.SIGTERM)
            process.wait(timeout=15)

    def shutdown_owned(self):
        outcomes = []
        daemon_failure = False
        for process, executable, token in reversed(self.processes):
            if executable != "dockerd":
                continue
            try:
                if self.own_process(process, executable, token):
                    process.send_signal(signal.SIGTERM)
                    process.wait(timeout=30)
                outcomes.append(
                    {"pid": process.pid, "executable": executable, "exit_code": process.returncode}
                )
            except Exception as error:
                daemon_failure = True
                outcomes.append(
                    {
                        "pid": process.pid,
                        "result": "failed",
                        "host_stop_new_vm_required": True,
                        "error_type": type(error).__name__,
                    }
                )
        if daemon_failure:
            return outcomes

        def ctr(group, arguments):
            process = group["ctnd"]
            token = str(group["root"] / "containerd.toml")
            if not self.own_process(process, "containerd", token):
                raise RuntimeError("owned containerd no longer available")
            address = group["ctnd_socket"]
            if (
                not str(address).startswith(str(self.runroot) + "/")
                or not stat.S_ISSOCK(address.lstat().st_mode)
                or address.lstat().st_uid != 0
            ):
                raise RuntimeError("owned containerd socket binding changed")
            value = subprocess.run(
                [
                    str(ENGINE / "ctr"),
                    "--address",
                    str(address),
                    "--namespace",
                    "moby",
                    "tasks",
                    *arguments,
                ],
                env=ENV,
                capture_output=True,
                timeout=8,
            )
            if len(value.stdout) + len(value.stderr) > 65536:
                raise RuntimeError("shutdown command output bound")
            return value

        def active_tasks(group):
            value = ctr(group, ["list"])
            if value.returncode:
                raise RuntimeError("owned task listing failed")
            tasks = {}
            for line in value.stdout.decode().splitlines()[1:]:
                parts = line.split()
                if len(parts) != 3 or parts[0] not in group["containers"] or not parts[1].isdigit():
                    raise RuntimeError("unrecognized task identity in owned namespace")
                if parts[2] not in {"RUNNING", "PAUSED", "STOPPED"}:
                    raise RuntimeError("unknown task state during shutdown")
                if parts[2] != "STOPPED":
                    tasks[parts[0]] = int(parts[1])
            return tasks

        for group in reversed(self.owned_groups):
            try:
                process = group.get("ctnd")
                if process is None:
                    continue
                if process.poll() is not None:
                    if group.get("containers") and not group.get("tasks_confirmed_stopped"):
                        raise RuntimeError(
                            "containerd exited before tracked tasks were confirmed stopped"
                        )
                    continue
                initial = active_tasks(group)
                for identity in sorted(initial):
                    value = ctr(group, ["kill", "--signal", "SIGTERM", identity])
                    if value.returncode and identity in active_tasks(group):
                        raise RuntimeError("tracked task SIGTERM failed")
                deadline = time.monotonic() + 5
                remaining = active_tasks(group)
                while remaining and time.monotonic() < deadline:
                    if any(initial.get(identity) != pid for identity, pid in remaining.items()):
                        raise RuntimeError("task PID changed; refusing escalation")
                    time.sleep(0.2)
                    remaining = active_tasks(group)
                for identity, pid in sorted(remaining.items()):
                    if initial.get(identity) != pid:
                        raise RuntimeError("task PID changed; refusing SIGKILL")
                    value = ctr(group, ["kill", "--signal", "SIGKILL", identity])
                    if value.returncode and identity in active_tasks(group):
                        raise RuntimeError("tracked task SIGKILL failed")
                deadline = time.monotonic() + 5
                remaining = active_tasks(group)
                while remaining and time.monotonic() < deadline:
                    if any(initial.get(identity) != pid for identity, pid in remaining.items()):
                        raise RuntimeError("task PID changed after escalation")
                    time.sleep(0.2)
                    remaining = active_tasks(group)
                if remaining:
                    raise RuntimeError("tracked tasks still active; host must stop the new VM")
                group["tasks_confirmed_stopped"] = True
                token = str(group["root"] / "containerd.toml")
                if self.own_process(process, "containerd", token):
                    process.send_signal(signal.SIGTERM)
                    process.wait(timeout=15)
                outcomes.append(
                    {
                        "group": group["name"],
                        "result": "passed",
                        "tracked_tasks_confirmed_stopped": sorted(initial),
                        "containerd_exit_code": process.returncode,
                    }
                )
            except Exception as error:
                outcomes.append(
                    {
                        "group": group["name"],
                        "result": "failed",
                        "host_stop_new_vm_required": True,
                        "error_type": type(error).__name__,
                    }
                )
        for thread in self.log_threads:
            thread.join(timeout=2)
        return outcomes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--expected-boot-id", required=True)
    parser.add_argument("--expected-machine-id-sha256", required=True)
    args = parser.parse_args()
    if os.geteuid() != 0 or not re.fullmatch(r"arc-probe-[a-z0-9]{8,32}", args.run_id):
        raise RuntimeError("requires root in the bound new guest and a fresh experiment namespace")
    preflight = prerequisites.inspect_guest()
    if (
        preflight["boot_id"] != args.expected_boot_id
        or preflight["machine_id_sha256"] != args.expected_machine_id_sha256
    ):
        raise RuntimeError("guest identity does not match the separately reviewed preflight")
    if any(
        name in os.environ
        for name in ("DOCKER_HOST", "DOCKER_CONTEXT", "CONTAINER_HOST", "CONTAINERD_ADDRESS")
    ):
        raise RuntimeError(
            "host/container context environment is forbidden; only explicit owned unix sockets"
        )
    inputs = {name: bounded_file(INPUTS / name, *expected) for name, expected in DEBS.items()}
    inputs[ALPINE.name] = bounded_file(ALPINE, 3976860, ALPINE_SHA)
    bound_binaries = bind_deb_binaries()
    for name in ("docker", "dockerd", "containerd", "ctr", "runc", "containerd-shim-runc-v2"):
        path = ENGINE / name
        bounded_file(path)
        if not os.access(path, os.X_OK):
            raise RuntimeError("required owned executable unavailable")
    experiment = Experiment(args, preflight)
    try:
        experiment.result["inputs"] = inputs
        experiment.result["bound_binaries"] = bound_binaries
        for executable, token in (
            ("docker", "28.3.2"),
            ("dockerd", "28.3.2"),
            ("containerd", "1.7.27"),
        ):
            version = experiment.command([ENGINE / executable, "--version"]).stdout.decode().strip()
            if token not in version:
                raise RuntimeError("owned executable version mismatch")
        experiment.strategies("restart-true", True)
        experiment.strategies("restart-false", False)
        experiment.live_tasks()
        experiment.result["result"] = "passed"
    except BaseException as error:
        experiment.result["error"] = {"type": type(error).__name__, "detail": str(error)}
        raise
    finally:
        shutdown = experiment.shutdown_owned()
        if any(item.get("result") == "failed" for item in shutdown):
            experiment.result["result"] = "failed"
        experiment.result["shutdown"] = shutdown
        experiment.result["commands"] = experiment.records
        record = experiment.save("result.json", experiment.result)
        print(
            json.dumps(
                {
                    "result": experiment.result["result"],
                    "evidence": record,
                    "not_a_desktop_start_guarantee": True,
                },
                separators=(",", ":"),
            ),
            flush=True,
        )
        if experiment.result["result"] != "passed" and sys.exc_info()[0] is None:
            raise RuntimeError("owned shutdown failed; stop only this new VM; see retained result")


if __name__ == "__main__":
    main()
