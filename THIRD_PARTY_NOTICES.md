# Third-Party Notices

This project is built on Langflow and includes or depends on third-party open-source software.

## Langflow

- Project: <https://github.com/langflow-ai/langflow>
- Version baseline: `1.11.6`
- License: MIT
- Copyright: Copyright (c) 2024 Langflow
- License copy: `licenses/Langflow-LICENSE.txt`

“Langflow” is used only to describe the upstream technology. This project is not endorsed by or affiliated with the Langflow maintainers.

## Noto Sans SC

- Source: Google Fonts / Noto, pinned commit `a85815a42757630ce188fdad368c2dfc444d4773`.
- License: SIL Open Font License 1.1, bundled at `review_core/assets/OFL.txt`.
- Copyright: Adobe / Noto font contributors as recorded in the bundled OFL notice.
- Font resource: `review_core/assets/NotoSansSC-Regular.ttf`, static weight 400 instance of the official variable font.
- SHA-256: `e3b799e4230233500ff152d1cc81ade6c64acb34958c90cd6b6e02927a2923a9`.
- Source URL, original resource hash and one-time FontTools conversion method: `review_core/assets/README.md`.
- Chinese reports embed the subset of this resource; no Apple system fonts are redistributed.

## Frontend runtime and fonts

- React and React DOM are MIT-licensed; retain their copyright and license text with distributed bundles.
- Carbon React and Carbon icons are Apache-2.0-licensed; retain applicable licenses and attribution notices.
- IBM Plex Web fonts are under SIL OFL 1.1. Their license accompanies the public-demo license directory.
- Frontend build dependencies and Python/container dependencies are separate scopes; a package present in a lockfile is not by itself evidence that its code is in a browser bundle.

## Python libraries and container contents

Psycopg 3 and its binary extension are LGPL-3.0-only. Langflow also installs LGPL libraries and a GPL-2.0-or-EPL-1.0 dual-licensed package. These components keep their own licenses. Binary wheels may bundle native libraries with additional notices and source requirements; the project's Apache-2.0 license does not replace those terms.

The exact license of Langflow's installed `zep-python 2.0.2` dependency remains unresolved: its installed package, exact PyPI source distribution and official release tag do not contain a license declaration. Do not infer permission for this release from an older branch's license.

## Dependency review status

The 2026-10-31 review and 2026-11-02 targeted follow-up are recorded in [docs/DEPENDENCY_LICENSES.md](docs/DEPENDENCY_LICENSES.md). License texts, exact package/image identities, source locations and remaining issues are preserved in release evidence. Source publication, the static browser demo and complete backend image redistribution have different scopes. Full backend image redistribution has not received a complete license signoff.

Exact Psycopg 3.3.5 and Psycopg2 2.9.12 build recipes and patches have been fingerprinted against their respective package owners. Exact AMD64 driver and legacy native material observations are recorded in docs/DEPENDENCY_LICENSES.md. Recipe/version matches, library build IDs and package licenses do not by themselves complete vendor-source correspondence or backend binary redistribution approval. The IBM wrapper license is distinct from clidriver terms; Zep 2.0.2 remains unresolved.


## Additional exact-version license copies

- Dnspython 2.9.0: ISC copyright and permission text at `licenses/dnspython-2.9.0-ISC.txt`.
- FastMCP / fastmcp-slim 3.4.10: Apache-2.0 text at `licenses/FastMCP-3.4.10-LICENSE.txt`; the slim package's same-version workspace declaration was checked.
- LFX 1.11.6: the same-version Langflow root MIT text is represented by `licenses/Langflow-LICENSE.txt`.

These copies address known missing package-level texts; they do not authorize full backend image redistribution. Exact native versions, source archive hashes, retained notices and remaining source/binary correspondence work are listed in `docs/DEPENDENCY_LICENSES.md`. Zep 2.0.2 remains unresolved; tags for the separately named `zep-cloud` package are not its license evidence.

## Isolated 1.13.1 candidate observations

The candidate source includes both exact sqlite-vec v0.1.9 upstream notice files at `licenses/sqlite-vec-LICENSE-MIT.txt` and `licenses/sqlite-vec-LICENSE-APACHE.txt`. Both are retained without selecting an alternative license. The collector checks these supplemental files in the actual candidate image; installed wheel own-text and native source correspondence remain separate checks. The shared Langflow MIT copy retains the complete v1.13.1 copyright and permission text, with one extra trailing newline.

The experimental langflow-base/LFX1.13.1 image excludes selected Zep, IBM driver and Psycopg binary distributions; default and API images retain their separately scoped obligations. APSW's installed license specimen and Psycopg's LGPL text were recorded. Exact upstream MIT/sqlite-vec source notices supplement explicitly retained installed-text gaps. The fixed repository MIT copy differs only by a trailing blank line; an independent same-image copy readback was not retained. Embedded SQLite/source, system libraries, frontend notices and full backend redistribution remain subject to further verification. See docs/evidence/langflow-candidate/README.md. No license-option or residual-risk acceptance is implied.
