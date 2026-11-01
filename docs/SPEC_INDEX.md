# Spec 索引

更新日期：2026-10-31（America/Los_Angeles）。固定 Contract、交付、技术结果、风险接受和最终接受分别记录。

| ID | 标题 | Contract / 版本 | 交付状态 | 依赖与验证覆盖 | 路径 | 下一步 |
|---|---|---|---|---|---|---|
| ARC-UPGRADE | AI Review Console 完善及后续升级 | approved / 0.1.0，固定字节不变 | implementing；WP-05 发布问题未关闭，continuous；完整 last_verified=null，最终接受 pending | `fac92ea` 的 CI `41259579902` 实际 success：154 Python、29 前端、真实四格式/三决定/九报告、浏览器；精确四镜像包级审计与许可材料已采集；原生 arm64 pins/pip check/Flow及虚构数据保全已复验。AC-19 有未解决漏洞与镜像许可事项，不标完整 verified | [UPGRADE_SPEC.md](UPGRADE_SPEC.md) | 按固定 [发布验收](evidence/v02-release/README.md) 关闭兼容升级、上游/厂商及许可材料问题；本地构建先处理容量警戒，再以新证据申请技术及最终接受 |

负责人的确切授权、保护边界、manifest 指纹、产物条件与冷启动入口见 [CURRENT_STATE.md](CURRENT_STATE.md)。固定 Spec 的编制时 review/not_authorized 字段不覆盖后续已记录批准，也不据修补或 CI 绿色自动改变最终接受。

[上轮收尾证据](evidence/v02-acceptance/README.md)保留原字节和原源码/环境适用范围。公开 GitHub 和 [静态虚构数据沙盒](ONLINE_DEMO.md)已另获授权；该沙盒不连接真实后端，不作为真实工作流验收替代。本轮仅同步源码/文档/证据，没有重新部署在线站点、发布真实后端镜像或接受剩余风险。

后续路线继续沿固定 Spec：先 WP-05，再 WP-08；WP-06..07 的模型及 WP-09 生产化仍有独立选择与授权。没有另建重复路线图。

历史入口保持原名：[DEVELOPMENT_PLAN.md](DEVELOPMENT_PLAN.md)、[ARCHITECTURE.md](ARCHITECTURE.md)、[VERIFICATION.md](VERIFICATION.md)、[SESSION_HANDOFF.md](SESSION_HANDOFF.md)。其中旧完成陈述或容器记录不能代替当前绑定证据。
