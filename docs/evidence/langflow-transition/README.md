# 候选依赖锁与迁移验收

日期：2026-11-04（America/Los_Angeles）。沿用已批准 `ARC-UPGRADE@0.1.0` / WP-05 / AD-03；本轮累计预算已由负责人扩为360分钟，既有累计保留。默认Langflow **1.11.6**、原SQLite和历史卷不变；本轮不执行默认升级、后端发布或历史清理。

本轮有限验证已完成；正式证据仅以同目录最终manifest选入的精确字节为准，未选输出不因目录取得证据资格。完整v0.2发布状态仍为未通过。

## 已固化的输入

候选完整334个Python发行包由前轮实际安装清单固定，不再仅依赖55条constraints。`compliance/langflow-candidate.lock` 为Linux AMD64 / CPython3.12.16的完整SHA-256锁，4个构建工具另有锁；不会把这份含平台wheel的锁称为ARM/Mac通用锁。所有传递依赖仍由pip校验，不忽略依赖，也不改第三方metadata。

首次[锁定CI41951805984](https://github.com/qife422/ai-review-console/actions/runs/41951805984)因为cuid0.4无wheel而失败，诊断及原日志SHA保留在`ci/lock-first-failure.json`。后续固定pip26.2.2/setuptools84.1.0/wheel0.48.0/packaging24.2后，以`--require-hashes --no-build-isolation`完成新环境安装；[CI41952562436](https://github.com/qife422/ai-review-console/actions/runs/41952562436)，source `82a028e5738f04c9ce642e76544ffbae5554ab62`实际核实exact334和pip check。330个wheel、4个sdist（cuid和3个IBM COS SDK包）；源码档案SHA不等于已证明生成wheel字节可复现。锁、官方archive URL/SHA、安装receipt和选择来源见`ci/lock/`。

## 默认CI与候选回归

主CI保留默认1.11.6 AMD64和ARM64，增加1.13.1 AMD64候选；版本断言、OS profile和artifact名显式区分。Collector先核实际镜像`/etc/os-release`：默认RHEL保留事务与补扫；候选Debian12仍做主扫描和许可证采集，RHEL专用步骤记`not_applicable`，不伪造补扫0。候选未装datamodel-code-generator时仅在实际base/LFX1.13.1条件下记`not_installed`；其余兼容检查保留。

原native英文材料不随常规CI重复读取；`prior-materials`显式表示本次未建立新镜像native正文证据，引用旧精确image的材料不自动跨镜像生效。完整发布、unknown覆盖和许可证门槛未因profile适配降低。

默认适配首轮[CI41951752227](https://github.com/qife422/ai-review-console/actions/runs/41951752227) / `8ac0c79b8f0099e5dd7baed799b92a76692f3e67`已通过251 Python/29前端、AMD业务和浏览器、ARM后端。紧凑原件/派生项与不可变image ID见`ci/baseline/`，ARM浏览器按配置跳过。

[完整CI41953014467](https://github.com/qife422/ai-review-console/actions/runs/41953014467) / `a1190a38e998ce9683495a07028a1b9e589303cf`四任务全部success：260 Python、29前端、默认AMD/ARM及候选AMD。候选5组件/2Flow/4格式/3决定/9报告、负向失败和重试去重、ARC界面键盘交互与下载均通过；这里的浏览器是ARC业务界面，不冒称Langflow管理编辑器已验收。实际LF image `sha256:69bf80f930187d91082d50a22f5543482aea10a6c1391d64e920b120a18ed3f0`；334发行包与固定清单missing/extra/changed均空。原安装清单、工作流、探针、扫描summary及有指纹的许可证子集见`ci/current/`。迁移结果独立于此CI。

## 隔离迁移与回滚边界

迁移入口仅允许GitHub当前run/attempt的三个全新namespace：baseline、upgrade、rollback；四个卷必须为项目自有local空定义卷，拒绝其他bind、历史卷或已有目标。先在新1.11.6库生成5个虚构案件、5份文档、9份报告和两条Flow，停写后创建两份plain dump及15个文件的检查点。raw dump和文件复制仅在新runner临时目录内，不上传、不复制原库。

upgrade先创建空PG及文件卷并恢复检查点，再启动1.13.1迁移自身schema；不重跑Flow bootstrap、不PATCH旧图、不执行应用修复迁移。验证列语义指纹（列名/type/nullability/相对顺序）、原业务全行、用户身份、Flow ID/graph及文件字节，再真实处理5个新案件，并把API返回、目标PG的DVID/任务/报告、目标卷文件SHA逐项关联。这里不是完整DDL/default/index/constraint等价证明。rollback恢复同一个**升级前**检查点到第三个新1.11.6环境，并重复真实业务验证；不表示原地降级或升级后新写入零丢失。

独立审查曾发现仅比对旧行子集可能跨环境假通过，已补真实端口/DB/网络/卷绑定和目标SQL/文件精确增量验证。冻结入口和修复后producer复查未发现剩余阻塞；这是代码审查，不替代实际CI。记录见`environment/migration-review.json`。

首轮[迁移CI41953022635](https://github.com/qife422/ai-review-console/actions/runs/41953022635)成功生成基线和检查点，在空库restore后的指纹比较停止，尚未启动1.13.1；诊断见`ci/migration/failure.json`，未选存原失败目标的raw schema。后续producer只把物理列序号归一成现存列相对顺序；列增删/改名/改序/type/nullability及业务、用户、Flow、文件断言继续严格比较。36项针对测试及独立负例复核通过，见`environment/environment-review.json`。

[迁移/回滚CI41954322019](https://github.com/qife422/ai-review-console/actions/runs/41954322019) / source `480246c00a94ecee420f4d778ebf302acf3d4b79`实际success。升级目标观察1.13.1、LF Alembic `d19e7b3c5a42`→`e4f6a8b2c1d3`；回滚目标观察1.11.6，仍为升级前revision。两目标各精确新增5cases/5documents/3decisions/9reports/9jobs，旧业务全行、两Flow身份/图和15个检查点文件保持，新增结果与各自目标SQL/卷逐项关联。实际migration LF image `sha256:b8ad829904ab7caa1700f521188d0c4a97d83416d0a970fe4bcb908d1c7a03ba`，与常规CI image独立，不跨image继承扫描。完整8个原JSON与选取来源见`ci/migration/`；capacity JSONL仅保留有原SHA的样本数/min/floor派生项，未选原全文。

新run的源LF `deployment`列live11/max12、`deployment_provider_account`列live9/max10；两个restore的孔洞均为空，raw schema SHA不同而完整列/行语义指纹一致。这直接支持本轮PG逻辑恢复压实物理列序的诊断；首失败目标raw未保留，不声称已逐字段重建首轮差异。回滚没有恢复升级后新增写入，也没有将历史故障/性能结果继承到候选。

## Debian与许可证

前轮133个provider ID涉及28源/52binary。按28个[Debian官方tracker源页面](https://security-tracker.debian.org/tracker/)及精确CVE条目分类：31延期/noDSA、24 noDSA、48低优先级仍未修、28开放/未定、1当前有补丁、1无发行版映射。这些是非重叠展示分类，不是CVSS、独立CVE或可利用性结论；完整衍生表、URL、时间及原HTML指纹见`sources/debian-tracker-assessment.json`，未选原页面全文。

APT的[CVE-2026-109518](https://security-tracker.debian.org/tracker/CVE-2026-109518)有同Bookworm补丁2.6.2。[官方security索引](https://deb.debian.org/debian-security/dists/bookworm-security/main/binary-amd64/Packages.xz)列出apt/libapt-pkg6.0 2.6.2，压缩索引SHA与InRelease条目匹配；该研究未独立验证OpenPGP。新实际镜像清单核实两包均2.6.2，复扫已无该精确2026 ID；APT的2011记录仍在。当前候选仍52binary/28source/132 provider ID，PyPI匹配0，mapping/query/detail unknown0；primary exit1保留。`environment/debian-delta.json`保留两快照原件指纹及集合差（仅该ID移出、无新增），不将跨时间计数或官方低优先级标签当作全部风险闭合。GnuTLS的[CVE-2026-95209](https://security-tracker.debian.org/tracker/CVE-2026-95209)虽有disputed描述但缺发行版表，继续未知，不直接排除。

仓库补入sqlite-vec0.1.9精确上游MIT和Apache两份原文，不选择替代许可；Apache响应与前轮指纹一致。Langflow/LFX1.13.1根MIT已有完整副本，与上游仅差末尾空行。新实际image三份project_files均`recorded`，1,066/1,068/10,931B及SHA与仓库逐字一致，关闭这三份补充副本实际携带的证据缺口；见`ci/current/collector-license-summary.json`。这些补充随包通知，不声称修复wheel own-text、不证明SQLite/native source对应或全部分发义务。APSW owntext匹配仍是前轮精确image的结论。Zep/driver在候选安装名及已知路径未检出，默认/API义务仍在；保留IBM SDK不能统称全部Apache或全部移除。

## 保护、容量与复核

原SQLite57,344B SHA `980ad5d23d866a52e4101966594e5a24ee67edef08475afc63ff9c3e1f6fca1f`；Spec SHA `a77947d0369566cef516641ef918e37d08046afc2edf8215dcff90d49ce01753`，baseline SHA `5ad13f524e74554b9c8cb30b9809ffbbbbed8e3d7fa4ede5625bb1b7d781bf2e`。默认Dockerfile含52inline pins且requirements.lock与8e96a36逐字一致；五旧包1155 payload逐文件size/SHA不变，见`environment/protected-input-review.json`。本地Docker不start/build/pull/prune，旧容量warning保留。

新temp2MiB，旧两temp加新总40MiB；选CI1MiB/50files，source128KiB/8files；候选和正式各100MiB/1000files，超过1GiB且源码100倍停止增长。新runner构建/安装有入口容量检查，迁移30GiB、锁20GiB；每5秒采样5GiB floor并中止命令，这不是Docker硬配额。迁移dump各8MiB/总32MiB、文件100件/32MiB、只选明确meta，不上传整树。未授权删除、压缩或历史迁移。实际CI选材39files/733,901B，sources3files/54,206B；最终量见environment/capacity.json及manifest。

native累计135,836,345B，余6files/26,795,216B输入/3,969,945B文本；本轮无新增target native读取，不重置旧101/100偏差或旧raw口径。泛化license/project通知与OS库存采集不冒充新native source验证。

## 后续计划

1. 对仍未修Debian记录保留官方状态与补丁复核；补SQLite/系统native的源码、通知、提供方式及上游前端第三方材料。默认/API的Zep及vendor/FIPS缺口独立保留。
2. 为候选补ARM独立平台锁/构建与原生对应材料、Mac宿主范围、Langflow管理编辑器、故障/恢复与性能。新库/检查点迁移成功不替代生产数据迁移审批或升级后写入恢复设计。
3. 完整发布条件、技术验收及负责人默认升级决定之后，才按AD-03替换默认；之后沿WP-08做版本历史/修改后再审、队列和失败诊断。LLM/OCR、真实身份/数据、生产部署继续独立选择。

WP-05仍implementing；AC-19未通过、完整last_verified=null、最终接受pending、残余风险未接受、后端分发未批准。主skill spec-development；现有Playwright CLI用于真实浏览器验收，无UI设计变化，不叠加设计或安全审查skill。Sol实施锁和迁移，Terra适配CI，Astra独立高风险审查；模型实际token/费用不可用，未编造计费或效率数字。
