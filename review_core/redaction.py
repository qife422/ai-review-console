from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass
from typing import Any

REDACTION_POLICY_VERSION = "2026.10.1"


@dataclass(frozen=True)
class RedactionMatch:
    category: str
    start: int
    end: int
    placeholder: str
    section_id: str = ""
    offset_basis: str = "original_unicode_code_points"


@dataclass(frozen=True)
class RedactionResult:
    text: str
    matches: list[RedactionMatch]
    policy_version: str = REDACTION_POLICY_VERSION

    def to_dict(self) -> dict[str, object]:
        return {
            "text": self.text,
            "matches": [asdict(match) for match in self.matches],
            "policy_version": self.policy_version,
            "policy_hash": REDACTION_POLICY_HASH,
            "count": len(self.matches),
        }


PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "EMAIL",
        re.compile(r"(?<![\w.-])[\w.+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", re.I),
    ),
    ("PHONE", re.compile(r"(?<!\d)(?:\+86[- ]?)?1[3-9]\d{9}(?!\d)")),
    ("ID", re.compile(r"(?<!\d)\d{17}[0-9Xx](?!\d)")),
    ("BANK_ACCOUNT", re.compile(r"(?<!\d)(?:\d[ -]?){15,19}(?!\d)")),
    (
        "ADDRESS",
        re.compile(r"(?:星河市|云港市|青岚市)[^，。\n]{2,28}(?:路|街|大道)\d{1,4}号"),
    ),
    ("PERSON", re.compile(r"(?:(?:联系人|申请人|负责人|签署人)[:：]\s*)[\u4e00-\u9fff]{2,4}")),
)

REDACTION_POLICY_HASH = hashlib.sha256(
    json.dumps(
        {
            "version": REDACTION_POLICY_VERSION,
            "patterns": [
                {"category": category, "pattern": pattern.pattern, "flags": pattern.flags}
                for category, pattern in PATTERNS
            ],
            "overlap_policy": "leftmost_longest_nonoverlap",
            "placeholder_format": "[{category}_{count:02d}]",
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
).hexdigest()


def policy_hash() -> str:
    return REDACTION_POLICY_HASH


@dataclass(frozen=True)
class RedactionDocument:
    sections: list[dict[str, Any]]
    matches: list[RedactionMatch]
    warnings: list[str]
    policy_version: str = REDACTION_POLICY_VERSION

    @property
    def text(self) -> str:
        return "\n\n".join(section["text"] for section in self.sections)

    def to_dict(self) -> dict[str, Any]:
        return {
            "sections": self.sections,
            "matches": [asdict(match) for match in self.matches],
            "warnings": self.warnings,
            "count": len(self.matches),
            "policy_version": self.policy_version,
            "policy_hash": REDACTION_POLICY_HASH,
            "redaction_policy_version": self.policy_version,
            "redaction_policy_hash": REDACTION_POLICY_HASH,
        }


def redact_sections(sections: Iterable[Mapping[str, Any]]) -> RedactionDocument:
    """Redact each section independently while assigning document-wide placeholder IDs."""
    output: list[dict[str, Any]] = []
    all_matches: list[RedactionMatch] = []
    counts: dict[str, int] = {}
    identities: set[str] = set()
    for index, section in enumerate(sections, start=1):
        section_id = str(section.get("section_id") or f"section-{index:04d}")
        locator = str(section.get("locator") or "")
        text = section.get("text")
        if not locator or not isinstance(text, str) or section_id in identities:
            raise ValueError("Sections must have unique IDs, a locator and text")
        identities.add(section_id)
        result = _redact(text, counts, section_id)
        output.append(
            {
                "index": int(section.get("index", index)),
                "section_id": section_id,
                "locator": locator,
                "text": result.text,
            }
        )
        all_matches.extend(result.matches)
    if not output:
        raise ValueError("A parsed document must contain at least one section")
    return RedactionDocument(output, all_matches, [])


def redact_text(text: str) -> RedactionResult:
    return _redact(text, {}, "")


def _redact(text: str, counts: dict[str, int], section_id: str) -> RedactionResult:
    candidates: list[tuple[int, int, str]] = []
    for category, pattern in PATTERNS:
        candidates.extend(
            (match.start(), match.end(), category) for match in pattern.finditer(text)
        )

    candidates.sort(key=lambda item: (item[0], -(item[1] - item[0])))
    accepted: list[tuple[int, int, str]] = []
    cursor = -1
    for start, end, category in candidates:
        if start >= cursor:
            accepted.append((start, end, category))
            cursor = end

    matches: list[RedactionMatch] = []
    chunks: list[str] = []
    cursor = 0
    for start, end, category in accepted:
        counts[category] = counts.get(category, 0) + 1
        placeholder = f"[{category}_{counts[category]:02d}]"
        chunks.append(text[cursor:start])
        chunks.append(placeholder)
        matches.append(
            RedactionMatch(
                category=category,
                start=start,
                end=end,
                placeholder=placeholder,
                section_id=section_id,
            )
        )
        cursor = end
    chunks.append(text[cursor:])
    return RedactionResult(text="".join(chunks), matches=matches)
