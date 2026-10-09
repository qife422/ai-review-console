from lfx.custom.custom_component.component import Component
from lfx.io import DataInput, Output
from lfx.schema import Data

from review_core.risk import score_sections


class ExplainableRiskScorer(Component):
    display_name = "Explainable Risk Scorer"
    description = "Score synthetic documents with transparent, versioned review rules."
    icon = "shield-alert"
    name = "ExplainableRiskScorer"

    inputs = [DataInput(name="document", display_name="Redacted Document", required=True)]
    outputs = [Output(name="assessment", display_name="Risk Assessment", method="score")]

    def score(self) -> Data:
        payload = dict(self.document.data)
        result = score_sections(payload["redacted_document"]["sections"])
        assessment = result.to_dict()
        if assessment["ruleset_hash"] != payload["ruleset_hash"]:
            raise ValueError("ruleset_hash_mismatch: worker and component rules differ")
        payload["assessment"] = assessment
        self.status = f"Risk {result.score}/100 ({result.level})"
        return Data(data=payload)
