# Chinese PDF font resource

`NotoSansSC-Regular.ttf` is a static weight-400 instance of the official Noto Sans SC
font, redistributed under the adjacent SIL Open Font License 1.1. The reserved font
name in that license is `Source`; the instance retains the upstream `Noto Sans SC`
family name. The font is embedded as a subset in generated PDFs. No operating-system
proprietary font is distributed.

- Primary source: https://github.com/google/fonts/tree/a85815a42757630ce188fdad368c2dfc444d4773/ofl/notosanssc
- Download: https://raw.githubusercontent.com/google/fonts/a85815a42757630ce188fdad368c2dfc444d4773/ofl/notosanssc/NotoSansSC%5Bwght%5D.ttf
- Upstream variable font SHA-256: `a3041811a78c361b1de50f953c805e0244951c21c5bd412f7232ef0d899af0da`
- Distributed static font SHA-256: `e3b799e4230233500ff152d1cc81ade6c64acb34958c90cd6b6e02927a2923a9`
- Local OFL.txt SHA-256: `babcfe66c8a098b2fa279bc724a3a342f8124f77ce18941fbcc1bbb39823cded`
- Transformation: FontTools `4.60.1`, `fontTools.varLib.instancer`, `wght=400`,
  `--update-name-table`; font coverage is not reduced. FontTools is a one-time
  development tool and is not required by the application runtime.
- Retrieval and conversion date: 2026-10-08 (America/Los_Angeles).

Conversion command, with the downloaded variable input in the destination:

```bash
python -m fontTools.varLib.instancer review_core/assets/NotoSansSC-Regular.ttf \
  wght=400 --update-name-table --output review_core/assets/NotoSansSC-Regular.ttf
```

The fixed distributed binary is the build input and its hash is checked at runtime.
Regenerating a font may change internal timestamps and therefore its file hash; a
replacement requires reviewing and updating the resource fingerprint. Setting
`REVIEW_REPORT_FONT` supports a deployment path to the same verified font bytes,
not an unverified font substitution.
