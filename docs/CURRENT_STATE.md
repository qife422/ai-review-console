# 当前状态

更新日期：2026-10-28（America/Los_Angeles）。这是项目冷启动和下一步工作的入口；实施要求以已确认的固定 Spec 为准，实际行为以源码、测试和运行观察为准。

授权依据：负责人先前明确表示“可以 开始吧 按我的开发范式完成升级”，确认固定候选 `ARC-UPGRADE@0.1.0`（下表指纹）并授权 P0/P1、WP-00..05 连续实施。2026-10-28 又明确授权“状态对齐和 v0.2 收尾验收，按我的开发范式推进”，要求整理已通过、待解决问题与后续计划并同步 GitHub。Spec 原文件作为确认时的固定输入保留，其内 `review/not_authorized` 是编制时状态；当前审批和执行状态以本文件及索引为准，不改写已确认语义。

## 阶段与候选

| 事项 | 当前值 |
|---|---|
| 项目实际状态 | v0.2 主链路代码已实现：上传虚构文档、持久化任务、真实 Langflow Intake、结果入库、人工决定和版本绑定报告；收尾验收尚未完整通过 |
| 当前工作 | 本轮状态对齐及功能收尾验收已完成；WP-05 发布检查仍有未解决项 |
| 活动 Contract | ARC-UPGRADE@0.1.0，contract_status=approved；固定正文未改 |
| 升级实施 | delivery_state=implementing；WP-00..04 主链路及多数功能/运行验收已有实际结果，WP-05 发布缺口未关闭；execution_mode=continuous |
| 内部复核结论 | 固定候选文档复核已完成；该结论不等于当前运行验收 |
| 升级技术验收 | 功能/运行有逐项局部通过证据；AC-19 依赖扫描未通过、镜像扫描/许可证复核受阻，完整 v0.2 不标 verified；完整交付的 last_verified=null |
| 升级最终接受 | pending |
| 本轮授权 | 本地 P0/P1 收尾验证及必要修复、隔离迁移/恢复演练、最小证据、状态文档及 GitHub 同步 |
| 公开展示授权 | 公开 GitHub 及仅使用预置虚构数据的独立静态沙盒已获授权并完成；不包含真实业务后端公网部署 |
| 尚未授权范围 | 真实公司文档、收费模型/OCR、生产数据或后端、破坏性迁移、历史清理；模型与生产化仍需后续选择 |
| Docker | 隔离项目 `ai-review-console-upgrade` 的 API 业务输入已核对，初始 Web 包已重建；后续路由补丁由当前源码浏览器及最终 CI 生产构建验证。验收后主服务和只读恢复 API 已停止，库卷及旧项目保持保护 |
| Git | 公开仓库 [qife422/ai-review-console](https://github.com/qife422/ai-review-console)，分支 `main`；本轮起点 `14d44b1210cff67b6f2bdd60de4523cc56bcb1e8`，验收修复源码提交 `540fd4c` 已推送，其 CI `40819513529` 已实际 success |

公开体验站为 [仅虚构数据的在线沙盒](https://ai-review-console-demo.adeptbread257.chatgpt.site)，其发布定位、源码恢复及独立验证范围见 [ONLINE_DEMO.md](ONLINE_DEMO.md)。它在浏览器内模拟四个预置样本，不连接真实 API、数据库、Langflow 或模型；静态沙盒的上线和浏览器验收不能作为真实主链路的通过证据。

## 固定输入与复核

| 文件 | SHA-256 | 用途 |
|---|---|---|
| [UPGRADE_SPEC.md](UPGRADE_SPEC.md) | `a77947d0369566cef516641ef918e37d08046afc2edf8215dcff90d49ce01753` | 已批准 Contract 的固定全文；编制时状态保留 |
| [spec-baseline.json](spec-baseline.json) | `5ad13f524e74554b9c8cb30b9809ffbbbbed8e3d7fa4ede5625bb1b7d781bf2e` | 2026-10-08 的 49 个原始输入清单；不是当前源码清单 |

2026-10-08 曾核对 23 个需求 ID、24 个 AC、10 个 WP 及 49 个原始输入。该历史检查不宣称升级后的源码仍匹配旧 baseline；本轮运行证据须另行绑定实际源码、环境与命令。

以下历史内部只读评审与单独复核均针对固定候选。它们是文档一致性检查，不是第三方安全审计，也不是本轮升级运行验收。

| Finding | 内容 | 状态 | 复核结果 |
|---|---|---|---|
| SF-01 | 执行token与租约恢复冲突 | closed | token绑定attempt；恢复同一run不轮换，过时attempt不能覆盖 |
| SF-02 | 报告partial、格式失败与决定后重试未定义 | closed | group与格式状态分开，专用reports/retry只补失败/缺失格式 |
| SF-03 | WP-01引用了后续新链路验收 | closed | 限定P0子项，完整版本/Flow验收保留在后续WP |
| SF-04 | 决定接口返回与现有CaseDetail不一致 | closed | 保留完整CaseDetail，增量附加任务信息 |
| SF-05 | 双份正文可能超过callback限制 | closed | sections为正文权威，禁止重复完整text |
| SF-06 | 未评分null与旧客户端兼容未明确 | closed | 不显示假0分，API与支持unknown的新前端共同发布 |

## 已实现能力与本轮验证

- 真实后端已具四格式虚构文件上传、源字节哈希、版本化文档与评估、持久化任务、真实两条 Flow、三种人工决定、JSON/HTML/中文 PDF 报告、部分失败重试及下载哈希校验。当前评分仍为确定性规则，没有 LLM 或 OCR。
- 本地 Python `124 passed`；另以隔离 PostgreSQL 命令执行四项数据库测试，`4 passed`，不再把首轮未配置库的四项 skip 记成验收完成。前端路由修复后 `29 passed`，TypeScript 通过；Ruff 通过。真实浏览器补验已核对同页 DOCX→PDF、无 reload、一次 GET、焦点/locator、后退与未知 hash；单元测试不单独等于整项端到端 AC 通过。
- GitHub 基线 `14d44b1` 的 CI 数字曾通过但截图中文缺字；字体修复提交 `85dddfd` 的 [Actions 40817201951](https://github.com/qife422/ai-review-console/actions/runs/40817201951) 实际 `128 passed`、真实 workflow/UI 作业通过，截图中文已核验。最终代码 `540fd4c` 的 [CI 40819513529](https://github.com/qife422/ai-review-console/actions/runs/40819513529) 已实际全部 success：128 Python、29 前端、真实 workflow/browser 通过；不依赖旧提交的绿色状态。
- 本地旧 API 镜像 `cb6ae183` 被识别为落后输入；本轮重建并核对实际运行源码后执行四格式 Intake、三种决定、九份报告下载、五组件及两条真实 Flow，stored Flow hash 前后不变。运行绑定见本轮证据，不以本地源码存在或旧镜像结果代替。

本轮 `active_evidence=sealed`：[验收摘要](evidence/v02-acceptance/README.md)与[正式 manifest](evidence/v02-acceptance/manifest.json)固定 187 个入选内容文件及来源/命令/环境/输入/结果/哈希，payload 5,181,623 字节。manifest SHA-256 为 `6e3fa0159c396b1d422b32d90ccabb772b82db5d5cbeddb6e385e0e54138ba1c`。仅这些入选文件是本轮活动证据；完整 v0.2 发布验收仍未通过，不能把证据封存等同于项目最终完成。

逐项 AC、实际方法及覆盖边界统一见 [v0.2 收尾验收](evidence/v02-acceptance/README.md)；该入口区分功能通过、CI 回读和发布未通过，不在活动摘要重复维护另一份完整矩阵。

证据中的原始日志保留 ANSI、尾随空白和原 EOF，不为源码格式检查重写已封存字节。源码/活动文档的差异检查与证据哈希回读分别执行；完整 `git diff --check` 对这些原始日志的空白提示不作为业务通过或失败依据。

性能另以 20 份顺序 1MiB 虚构 TXT、AI 关闭、真实 Intake 和混合查询复测：查询 p95 **0.118757s**（≤0.5s）、上传 p95 **0.094931s**（≤3s）、Intake 最大 **3.420485s**（≤120s），20 任务未丢失。环境及原始样本见 `checks/runtime/workflow.json`。此前查询 p95 约 **1.42s** 的失败记录保留；本轮结果不外推为高并发或生产 SLA。

修复和失败观察保留：首轮 auth 场景遇真实 429，验收脚本过严要求恢复 attempt==1 而假失败；修正为合法重试代次并复核旧 job/token/唯一性后补验通过。恢复 API 首轮在空目标卷遇 DAC 权限失败，按同一精确文件计划和确认空卷修复访问权限，未盲建第二恢复目标，重验通过。AC-14 脚本首轮在只读前检误写数据库模块名即退出，未注入或新增案件；修复后才执行一案件验收。

原 SQLite `review_console.sqlite3` 仍为 **57,344 字节**，SHA-256 `980ad5d23d866a52e4101966594e5a24ee67edef08475afc63ff9c3e1f6fca1f`，未修改。逻辑恢复目标为 `arc_restore_2ed4123efdbb`；只读恢复 API、隔离文件卷和主运行卷分开，不把选取的三案件文件恢复等同于全部文件备份或生产灾备。

## 待解决的发布问题

- Python 锁定运行依赖 `certifi 2026.7.22`、`Pillow 12.3.0`、`pypdf 6.16.2`，上游返回 60 条原始结果，按包/advisory alias 归并 **59 组**。上游 JSON 未提供 severity 的项保持未知，不编造等级；修补兼容性和回归尚未实施。
- Node 全依赖审计 **5 个 affected packages**（3 high / 2 moderate）；`--omit=dev` 仍列 `source-map-js` high。锁文件生产标记、构建 peer 与实际浏览器 bundle 可达性须分别分析，不能仅由标记断言线上可利用或完全无影响。完整条目、来源、版本及查询时间见发布证据。
- 镜像 SBOM/依赖和许可证元数据已选入，但 Scout 登录条件阻止完整镜像漏洞扫描，结果是未知 `findings=null`。Python `psycopg`/`psycopg-binary` LGPL 元数据及镜像内 unknown/review 项需按实际分发复核；元数据收集不等于许可证批准。
- 当前未接受这些残余风险，没有为了宣布完成而降低 AC-19；完整技术验收与最终接受继续保持未通过/`pending`。

## 下一工作包与保护范围

活动 WP：WP-00..04 主体代码已存在，本轮 WP-05 及相关 AC 的收尾验证和必要修复已记录，下一步继续关闭发布问题。原 SQLite `review_console.sqlite3`、历史数据库和 Docker 卷均受保护，不在原目标实施迁移。隔离 PostgreSQL 卷为 `ai-review-console-upgrade_postgres-data`，文档/报告/config 卷均同项目前缀；恢复演练另选明确隔离目标。版本化迁移必须显式运行，旧库默认拒绝启动迁移。

本轮计划窗口 60 分钟，模型用量粗估 2–3 万 token，均非实际计费数据；同目标跨 turn/子代理累计计量，不通过换工作包清零。本轮得到状态基线、回归、真实链路/恢复/性能和明确发布缺口；达到预算停点或产物阈值时停止可选扩张并保留结果。

本轮 `continuous`：在范围内连续编辑、诊断、修复和验证，不逐步要求继续。用户已授权本项目 GitHub 同步；其他外部写入不据此扩大。需要改变人工审批/数据语义、越过保护范围、收费调用、生产操作、不可恢复迁移或产物阈值触发时暂停受影响部分。普通可逆技术故障三轮有不同假设和实际结果而无进展后停止受影响范围，保留现场并报告。

保护范围：现有数据库和 Docker 卷、历史 fixtures/报告/截图/SBOM、已记录决定、无关用户修改。产物按固定 Spec §16 分类和限额：临时验证单 WP 256MiB/10,000 文件，候选/正式证据单交付 100MiB/1,000 文件，缓存总量警戒 4GiB/100,000 文件，项目镜像归属 12GiB/单 WP 净增 3GiB；适用源码放大阈值同时生效。本轮作者源码基线 638,871 字节，[最终盘点](evidence/v02-acceptance/final-inventory.json)中缓存 666,736,842 字节 / 46,122 文件，临时输出 27,448,735 字节 / 658 文件，证据约 5MiB；已量测根在阈值内。业务文件卷 96 文件 / 42,671,451 字节，低于 1GiB / 5,000 文件。宿主镜像报告量增加约 60MB、构建缓存增加约 45MB；宿主总量约 19.14GB 含其他项目和共享层，不是本项目归属容量。五个历史镜像 ID 元数据不可回读，已标记 unavailable，不当作活动运行证据；完整历史项目占用仍是部分盘点。`pending_cleanup=true`，无自动清理、压缩或历史迁移授权。

## 后续顺序

1. 本轮代码 `540fd4c` CI 已回读成功；验收摘要及 manifest 固定本轮实际通过/失败，不修改已批准 AC。
2. WP-05 优先修补依赖并重跑相关回归与依赖审计，再满足镜像扫描登录条件、核对镜像 findings 和许可证 unknown/review 项。证据齐备后申请完整技术验收及用户最终接受，当前不以已上线沙盒代替。
3. v0.2 稳定后，沿既有 WP-08 增强修订再审、版本历史、队列效率、诊断和受控恢复；不依赖模型的项目可优先。P2 / WP-06..07 的模型建议先决定供应商、预算、数据出口及冻结评测；OCR 独立选择。P4 / WP-09 生产身份、权限、基础设施与发布恢复另行确定 Contract，当前不实施。

详细路线和完成条件继续以固定 Spec §4、§14、§15 为准，不另建重复路线图。技术验证、风险接受、用户最终接受及生产部署授权保持独立。

## 最小阅读顺序

适用 AGENTS → 本文件 → [SPEC_INDEX.md](SPEC_INDEX.md) → [本轮验收摘要](evidence/v02-acceptance/README.md) → [UPGRADE_SPEC.md](UPGRADE_SPEC.md) 中当前 WP → 实际源码/配置与证据输入指纹。只有解决冲突时才读取历史SESSION_HANDOFF，不从历史容器运行记录判断当前状态。
