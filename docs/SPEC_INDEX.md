# Spec 索引

更新日期：2026-10-28（America/Los_Angeles）。本索引定位活动 Contract、实施状态与下一步；固定要求见对应 Spec，源码/测试/配置和本轮运行证据决定实际能力。

| ID | 标题 | Contract状态 | 活动版本 | 实施状态 | 依赖 | 升级已验证覆盖 | 路径 | 建议下一步 |
|---|---|---|---|---|---|---|---|---|
| ARC-UPGRADE | AI Review Console 完善及后续升级 | approved | 0.1.0 | implementing；WP-00..04 主体与功能/运行验证已有实际结果，WP-05 发布缺口未关闭；continuous | 本轮起点 14d44b1；字体 CI 85dddfd 已回读；修复代码 540fd4c 的 CI 40819513529 已 success；固定 baseline 为 10/8 历史输入 | 四格式/三决定/九下载、PG 并发、故障/隔离恢复、PDF/locator、路由补验及 20×1MiB 性能已观察；最终代码 CI 的 128 Python/29 前端/真实 workflow-browser 已回读通过，AC-19 failed/blocked | [UPGRADE_SPEC.md](UPGRADE_SPEC.md) | 本轮验收记录已封存并对齐；接续修补依赖重测、补镜像扫描/许可证复核，齐备后申请技术及最终接受 |

固定指纹、负责人的确认及本轮收尾/GitHub 同步授权、局部通过与待解决项、保护边界和下一步见 [CURRENT_STATE.md](CURRENT_STATE.md)。固定 Spec 正文保留确认时字节，其中编制状态不覆盖后续授权；最终接受仍 `pending`，完整 v0.2 尚未标记 `verified`。

公开 GitHub 和 [静态在线沙盒](ONLINE_DEMO.md)已另获授权并交付；沙盒只使用预置虚构数据、在浏览器内模拟，不继承为真实后端的 AC 证据。路线表中的下一步不构成新的模型计费、生产部署、旧数据迁移或清理授权。

历史资料保持原名称：

- [DEVELOPMENT_PLAN.md](DEVELOPMENT_PLAN.md)：原始开发意图，其中的完成描述不能代替当前实际能力核对。
- [ARCHITECTURE.md](ARCHITECTURE.md)：架构说明；当前已实现能力和验收边界以活动状态及实际代码为准。
- [VERIFICATION.md](VERIFICATION.md)：2026-09-01的历史运行/构建记录。
- [SESSION_HANDOFF.md](SESSION_HANDOFF.md)：历史暂停和续接记录，不是当前运行状态。
