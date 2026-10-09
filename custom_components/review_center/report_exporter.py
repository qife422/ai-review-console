from __future__ import annotations

import os

from lfx.custom.custom_component.component import Component
from lfx.io import MultilineInput, Output
from lfx.schema import Data

from custom_components.review_center.runtime import execution_context
from review_core.reporting import canonical_hash, export_report_artifacts


class DecisionReportExporter(Component):
    display_name = "Decision Report Exporter"
    description = "Export a synthetic, human-decided review as JSON, HTML, or PDF."
    icon = "file-down"
    name = "DecisionReportExporter"

    inputs = [
        MultilineInput(
            name="runtime_json",
            display_name="Bound Decision Execution",
            value="",
            required=True,
            advanced=True,
        ),
    ]
    outputs = [Output(name="artifact", display_name="Report Artifact", method="export")]

    def export(self) -> Data:
        context = execution_context(self.runtime_json)
        payload = context.get("snapshot")
        if not isinstance(payload, dict):
            raise ValueError("decision_snapshot_missing: a bound snapshot is required")
        if payload.get("decision") not in {"approved", "rejected", "changes_requested"}:
            raise ValueError("A recorded human decision is required before report export")
        snapshot_hash = str(payload.get("snapshot_hash", ""))
        if not snapshot_hash or canonical_hash(payload) != snapshot_hash:
            raise ValueError("snapshot_hash_mismatch: decision snapshot changed")
        for key in ("case_id", "document_version_id", "decision_id"):
            if payload.get(key) != context.get(key):
                raise ValueError(f"snapshot_identity_mismatch: {key}")
        formats = context.get("formats", ["json", "html", "pdf"])
        if (
            not isinstance(formats, list)
            or not formats
            or any(item not in {"json", "html", "pdf"} for item in formats)
        ):
            raise ValueError("report_formats_invalid: expected json, html or pdf")
        generated = export_report_artifacts(
            payload, os.getenv("REPORT_STORAGE_ROOT", "/app/artifacts"), formats
        )
        artifacts = [
            {
                key: item[key]
                for key in (
                    "format",
                    "storage_key",
                    "sha256",
                    "size",
                    "template_version",
                )
            }
            for item in generated["artifacts"]
        ]
        errors = [
            {"format": report_format, **error}
            for report_format, error in generated["errors"].items()
        ]
        result = {
            **{
                key: context[key]
                for key in (
                    "case_id",
                    "document_version_id",
                    "job_id",
                    "execution_token",
                    "payload_hash",
                    "flow_id",
                    "flow_hash",
                    "decision_id",
                )
            },
            "schema_version": "1.0",
            "snapshot_hash": snapshot_hash,
            "artifacts": artifacts,
            "errors": errors,
            "data_classification": "SYNTHETIC_DEMO_ONLY",
        }
        self.status = f"Generated {len(artifacts)} formats; failed {len(errors)} formats"
        return Data(data=result)
