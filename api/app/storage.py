from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_RUNTIME_BYTES = 1024 * 1024 * 1024
MAX_RUNTIME_FILES = 5000
MIME_TYPES = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "txt": "text/plain",
    "md": "text/markdown",
}


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def content_hash(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def documents_root() -> Path:
    return Path(os.getenv("DOCUMENTS_ROOT", "/tmp/ai-review-console-documents")).resolve()


def reports_root() -> Path:
    return Path(os.getenv("REPORTS_ROOT", "/tmp/ai-review-console-reports")).resolve()


def resolve_storage(root: Path, key: str) -> Path:
    candidate = (root / key).resolve()
    if not candidate.is_relative_to(root) or candidate == root:
        raise ValueError("storage_path_invalid")
    return candidate


def storage_inventory() -> tuple[int, int]:
    total = count = 0
    for root in (documents_root(), reports_root()):
        if root.exists():
            for path in root.rglob("*"):
                if path.is_file():
                    count += 1
                    total += path.stat().st_size
    return total, count


def save_document(version_id: str, extension: str, data: bytes) -> str:
    total, count = storage_inventory()
    if total + len(data) > MAX_RUNTIME_BYTES or count + 1 > MAX_RUNTIME_FILES:
        raise ValueError("runtime_storage_threshold")
    key = f"{version_id}/source.{extension}"
    path = resolve_storage(documents_root(), key)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation. Files left by a failed DB commit remain for read-only inventory.
    with path.open("xb") as target:
        target.write(data)
    return key
