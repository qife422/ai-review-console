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
received -> parsed -> redacted -> scored -> pending_approval
                                              |
                         approved / rejected / changes_requested
                                              |
                                           exported
```

Every retry carries a deterministic case ID or idempotency key. Human approval never keeps a Langflow request open. The intake Flow creates a pending task and exits; a later decision triggers report generation.

## Custom component contract

| Component | Input | Output | Side effect |
|---|---|---|---|
| SyntheticDocumentParser | trusted file path | parsed `Data` | none |
| DeterministicPIIRedactor | parsed `Data` | redacted `Data` | none |
| ExplainableRiskScorer | redacted `Data` | assessment `Data` | none |
| ApprovalTaskGateway | assessment `Data` | task `Data` | idempotent Review API call |
| DecisionReportExporter | decision `Data` or JSON | artifact `Data` | writes report to artifact mount |

## Security defaults

- authentication enabled;
- self-registration disabled;
- webhook authentication enabled;
- UI creation/editing of arbitrary custom components disabled;
- repository component path remains allow-listed;
- Langflow port bound to `127.0.0.1` in the demo;
- runtime secrets supplied by environment;
- fixed Langflow version, with image digest pinning required before release.

## Production gaps

The demo header `X-Reviewer` is not an identity system. A production deployment requires OIDC/SSO, authorization, malware scanning, immutable audit storage, object-storage access controls, egress policy and a supported backup/restore procedure.

