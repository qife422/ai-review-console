from __future__ import annotations

import hashlib
import io
import stat
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from xml.etree import ElementTree

from docx import Document
from pypdf import PdfReader

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}
MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_PAGES = 200
MAX_TEXT_BYTES = 1024 * 1024
MAX_DOCX_EXPANDED_BYTES = 100 * 1024 * 1024
MAX_DOCX_MEMBERS = 10_000
SYNTHETIC_MARKER = "SYNTHETIC DEMO DOCUMENT"
PARSER_VERSION = "2026.10.1"
MIME_TYPES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt": "text/plain",
    ".md": "text/markdown",
}
W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


class DocumentParseError(ValueError):
    """A non-retryable input failure safe to expose without source contents."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        self.retryable = False
        super().__init__(detail)


@dataclass(frozen=True)
class ParsedSection:
    index: int
    locator: str
    text: str
    section_id: str = ""

    def to_dict(self) -> dict[str, object]:
        return {**asdict(self), "section_id": self.section_id or f"section-{self.index:04d}"}


@dataclass(frozen=True)
class ParsedDocument:
    filename: str
    mime_type: str
    sha256: str
    text: str
    sections: list[ParsedSection]
    warnings: list[str]
    parser_version: str = PARSER_VERSION

    def to_dict(self) -> dict[str, object]:
        # Sections are the wire authority. The compatibility text is not duplicated.
        return {
            "filename": self.filename,
            "mime_type": self.mime_type,
            "sha256": self.sha256,
            "sections": [section.to_dict() for section in self.sections],
            "warnings": self.warnings,
            "parser_version": self.parser_version,
        }


class _Sections(list[ParsedSection]):
    """Keep the UTF-8 text limit without repeatedly encoding earlier paragraphs."""

    byte_count: int = 0

    def add(self, locator: str, text: str) -> None:
        text = text.strip()
        _check_text(text)
        if not text:
            return
        count = len(text.encode("utf-8")) + (2 if self else 0)
        if self.byte_count + count > MAX_TEXT_BYTES:
            _fail("text_too_large", "Extracted text exceeds the 1 MiB UTF-8 limit")
        self.byte_count += count
        index = len(self) + 1
        self.append(ParsedSection(index, locator, text, f"section-{index:04d}"))


def _fail(code: str, detail: str) -> None:
    raise DocumentParseError(code, detail)


def validate_document_bytes(content: bytes, extension: str) -> None:
    """Validate size and declared type before a document can enter a parsing job."""
    suffix = extension.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        _fail("unsupported_type", "Only PDF, DOCX, TXT and Markdown documents are supported")
    if not content:
        _fail("empty_document", "Document is empty")
    if len(content) > MAX_FILE_BYTES:
        _fail("file_too_large", "Document exceeds the 10 MiB limit")
    is_pdf = content.startswith(b"%PDF-")
    is_zip = content.startswith((b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"))
    if suffix == ".pdf" and not is_pdf:
        _fail("type_mismatch", "Declared PDF does not have a valid PDF header")
    if suffix == ".docx" and not is_zip:
        _fail("type_mismatch", "Declared DOCX is not an OOXML ZIP document")
    if suffix in {".txt", ".md"} and (is_pdf or is_zip):
        _fail("type_mismatch", "Declared text document contains a PDF or ZIP structure")


def _validate_file(path: Path) -> bytes:
    try:
        resolved = path.resolve(strict=True)
        if not resolved.is_file():
            _fail("invalid_document_path", "Document path must point to a regular file")
        if resolved.stat().st_size > MAX_FILE_BYTES:
            _fail("file_too_large", "Document exceeds the 10 MiB limit")
        content = resolved.read_bytes()
    except OSError as exc:
        raise DocumentParseError("document_unavailable", "Document cannot be read") from exc
    validate_document_bytes(content, path.suffix)
    return content


def _check_text(text: str) -> None:
    if "\ufffd" in text or any(ord(char) < 32 and char not in "\n\r\t" for char in text):
        _fail("unsupported_content", "Document contains undecodable or unsupported text")


def _pdf_sections(content: bytes, sections: _Sections, warnings: list[str]) -> None:
    try:
        reader = PdfReader(io.BytesIO(content), strict=True)
        if reader.is_encrypted:
            _fail("encrypted_pdf", "Encrypted PDFs are not supported")
        if len(reader.pages) > MAX_PAGES:
            _fail("page_limit_exceeded", "PDF exceeds the 200 page limit")
        root = reader.trailer["/Root"]
        names = root.get("/Names", {})
        if hasattr(names, "get_object"):
            names = names.get_object()
        if any(key in root for key in ("/OpenAction", "/AA", "/AcroForm")) or any(
            key in names for key in ("/EmbeddedFiles", "/JavaScript")
        ):
            _fail("unsupported_content", "PDF actions, fields and embedded files are unsupported")
        for page_index, page in enumerate(reader.pages, start=1):
            for annotation_ref in page.get("/Annots", []):
                annotation = annotation_ref.get_object()
                if annotation.get("/Subtype") != "/Link":
                    _fail("unsupported_content", "PDF annotations may contain unparsed body text")
            page_text = (page.extract_text() or "").strip()
            if not page_text:
                if len(page.images):
                    _fail("requires_ocr", "A PDF page contains images but no extractable text")
                contents = page.get_contents()
                paint_operators = {
                    b"Do",
                    b"sh",
                    b"S",
                    b"s",
                    b"f",
                    b"F",
                    b"f*",
                    b"B",
                    b"B*",
                    b"b",
                    b"b*",
                }
                if contents is not None and any(
                    operator in paint_operators for _, operator in contents.operations
                ):
                    _fail("unsupported_content", "PDF drawing content has no extractable text")
                warnings.append(f"informational:blank_page:{page_index}")
            sections.add(f"page:{page_index}", page_text)
    except DocumentParseError:
        raise
    except Exception as exc:
        raise DocumentParseError("invalid_pdf", "PDF structure or text cannot be parsed") from exc


def _validate_docx_archive(content: bytes) -> None:
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            members = archive.infolist()
            if len(members) > MAX_DOCX_MEMBERS:
                _fail("docx_member_limit", "DOCX ZIP contains too many members")
            if sum(member.file_size for member in members) > MAX_DOCX_EXPANDED_BYTES:
                _fail("docx_expanded_limit", "DOCX expanded contents exceed the 100 MiB limit")
            names = [member.filename for member in members]
            if len(names) != len(set(names)):
                _fail("invalid_docx", "DOCX ZIP contains duplicate member names")
            required = {"[Content_Types].xml", "_rels/.rels", "word/document.xml"}
            if not required.issubset(names):
                _fail("type_mismatch", "ZIP is not a Word OOXML document")
            for member in members:
                path = PurePosixPath(member.filename)
                if (
                    path.is_absolute()
                    or ".." in path.parts
                    or "\\" in member.filename
                    or (path.parts and ":" in path.parts[0])
                ):
                    _fail("invalid_docx", "DOCX ZIP contains a path outside its document boundary")
                if stat.S_ISLNK(member.external_attr >> 16) or member.flag_bits & 1:
                    _fail(
                        "invalid_docx", "DOCX ZIP contains unsupported links or encrypted members"
                    )
                if member.filename.startswith(("word/embeddings/", "word/activeX/")):
                    _fail(
                        "unsupported_content", "DOCX embedded objects may contain unparsed clauses"
                    )
                if member.filename.endswith(".xml"):
                    data = archive.read(member)
                    if b"<!DOCTYPE" in data or b"<!ENTITY" in data:
                        _fail("invalid_docx", "OOXML external entities are not supported")
                    if member.filename.startswith("word/"):
                        tree = ElementTree.fromstring(data)
                        unsupported = {
                            "object",
                            "pict",
                            "drawing",
                            "txbxContent",
                            "altChunk",
                            "sdt",
                            "ins",
                            "del",
                            "moveFrom",
                            "moveTo",
                            "footnoteReference",
                            "endnoteReference",
                            "subDoc",
                            "instrText",
                            "fldChar",
                            "sym",
                            "ruby",
                        }
                        if any(
                            element.tag.removeprefix(W_NS) in unsupported for element in tree.iter()
                        ):
                            _fail("unsupported_content", "DOCX contains an unparsed body structure")
                        has_auxiliary_text = any(
                            member.filename.startswith(f"word/{part}")
                            for part in ("header", "footer", "footnotes", "endnotes")
                        ) and any((node.text or "").strip() for node in tree.iter(f"{W_NS}t"))
                        if has_auxiliary_text:
                            _fail("unsupported_content", "DOCX has text outside its supported body")
            content_types = archive.read("[Content_Types].xml")
            docx_type = (
                b"application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"
            )
            if docx_type not in content_types:
                _fail("type_mismatch", "OOXML main document is not a supported DOCX document")
    except DocumentParseError:
        raise
    except (zipfile.BadZipFile, KeyError, RuntimeError, ElementTree.ParseError) as exc:
        raise DocumentParseError(
            "invalid_docx", "DOCX ZIP or XML structure cannot be parsed"
        ) from exc


def _docx_sections(content: bytes, sections: _Sections) -> None:
    _validate_docx_archive(content)
    try:
        document = Document(io.BytesIO(content))
        paragraph_number = table_number = 0
        for item in document.element.body:
            if item.tag == f"{W_NS}p":
                paragraph_number += 1
                sections.add(f"paragraph:{paragraph_number}", _paragraph_text(item))
            elif item.tag == f"{W_NS}tbl":
                table_number += 1
                for row_number, row in enumerate(item.findall(f"{W_NS}tr"), start=1):
                    for cell_number, cell in enumerate(row.findall(f"{W_NS}tc"), start=1):
                        if cell.find(f".//{W_NS}tbl") is not None:
                            _fail("unsupported_content", "Nested DOCX tables are not supported")
                        text = "\n".join(
                            _paragraph_text(paragraph) for paragraph in cell.findall(f"{W_NS}p")
                        )
                        sections.add(
                            f"table:{table_number}/row:{row_number}/cell:{cell_number}", text
                        )
            elif item.tag != f"{W_NS}sectPr":
                _fail("unsupported_content", "DOCX body contains an unsupported structure")
    except DocumentParseError:
        raise
    except Exception as exc:
        raise DocumentParseError(
            "invalid_docx", "DOCX paragraphs and tables cannot be parsed"
        ) from exc


def _paragraph_text(element: object) -> str:
    text: list[str] = []
    for node in element.iter():  # type: ignore[attr-defined]
        if node.tag == f"{W_NS}t":
            text.append(node.text or "")
        elif node.tag == f"{W_NS}tab":
            text.append("\t")
        elif node.tag in {f"{W_NS}br", f"{W_NS}cr"}:
            text.append("\n")
    return "".join(text)


def parse_document(file_path: str | Path, *, require_synthetic: bool = True) -> ParsedDocument:
    path = Path(file_path)
    content = _validate_file(path)
    suffix = path.suffix.lower()
    warnings: list[str] = []
    sections = _Sections()
    if suffix == ".pdf":
        _pdf_sections(content, sections, warnings)
    elif suffix == ".docx":
        _docx_sections(content, sections)
    else:
        try:
            decoded = content.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise DocumentParseError(
                "invalid_encoding", "Text documents must use valid UTF-8"
            ) from exc
        for block_number, block in enumerate(decoded.split("\n\n"), start=1):
            sections.add(f"block:{block_number}", block)
    text = "\n\n".join(section.text for section in sections)
    if not text:
        _fail("empty_text", "Document contains no extractable text")
    if require_synthetic and SYNTHETIC_MARKER not in text:
        _fail(
            "synthetic_marker_missing", "Document must contain the synthetic demonstration marker"
        )
    return ParsedDocument(
        filename=path.name,
        mime_type=MIME_TYPES[suffix],
        sha256=hashlib.sha256(content).hexdigest(),
        text=text,
        sections=list(sections),
        warnings=warnings,
    )
