# 当前状态

更新日期：2026-10-31（America/Los_Angeles）。这是冷启动入口，要求以固定 Contract 为准，当前实际能力以源码、测试和绑定证据为准。

负责人此前已确认 `ARC-UPGRADE@0.1.0` 并授权 P0/P1、WP-00..05 连续实施；2026-10-28 授权状态对齐和收尾验收；2026-10-31 进一步授权按开发范式修补依赖、完成镜像扫描/许可证确认、回归和 GitHub 同步。本轮对单个中止 Grype DB 缓存的精确删除又取得明确回复“允许删除这项缓存并继续”。这些决定不构成剩余风险接受或生产授权。

## 当前结论

| 轴 | 当前状态 |
|---|---|
| Contract | `ARC-UPGRADE@0.1.0`，approved；固定正文未改 |
| 交付 | implementing；WP-00..04 主体及主链路已有证据，WP-05 的发布问题未关闭；continuous |
| 本轮工作 | 兼容修补、实际扫描、许可识别、回归、故障恢复与保全记录完成；结果含明确未通过项 |
| 功能验证 | 代码 `fac92ea797c96cd8d12581bf616d0295e8312186` 的最终 CI 已 completed/success：154 Python、29 前端、真实 workflow 与浏览器通过；原生 arm64 真实 Flow、pin、pip check、旧虚构案/报告保全补验通过 |
| 发布检查 AC-19 | 检查已执行且资料可追溯；仍 failed / unresolved findings，不把采集成功或 CI 绿记成发布通过 |
| 完整技术验收 | 完整 v0.2 的 `last_verified=null`；具体局部通过按证据范围理解 |
| 最终接受 | pending；没有接受任何剩余风险 |
| 本轮正式证据 | `active_evidence=sealed`，见下方固定 manifest；上轮证据仍保留原字节 |
| 外部范围 | 已授权公开 GitHub 与既有仅预置虚构数据的静态沙盒；本轮不重新部署真实后端或在线站点 |
| 保护范围 | 原 SQLite、历史数据库/卷、已记录决定、固定 Spec/baseline、历史证据和无关用户文件；没有生产切换或历史清理 |

## 当前证据入口

- [本轮发布验收](evidence/v02-release/README.md)：已解决、未解决、后续工作、扫描边界、失败/恢复与产物处置。
- [正式 manifest](evidence/v02-release/manifest.json)：精确源码、CI/image、来源、producer、文件及 SHA-256。manifest SHA-256：`c2a9cba23f3653e7c507654631f74568ee7490f80212ffe382c92323a4547f36`。
- [最终 CI 41259579902](https://github.com/qife422/ai-review-console/actions/runs/41259579902)：真实回读的 `fac92ea`，不沿用旧提交绿色状态。
- [上轮 AC-01..19 收尾记录](evidence/v02-acceptance/README.md)：固定在其原源码/环境范围；没有把其中故障、隔离恢复和性能旧值重新标为当前依赖的完整新验收。

源码业务/测试/依赖/Flow/CI 等 107 个输入有指纹；随后文档整理单独记录影响。README 同时会进入 API wheel 描述/COPY 文档，当前证明的精确镜像仍是 `fac92ea` 构建的 ID，不宣称后续文档提交又重建了同一镜像或完成了另一轮 CI。详见 [文档影响](evidence/v02-release/environment/documentation-impact.json)。

## 修补与剩余问题

应用锁升级 certifi/Pillow/pypdf 后，33 个运行包审计为 0；前端 Vite/Vitest 及相关传递包修补后全量与 omit=dev 审计均 0。基础 digest、API pip、Web curl/brotli 已修补，Web 包级镜像查询 0。Langflow 保留 1.11.6，另外 25 个安全/兼容 pin 均在最终 CI inventory 确认，依赖一致性及实际两条 Flow 通过。

最终实际 Linux/amd64 镜像仍有包级匹配：API 114 个 Debian IDs；Langflow 8 个 Python 包 / 90 IDs / 65 alias 组，另 23 个 RHSA IDs；PostgreSQL 116 个 Debian IDs。跨镜像 ID 有重叠，不能相加当独立 CVE。默认扫描的 226 个 RPM unknown 由同 image ID、相等条目集合的补扫覆盖，合并后本清单范围 mapping/query/detail unknown=0；原 exit 2 仍保留，不因此宣称漏洞清零。检查不包含完整文件系统、静态二进制、内嵌库或可利用性审计。

许可证识别与实际材料分开：dnspython、fastmcp-slim、LFX 的缺包内文本已按精确上游版本确认；`zep-python 2.0.2` 仍缺充分许可依据。IBM clidriver、wheel 原生库及完整 GPL/LGPL/MPL 等分发材料尚未闭环，完整后端镜像不作分发批准。许可启发式误选的源码/pyc 已在人工解释中排除；没有因目录名或字段不为空就宣布通过。

各项包名/版本、修复事件、上游上限、跨 major / pre-1.0 / exact 成套升级原因、无已确认 fixed 事件，以及许可证和容量的关闭条件，统一在本轮验收入口，不另维护重复清单或新路线图。

## 数据、环境与产物

原 `review_console.sqlite3` 仍为 57,344 字节，SHA-256 `980ad5d23d866a52e4101966594e5a24ee67edef08475afc63ff9c3e1f6fca1f`。仅本轮新隔离项目 `ai-review-console-release` 使用新库卷并生成明确虚构记录；故障前 5 个案件及 9 份报告已回读保全。原/历史库卷没有迁移或清理。当前 Docker 健康，active jobs=0 后验收服务已停止；测试库卷、镜像和资料保留。

磁盘预检遗漏及 Grype DB 解压造成的容量/ENOSPC/EROFS 失败如实保留。用户仅授权删除已盘点的单个中止缓存目录 `/private/tmp/arc-v02-release-close.p3RyvK/tool-cache/grype-db`，共 2,966,994,944 字节；已核对单文件、无消费者、删除后缺失和空间回读，没有顺带删除工具、其他缓存、卷或证据。Docker 与本机 pip 已恢复，后续原生验证通过。

临时来源根 `/private/tmp/arc-v02-release-close.p3RyvK`，候选 `artifacts/evidence-candidates/v02-release/`，正式 `docs/evidence/v02-release/`。正式资格只属于外层 manifest 选入的固定字节；ZIP、构建树、包缓存、DB dump 和未入选隐藏浏览器文件不因此成为正式证据。原始日志的空白/ANSI/EOF 不为源码格式检查而重写。

当前缓存约 0.97GB / 49,046 文件，临时输出约 47MB / 534 文件；候选/正式各小于 100MiB / 1,000 文件，业务卷 28 文件 / 417,269 字节。源码、固定字体/上游依赖、包缓存与派生输出分列，临时/证据未触发 1GiB 且源码 100倍的放大门槛。

Docker 镜像和构建缓存全局报告量的本轮增量代理约 3.63GB，超过单 WP 3GiB 警戒。已停止后续构建/拉取/缓存扩张，仅完成已有镜像验证和停服务；共享层与历史归属不完整，不能宣称精确项目物理总量已在 12GiB 门槛内。下次继续本地构建前先确定容量与处置，未授权 prune、历史迁移或扩大额度。`cache_state=warning`（Docker），`pending_cleanup=true`；其余缓存/临时/候选保留待处理。完整盘点及授权处置见本轮证据。

## 固定输入与后续顺序

| 固定输入 | SHA-256 |
|---|---|
| [UPGRADE_SPEC.md](UPGRADE_SPEC.md) | `a77947d0369566cef516641ef918e37d08046afc2edf8215dcff90d49ce01753` |
| [spec-baseline.json](spec-baseline.json)（历史 2026-10-08 输入） | `5ad13f524e74554b9c8cb30b9809ffbbbbed8e3d7fa4ede5625bb1b7d781bf2e` |
| 上轮正式 manifest | `6e3fa0159c396b1d422b32d90ccabb772b82db5d5cbeddb6e385e0e54138ba1c` |

1. 先按本轮固定结果关闭 WP-05 剩余发布问题：Langflow 上限冲突与成套兼容升级、厂商补丁/适用性、Zep 精确许可和完整二进制材料。跨版本方案先固定候选、影响和重测范围；不强装冲突依赖或默认接受风险。本地构建另先处理已触发的容量警戒。
2. 有新证据后复验并申请完整技术验收和最终接受；当前没有用虚构沙盒、CI 绿色或证据封存代替这两个决定。
3. v0.2 发布门槛解决后沿既有 WP-08 增强版本历史、再审、队列效率、诊断与受控恢复。模型供应商/预算/数据出口、OCR和生产化仍按固定 Spec 独立选择，不在本轮执行。

本轮计划窗口 90 分钟，初始模型量级粗估 3–5 万 token，均非实际计费；同目标跨 turn/子代理累计，没有以切片清零。真实资料接入、收费模型/身份服务、不可恢复迁移、向他人发送消息及其他历史清理不在本轮授权范围。普通故障三轮有证据且无进展即停受影响范围；语义、权限、数据、不可逆或容量边界即时停受影响动作。

最小阅读：适用 AGENTS → 本文件 → [SPEC_INDEX.md](SPEC_INDEX.md) → 本轮发布验收与具体证据 → 固定 Spec 当前 WP → 实际源码。旧 SF 文档评审结论和历史运行按其 Git 版本/原记录理解，不当作本轮运行证明。
