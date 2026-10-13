# Upgrade release evidence

Contract: `ARC-UPGRADE@0.1.0`, `RELEASE-001` / `AC-19`.

This directory contains **unsealed P0/P1 candidates**, not a production approval.
Historical `../sbom/` files were not changed. Generation time, tool versions,
fixed-input SHA-256, commands, image platform/ID, contents and file hashes are
recorded in the stage manifests.

## Current result

- Python locked runtime: 33 exact pins; CycloneDX 1.5 strict-schema valid.
- Node lock: 241 package paths / 237 unique components; CycloneDX 1.5 valid.
  npm 10.9.2 emitted four duplicate component/dependency references. Only the
  unsealed derived SBOM was normalized; native `node-sbom.stdout` is retained,
  and the before/after hashes and edge-union method are in `sbom-validation.json`.
  Active locked-input SHA-256 is
  `4333ef73332a46fc299d162478978aed269a99952bb88c60f1eed1b43200d96e`
  (root application version 0.2.0; dependency pins unchanged), recorded by
  `node-refresh-manifest.json`. The old 0.1.0 input is explicitly superseded.
- Python locked-input SHA-256 is
  `3e922f3cd862294cc26dc83d6376415baed2ca8536bbb95a7aa67a475934078e`.
- Three image SBOMs: installed OS/Python package-manager metadata only. No image
  was saved/exported, and no full filesystem was traversed. Undiscovered/static
  binaries, vendored assets and the complete image file tree are not covered.
- Online vulnerability audits **were not executed**. The execution reviewer
  rejected external sending of package names/versions without specific authority.
  PyPI/PyPA, npm Registry and Docker Scout authorization is pending. Counts are
  `null`, not zero; database snapshot dates are unavailable because no queries ran.
  `AC-19` therefore remains partial, and historical audits are not substituted.

| Runtime image | Immutable local ID | Platform | Metadata packages |
|---|---|---|---:|
| API | `sha256:4e807fd845c49d138849f25a1e3521d41ec4a9daa80c3af23c1ea9bdbbf2f29b` | linux/arm64 | 140 (105 deb, 35 PyPI) |
| Langflow | `sha256:ff0f5cc380743034c05b4bfcf587be0e714da1610799f0c7c41d45902a5267c4` | linux/arm64 | 770 (226 rpm, 544 PyPI) |
| Web | `sha256:1c74f907504a137f7348ee3bd845eda464dfeb6335952de4fcb9623a2c41e325` | linux/arm64 | 70 apk |

Langflow's interpreter is `/app/.venv/bin/python` (Python 3.14.7). Duplicate
`lib`/`lib64` importlib paths produced 1088 raw distribution rows; normalization
by package name/version yields 544 unique Python components. All raw stdout is
retained. The initial Web candidate's old ID and before/after derived hashes are
preserved in the runtime revision records. Earlier API/Langflow identities were
refreshed after the transport encoding fix; old metadata stdout remains intact.
`langflow-web-manifest.json` and `final-runtime-manifest.json` are explicitly
superseded; use `verified-runtime-manifest.json`, `verified-review-manifest.json`
and `sbom-validation.json`. API package metadata confirms application 0.2.0.

## License checks

These are metadata observations, not legal conclusions or distribution approval.
Unknown values and conservative copyleft/restricted-license matches need review.

| Inventory | Recorded | Unknown | Review required |
|---|---:|---:|---:|
| Python exact locked packages | 31 | 0 | 2 |
| Node package-lock paths | 241 | 0 | 0 |
| API image | 42 | 17 | 81 |
| Langflow image | 592 | 10 | 168 |
| Web image | 51 | 0 | 19 |

Sources: exact-version Python `METADATA` (including `License-Expression` and
license classifiers), lock-file license fields, Debian copyright `License:`
fields, RPM `LICENSE` headers and APK `L` fields. Missing local greenlet metadata
was filled from the exact `greenlet==3.5.5` package in the final API image:
`MIT AND PSF-2.0`. `psycopg` and `psycopg-binary` declare `LGPL-3.0-only`.
Strict CycloneDX validation used the existing local jsonschema 4.23.0 and
cyclonedx-python-lib 11.12.0; SPDX checks were structural, not full-schema.

## Reproduction and continuation

Producer: `../../scripts/scan_release.py`. Exact executed commands are in the
manifests. Tools already installed: npm 10.9.2, pip-audit 2.10.1, Docker Scout
1.18.1; no tools or vulnerability databases were downloaded.

Temporary consumer root: `/private/tmp/arc-release-scan.lBO9lV` (about 2.8 MiB).
Candidate evidence: about 5.4 MiB; both are below their limits.
The root is retained without cleanup authority. No containers, volumes or Docker
configuration belonging to the original project were modified. Inventory reads
used auto-removed, no-network, no-mount, read-only, resource-limited containers.

After explicit external-sending authorization, the existing inventories can be
audited without recataloging images or replacing SBOMs:

```bash
.venv/bin/python scripts/scan_release.py audit \
  --record authorized-audit --allow-online-audit \
  --runtime-record verified-runtime \
  --temporary-root /private/tmp/arc-release-scan.lBO9lV
```

This contacts the PyPI/PyPA vulnerability JSON API, the official npm registry
audit API, and Docker Scout with the existing SPDX package inventory. It records
real findings and provider errors separately. Do not run until authorized.
Remote services may not expose reproducible database dates even after execution;
record that limitation and the actual query timestamp rather than inventing one.
