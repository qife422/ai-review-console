# Dependency and license evidence

Generated on 2026-09-01 from the fixed inputs in `requirements.lock` and `frontend/package-lock.json`.

| Evidence | Format | SHA-256 |
|---|---|---|
| `sbom/python.cdx.json` | CycloneDX JSON | `73d49f7a8dab3168ef263a4a40f1b465800cbfa0709a7c3dac4734ebcc2e3682` |
| `sbom/node.cdx.json` | CycloneDX JSON | `25e4edc72a8810f472628cbed4f0dfea606c6d1184196528761217e2cbf7cdb1` |
| `sbom/api-image.cdx.json` | CycloneDX JSON | `ed031b6afde02c4b65e436f06d32791a38b49673a0a6becd45db13df3e609b5b` |
| `sbom/web-image.cdx.json` | CycloneDX JSON | `1d8dfcf399a0a7028f6a16d1ef8cd20ee8a47579056b24b542d4724627cb9158` |

Generation and validation commands:

```bash
.venv/bin/pip-audit --requirement requirements.lock \
  --format cyclonedx-json --output compliance/sbom/python.cdx.json
cd frontend && npm sbom --sbom-format=cyclonedx > ../compliance/sbom/node.cdx.json
npm audit --omit=dev
docker sbom ai-review-console-api:local --format cyclonedx-json
docker sbom ai-review-console-web:latest --format cyclonedx-json
```

Observed result: no known vulnerabilities in the locked Python runtime dependency set and no known vulnerabilities in production Node dependencies. Local SBOM generation completed for the application API and Web images; the API evidence was refreshed from final image ID `sha256:9af748b5948f254215ef1502e0d3625f3edeca5093f89b1d8713c7fdcfe11cca`. The Langflow application image was built from the pinned upstream digest `sha256:5338f6851fbab3d0476f7701dacbe749f58fa81a4c1317ad1d52164ce1231a14`; its full local image scan exceeded the bounded validation window, so a fresh registry/image scan remains a release gate. Vulnerability and license databases change after this evidence is generated.

Direct upstream notices are kept in `../THIRD_PARTY_NOTICES.md` and `../licenses/`.
