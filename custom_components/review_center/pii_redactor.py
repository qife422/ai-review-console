from lfx.custom.custom_component.component import Component
from lfx.io import DataInput, Output
from lfx.schema import Data

from review_core.redaction import redact_sections


class DeterministicPIIRedactor(Component):
    display_name = "Deterministic PII Redactor"
    description = "Redact synthetic identifiers using a versioned deterministic policy."
    icon = "scan-eye"
    name = "DeterministicPIIRedactor"

    inputs = [DataInput(name="document", display_name="Parsed Document", required=True)]
    outputs = [Output(name="redacted", display_name="Redacted Document", method="redact")]

    def redact(self) -> Data:
        payload = dict(self.document.data)
        result = redact_sections(payload["parsed_document"]["sections"])
        redacted = result.to_dict()
        if redacted["redaction_policy_hash"] != payload["redaction_policy_hash"]:
            raise ValueError("policy_hash_mismatch: worker and component policies differ")
        payload["redacted_document"] = redacted
        self.status = f"Redacted {redacted['count']} synthetic PII matches"
        return Data(data=payload)
