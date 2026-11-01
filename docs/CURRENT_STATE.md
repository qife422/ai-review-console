# 当前状态

更新日期：2026-10-31（America/Los_Angeles）。冷启动以本文件、固定 Contract、实际源码和绑定证据为准。

负责人已确认 `ARC-UPGRADE@0.1.0`，授权 P0/P1、WP-00..05 continuous；本轮明确要求先盘点镜像/缓存容量，再处理 Langflow 剩余兼容升级和许可缺口、回归并同步 GitHub。该授权不包含历史清理、风险接受、真实数据或生产部署。上轮仅针对单个中止 Grype DB 的删除已经完成，不扩展至其他镜像、缓存或卷。

| 轴 | 当前状态 |
|---|---|
| Contract | approved / `ARC-UPGRADE@0.1.0`；固定正文未改 |
| 交付 | implementing；WP-05 发布问题仍 open；continuous |
| 本轮结果 | 容量盘点、兼容升级、许可材料补充、回归和问题/计划同步完成；具体通过与未通过分列 |
| 功能验证 | `a64ab476c8acfaa36a3d6cc260a4c6c286bad380` 的 CI `41263397231`：completed/success；161 Python / 29 前端、真实四格式/三决定/九报告、失败重试、双主题双尺寸浏览器、52 pins/pip check及离线兼容探针通过 |
| 发布检查 AC-19 | not passed；残余包级发现和完整镜像分发材料仍未关闭；CI 绿色不代表发布通过 |
| 完整技术验收 | `last_verified=null`；局部通过以精确版本和范围理解 |
| 最终接受 | pending；未接受剩余风险 |
| 证据 | `active_evidence=sealed`；本轮增量及原固定证据见下方 |
| 外部范围 | GitHub 公开源码；既有仅虚构预置数据的静态沙盒保留，本轮未重部署在线站点或真实后端 |
| 保护 | 原 SQLite、历史库/卷、已记录决定、固定 Spec/baseline、历史证据和无关文件未迁移或清理 |

## 当前证据

- [本轮兼容与许可补验](evidence/release-compatibility/README.md)：已解决、剩余约束、容量、扫描与后续关闭条件。
- [本轮 manifest](evidence/release-compatibility/manifest.json)：SHA-256 `0466646bd5eecd32768e9fc61bf138815853292049a41a95dc1d98927e2081ef`；精确 source/image、命令/方法、producer 和 payload 指纹。
- [实际代码 CI 41263397231](https://github.com/qife422/ai-review-console/actions/runs/41263397231)。随后文档提交的影响另见本轮 `environment/documentation-impact.json`；不把后续文档字节标成该次构建的镜像。
- [前次发布验收](evidence/v02-release/README.md)及[更早收尾验收](evidence/v02-acceptance/README.md)仍适用于其原输入/环境，固定原字节；故障、隔离恢复及性能没有在新依赖下重跑。

## 已解决与剩余

本轮把 OAuthlib 升至 4.0.0、datamodel-code-generator 升至 0.81.0、OTel 成套升至 1.45.1/0.66b1，另固定其两个新增 exporter 依赖。Langflow 仍为 1.11.6，现在共 52 个显式 pin。新增离线探针覆盖相关兼容行为与安全回归，真实 Flow 分开验证；metadata 图不代替安装和运行。

新 CI 的 Linux/amd64 包级扫描仍有记录：API 114 个 Debian IDs；Langflow 5 个 Python 包 / 81 IDs / 59 alias 组，另 23 个 RHSA IDs；PostgreSQL 116 个 Debian IDs，Web 为 0。跨镜像 provider IDs 并集 245，不等于独立 CVE 或可利用漏洞数。默认 226 RPM unknown 的原 exit 2 保留，由同一 LF image ID、字节完全相同清单的 RHEL 补扫覆盖 223 软件包及 3 公钥；清单内合并 mapping/query/detail unknown=0，原补扫 exit 1 保留。没有覆盖全部文件系统、静态/内嵌二进制或可利用性。

补入 dnspython/FastMCP 原文，LFX 使用同版本 Langflow MIT，镜像携带副本情况由新 CI 哈希证明。许可采集会排除误选源码/pyc；新增 util-http 0.66b1 缺自身文本，已按精确同 tag/版本及哈希映射到镜像实际携带的 OTel instrumentation Apache 原文，不改写原始 own-text 缺失。Zep 2.0.2 仍缺充分许可依据，current extras 的 exact pin 未被忽略；同名 `v2.0.0` tag 实为 zep-cloud，不能转移许可。原生库的实际版本、路径哈希、官方源码校验及缺项已形成[矩阵](DEPENDENCY_LICENSES.md)，但厂商 FIPS source/patch、部分 native 对应材料、AMD64 IBM driver 和完整二进制分发条件仍未闭环。完整后端镜像没有分发批准。

## 容量、数据与产物

精确 Docker 盘点：全局 layers 21,874,078,300B，加非 shared build-cache 2,413,293,031B，记账合计 24,287,371,331B；shared cache 不重复相加。已知 ARC 11 个 image ID，另 6 个历史引用 ID 元数据不可用。当前全局增长代理约 2.900GiB，不抹掉此前 3GiB 警戒，也不能证明项目完整物理总量低于 12GiB。因此继续暂停本地 build/pull/构建缓存扩张，本轮改用隔离 CI。无 prune、历史迁移或其他清理；`cache_state=warning`、`pending_cleanup=true`。

原 SQLite 57,344B，SHA-256 `980ad5d23d866a52e4101966594e5a24ee67edef08475afc63ff9c3e1f6fca1f`；原 Spec `a77947d0369566cef516641ef918e37d08046afc2edf8215dcff90d49ce01753`、baseline `5ad13f524e74554b9c8cb30b9809ffbbbbed8e3d7fa4ede5625bb1b7d781bf2e` 均不变。保护核对与旧 payload 完整性见本轮 `environment/protection-check.json`。

本轮 temp `/private/tmp/arc-release-followup.rLeRu5`、候选 `artifacts/evidence-candidates/release-compatibility/`、正式 `docs/evidence/release-compatibility/`。仅 manifest 选入字节为正式证据；原始全局 Docker snapshot 私有保留，ZIP/缓存/构建树/数据库不入包。新临时产物上限 40MiB（全局 temp 门槛 256MiB/10,000），候选/正式各 100MiB/1,000，源码放大门槛 >1GiB 且 >100倍；本轮实际量见 manifest。旧缓存和历史产物保留待处置，没有为恢复旧路径复制完整树。

原生许可采集原计划全批 100 路径，producer 按镜像执行而实际 101 路径/95,522,697B；偏差保留，后续停止补读，不标成满足全批限额。新镜像的 native byte correspondence 尚未由本轮旧 ARM 样本证明。

## 后续顺序

1. 继续 WP-05：Pillow/filelock/setuptools 的上游版本上限、chromadb/couchbase 的明确修复/厂商适用性，及 Debian/RHEL 基础包；先固定受支持候选和影响，再跑依赖图、精确镜像、探针、真实 Flow/报告和受影响故障回归。
2. 关闭 Zep 精确许可及 native/完整源码与通知材料；本地扩张前补足容量归属和峰值估算。清理、迁移或额度改变需另有适用的明确决定。
3. 发布条件全部关闭后申请完整技术及负责人最终接受，再进入既有 WP-08 的版本历史、再审、队列效率和诊断。模型/OCR/真实数据/生产化仍按固定 Spec 独立选择。

同目标预算 90 分钟跨 turn/子代理累计，没有切片清零。普通技术故障三轮有证据且无进展即停止受影响范围；权限、Contract、数据、不可逆或容量边界即时停受影响动作。最小阅读：适用 AGENTS → 本文件 → [Spec 索引](SPEC_INDEX.md) → 本轮增量证据 → 固定 Spec 当前 WP → 代码。
