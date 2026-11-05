# 当前状态

更新日期：2026-11-04（America/Los_Angeles）。冷启动以本文件、固定Contract、实际源码和限定范围的证据为准。

负责人已批准ARC-UPGRADE@0.1.0及WP-00..05 continuous；前轮已完成候选锁、隔离迁移/回滚和补验；本轮用户在确认自查/上传后允许下一步，先补候选ARM独立锁、双架构回归并同步GitHub。用户明确将同目标累计预算扩至360分钟，既有累计保留；没有扩大默认替换、原始数据、历史清理或后端发布权限。工具门禁只覆盖已验证的工作区shell/文件补丁路径，登记不授予权限。

| 轴 | 当前状态 |
|---|---|
| Contract | approved/0.1.0，固定正文不变 |
| 交付 | implementing；WP-05发布问题仍open；本轮有限候选验证已收尾 |
| 默认运行时 | 1.11.6，原Dockerfile含52inline pins及既有系统补丁，字节不变 |
| 精简候选 | base/LFX1.13.1；334包独立AMD64/ARM64 SHA锁+4工具锁，各自新环境及实际镜像均exactset一致 |
| 常规CI | e6f6fe7 / CI41979142562 success：271 Python/29前端、默认与候选各AMD/ARM；AMD浏览器通过，ARM GUI跳过 |
| 候选ARM | 原生Linux/aarch64，334包/4工具独立新装与真实Flow/报告通过；非Mac宿主或ARM旧schema迁移证明 |
| 隔离迁移/回滚 | 480246c / CI41954322019 success：旧检查点→新1.13.1及第三新1.11.6；两目标各再处理5案/9报告；限前轮AMD精确image，不继承ARM |
| 系统与许可 | APT/libapt2.6.2补丁及三份通知副本实际回读通过；本轮两个LF候选各132 provider记录，完整native/source未闭合 |
| 发布AC-19 | not passed；默认完整发布条件与二进制分发材料未完成 |
| 完整技术验收 | last_verified=null；局部结果按精确source/run/image/profile理解 |
| 最终接受 | pending；未接受残余风险或批准完整后端分发 |
| 保护 | 原SQLite/历史卷、Spec/baseline、六旧封存包不变；没有本地Docker增长、清理或原库迁移 |

## 活动证据

- [本轮ARM结果、待解决及计划](evidence/langflow-arm/README.md)，[正式manifest](evidence/langflow-arm/manifest.json)，SHA-256 `7facd4561ccab08d137c45b748b8aa459ba042f21881fe87677527de29852a7d`。
- [最新完整CI41979142562](https://github.com/qife422/ai-review-console/actions/runs/41979142562)：source e6f6fe7b908b7fab1b4f85e9f5a4fa22890fc923；候选ARM LF image sha256:a5939d54d52e42c88138c81d2059386fd31b3c1f66b7373358b35374b6b9627d，AMD LF image sha256:26a433f984fcb8da102faf0a77daa668c4ccfdc3a7177ac17ff961925547d27f；完整271/29、四个runtime lane均通过。
- [ARM锁CI41978766690](https://github.com/qife422/ai-review-console/actions/runs/41978766690)：source38edc84，ARM334包与4工具分别新装/pip check，59个所选archive SHA不同于AMD，包版本未变。
- [前轮依赖锁/迁移结果](evidence/langflow-transition/README.md)，[正式manifest](evidence/langflow-transition/manifest.json)，SHA-256 `81701508dc131ef4dbdc8743f46fdcb57c98969a4567696fd3c289c7843f1af5`。
- [前轮完整CI41953014467](https://github.com/qife422/ai-review-console/actions/runs/41953014467)：source a1190a38e998ce9683495a07028a1b9e589303cf，candidate LF image sha256:69bf80f930187d91082d50a22f5543482aea10a6c1391d64e920b120a18ed3f0；实际334清单/安装/Flow/ARC浏览器和扫描通知材料绑定同image。
- [哈希锁CI41952562436](https://github.com/qife422/ai-review-console/actions/runs/41952562436)：source82a028e，4工具及334包分别严格新装/pip check；4个sdist锁的是源码档案，不宣称wheel二进制复现。
- [迁移/回滚CI41954322019](https://github.com/qife422/ai-review-console/actions/runs/41954322019)：source480246c00a94ecee420f4d778ebf302acf3d4b79；升级/回滚镜像独立于常规CI，见本轮manifest；不是原地降级或升级后写入零丢失。
- [上轮候选](evidence/langflow-candidate/README.md)、[系统维护](evidence/runtime-maintenance/README.md)、[兼容补验](evidence/release-compatibility/README.md)、[发布扫描](evidence/v02-release/README.md)、[早期验收](evidence/v02-acceptance/README.md)保持原字节，仅按原适用范围使用；不跨镜像继承native或故障性能通过。

## 已解决与待解决

本轮AMD/ARM安装名版本均334且与固定清单完全一致；58个ARM wheel档案及magika通用wheel独立选取，4个sdist仍按固定工具/no-build-isolation严格哈希安装。ARM后端真实四格式/三决定/九报告通过，GUI未验收；本轮两个候选profile四服务扫描provider并集各157，单个LF各132，不能混成全默认系统的计数。三通知副本在两个image回读均一致，current native正文仍未采集。

候选锁由前轮真实334清单生成，原55条constraints保留作历史边界来源，构建改用完整哈希锁且依赖检查开启。首次wheel-only因cuid0.4无wheel失败；固定4工具并禁用build isolation后通过，未降版本或绕过依赖。候选normal CI明确Debian12，默认RHEL事务/补扫仍保留；不适用步骤标not_applicable，未知和原扫描exit保留。候选datamodel未安装仅按actual1.13.1显式记录，其余兼容探针保留。

前轮AMD官方28源/133旧记录已分类：31延期/noDSA、24 noDSA、48低优先级仍未修、28开放/未定、1可补丁、1映射未知。候选实际APT/libapt升级2.6.2并复扫移除精确DEBIAN-CVE-2026-109518；APT2011记录仍在。本轮两个LF候选各443库存=334Python+109Debian，各52个匹配包/132 provider ID；ARM匹配28个source，本轮ARM PyPI匹配0、两候选mapping/query/detail unknown0，primary exit1。跨时间/发行版/服务计数不当作独立CVE或风险变化结论；无DSA、延期、unimportant和disputed不自动成为已修或风险接受。

本轮AMD/ARM实际candidate image均已携带Langflow MIT和sqlite-vec MIT/Apache三份副本，状态recorded及SHA与repo一致。MIT与精确上游只差末尾空行；完整两种sqlite-vec原文均保留，不选择替代许可。此闭项只涵盖补充通知实际携带，不伪称wheel owntext已修或native source对应已完成。APSW owntext精确匹配仍属前轮image。候选Zep/driver等安装名及已知路径未检出，默认/API的Zep精确许可、vendor/FIPS、SQLite及系统native源码、完整前端第三方材料继续独立open；仍有IBM SDK，不统称全部Apache。

迁移校验限定列语义指纹（列名/type/nullability/相对顺序）、业务全行、用户身份、Flow和文件，以及目标PG/卷的新业务精确关联；不宣称完整DDL/default/index/constraint等价。回滚是恢复升级前检查点到第三个新旧版环境，不涵盖升级后新写入RPO0，也不操作原SQLite/历史卷。

## 保护与产物

原SQLite57,344B SHA980ad5d23d866a52e4101966594e5a24ee67edef08475afc63ff9c3e1f6fca1f；固定Spec SHAa77947d0369566cef516641ef918e37d08046afc2edf8215dcff90d49ce01753；baseline SHA5ad13f524e74554b9c8cb30b9809ffbbbbed8e3d7fa4ede5625bb1b7d781bf2e。前五包1155payload完整审计保留，上一包88payload本轮逐size/SHA核对；六旧manifest均未变，所有旧包路径相对e1d8a02无变更。默认Dockerfile/52pins、requirements.lock和AMD两锁相对上一检查点原字节一致。

新temp /private/tmp/arc-langflow-arm.tlmz8anp 上限1MiB；旧三temp加新总40MiB；CI选材600KiB/40files，source64KiB/4files，候选/正式各100MiB/1000files，沿既有源码放大停点。ZIP仅内存并核GitHub size/digest；pip报告、档案、安装树、缓存和整个构建目录不封存。临时和历史产物保留待授权处置，没有删除、迁移或压缩。

Native累计135,836,345B，余6files/26,795,216B输入/3,969,945B文本，旧101/100偏差保留。本轮target native读取0；常规CI prior-materials不重复English，不将旧正文视作新image证据。实际最终容量与只读保护记录见新manifest；旧本地Docker warning/pending_cleanup保留，未start/build/pull/prune，也不宣称重新盘点了全部本地layers归属。

## 下一步

1. 补Mac宿主实际运行、Langflow管理编辑器、候选故障恢复/性能及ARM旧schema隔离迁移；原库迁移和升级后写入恢复设计独立评估。
2. 按供应商状态继续处理132条候选Debian记录及默认/API残余，补SQLite/系统native对应源码、通知/提供方式、Zep和vendor/FIPS许可缺口，维持共享目标额度。
3. 完整发布条件、技术验收及负责人AD-03默认升级决定后才切换默认，再沿WP-08做版本历史、修改后再审、队列和失败诊断；LLM/OCR、真实身份/数据及生产部署独立选择。

普通技术同一阻塞三轮有证据无进展才停受影响范围；权限/Contract/数据/不可逆/容量即时停。最小阅读：适用AGENTS→本文件→Spec索引→活动证据→固定Spec相应WP→源码。
