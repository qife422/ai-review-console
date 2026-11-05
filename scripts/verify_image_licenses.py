"""Collect bounded license evidence from exact local images; never approve distribution.

Example: python scripts/verify_image_licenses.py --image api=sha256:<64 hex>
--output-dir "$RUNNER_TEMP/image-licenses". Output must be absent or empty.
The whole invocation shares at most 100 license texts / 8 MiB of text input.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import io
import json
import re
import stat
import subprocess
import sys
import tarfile
import threading
from datetime import UTC, datetime
from pathlib import Path

MAX_FILE = 256 * 1024
MAX_FILES = 100
MAX_BYTES = 8 * 1024 * 1024
MAX_COMMAND_OUTPUT = 16 * 1024 * 1024
IMAGE_RE = re.compile(r"(api|langflow|web)=(sha256:[a-f0-9]{64})\Z")
SELECTED_PACKAGES = frozenset(
    [
        "certifi",
        "pillow",
        "pypdf",
        "python-docx",
        "reportlab",
        "aiohttp",
        "authlib",
        "black",
        "brotli",
        "dnspython",
        "fastmcp",
        "fastmcp-slim",
        "fsspec",
        "gitpython",
        "joserfc",
        "langchain-nvidia-ai-endpoints",
        "langgraph",
        "langgraph-sdk",
        "litellm",
        "mako",
        "mcp",
        "mem0ai",
        "multidict",
        "nltk",
        "pyasn1",
        "pyjwt",
        "pymongo",
        "transformers",
        "urllib3",
        "yarl",
        "psycopg",
        "psycopg-binary",
        "psycopg2-binary",
        "frozendict",
        "grandalf",
        "crc32c",
        "google-crc32c",
        "llm-sandbox",
        "lfx",
        "langflow",
        "peewee",
        "smolagents",
        "langchain-mongodb",
        "agent-lifecycle-toolkit",
        "uncurl",
        "twelvelabs",
        "zep-python",
        "oauthlib",
        "datamodel-code-generator",
        "opentelemetry-api",
        "opentelemetry-sdk",
        "opentelemetry-proto",
        "opentelemetry-exporter-otlp",
        "opentelemetry-exporter-otlp-proto-common",
        "opentelemetry-exporter-otlp-proto-grpc",
        "opentelemetry-exporter-otlp-proto-http",
        "opentelemetry-exporter-otlp-common",
        "opentelemetry-exporter-http-transport",
        "opentelemetry-exporter-prometheus",
        "opentelemetry-semantic-conventions",
        "opentelemetry-instrumentation",
        "opentelemetry-util-http",
        "opentelemetry-instrumentation-asgi",
        "opentelemetry-instrumentation-fastapi",
        "opentelemetry-instrumentation-logging",
        "opentelemetry-instrumentation-redis",
        "opentelemetry-instrumentation-requests",
        "opentelemetry-instrumentation-sqlalchemy",
        "opentelemetry-instrumentation-threading",
        "opentelemetry-instrumentation-urllib3",
    ]
)
PROJECT_FILES = (
    "/app/LICENSE",
    "/app/THIRD_PARTY_NOTICES.md",
    "/app/docs/DEPENDENCY_LICENSES.md",
    "/app/review_core/assets/OFL.txt",
)
LANGFLOW_LICENSE_FILES = (
    "/app/licenses/dnspython-2.9.0-ISC.txt",
    "/app/licenses/FastMCP-3.4.10-LICENSE.txt",
    "/app/licenses/Langflow-LICENSE.txt",
)
CANDIDATE_NOTICE_FILES = (
    "/app/licenses/sqlite-vec-LICENSE-MIT.txt",
    "/app/licenses/sqlite-vec-LICENSE-APACHE.txt",
)
FONT_PATH = "/app/review_core/assets/NotoSansSC-Regular.ttf"
WEB_ROOT = "/usr/share/nginx/html/licenses"
WEB_FILES = ("THIRD_PARTY_LICENSES.md", "IBM-Plex-OFL-1.1.txt", "PROJECT-Apache-2.0.txt")


def now() -> str:
    return datetime.now(UTC).isoformat()


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def normalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


class TextBudget:
    def __init__(self, files: int = MAX_FILES, size: int = MAX_BYTES):
        if not 0 <= files <= MAX_FILES or not 0 <= size <= MAX_BYTES:
            raise ValueError("Invalid remaining text budget")
        self.files_left = files
        self.bytes_left = size

    def take(self, data: bytes) -> tuple[bool, str | None]:
        if len(data) > MAX_FILE:
            return False, "per_file_limit"
        if self.files_left == 0:
            return False, "batch_file_limit"
        if len(data) > self.bytes_left:
            return False, "batch_byte_limit"
        self.files_left -= 1
        self.bytes_left -= len(data)
        return True, None

    def remaining(self) -> dict[str, int]:
        return {"files": self.files_left, "bytes": self.bytes_left}


def read_file(path: Path, allowed_root: Path, budget: TextBudget, *, text: bool = True) -> dict:
    """Read only a declared regular file inside its approved root; skip explicitly."""
    result = {"path": str(path), "state": "skipped", "sha256": None}
    resolved = path.resolve()
    result["resolved_path"] = str(resolved)
    if not resolved.is_relative_to(allowed_root.resolve()):
        return result | {"reason": "resolved_path_outside_allowed_root"}
    try:
        info = path.stat()
        if not stat.S_ISREG(info.st_mode):
            return result | {"reason": "not_regular_file"}
        result["bytes"] = info.st_size
        # Font bytes are hashed in chunks and never placed in the output.
        limit = MAX_FILE if text else 20 * 1024 * 1024
        if info.st_size > limit:
            return result | {"reason": "per_file_limit" if text else "font_hash_input_limit"}
        if text:
            with path.open("rb") as stream:
                data = stream.read(MAX_FILE + 1)
            ok, reason = budget.take(data)
            if not ok:
                return result | {"reason": reason}
            decoded = data.decode("utf-8", errors="replace")
            return result | {
                "state": "recorded",
                "bytes": len(data),
                "sha256": digest(data),
                "text": decoded,
                "encoding": "utf-8; invalid bytes replaced, raw byte hash retained",
            }
        hasher = hashlib.sha256()
        size = 0
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(64 * 1024), b""):
                size += len(chunk)
                if size > limit:
                    return result | {"reason": "font_hash_input_limit"}
                hasher.update(chunk)
        return result | {"state": "hashed_only", "bytes": size, "sha256": hasher.hexdigest()}
    except FileNotFoundError:
        return result | {"reason": "missing_file"}
    except OSError as error:
        return result | {"reason": "read_error", "error_type": type(error).__name__}


def collect_python(name: str, budget: TextBudget) -> dict:
    """Run inside an isolated image; use only importlib's declared file lists."""
    packages = []
    selected = []
    seen = set()
    for distribution in importlib.metadata.distributions():
        metadata = distribution.metadata
        package_name = metadata.get("Name", "")
        version = distribution.version
        key = (normalize(package_name), version)
        if key in seen:
            continue
        seen.add(key)
        if len(seen) > 5000:
            raise ValueError("Python distribution count limit")
        item = {
            "name": package_name,
            "version": version,
            "location": str(distribution.locate_file("")),
            "license_expression": metadata.get("License-Expression"),
            "license_metadata": metadata.get("License"),
        }
        for field in ("license_expression", "license_metadata"):
            value = item[field]
            if value is not None and len(value.encode()) > MAX_FILE:
                item[field] = None
                item.setdefault("metadata_skipped", []).append(
                    {"field": field, "reason": "metadata_field_limit"}
                )
        packages.append(item)
        if key[0] not in SELECTED_PACKAGES:
            continue
        root = Path(distribution.locate_file(""))
        declared = distribution.files
        files = []
        if declared is not None:
            for declared_file in declared:
                if not any(
                    word in Path(str(declared_file)).name.lower()
                    for word in ("license", "copying", "notice", "copyright")
                ):
                    continue
                path = Path(distribution.locate_file(declared_file))
                if "__pycache__" in path.parts or path.suffix.lower() in {
                    ".py",
                    ".pyc",
                    ".pyo",
                    ".so",
                    ".pyd",
                    ".dll",
                    ".dylib",
                    ".exe",
                }:
                    files.append(
                        {
                            "path": str(path),
                            "declared_file": str(declared_file),
                            "state": "excluded",
                            "reason": "source_or_binary_filename_is_not_license_text",
                            "sha256": None,
                        }
                    )
                    continue
                record = read_file(path, root, budget)
                files.append(record | {"declared_file": str(declared_file)})
        selected.append(
            item
            | {
                "declared_file_list_available": declared is not None,
                "license_files": files,
                "license_text_state": "recorded"
                if any(f["state"] == "recorded" for f in files)
                else "no_license_text_recorded",
                "missing_text_is_not_permission": True,
            }
        )
    project_paths = PROJECT_FILES + (LANGFLOW_LICENSE_FILES if name == "langflow" else ())
    if name == "langflow" and any(
        normalize(p["name"]) == "langflow-base" and p["version"] == "1.13.1"
        for p in packages
    ):
        project_paths += CANDIDATE_NOTICE_FILES
    project = [read_file(Path(p), Path("/app"), budget) for p in project_paths]
    project.append(read_file(Path(FONT_PATH), Path("/app"), budget, text=False))
    installed_names = {normalize(p["name"]) for p in packages}
    return {
        "image_name": name,
        "collected_at": now(),
        "method": "installed Python metadata and explicitly declared license files; no tree walk",
        "python_version": sys.version,
        "packages": sorted(packages, key=lambda p: (normalize(p["name"]), p["version"])),
        "selected_packages": sorted(selected, key=lambda p: normalize(p["name"])),
        "selected_not_installed": sorted(SELECTED_PACKAGES - installed_names),
        "project_files": project,
        "remaining_budget": budget.remaining(),
        "legal_approval": False,
        "limitations": [
            "Metadata and collected text do not establish all redistribution obligations are met.",
            "Native bundled-library notices and source handling need separate review.",
            "zep-python 2.0.2 with no exact-release license remains unresolved, not approved.",
        ],
    }


def image_argument(value: str) -> tuple[str, str]:
    match = IMAGE_RE.fullmatch(value)
    if match is None:
        raise argparse.ArgumentTypeError("Use api|langflow|web=sha256:<64 lowercase hex>; no tags")
    return match.group(1), match.group(2)


def prepare_output(path: Path) -> Path:
    if path.is_symlink():
        raise ValueError("Output directory cannot be a symbolic link")
    destination = path.resolve()
    if destination == Path(destination.anchor):
        raise ValueError("Output directory cannot be the filesystem root")
    if destination.exists():
        if not destination.is_dir() or any(destination.iterdir()):
            raise ValueError("Output must be absent or an empty directory; never overwrite")
    else:
        destination.mkdir(parents=True, exist_ok=False)
    return destination


def run_bounded(command: list[str], payload: bytes = b"") -> dict:
    """Bound stdout/stderr in memory, including a faulty image's output."""
    proc = subprocess.Popen(
        command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    buffers = {"stdout": bytearray(), "stderr": bytearray()}
    exceeded = threading.Event()

    def consume(label: str, stream, limit: int) -> None:
        while chunk := stream.read(8192):
            if len(buffers[label]) + len(chunk) > limit:
                exceeded.set()
                proc.kill()
                break
            buffers[label].extend(chunk)
        stream.close()

    readers = [
        threading.Thread(target=consume, args=("stdout", proc.stdout, MAX_COMMAND_OUTPUT)),
        threading.Thread(target=consume, args=("stderr", proc.stderr, MAX_FILE)),
    ]
    for reader in readers:
        reader.start()
    reason = None
    try:
        try:
            proc.stdin.write(payload)
            proc.stdin.close()
        except BrokenPipeError:
            pass
        proc.wait(timeout=180)
    except subprocess.TimeoutExpired:
        reason = "command_timeout"
        proc.kill()
        proc.wait()
    for reader in readers:
        reader.join(timeout=5)
    if exceeded.is_set():
        reason = "command_output_limit"
    return {
        "exit_code": proc.returncode,
        "stop_reason": reason,
        "stdout": bytes(buffers["stdout"]),
        "stderr": bytes(buffers["stderr"]),
    }


def docker_command() -> list[str]:
    return [
        "docker",
        "run",
        "--rm",
        "-i",
        "--read-only",
        "--network",
        "none",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--memory",
        "512m",
        "--pids-limit",
        "64",
        "--log-driver",
        "none",
        "--entrypoint",
    ]


def collect_web_archive(data: bytes, budget: TextBudget) -> list[dict]:
    found = {}
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:") as archive:
        for member in archive:
            if member.name not in WEB_FILES:
                continue
            record = {"path": f"{WEB_ROOT}/{member.name}", "state": "skipped", "sha256": None}
            if member.name in found:
                raise ValueError("Duplicate web license archive member")
            if not member.isfile():
                found[member.name] = record | {"reason": "not_regular_file_or_symlink"}
                continue
            if member.size > MAX_FILE:
                found[member.name] = record | {"reason": "per_file_limit", "bytes": member.size}
                continue
            stream = archive.extractfile(member)
            if stream is None:
                found[member.name] = record | {"reason": "missing_archive_file_content"}
                continue
            content = stream.read(MAX_FILE + 1)
            ok, reason = budget.take(content)
            found[member.name] = record | (
                {
                    "state": "recorded",
                    "bytes": len(content),
                    "sha256": digest(content),
                    "text": content.decode("utf-8", errors="replace"),
                }
                if ok
                else {"reason": reason}
            )
    return [
        found.get(
            n,
            {
                "path": f"{WEB_ROOT}/{n}",
                "state": "skipped",
                "sha256": None,
                "reason": "missing_file",
            },
        )
        for n in WEB_FILES
    ]


def write_json(path: Path, data: dict) -> dict:
    raw = (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode()
    with path.open("xb") as stream:
        stream.write(raw)
    return {"path": path.name, "bytes": len(raw), "sha256": digest(raw)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", action="append", type=image_argument, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if len(args.image) > 3 or len({n for n, _ in args.image}) != len(args.image):
        parser.error("Provide at most three distinct api/langflow/web images")
    output = prepare_output(args.output_dir)
    producer = Path(__file__).resolve().read_bytes()
    budget = TextBudget()
    records = []
    files = []
    all_collected = True
    for name, image_id in args.image:
        started = now()
        if name == "web":
            # Only these three explicit files, no recursive archive and no dereference.
            command = docker_command() + ["tar", image_id, "-c", "-C", WEB_ROOT, *WEB_FILES]
            payload = b""
        else:
            command = docker_command() + [
                "python",
                image_id,
                "-",
                "--_collect",
                name,
                json.dumps(budget.remaining()),
            ]
            payload = producer
        result = run_bounded(command, payload)
        record = {
            "image_name": name,
            "image_id": image_id,
            "started_at": started,
            "ended_at": now(),
            "command": command,
            "stdin_sha256": digest(payload),
            "producer_sha256": digest(producer),
            "exit_code": result["exit_code"],
            "stop_reason": result["stop_reason"],
            "stderr": result["stderr"].decode("utf-8", errors="replace"),
            "stdout_sha256": digest(result["stdout"]),
        }
        try:
            if result["stop_reason"] or result["exit_code"] != 0:
                raise ValueError("Collector command failed or exceeded a bound")
            if name == "web":
                collected = {
                    "license_files": collect_web_archive(result["stdout"], budget),
                    "legal_approval": False,
                }
            else:
                collected = json.loads(result["stdout"])
                remaining = collected["remaining_budget"]
                if remaining["files"] > budget.files_left or remaining["bytes"] > budget.bytes_left:
                    raise ValueError("Invalid collector budget response")
                budget = TextBudget(remaining["files"], remaining["bytes"])
            record["collection_state"] = "collected_with_explicit_scope"
            record["result"] = collected
        except (ValueError, KeyError, tarfile.TarError) as error:
            record["collection_state"] = "failed"
            record["error"] = str(error)
            all_collected = False
        files.append(write_json(output / f"{name}.json", record))
        records.append({k: record[k] for k in ("image_name", "image_id", "collection_state")})
    manifest = {
        "created_at": now(),
        "producer": "scripts/verify_image_licenses.py",
        "producer_sha256": digest(producer),
        "contract": "ARC-UPGRADE@0.1.0",
        "acceptance": ["RELEASE-001", "AC-19"],
        "images": records,
        "files": files,
        "text_limits": {"per_file_bytes": MAX_FILE, "files": MAX_FILES, "total_bytes": MAX_BYTES},
        "remaining_budget": budget.remaining(),
        "legal_approval": False,
        "qualification": "Collection success is not full license/distribution approval.",
    }
    write_json(output / "manifest.json", manifest)
    print(json.dumps({"output_dir": str(output), "images": records, "legal_approval": False}))
    return 0 if all_collected else 1


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--_collect":
        if sys.argv[2] not in {"api", "langflow"}:
            raise SystemExit("Unsupported Python image name")
        limits = json.loads(sys.argv[3])
        print(
            json.dumps(
                collect_python(sys.argv[2], TextBudget(limits["files"], limits["bytes"])),
                ensure_ascii=False,
            )
        )
    else:
        raise SystemExit(main())
