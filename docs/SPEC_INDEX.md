# Spec 索引

更新日期：2026-11-04（America/Los_Angeles）。固定 Contract、交付、技术结果、风险接受和最终接受分别记录。

| ID | 标题 | Contract / 版本 | 交付状态 | 依赖与验证覆盖 | 路径 | 下一步 |
|---|---|---|---|---|---|---|
| ARC-UPGRADE | AI Review Console 完善及后续升级 | approved/0.1.0，固定字节不变 | implementing；WP-05仍open；完整last_verified=null，最终接受pending | 默认1.11.6基线32eb636/CI41940799240通过194/29；隔离候选1.13.1 e73ab92/CI41943564415通过198/29、完整业务及GUI登录；候选PyPI0但Debian133/native分发未闭合 | [UPGRADE_SPEC.md](UPGRADE_SPEC.md) | 依[候选实证](evidence/langflow-candidate/README.md)补锁定/系统/许可与迁移回滚，再按AD-03决定默认升级；发布条件后WP-08 |

负责人的确切授权、保护边界、manifest 指纹、产物条件与冷启动入口见 [CURRENT_STATE.md](CURRENT_STATE.md)。固定 Spec 的编制时 review/not_authorized 字段不覆盖后续已记录批准，也不据修补或 CI 绿色自动改变最终接受。

[上轮收尾证据](evidence/v02-acceptance/README.md)保留原字节和原源码/环境适用范围。公开 GitHub 和 [静态虚构数据沙盒](ONLINE_DEMO.md)已另获授权；该沙盒不连接真实后端，不作为真实工作流验收替代。本轮仅同步源码/文档/证据，没有重新部署在线站点、发布真实后端镜像或接受剩余风险。

后续路线继续沿固定 Spec：先 WP-05，再 WP-08；WP-06..07 的模型及 WP-09 生产化仍有独立选择与授权。没有另建重复路线图。

历史入口保持原名：[DEVELOPMENT_PLAN.md](DEVELOPMENT_PLAN.md)、[ARCHITECTURE.md](ARCHITECTURE.md)、[VERIFICATION.md](VERIFICATION.md)、[SESSION_HANDOFF.md](SESSION_HANDOFF.md)。其中旧完成陈述或容器记录不能代替当前绑定证据。
