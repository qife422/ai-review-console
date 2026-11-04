# 当前状态

更新日期：2026-11-03（America/Los_Angeles）；主体系统/依赖验证于11-02执行，定向许可修复与最终功能CI于11-03执行。本文件为冷启动入口，固定 Contract、实际源码和有范围的证据共同定义当前状态。

负责人已批准 `ARC-UPGRADE@0.1.0`，授权 P0/P1、WP-00..05 continuous；本次授权继续评估 Langflow、处理系统补丁和许可证、回归并同步 GitHub。用户在累计180分钟预算确认后回复“可以”，同目标当时已耗约87.6分钟保留，不清零。本次没有历史清理、真实数据、生产部署、完整后端镜像分发或残余风险接受授权。

| 轴 | 当前状态 |
|---|---|
| Contract | approved / 0.1.0；固定正文不变 |
| 交付 | implementing；WP-05发布问题仍open，continuous |
| 当前运行时 | Langflow1.11.6原base digest和52个显式Python pins保持；新增UBI公共仓库系统补丁层及Web libexpat维护 |
| 本轮功能代码 | adb93c4b9f6af508188f696b8d7d1ef1dc5668ac / CI 41760412382：191 Python/29前端；AMD完整工作流/浏览器、Linux ARM后端全部success；只定向补采唯一English协议 |
| 发布AC-19 | not passed；剩余依赖/供应商及分发材料仍未闭项 |
| 完整技术验收 | last_verified=null；局部通过仅在对应source/image/profile范围 |
| 最终接受 | pending，未接受残余风险 |
| 活动证据 | sealed；本轮系统维护增量，旧三个包原字节保留 |
| 外部范围 | 公开GitHub源码和既有虚构数据静态沙盒；本轮没有重部署沙盒或真实后端 |
| 保护范围 | 原SQLite、历史数据库/卷、决定、固定Spec/baseline、历史证据与无关文件 |

## 当前证据

- [系统维护与候选评估](evidence/runtime-maintenance/README.md)：已解决、实际测试/扫描、限制和后续关闭条件。
- [正式manifest](evidence/runtime-maintenance/manifest.json)：SHA-256 `5a400e77b5e3b28426f2efe99d723b48aee5e1e95d9c7e4a4c9665364963b724`。
- [功能代码CI](https://github.com/qife422/ai-review-console/actions/runs/41760412382)：精确source/images和两种profile结果。之后纯文档/证据提交使用 `[skip ci]`，不声称跳过是成功，也不声称新说明字节属于这些精确镜像；影响见[文档提交影响](evidence/runtime-maintenance/environment/documentation-impact.json)。
- [前次兼容补验](evidence/release-compatibility/README.md)、[前次发布扫描](evidence/v02-release/README.md)、[早期收尾](evidence/v02-acceptance/README.md)按其原输入/环境理解。旧故障恢复、隔离恢复、性能不标成在新系统补丁下完整重跑。

## 已验证与剩余

系统维护在两架构实际更新60个既有软件EVR、新增1软件无移除；227条RPM=224软件+3公钥。RHEL补扫0ID/0unknown，主扫描exit2与227RPM unknown原记录保留，由同exactimage/fullEVR集合补扫覆盖，清单内合并unknown0。Web libexpat2.10.0-r0扫描0；API126、PostgreSQL130个Debian IDs；LF仍5个Python包/81 IDs/59 alias组，provider并集236。这些不是独立CVE/可利用性计数，也不覆盖全部内嵌文件。

最终实际191 Python/29前端、52pins/pip check/兼容探针、5组件/2Flow/4格式/3决定/9下载通过；AMD浏览器passed，ARM仅后端。负向失败重试保持同case/version并一次重试代次，仍failed是预期，不标成成功恢复。详细指标和精确source/image、未选范围见本轮证据。

11-02官方候选快照评估（不代表未来最新）：稳定1.13.0仍保留Pillow<13/filelock<4/setuptools<84；RC1.13.1rc2、当次可见开发版1.14.0.dev14仅放开当前Python分支的filelock>=4.2.1,<5。没有候选安装/GUI/API/迁移兼容通过证据，因此保持当前固定基线。1.13元数据中的bundles/extras拆分只提供fresh runtime去除Zep的未来核实路径，不证明旧胖镜像内集成已移除。

已补齐Psycopg3.3.5与Psycopg2-binary2.9.12各自精确recipe/patch来源，纠正跨owner配方比较；实际AMD取得IBM REDIST、notices和55,713B英文协议。协议标识v11.5.9/LI L-ASUX-ZXSTFM，不能据此独立断定libdb2二进制fixpack。新增本轮12文件/40,256,769B，加旧输入累计135,779,466B；最后沿共享剩余额度只读唯一English路径，剩8文件/26,852,095B输入/4,026,824B文本。许可文本取得关闭材料缺失，分发条件/全清单符合与厂商源码仍未批准。

完整后端分发尚未批准，Zep2.0.2精确许可、厂商FIPS/若干native对应源码、IBM完整文件清单与许可条件仍在后续清单；Python包的项目许可不覆盖所有随包二进制。

## 数据、容量与产物

原SQLite57,344B，SHA-256 `980ad5d23d866a52e4101966594e5a24ee67edef08475afc63ff9c3e1f6fca1f`。固定Spec `a77947d0369566cef516641ef918e37d08046afc2edf8215dcff90d49ce01753`、baseline `5ad13f524e74554b9c8cb30b9809ffbbbbed8e3d7fa4ede5625bb1b7d781bf2e`，三个旧正式包全部payload逐文件复核不变。本轮仅使用新CI项目/新虚构记录；原库卷未启动、迁移或删除。

本地Docker socket不可连接，当前layers/历史归属未新验，原 `cache_state=warning` 和 `pending_cleanup=true` 保留。没有为继续验证启动本地Docker、build/pull、prune、迁移或扩大本地缓存。宿主空间及旧盘点适用范围见本轮capacity记录。CI两架构先记录uname/df，低于12GiB停安装/构建，collector仍保留6GiB入口/5GiB运行余量门禁。

本轮temp `/private/tmp/arc-runtime-maintenance.wT9huB`，候选 `artifacts/evidence-candidates/runtime-maintenance/`，正式 `docs/evidence/runtime-maintenance/`。temp40MiB/10,000文件；双架构CI合计选择20MiB/200文件；候选/正式各100MiB/1,000文件；源码放大门槛>1GiB且>100倍。仅manifest选中固定字节为正式证据，私有ZIP/未选文件/缓存/构建树/数据库保留原分类，无清理或整树备份。

Native输入首次实际10文件/40,177,611B；随后用固定 `compliance/native-baseline.json` 恢复剩余10文件/26,931,253B做定向补采；第三轮只新增23,445B notices，最后沿剩余9文件/26,907,808B继续唯一英文协议目标，不重读driver40MB、不重新完整遍历。ARM不另开第二份targetednative预算，旧101/100路径偏差保留；实际累计见manifest和补采原件。

## 后续计划

1. 先继续WP-05的明确剩余项：Pillow/filelock/setuptools上限、chromadb/couchbase的修复或厂商适用性、Debian残余记录，以及Zep/native/IBM完整分发材料。候选运行时需按AD-03固定版本/影响/重测，涉及行为、认证或数据语义时先形成delta与对应决定。
2. 发布条件、完整技术验收和负责人最终接受后，按现有WP-08做版本历史、修改后再审、队列筛选与效率、失败诊断及受控恢复；首个可运行功能切片优先“查看历史版本并对要求修改的案件提交新版本”。
3. LLM语义建议、OCR、真实身份/权限、真实数据和生产部署仍是独立阶段；需模型/预算/数据出口与评测决定，不因本轮CI绿色直接开启。

普通技术问题三轮有证据且无进展即停止受影响范围；权限、Contract、数据、不可逆和容量边界即时停止受影响动作。最小阅读：适用AGENTS → 本文件 → [Spec索引](SPEC_INDEX.md) → 本轮证据 → 固定Spec当前WP → 源码。
