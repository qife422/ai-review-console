from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass
from typing import Any

RULESET_VERSION = "2026.10.1"
OFFSET_BASIS = "unicode_code_points"


@dataclass(frozen=True)
class RiskFinding:
    rule_id: str
    category: str
    title: str
    severity: str
    points: int
    evidence: str
    recommendation: str
    section_id: str = ""
    locator: str = ""
    start: int = 0
    end: int = 0
    offset_basis: str = OFFSET_BASIS


@dataclass(frozen=True)
class RiskAssessment:
    score: int
    level: str
    dimensions: dict[str, int]
    findings: list[RiskFinding]
    ruleset_version: str = RULESET_VERSION

    def to_dict(self) -> dict[str, object]:
        return {
            "score": self.score,
            "level": self.level,
            "dimensions": self.dimensions,
            "findings": [asdict(finding) for finding in self.findings],
            "ruleset_version": self.ruleset_version,
            "ruleset_hash": RULESET_HASH,
        }


RULES: tuple[dict[str, object], ...] = (
    {
        "id": "PRIV-001",
        "category": "privacy",
        "title": "检测到个人信息字段",
        "severity": "high",
        "points": 24,
        "pattern": re.compile(r"身份证|个人手机号|家庭住址"),
        "recommendation": "在分发前完成个人信息最小化和脱敏复核。",
    },
    {
        "id": "LEGAL-002",
        "category": "legal",
        "title": "责任上限缺失或无限责任",
        "severity": "critical",
        "points": 28,
        "pattern": re.compile(r"无限责任|不设责任上限|承担全部损失"),
        "recommendation": "增加明确、对等且可量化的责任上限。",
    },
    {
        "id": "FIN-003",
        "category": "financial",
        "title": "异常预付款比例",
        "severity": "high",
        "points": 20,
        "pattern": re.compile(r"(?:预付|预付款)[^。\n]{0,12}(?:80|90|100)%"),
        "recommendation": "改为按里程碑分期付款并绑定验收条件。",
    },
    {
        "id": "SEC-004",
        "category": "security",
        "title": "允许共享账号或明文凭据",
        "severity": "critical",
        "points": 26,
        "pattern": re.compile(r"共享账号|明文密码|通用管理员账号"),
        "recommendation": "要求独立身份、最小权限和凭据安全存储。",
    },
    {
        "id": "POL-005",
        "category": "policy",
        "title": "自动续约通知期不足",
        "severity": "medium",
        "points": 13,
        "pattern": re.compile(r"自动续约[^。\n]{0,18}(?:3日|三日|5日|五日)"),
        "recommendation": "延长续约提醒窗口并提供显式退出方式。",
    },
    {
        "id": "LEGAL-006",
        "category": "legal",
        "title": "单方变更权",
        "severity": "medium",
        "points": 15,
        "pattern": re.compile(r"单方变更|无需另行通知"),
        "recommendation": "要求实质变更经双方书面确认。",
    },
)

RULESET_HASH = hashlib.sha256(
    json.dumps(
        {
            "version": RULESET_VERSION,
            "rules": [
                {
                    **{key: value for key, value in rule.items() if key != "pattern"},
                    "pattern": rule["pattern"].pattern,
                    "flags": rule["pattern"].flags,
                }
                for rule in RULES
            ],
            "thresholds": [25, 50, 75],
            "score_policy": "unique_rule_points_capped_100",
            "dimension_multiplier": 3,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
).hexdigest()


def ruleset_hash() -> str:
    return RULESET_HASH


def _excerpt_bounds(text: str, start: int, end: int, radius: int = 28) -> tuple[int, int]:
    left = max(0, start - radius)
    right = min(len(text), end + radius)
    last_open = text.rfind("[", 0, left + 1)
    last_close = text.rfind("]", 0, left + 1)
    if last_open > last_close:
        left = last_open
    last_open_before_right = text.rfind("[", 0, right)
    last_close_before_right = text.rfind("]", 0, right)
    if last_open_before_right > last_close_before_right:
        next_close = text.find("]", right)
        if next_close != -1:
            right = next_close + 1
    while left < right and text[left].isspace():
        left += 1
    while right > left and text[right - 1].isspace():
        right -= 1
    return left, right


def _excerpt(text: str, start: int, end: int, radius: int = 28) -> str:
    left, right = _excerpt_bounds(text, start, end, radius)
    return text[left:right]


def score_document(text: str) -> RiskAssessment:
    return score_sections([{"section_id": "section-0001", "locator": "block:1", "text": text}])


def score_sections(sections: Iterable[Mapping[str, Any]]) -> RiskAssessment:
    """Locate a rule's first evidence while preserving the original unique-rule scoring."""
    section_list = list(sections)
    if not section_list:
        raise ValueError("Scoring requires a parsed, redacted document")
    identities: set[str] = set()
    for section in section_list:
        section_id = section.get("section_id")
        if (
            not isinstance(section_id, str)
            or not section_id
            or section_id in identities
            or not section.get("locator")
            or not isinstance(section.get("text"), str)
        ):
            raise ValueError("Scoring sections must have unique IDs, locators and text")
        identities.add(section_id)
    findings: list[RiskFinding] = []
    dimensions = {"privacy": 0, "legal": 0, "financial": 0, "security": 0, "policy": 0}
    for rule in RULES:
        pattern = rule["pattern"]
        assert isinstance(pattern, re.Pattern)
        hit = next(
            (
                (section, match)
                for section in section_list
                if (match := pattern.search(section["text"]))
            ),
            None,
        )
        if hit is None:
            continue
        section, match = hit
        text = section["text"]
        left, right = _excerpt_bounds(text, match.start(), match.end())
        category = str(rule["category"])
        points = int(rule["points"])
        dimensions[category] = min(100, dimensions[category] + points * 3)
        findings.append(
            RiskFinding(
                rule_id=str(rule["id"]),
                category=category,
                title=str(rule["title"]),
                severity=str(rule["severity"]),
                points=points,
                evidence=text[left:right],
                recommendation=str(rule["recommendation"]),
                section_id=section["section_id"],
                locator=str(section["locator"]),
                start=left,
                end=right,
            )
        )

    score = min(100, sum(finding.points for finding in findings))
    if score >= 75:
        level = "critical"
    elif score >= 50:
        level = "high"
    elif score >= 25:
        level = "medium"
    else:
        level = "low"
    return RiskAssessment(score=score, level=level, dimensions=dimensions, findings=findings)
