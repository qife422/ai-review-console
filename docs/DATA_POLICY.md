# Synthetic Data Policy

## Rule

The repository, demo database, screenshots, reports and presentations may contain synthetic data only. No company confidential information is allowed.

## Allowed

- fictional organization `Northstar Example Labs`;
- fixed fictional Chinese names created for the demo;
- `example.com`, `example.org` and `example.net` domains;
- generated document identifiers, telephone numbers, addresses and contract clauses explicitly marked synthetic;
- deterministic outputs derived from repository fixtures.

## Prohibited

- real customer, employee, supplier or partner records;
- copied or lightly rewritten production contracts;
- internal domains, hostnames, source URLs or account IDs;
- API keys, access tokens, cookies, passwords or private keys;
- screenshots of real systems or signed-in accounts;
- model prompts or outputs containing confidential context.

## Required markings

Every fixture and exported report includes `SYNTHETIC DEMO DOCUMENT` or `SYNTHETIC DEMO DATA ONLY`. The Web footer and README repeat the same classification.

## Review before release

Run secret scanning and search exported artifacts for unexpected domains, credentials and unmarked documents. Generated reports are not automatically accepted as release evidence until their hashes and source fixture are recorded.

