# Clarify the license for the published zep-python 2.0.2 artifacts

Draft only — not sent or posted. Publishing this message to getzep/zep-python requires separate authorization to contact a third party.

We are reviewing the license evidence for the published `zep-python==2.0.2` package and would appreciate clarification for that exact release.

The PyPI files are:

- `zep_python-2.0.2-py3-none-any.whl`, SHA-256 `d7b2cadf1eb15007825362cae5ddff9c9d0ada5b4f75cf91e5b87986459f7817`.
- `zep_python-2.0.2.tar.gz`, SHA-256 `919fd635ad5801f30d9ef6da0bb99e854ed4c3cd1357dc8ada4a39b8171a41bc`.

Our check found no License/License-Expression/License-File fields in their metadata and no license-named archive members. The `v2.0.2` tag resolves to `c5f9144aa065706294c7e43ae1b954fd0a8d9039`; its pyproject matches the sdist, but we did not find a LICENSE file or an explicit license declaration there. The current main branch has an Apache-2.0 license, while the oss branch identifies itself as version 1.5.0. We do not want to assume that either covers a distinct historical release.

Could a maintainer please:

1. Confirm the license and copyright notices that apply to these exact 2.0.2 artifacts, including generated SDK code.
2. Provide a canonical, version-bound license statement or source location, and confirm whether the current Apache-2.0 text is intended to cover this release.
3. Indicate which notices should accompany redistribution of this package.

Related issue [#304](https://github.com/getzep/zep-python/issues/304) concerns metadata for `zep-cloud`; this question is specifically about the distinct historical `zep-python` 2.0.2 artifacts.

We are asking for release-specific evidence, rather than suggesting that missing metadata alone proves the code has no license.

Sources: [PyPI 2.0.2](https://pypi.org/project/zep-python/2.0.2/), [exact source](https://github.com/getzep/zep-python/tree/c5f9144aa065706294c7e43ae1b954fd0a8d9039).
