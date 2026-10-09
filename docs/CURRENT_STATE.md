# 当前状态

更新日期：2026-10-08（America/Los_Angeles）。这是项目冷启动和下一步工作的入口；实施要求以已确认的固定Spec为准，实际行为以源码、测试和运行观察为准。

授权依据：负责人在计划交付后明确表示“可以 开始吧 按我的开发范式完成升级”。该指令同时确认固定候选 `ARC-UPGRADE@0.1.0`（下表指纹）并授权 P0/P1、WP-00..05 连续实施。Spec 原文件作为确认时的完整固定输入保留，其内 review/not_authorized 是编制时状态；当前审批和执行状态以本文件及索引为准，不修改已确认语义。模型/预算/OCR/生产化仍需后续选择。

## 阶段与候选

| 事项 | 当前值 |
|---|---|
| 项目实际状态 | 可演示的小型参考实现；新增文件到Langflow、入库、审批与报告的自动链路未接通 |
| 当前工作 | P0/P1 主链路升级实施；先隔离运行、再绑定验收 |
| 候选Contract | ARC-UPGRADE@0.1.0，contract_status=approved；固定正文未改 |
| 升级实施 | delivery_state=implementing，WP-00..05，continuous |
| 内部复核结论 | Ready：可进入P0/P1的Contract确认；P2/P3可选项和P4有明确后续选择点 |
| 升级技术验收 | last_verified=null；本候选AC尚未执行 |
| 升级最终接受 | pending |
| 本轮授权 | 本地源码/配置/UI/测试升级、必要运行和隔离迁移演练、最小证据 |
| 功能实施授权 | P0/P1；无付费调用、真实文档、公网或生产写入、历史清理授权 |
| 部署/计费/清理授权 | 无 |
| Docker | 已启动；新隔离 Compose project=ai-review-console-upgrade，旧容器/卷未启动或改写 |
| Git | 已建立仅本地Git；即将留下首个已验证切片检查点；无远端/推送 |

## 固定输入与复核

| 文件 | SHA-256 | 用途 |
|---|---|---|
| [UPGRADE_SPEC.md](UPGRADE_SPEC.md) | `a77947d0369566cef516641ef918e37d08046afc2edf8215dcff90d49ce01753` | 当前候选全文；后续授权绑定该版本/指纹 |
| [spec-baseline.json](spec-baseline.json) | `5ad13f524e74554b9c8cb30b9809ffbbbbed8e3d7fa4ede5625bb1b7d781bf2e` | 49个源码/配置/依赖输入的逐文件清单与指纹 |

本轮实际检查：23个需求ID、24个AC、10个WP唯一；49个输入的字节大小和SHA-256全部回读匹配，未修改业务源码。Spec引用的本地文档可发现，没有未填写的占位内容。

内部只读评审与修正文案后的单独复核，均针对固定候选。它是文档一致性检查，不是第三方安全审计，也不是升级运行验收。

| Finding | 内容 | 状态 | 复核结果 |
|---|---|---|---|
| SF-01 | 执行token与租约恢复冲突 | closed | token绑定attempt；恢复同一run不轮换，过时attempt不能覆盖 |
| SF-02 | 报告partial、格式失败与决定后重试未定义 | closed | group与格式状态分开，专用reports/retry只补失败/缺失格式 |
| SF-03 | WP-01引用了后续新链路验收 | closed | 限定P0子项，完整版本/Flow验收保留在后续WP |
| SF-04 | 决定接口返回与现有CaseDetail不一致 | closed | 保留完整CaseDetail，增量附加任务信息 |
| SF-05 | 双份正文可能超过callback限制 | closed | sections为正文权威，禁止重复完整text |
| SF-06 | 未评分null与旧客户端兼容未明确 | closed | 不显示假0分，API与支持unknown的新前端共同发布 |

## 已知能力与证据边界

- 12个预置虚构案件；总览、队列、脱敏对照、规则证据、三种决定与报告函数已实现。
- 5个可信Langflow组件与两条示例Flow存在；真实执行记录来自历史集成验证。
- 本次状态核对复跑：Python 9项测试、前端1项测试、TypeScript检查通过。它们只证明当前测试覆盖的演示行为，不覆盖本升级AC。
- 当前网页不支持上传新文件；网关未持久化新结果；决定未触发真实报告Flow；评分未调用LLM；PDF中文、并发审批、导出门禁、镜像标签与文档差异已列入Spec。
- 历史镜像/SBOM/漏洞结果只在其旧输入与日期范围内有效；新发布须重新扫描。

## 下一工作包与保护范围

活动WP：WP-00基线已只读确认；WP-01..04并行实现，WP-05待整栈运行。旧 SQLite `review_console.sqlite3` 为57,344字节，12案件、17审计；不对原库实施迁移。新隔离PostgreSQL卷为`ai-review-console-upgrade_postgres-data`，文档/报告/config卷均同项目前缀。旧`ai-review-console_postgres-data`及`ai-review-console_report-artifacts`保持原状。版本化迁移必须在明确隔离目标显式运行，旧库默认拒绝启动迁移。

成本估算：首个可运行切片30–90分钟，整轮约2–4小时/3–8万token（非计费统计）。主要不确定性为Langflow兼容、故障恢复、镜像扫描和浏览器验收。达到估算两倍或容量阈值时停止可选扩张并重新估算。

负责人确认候选并授权指定WP后，默认continuous：在范围内连续编辑、诊断、修复和验证，不逐步要求继续。需要改变人工审批/数据语义、越过保护范围、付费/外部写入、不可恢复迁移、产物阈值触发时暂停受影响部分。普通可逆技术故障三轮有证据且无进展后保留现场并报告。

保护范围：现有数据库和Docker卷、历史fixtures/报告/截图/SBOM、已记录决定、无关用户修改。产物阈值见Spec §16。只读盘点：.venv261MiB、node_modules460MiB、dist2.8MiB、历史compliance792KiB/screenshots384KiB/Flow44KiB；cache_state=within_threshold。新字体约10MiB（OFL、资源hash及来源附资产）；正式证据尚未封存。pending_cleanup=true；无清理/压缩/历史迁移授权。

后续选择：P2模型/预算/出口、P3是否OCR、P4生产部署/身份/数据范围。这些选择不阻止P0/P1候选评审。

## 最小阅读顺序

适用AGENTS → 本文件 → [SPEC_INDEX.md](SPEC_INDEX.md) → [UPGRADE_SPEC.md](UPGRADE_SPEC.md) → 当前WP涉及的源码/配置与基线。只有解决冲突时才读取历史SESSION_HANDOFF，不从历史容器运行记录判断当前状态。
