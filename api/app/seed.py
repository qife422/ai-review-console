from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from review_core.redaction import redact_text
from review_core.risk import score_document

from .models import AuditEvent, ReviewCase

SEED_CASES = (
    (
        "RC-260901-001",
        "数据处理补充协议",
        "dpa-synthetic.pdf",
        "负责人：林晞，个人手机号 13800138001。供应方承担全部损失，且不设责任上限。",
    ),
    (
        "RC-260901-002",
        "年度软件订阅续约",
        "renewal-synthetic.docx",
        "联系人：周予安。服务将在到期前三日自动续约，客户可书面退出。",
    ),
    (
        "RC-260901-003",
        "安全运维服务说明",
        "security-synthetic.md",
        "使用共享账号和明文密码完成紧急运维，通用管理员账号由双方保管。",
    ),
    (
        "RC-260901-004",
        "采购付款条款",
        "payment-synthetic.pdf",
        "申请人：宋知遥。签约后预付款90%，其余款项在最终验收后支付。",
    ),
    (
        "RC-260901-005",
        "标准保密协议",
        "nda-synthetic.docx",
        "双方仅为项目评估目的使用机密信息，责任上限为已支付费用。",
    ),
    (
        "RC-260901-006",
        "顾问服务工作说明",
        "sow-synthetic.txt",
        "联系人：程嘉屿，邮箱 cheng.jiayu@example.com，项目按月验收并付款。",
    ),
    (
        "RC-260901-007",
        "数据导出申请",
        "export-synthetic.md",
        "申请人：许念，身份证 11010119900307991X，家庭住址星河市观澜路88号。",
    ),
    (
        "RC-260901-008",
        "渠道合作协议",
        "partner-synthetic.pdf",
        "平台可单方变更结算规则，无需另行通知，合作方承担全部损失。",
    ),
    (
        "RC-260901-009",
        "设备试用确认",
        "trial-synthetic.txt",
        "设备仅用于内部测试，试用期结束后归还，无自动续约。",
    ),
    (
        "RC-260901-010",
        "培训服务订单",
        "training-synthetic.docx",
        "负责人：顾清和。课程完成后十个工作日内付款，双方确认交付清单。",
    ),
    (
        "RC-260901-011",
        "托管服务变更单",
        "hosting-synthetic.md",
        "服务方可单方变更服务区域，客户预付款80%，变更无需另行通知。",
    ),
    (
        "RC-260901-012",
        "访问权限例外申请",
        "access-synthetic.pdf",
        "申请人：沈砚，使用通用管理员账号访问测试环境，期限为七天。",
    ),
)

STATUSES = (
    "pending_approval",
    "pending_approval",
    "pending_approval",
    "approved",
    "approved",
    "ready",
    "changes_requested",
    "rejected",
    "ready",
    "approved",
    "pending_approval",
    "pending_approval",
)

OWNERS = ("林澈", "梁书宁", "陈闻野", "叶庭安")


def seed_database(session: Session) -> None:
    count = session.scalar(select(func.count()).select_from(ReviewCase)) or 0
    if count:
        return
    now = datetime.now(UTC)
    for index, (case_id, title, filename, original) in enumerate(SEED_CASES):
        redaction = redact_text(original)
        assessment = score_document(redaction.text)
        status = STATUSES[index]
        decision = status if status in {"approved", "rejected", "changes_requested"} else None
        submitted_at = now - timedelta(hours=3 * index + 1)
        case = ReviewCase(
            id=case_id,
            title=title,
            document_name=filename,
            document_type=filename.rsplit(".", 1)[-1].upper(),
            document_hash=hashlib.sha256(original.encode()).hexdigest(),
            status=status,
            risk_score=assessment.score,
            risk_level=assessment.level,
            owner=OWNERS[index % len(OWNERS)],
            submitted_at=submitted_at,
            due_at=submitted_at + timedelta(hours=24 + index),
            original_text=f"SYNTHETIC DEMO DOCUMENT\nNorthstar Example Labs\n\n{original}",
            redacted_text=f"SYNTHETIC DEMO DOCUMENT\nNorthstar Example Labs\n\n{redaction.text}",
            findings_json=json.dumps(
                [finding.__dict__ for finding in assessment.findings], ensure_ascii=False
            ),
            dimensions_json=json.dumps(assessment.dimensions, ensure_ascii=False),
            warnings_json="[]",
            pii_count=len(redaction.matches),
            decision=decision,
            decision_reason="虚构演示审批记录，条款已完成复核。" if decision else None,
            decided_by=OWNERS[(index + 1) % len(OWNERS)] if decision else None,
            decided_at=submitted_at + timedelta(hours=2) if decision else None,
            flow_run_id=f"lf-demo-{index + 1:04d}",
        )
        session.add(case)
        # No ORM relationship is used here; flush the parent explicitly before
        # adding its FK-bound audit events on PostgreSQL.
        session.flush()
        session.add(
            AuditEvent(
                case_id=case_id,
                event_type="case_scored",
                actor="Langflow Intake Flow",
                detail=f"规则评分完成，风险分数 {assessment.score}。",
                occurred_at=submitted_at,
            )
        )
        if decision:
            decision_label = {
                "approved": "批准",
                "rejected": "驳回",
                "changes_requested": "要求修改",
            }[decision]
            session.add(
                AuditEvent(
                    case_id=case_id,
                    event_type="decision_recorded",
                    actor=case.decided_by or "synthetic-reviewer",
                    detail=f"决定：{decision_label}。虚构演示审批记录。",
                    occurred_at=case.decided_at or submitted_at,
                )
            )
    session.commit()
