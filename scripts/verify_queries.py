"""Read-only query diagnostic after an explicitly recorded mixed-load benchmark.

Does not replace the original failing measurements or create any new cases.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

import httpx


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--benchmark", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--api-url", default="http://localhost:8080")
    args = parser.parse_args()
    if urlparse(args.api_url).hostname not in {"localhost", "127.0.0.1"}:
        raise ValueError("Only a loopback diagnostic is authorized")
    output = args.output.resolve()
    allowed = (Path(tempfile.gettempdir()).resolve(), Path("/private/tmp"))
    if output.exists() or not any(output.parent.is_relative_to(root) for root in allowed):
        raise ValueError("Use a new output in an existing system temporary directory")
    original_bytes = args.benchmark.read_bytes()
    benchmark = json.loads(original_bytes)["benchmark"]
    cases = benchmark["samples"]
    if not 1 <= len(cases) <= 20:
        raise ValueError("Bound the diagnostic to the existing 1–20 benchmark cases")
    measurements = []
    with httpx.Client(base_url=args.api_url, timeout=15) as client:
        for sample in cases:
            for path in ("/api/cases", "/api/summary", f"/api/cases/{sample['case_id']}"):
                started = time.monotonic()
                response = client.get(path).raise_for_status()
                elapsed = time.monotonic() - started
                measurements.append(
                    {"path": path, "seconds": round(elapsed, 6), "bytes": len(response.content)}
                )
    values = sorted(item["seconds"] for item in measurements)
    p95 = values[math.ceil(len(values) * 0.95) - 1]
    evidence = {
        "contract": "ARC-UPGRADE@0.1.0",
        "producer": "scripts/verify_queries.py",
        "producer_sha256": digest(Path(__file__).read_bytes()),
        "checked_at": datetime.now(UTC).isoformat(),
        "method": (
            "read-only queries across the same 20 completed 1 MiB benchmark cases; "
            "no new Intake or uploads"
        ),
        "environment": benchmark["environment"],
        "original_benchmark": str(args.benchmark.resolve()),
        "original_benchmark_sha256": digest(original_bytes),
        "original_query_p95_seconds": benchmark["query_p95_seconds"],
        "original_query_target_met": benchmark["targets_met"]["query_p95_le_500_ms"],
        "measurements": measurements,
        "query_p95_seconds": p95,
        "query_p95_le_500_ms": p95 <= 0.5,
        "limitations": (
            "Read-only retest is a diagnostic, not a replacement for the mixed-load upload "
            "benchmark. No CPU or memory contention cause is proven."
        ),
    }
    output.write_bytes(json.dumps(evidence, ensure_ascii=False, indent=2).encode())
    print(
        json.dumps(
            {
                "evidence": str(output),
                "sha256": digest(output.read_bytes()),
                "query_p95_seconds": p95,
            }
        )
    )


if __name__ == "__main__":
    main()
