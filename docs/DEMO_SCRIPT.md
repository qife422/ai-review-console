# Demo Script

Target length: 6 minutes.

## Prepare

1. Copy `.env.example` to `.env` and replace every placeholder.
2. Run `docker compose up --build`.
3. Wait until `web`, `api`, `langflow` and `postgres` are healthy and `flow-init` exits successfully.
4. Open <http://localhost:8080>.

## Walkthrough

### Establish the boundary

Point to the header and footer attribution: the product is built on Langflow and the demo uses synthetic data only. Explain that Langflow performs workflow orchestration while the Review API owns approvals and audit records.

### Review operations

On the overview, call out the pending approval count, risk distribution and leading risk categories. Open the review queue and filter to high risk.

### Inspect evidence

Open `数据处理补充协议`. Show the risk score, rule version and Langflow run ID. Review the evidence for unlimited liability, then switch to the document comparison tab to show deterministic placeholders.

### Human decision

Choose `记录决定`, select `要求修改`, and enter: `请增加责任上限，并确认个人信息最小化范围。` Confirm the action. Show the new status and the appended audit event.

### Export

Download the PDF report. Point out the synthetic-data classification, document hash, decision, rule findings and `Built on Langflow` attribution.

### Show the Flow

Open the local Langflow admin UI at <http://localhost:7860>. Show `Document Review Intake` and its four connected trusted components. Explain that the run ends after creating the asynchronous approval task. Show `Document Review Decision` as the separate export stage.

## Close

State the non-goals clearly: no real company data, no automatic legal decision and no claim that the demo authentication model is production ready.

