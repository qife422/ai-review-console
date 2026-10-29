"""Reproduce the selected synthetic AC-12 report from snapshot.json.
Run from repository root: .venv/bin/python verify-pdf.py INPUT_SNAPSHOT NEW_OUTPUT_DIR
The new output directory must not exist. No database or service is used.
"""
from pathlib import Path
import hashlib, json, subprocess, sys
from pypdf import PdfReader
from review_core.reporting import build_json_report, build_html_report, build_pdf_report
source, target = Path(sys.argv[1]), Path(sys.argv[2])
target.mkdir(exist_ok=False)
snapshot = json.loads(source.read_text())
for fmt, builder in (("json", build_json_report), ("html", build_html_report), ("pdf", build_pdf_report)):
    value = builder(snapshot)
    (target / ("report." + fmt)).write_bytes(value if isinstance(value, bytes) else value.encode())
subprocess.run(["pdftoppm", "-r", "100", "-png", str(target / "report.pdf"), str(target / "page")], check=True)
text = [page.extract_text() or "" for page in PdfReader(target / "report.pdf").pages]
(target / "extracted-pages.json").write_text(json.dumps(text, ensure_ascii=False, indent=2))
print(json.dumps({"pages": len(text), "pdf_sha256": hashlib.sha256((target / "report.pdf").read_bytes()).hexdigest()}))
