# Spec 索引

更新日期：2026-10-08（America/Los_Angeles）。本索引定位候选、实施状态与下一步，完整要求见对应Spec；源码/测试/配置是实际行为的权威来源。

| ID | 标题 | Contract状态 | 活动版本 | 实施状态 | 依赖 | 升级已验证覆盖 | 路径 | 建议下一步 |
|---|---|---|---|---|---|---|---|---|
| ARC-UPGRADE | AI Review Console 完善及后续升级 | approved | 0.1.0 | implementing，WP-00..05 continuous | 现有演示实现，输入指纹见baseline | 升级运行验收待执行；单元测试正在扩展 | [UPGRADE_SPEC.md](UPGRADE_SPEC.md) | 隔离环境验证真实上传、Intake、审批、Decision及下载 |

固定指纹、负责人的明确确认与实施授权、复核结果和保护边界见 [CURRENT_STATE.md](CURRENT_STATE.md)。Spec正文保留确认时字节，其中编制状态不覆盖本索引的后续授权。next step本身不构成新的计费、生产部署、旧数据迁移或清理授权。

历史资料保持原名称：

- [DEVELOPMENT_PLAN.md](DEVELOPMENT_PLAN.md)：原始开发意图，其中的完成描述不能代替当前实际能力核对。
- [ARCHITECTURE.md](ARCHITECTURE.md)：旧目标架构，自动链路尚未完整落地。
- [VERIFICATION.md](VERIFICATION.md)：2026-09-01的历史运行/构建记录。
- [SESSION_HANDOFF.md](SESSION_HANDOFF.md)：历史暂停和续接记录，不是当前运行状态。
