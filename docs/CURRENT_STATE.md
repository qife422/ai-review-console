# 当前状态

更新日期：2026-11-04（America/Los_Angeles）。冷启动以本文件、固定Contract、实际源码和有范围的证据为准。

负责人已批准ARC-UPGRADE@0.1.0及WP-00..05 continuous；本次明确授权精简Langflow候选隔离验证、剩余依赖与许可、回归、结果及计划同步GitHub。用户明确把同目标预算由180扩至250分钟，既有累计保留；只调整时间，不授权历史清理、默认runtime替换、后端发布、许可替代选项或风险接受。工具门禁不覆盖所有MCP/云端路径，登记不授予这些权限。

| 轴 | 当前状态 |
|---|---|
| Contract | approved/0.1.0，固定正文不变 |
| 交付 | implementing；WP-05发布问题仍open；本轮有限隔离实验已完成 |
| 默认运行时 | 1.11.6原base digest+52pins+既有系统补丁；未被候选替换 |
| 精简候选 | langflow-base1.13.1 + lfx[sqlite]1.13.1，Linux AMD64新库；334 Python distributions |
| 候选功能验证 | e73ab92 / CI41943564415 success：198 Python/29前端；5组件/2Flow/4格式/3决定/9报告、API403/登录/版本、GUI真实登录与两Flow可见 |
| 默认基线验证 | 32eb636 / CI41940799240 success：194 Python/29前端、AMD业务/ARC浏览器及Linux ARM后端 |
| 发布AC-19 | not passed；Debian记录、完整native/分发材料及默认升级范围未闭合 |
| 完整技术验收 | last_verified=null；局部通过按各source/image/profile理解 |
| 最终接受 | pending；未接受残余风险或批准完整后端分发 |
| 保护 | 原SQLite/历史卷、Spec/baseline、四旧封存包不变；无本地Docker增长/清理/迁移 |

## 活动证据

- [精简候选结果、未解决与计划](evidence/langflow-candidate/README.md)，[正式manifest](evidence/langflow-candidate/manifest.json)：SHA-256 `ca0a0b0b38c2ca735ae17b83c93cc022fd89899a8b8f0e82b978b1eb3b5a38ec`。
- [候选实际CI](https://github.com/qife422/ai-review-console/actions/runs/41943564415)，精确source `e73ab92321483403fafd03e721182c5426ae6359`、image `sha256:bab518885b0099096f7843c3016227644246f3f165e74fbd040f373a4ec8bffb`。后续说明提交不声称是这些精确镜像字节；见[文档影响](evidence/langflow-candidate/environment/documentation-impact.json)。
- [前轮系统维护](evidence/runtime-maintenance/README.md)、[兼容补验](evidence/release-compatibility/README.md)、[发布扫描](evidence/v02-release/README.md)、[早期验收](evidence/v02-acceptance/README.md)原字节保留，仅按原输入/环境理解。

## 已解决与待解决

候选已实际升级Pillow13.0.0/filelock4.2.1/setuptools84.1.0，chromadb/couchbase不在安装清单。55条constraints包含原52中的2项上游floor修订（PyJWT2.15.1/transformers5.10.1）及3个新显式边界，不强制安装未使用集成。PyPI包级匹配0，顶层langflow未安装但其1.13.1 family补查也0；均不是全FS/静态或可利用性保证。

候选扫描443行=334Python+109Debian；52个Debian binary/28source包有133 provider IDs，原exit1保留，mapping/query/detail unknown0。不能把133当独立CVE，不能与旧RHEL0直接比较风险。默认新baseline快照仍LF5包81、API127、PG131、Web0、并集237；完整默认发布尚未通过。

候选未安装Zep、ibm_db/clidriver相关driver、Psycopg binary两包；仅限安装名和已知driver路径。IBM SDK仍在，分别声明BSD-3-Clause/MIT。Psycopg3.3.5纯Python+构建APT libpq5路径正常，runtime报告150019；仍有LGPL/系统native义务。APSW actual owntext1,166B匹配精确source；base/sqlitevec本轮未采到白名单declared specimen，LFX owntext缺记录，已补精确上游MIT及sqlitevec源许可。repo MIT副本仅末尾空行差异，actual镜像副本独立回读未保留；SQLite/source、前端嵌入依赖与完整分发材料仍pending。旧默认及API vendor/FIPS问题未由候选跨环境关闭。

本轮14个新target文件/40,313,648B，加旧95,522,697B=135,836,345B；共享余额6files/26,795,216B输入/3,969,945B文本，旧101/100偏差保留。旧raw继续9→8的固定起算与真实跨CI消耗差异有外部对账，不能把raw旧值当剩余预算。新采集默认false，仅需要时显式true，并先核剩余额度。

## 数据与产物

原SQLite57,344B SHA `980ad5d23d866a52e4101966594e5a24ee67edef08475afc63ff9c3e1f6fca1f`；固定Spec `a77947d0369566cef516641ef918e37d08046afc2edf8215dcff90d49ce01753`、baseline `5ad13f524e74554b9c8cb30b9809ffbbbbed8e3d7fa4ede5625bb1b7d781bf2e`。四旧包全部payload逐文件复核，原库卷未启动、迁移或删除。未把旧故障/恢复/性能继承为1.13.1通过。

新temp `/private/tmp/arc-langflow-candidate.qya6psom` 上限3MiB，连前轮temp合计40MiB；newCI合计1MiB/50files（实选40files/416,324B），sources12files/256KiB；候选`artifacts/evidence-candidates/langflow-candidate/`与正式`docs/evidence/langflow-candidate/`各100MiB/1000files，放大>1GiB且100倍停。ZIP未落盘，scratch/cache/未选whole报告不因目录取得证据资格；保留待授权处置，无清理或整树备份。旧本地Docker容量warning/pending_cleanup保留，本轮未新盘点全部layers/历史归属，也未start/build/pull/prune。

## 下一步

1. 固化候选完整依赖锁与哈希，分类Debian133记录和供应商修复；补自带许可副本/对应源码及完整分发材料，继续按实际目标读数对账。
2. 默认collector仍绑定RHEL事务/补扫与旧native continuation，先适配新发行版且不弱化门槛，再按AD-03提出明确默认升级delta，补ARM/Mac、管理编辑器、旧schema隔离迁移与回滚、故障/恢复/性能；fresh-db成功不替代这些证据。
3. 发布条件和最终决定后才替换默认，再沿WP-08做版本历史、修改后再审、队列和诊断。LLM/OCR/真实身份/真实数据与生产部署独立选择。

普通技术阻塞三轮有证据无进展即停受影响范围；权限/Contract/数据/不可逆/容量即时停。最小阅读：适用AGENTS→本文件→[Spec索引](SPEC_INDEX.md)→活动证据→固定Spec相应WP→源码。
