#!/usr/bin/env python3
"""Bounded official PyPI candidate evidence; stdlib only; no artifact downloads."""
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import sys
import time
import urllib.request

OUT = Path(__file__).resolve().parent
CAP_RESPONSE = 512 * 1024
CAP_TOTAL = 3 * 1024 * 1024
TOTAL = 0
HTTP = []
START = dt.datetime.now(dt.timezone.utc).isoformat()
FILES = ('candidate-metadata.json', 'candidate-summary.json', 'candidate-run.json')
for item in FILES:
    if (OUT / item).exists():
        raise SystemExit('Refusing existing output: ' + item)

def fetch(url):
    global TOTAL
    started = dt.datetime.now(dt.timezone.utc).isoformat()
    t0 = time.monotonic()
    req = urllib.request.Request(url, headers={'User-Agent': 'ARC-candidate-evidence/1 (stdlib, metadata only)', 'Accept': 'application/json,text/html'})
    with urllib.request.urlopen(req, timeout=25) as response:
        body = response.read(CAP_RESPONSE + 1)
        if len(body) > CAP_RESPONSE:
            raise RuntimeError('Response size cap reached')
        TOTAL += len(body)
        if TOTAL > CAP_TOTAL:
            raise RuntimeError('HTTP aggregate cap reached')
        rec = {'url': url, 'final_url': response.url, 'started_at_utc': started,
               'finished_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
               'elapsed_seconds': round(time.monotonic() - t0, 6), 'status': response.status,
               'content_type': response.headers.get('Content-Type'),
               'server_date': response.headers.get('Date'),
               'response_bytes': len(body), 'raw_response_sha256': hashlib.sha256(body).hexdigest()}
    HTTP.append(rec)
    return body, rec

def put(name, value):
    data = (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode()
    with (OUT / name).open('xb') as stream:
        stream.write(data)
    return {'path': name, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}

selected = {'stable': '1.13.0', 'rc': '1.13.1rc2', 'dev': '1.14.0.dev14'}
history_record = {'url': 'https://pypi.org/project/langflow-base/', 'method': 'Official PyPI release history read via web tool immediately before producer; urllib HTML receives Client Challenge. Fixed version inputs independently verified through exact JSON identities.', 'observed_at_utc': '2026-11-03T05:43:25+00:00', 'latest_stable': '1.13.0', 'latest_rc': '1.13.1rc2', 'latest_dev': '1.14.0.dev14', 'raw_html_saved': False}

records = []
matrix = {}
for kind, version in selected.items():
    matrix[kind] = {'version': version, 'packages': {}}
    for package in ('langflow', 'langflow-base', 'lfx'):
        body, provenance = fetch(f'https://pypi.org/pypi/{package}/{version}/json')
        data = json.loads(body)
        info = data['info']
        if info['name'] != package or info['version'] != version:
            raise RuntimeError('Package identity mismatch')
        fields = {key: info.get(key) for key in ('name', 'version', 'requires_python', 'requires_dist', 'provides_extra', 'license', 'license_expression', 'project_urls', 'yanked', 'yanked_reason')}
        fields['release_files_metadata_only'] = [{key: row.get(key) for key in ('filename', 'size', 'packagetype', 'python_version', 'requires_python', 'upload_time_iso_8601', 'digests', 'yanked')} for row in data['urls']]
        records.append({'candidate_kind': kind, 'provenance': provenance, 'fields': fields})
        dependencies = info.get('requires_dist') or []
        matrix[kind]['packages'][package] = {
            'requires_python': info.get('requires_python'), 'yanked': info.get('yanked'),
            'security_constraint_strings': [item for item in dependencies if re.match(r'^(?:pillow|filelock|setuptools)(?:[<>=!~;\[]|$)', item, re.I)],
            'base_lfx_bundle_zep_ibm_requirements': [item for item in dependencies if re.match(r'^(?:langflow-base|lfx|lfx-bundles|lfx-ibm|zep-python)(?:[<>=!~;\[]|$)', item, re.I)]}

metadata = {'schema': 'arc.official-candidate-metadata.v1', 'collection_started_at_utc': START,
            'method': 'stdlib urllib GET official versioned PyPI JSON; retain all Requires-Dist verbatim and selected exact fields; hash original response bytes before JSON extraction; no wheels/sdists/history JSON downloaded or saved',
            'discovery': {'source': history_record, 'selection': 'Fixed exact version inputs from official release history observed by web tool; no general-history JSON downloaded. JSON package/version checked for all nine responses.', 'selected': selected},
            'records': records, 'coverage': 'PyPI metadata only; does not prove installability, Docker image extras, import behavior, support policy, or exploitability'}
files = [put('candidate-metadata.json', metadata)]
summary = {'schema': 'arc.langflow-candidate-assessment.v1', 'collected_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
           'baseline': {'langflow': '1.11.6', 'source': 'a64ab476c8acfaa36a3d6cc260a4c6c286bad380', 'contract': 'ARC-UPGRADE@0.1.0', 'decision': 'Keep current default; no image/Dockerfile/Spec change'},
           'constraint_matrix': matrix,
           'findings': [
               'Stable 1.13.0 does not lift Pillow<13, filelock<4, or setuptools<84.',
               'RC 1.13.1rc2 and current development candidate lift filelock to >=4.2.1,<5 for Python>=3.11; Pillow<13 and setuptools<84 remain in langflow-base and lfx.',
               'Current Python3.14 satisfies candidate Requires-Python, but a complete resolved candidate graph and runtime are not tested by this collection.',
               'Pinned current PyJWT2.15.0 and transformers5.10.0 require reconciliation against candidate floors; all existing52 pins must be checked against exact selected candidate metadata.',
               'Metadata extras and regular dependencies are distinct; historical/default installed extras cannot be inferred from pip check or the top package alone.'
           ],
           'unknowns': {
               'official_docker_installed_bundles_zep_ibm': 'Unknown: no candidate Docker image manifest/content inspected or pulled.',
               'minimal_langflow_base_preserves_admin_ui_api': 'Unknown: metadata summary is not independent proof of startup/static assets/API/Flow import compatibility; do not replace full runtime with bare LFX.',
               'candidate_runtime_installability': 'Unknown: no build, resolver, installation, Docker or CI was run in this task.'},
           'migration_review': {
               'status': 'Planning cautions from earlier official documentation review; pages linked below were not fetched by this producer.',
               'items': ['Recheck authentication default and required superuser credentials for selected exact version.', 'Use a new isolated database; official1.13 timestamp migrations and autostart migrations cannot be tried against original business/history volumes.', 'Recheck Chroma/Local DB deprecation and SQLite Knowledge/Memory migration before attaching any protected directories.'],
               'sources': ['https://www.langflow.org/blog/langflow-1-13/', 'https://docs.langflow.org/database-migrations', 'https://docs.langflow.org/knowledge-storage-upgrade']},
           'candidate_gate': ['Fix exact supported candidate/version/digest/architecture and installed extras before implementation, as required by Spec AD-03 and runtime compatibility requirements.', 'Require a coherent full dependency resolution with no metadata edits/no-deps; explain every changed current pin and new transitive package.', 'Verify component discovery, both real Flows, strict results/callback/report contracts, authentication, admin UI/API and isolated migration/rollback.', 'Rerun offline security/compatibility probes, browser regression, exact-image OS/PyPI/RHEL scans and package/native redistribution-license evidence.'],
           'prerelease_decision': 'Do not automatically adopt RC/dev: they currently offer only partial filelock closure, introduce migration/provider/dependency changes, and lack a project-specific resolved/build/runtime acceptance result. A bounded isolated candidate experiment is a separate concrete step, not a production/default upgrade or risk acceptance.',
           'limits': {'network_payload_total_cap_bytes': CAP_TOTAL, 'response_cap_bytes': CAP_RESPONSE, 'output_cap_bytes': 3 * 1024 * 1024, 'file_cap': 20, 'local_docker_started': False, 'installed_packages': False, 'source_changed': False}}
files.append(put('candidate-summary.json', summary))
producer = Path(__file__).read_bytes()
run = {'schema': 'arc.command-record.v1', 'started_at_utc': START,
       'finished_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(), 'argv': sys.argv,
       'actual_command': f'python3 {Path(__file__).resolve()}', 'exit_code': 0,
       'producer': {'path': str(Path(__file__).resolve()), 'bytes': len(producer), 'sha256': hashlib.sha256(producer).hexdigest()},
       'http_total_bytes': TOTAL, 'http_request_count': len(HTTP), 'requests': HTTP,
       'outputs': files, 'remaining_scope': 'Metadata-only assessment; no runtime adoption or release acceptance'}
files.append(put('candidate-run.json', run))
print(json.dumps({'selected': selected, 'http_bytes': TOTAL, 'request_count': len(HTTP), 'files': files, 'matrix': matrix}, ensure_ascii=False))
