# Architecture

## Purpose

AI Review Console is a single-organization synthetic-data reference implementation. Langflow 1.11.6 is the workflow engine. The Review API is the source of truth for review cases, human decisions and audit events.

## Trust boundaries

1. The browser talks only to the Review API through the Web reverse proxy.
2. The Review API owns business state and keeps the Langflow credential server-side.
3. Langflow runs trusted repository components in an isolated container.
4. PostgreSQL hosts separate `review_console` and `langflow` databases.
5. Source documents and report artifacts have separate mounted paths.

Langflow is a Python execution environment. It is not treated as a tenant isolation or end-user authorization boundary.

## Review lifecycle

```text
received -> processing -> pending_approval (or failed)
                                              |
                         approved / rejected / changes_requested
                                              |
                                       report: queued -> processing -> ready / partial / failed
```

Business, workflow and per-format artifact states are separate. Upload idempotency binds file bytes and metadata. PostgreSQL claims jobs atomically with 90-second leases renewed every 15 seconds; executions are bounded at 120 seconds, with at most three attempts (10/30-second retry waits). Recovering an existing run keeps its execution token; a new attempt rotates it. Late failures cannot overwrite a committed success.

The API is the only writer of business records. Intake callbacks must match version/job/token/input/flow/config hashes and recomputed evidence. A compare-and-swap human decision, audit and report job commit in one transaction. Report callbacks verify immutable snapshot references, actual file bytes and hashes. Partial groups preserve the decision and ready formats; dedicated retries fill only missing/failed formats.

Human approval never keeps a Langflow request open. The authenticated Build API executes a detached graph with one runtime input override; business execution never PATCHes the shared Flow. Seed labels and text-derived hashes remain explicitly historical and are not real upstream execution evidence.

## Custom component contract

| Component | Input | Output | Side effect |
|---|---|---|---|
| SyntheticDocumentParser | bound runtime envelope and trusted source path | parsed sections/locators | none |
| DeterministicPIIRedactor | parsed `Data` | redacted `Data` | none |
| ExplainableRiskScorer | redacted `Data` | assessment `Data` | none |
| ApprovalTaskGateway | complete bound Intake envelope | persisted result `Data` | authenticated idempotent API callback |
| DecisionReportExporter | immutable human-decision snapshot | per-format artifact metadata/errors | publishes immutable files; Worker reconciles through API |

## Security defaults

- authentication enabled;
- self-registration disabled;
- webhook authentication enabled;
- UI creation/editing of arbitrary custom components disabled;
- repository component path remains allow-listed;
- Langflow port bound to `127.0.0.1` in the demo;
- runtime secrets supplied by environment;
- fixed Langflow version and reviewed multi-architecture digest in the actual Dockerfile;
- explicit versioned migration; startup cannot silently upgrade an existing database;
- API writes sources; Langflow reads sources and writes reports; API/Worker read reports;
- service token stays server-side; browser identity remains demo-only.

## Production gaps

The demo header `X-Reviewer` is not an identity system. A production deployment requires OIDC/SSO, authorization, malware scanning, immutable audit storage, object-storage access controls, egress policy and a supported backup/restore procedure.
