from enum import Enum
from pathlib import Path

import pytest
from pydantic import BaseModel, Field

from scripts.verify_dependency_compatibility import (
    prohibit_network,
    scratch_inventory,
    validate_model,
)


class SyntheticDecision(Enum):
    approve = "approve"
    reject = "reject"
    request_changes = "request_changes"


class SyntheticModel(BaseModel):
    case_id: str
    score: int = Field(ge=0, le=100)
    decision: SyntheticDecision


def test_generated_model_contract_uses_json_values_and_rejects_invalid_payloads() -> None:
    assert validate_model(SyntheticModel) == {"valid_payloads": 1, "rejected_payloads": 3}


def test_scratch_guard_counts_files_and_rejects_symlinks(tmp_path: Path) -> None:
    (tmp_path / "synthetic.txt").write_text("synthetic")
    assert scratch_inventory(tmp_path) == {"files": 1, "bytes": 9}
    (tmp_path / "link").symlink_to(tmp_path / "synthetic.txt")
    with pytest.raises(RuntimeError, match="symlink"):
        scratch_inventory(tmp_path)


def test_scratch_guard_rejects_excess_file_count(tmp_path: Path) -> None:
    for index in range(51):
        (tmp_path / str(index)).write_bytes(b"")
    with pytest.raises(RuntimeError, match="8MiB/50"):
        scratch_inventory(tmp_path)


def test_probe_network_guard_rejects_any_destination() -> None:
    with pytest.raises(RuntimeError, match="forbids network"):
        prohibit_network(("provider.invalid", 443))
