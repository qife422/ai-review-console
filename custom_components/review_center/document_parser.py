from lfx.custom.custom_component.component import Component
from lfx.io import MultilineInput, Output
from lfx.schema import Data

from custom_components.review_center.runtime import (
    controlled_source,
    envelope_context,
    execution_context,
)
from review_core import parse_document


class SyntheticDocumentParser(Component):
    display_name = "Synthetic Document Parser"
    description = "Parse a synthetic PDF, DOCX, TXT, or Markdown file into traceable text sections."
    icon = "file-text"
    name = "SyntheticDocumentParser"

    inputs = [
        MultilineInput(
            name="runtime_json",
            display_name="Bound Execution Input",
            value="",
            required=True,
            info="Supplied by the trusted worker for each run; no fixture fallback.",
            advanced=True,
        ),
    ]
    outputs = [Output(name="document", display_name="Parsed Document", method="parse")]

    def parse(self) -> Data:
        context = execution_context(self.runtime_json)
        try:
            result = parse_document(controlled_source(context))
        except ValueError as exc:
            code = getattr(exc, "code", "document_parse_failed")
            raise ValueError(f"{code}: {exc}") from exc
        if result.sha256 != context.get("source_sha256"):
            raise ValueError("source_hash_mismatch: document bytes changed")
        self.status = f"Parsed {len(result.sections)} sections with {len(result.warnings)} warnings"
        return Data(
            data={
                **envelope_context(context),
                "parsed_document": result.to_dict(),
                "warnings": list(result.warnings),
            }
        )
