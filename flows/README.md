# Langflow Flows

`scripts/bootstrap_langflow.py` reads the live component templates from Langflow `1.11.6`, builds version-compatible Flow graphs and uploads them idempotently:

- `Document Review Intake`: parser -> redactor -> scorer -> approval gateway;
- `Document Review Decision`: decision report exporter with an API-editable decision JSON input.

The bootstrapper can also write portable Flow JSON files after Langflow is running:

```bash
LANGFLOW_URL=http://localhost:7860 \
LANGFLOW_SUPERUSER=review-admin \
LANGFLOW_SUPERUSER_PASSWORD=change-me \
.venv/bin/python scripts/bootstrap_langflow.py --write flows/generated
```

No Flow file contains an API key. Runtime secrets are resolved from environment variables.

`generated/` contains the portable JSON exported from the verified `1.11.6` component registry. The Compose `flow-init` service creates or updates the same two Flows on every deployment.

To validate both graphs through Langflow's authenticated build API:

```bash
LANGFLOW_SUPERUSER_PASSWORD=change-me \
.venv/bin/python scripts/validate_langflow.py
```
