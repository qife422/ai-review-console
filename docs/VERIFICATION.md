# Verification record

Verified on 2026-09-01 (Asia/Shanghai) using Docker Engine 28.3.2 and Docker Compose 2.38.2 on arm64.

## Automated checks

| Check | Result |
|---|---|
| `ruff check .` | passed |
| `pytest -q` | 9 passed |
| `npm test -- --run` | 1 test file passed |
| `npm run build` | production Vite build passed |
| `pip-audit --requirement requirements.lock` | no known vulnerabilities found |
| `npm audit --omit=dev` | 0 vulnerabilities |
| `docker compose config --quiet` | passed |
| API, Web and Langflow image builds | passed |
| Final API image CycloneDX SBOM | generated and hashed |

Pytest emits one upstream `StarletteDeprecationWarning` concerning the current TestClient/httpx bridge. It does not affect the application runtime or test result and should be revisited on the next FastAPI/Starlette upgrade.

## Compose integration

- PostgreSQL, Langflow and Review API reported healthy.
- Web served through Nginx at `http://localhost:8080` and proxied `/api/health` successfully.
- Langflow remained bound to `127.0.0.1:7860`.
- `flow-init` exited with code 0 and updated `Document Review Intake` and `Document Review Decision` idempotently.
- Langflow exposed all five repository-controlled custom components.
- `scripts/validate_langflow.py` executed both Flows through Langflow's authenticated build API without an error event.
- The final API image SBOM was regenerated from image ID `sha256:9af748b5948f254215ef1502e0d3625f3edeca5093f89b1d8713c7fdcfe11cca`; its evidence hash is recorded in `compliance/README.md`.
- Intake Flow invoked the Review API approval gateway successfully.
- Decision Flow produced `/app/artifacts/RC-DEMO-report.pdf` with SHA-256 `576902b7f499924e81fcfa7126b54631d9ffc7eccefe338225d736f16bce383b`.

## Browser validation

The production Docker endpoint was checked with Playwright at 1440 x 1000 and the local responsive build at 390 x 844.

- overview, queue, case detail, document comparison, audit tab and decision modal rendered;
- approval gating, decision submission and report enablement worked;
- a second decision was disabled after the first recorded outcome;
- findings showed `[PERSON_01]` and `[PHONE_01]` placeholders instead of source values;
- light and dark Carbon themes rendered;
- mobile document width and scroll width both measured 390 px;
- browser console had no errors or warnings (Carbon v12 migration notices were informational).

The final repository `frontend/dist/index.html` and the file served by the running Web container both had SHA-256 `8fc779381abd27722163eaee32d7cc05e5659d8820b1527c648d29b5d89ee74b`.

Screenshots are kept in `demo/screenshots/`. They use only fixed-seed synthetic data.
