import os

import httpx
from lfx.custom.custom_component.component import Component
from lfx.io import DataInput, Output, SecretStrInput, StrInput
from lfx.schema import Data


class ApprovalTaskGateway(Component):
    display_name = "Approval Task Gateway"
    description = "Persist a bound review result before declaring it ready for human approval."
    icon = "user-check"
    name = "ApprovalTaskGateway"

    inputs = [
        DataInput(name="assessment", display_name="Risk Assessment", required=True),
        StrInput(
            name="review_api_url",
            display_name="Review API URL",
            value="http://api:8000",
            advanced=True,
        ),
        SecretStrInput(
            name="service_token",
            display_name="Service Token",
            value="",
            required=False,
            advanced=True,
        ),
    ]
    outputs = [Output(name="task", display_name="Approval Task", method="create_task")]

    def create_task(self) -> Data:
        payload = dict(self.assessment.data)
        endpoint = f"{self.review_api_url.rstrip('/')}/api/integrations/langflow/results"
        headers = {"X-Service-Token": self.service_token or os.getenv("REVIEW_SERVICE_TOKEN", "")}
        response = httpx.post(endpoint, json=payload, headers=headers, timeout=15)
        response.raise_for_status()
        result = response.json()
        if not isinstance(result, dict) or not result.get("accepted"):
            raise ValueError("callback_not_persisted: the review API did not accept the result")
        self.status = f"Persisted review for {payload['case_id']}"
        return Data(
            data={
                "case_id": payload["case_id"],
                "job_id": payload["job_id"],
                "gateway_result": result,
            }
        )
