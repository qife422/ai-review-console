# Spec 索引

更新日期：2026-11-05（America/Los_Angeles）。固定Contract、交付、技术结果、风险接受和最终接受分别记录。

| ID | 标题 | Contract / 版本 | 交付状态 | 依赖与验证覆盖 | 路径 | 下一步 |
|---|---|---|---|---|---|---|
| ARC-UPGRADE | AI Review Console 完善及后续升级 | approved/0.1.0，固定字节不变 | implementing；WP-05仍open；完整last_verified=null，最终接受pending | AMD专项5项故障/PDF恢复/20×1MiB性能通过；编辑器通过虚构副本改名、保存、重载及API回读（C专项success，305项Python/29项前端通过）；候选AMD/ARM独立334包/4工具SHA锁；e6f6fe7/CI41979142562通过271/29、默认/候选双架构后端及AMD浏览器；前轮AMD480246c/CI41954322019检查点升级/旧版恢复通过，不继承ARM；ARM候选PyPI0、Debian132/native分发仍open | [UPGRADE_SPEC.md](UPGRADE_SPEC.md) | 依[本轮专项实证](evidence/candidate-acceptance/README.md)补Mac宿主、ARM迁移/管理验证及系统许可，再按AD-03决定默认升级；之后WP-08 |

确切授权、保护边界、manifest、产物规则与冷启动入口见[CURRENT_STATE.md](CURRENT_STATE.md)。用户已把同目标累计预算扩至360分钟，既有计量保留；默认1.11.6和原数据不变。固定Spec编制时review/not_authorized字段不覆盖后续批准；局部CI成功不改变完整发布或最终接受。

[本轮编辑器/恢复/性能](evidence/candidate-acceptance/README.md)、[前轮ARM验收](evidence/langflow-arm/README.md)、[前轮依赖锁/迁移验收](evidence/langflow-transition/README.md)与[上轮精简候选](evidence/langflow-candidate/README.md)分别绑定精确source/run/image，七旧封存包原字节保留。公开GitHub和[静态虚构数据沙盒](ONLINE_DEMO.md)已另获授权；本轮没有重新部署站点、发布真实后端镜像、切换默认或接受残余风险。

沿固定Spec先WP-05、再WP-08；WP-06..07模型与WP-09生产化仍有独立选择。历史入口保持原名：[DEVELOPMENT_PLAN.md](DEVELOPMENT_PLAN.md)、[ARCHITECTURE.md](ARCHITECTURE.md)、[VERIFICATION.md](VERIFICATION.md)、[SESSION_HANDOFF.md](SESSION_HANDOFF.md)；旧完成陈述不代替当前绑定证据。
