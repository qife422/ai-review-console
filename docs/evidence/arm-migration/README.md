# ARM 隔离迁移与检查点恢复

日期：2026-11-05（America/Los_Angeles）。沿用 `ARC-UPGRADE@0.1.0` / WP-05 / AC-17 / AD-03候选验证。用户明确允许后续计划继续，并将同目标累计预算扩至460分钟；原累计、修复次数和保护边界保留。默认Langflow **1.11.6**、原SQLite和历史卷不变。本包只覆盖GitHub新建Linux ARM64环境和完全虚构的数据。

正式证据只由最终manifest列出的精确字节取得资格；本轮成功与未测范围分别记录，不改变完整v0.2发布状态。

## 实际运行

[CI42086830311](https://github.com/qife422/ai-review-console/actions/runs/42086830311)，source `7877364c17f5442df620f8be5c0f6f5a2c6f0d21`。实际整体success，所有job步骤成功，原生ARM单job用时672秒。GitHub artifact13443877085的内存ZIP50,527B，官方SHA-256 `7220b8371291bfea81f6610a5e43e0b1b94c33d40d845bf437962fbd8666b5db`核对一致；10个原始member及选择receipt已固定。

| 阶段 | 操作及验收范围 | 本轮结果 |
|---|---|---|
| baseline | 新1.11.6中生成5个虚构案件、文档及9报告；停写后取得两库plain dump和文件检查点 | 通过：5案/5文档/9报告；检查点15文件/211,475B |
| upgrade | 恢复同一检查点到空PG/文件卷，启动1.13.1自身schema迁移；禁止重新bootstrap、PATCH旧图或执行应用修复迁移 | 通过：旧数据/Flow/文件保全，各项新增业务精确关联 |
| rollback | 将升级前检查点恢复到第三个空1.11.6环境，再做真实新业务校验 | 通过：同一升级前检查点，独立新目标业务验证通过 |

两个目标分别实证1.13.1、1.11.6，各新增5案件、5文档版本、3决定、9报告、9任务；校验包含3个常规审批样本，另有Markdown和负向失败/重试去重，共5案。旧业务行、用户身份、两条Flow的ID/graph和15个检查点文件由producer逐项验证保持。Langflow检查点Alembic为`d19e7b3c5a42`，候选启动后为`e4f6a8b2c1d3`，旧版恢复保持原revision。

`before_schema`为检查点指纹，`after_schema`为启动后、业务验证前快照；新增数量来自producer实际SQL和文件关联断言，不能从这两个快照独立重算增量。旧列的name/type/nullability/相对顺序按语义核对，plain dump恢复压实了物理ordinal gaps，不宣称物理schema原字节、完整DDL/default/index/constraint等价。raw dumps及文件载荷未封存，离线读者不能在本包重跑其字节验证；原JSON保留运行时断言与指纹。负向重试仍失败是预期边界，不当作ARM正向故障恢复通过。

## 架构与隔离保护

手动workflow保留名称和默认AMD64入口，只新增architecture选择；本轮选择`arm64`并使用`ubuntu-24.04-arm`。入口要求runner变量、Linux宿主机及Docker server报告的架构一致；在任何基线数据写入前核对旧版LF、候选LF、API、Web和PostgreSQL五个实际镜像均为linux/arm64，记录完整image ID。PostgreSQL引用从有效Compose取得且保持固定digest，bounded pull后再检查；不把标签或候选自身断言当作其余镜像的平台证明。

候选Dockerfile仍按TARGETARCH选择既有ARM334包/4工具哈希锁；两平台锁均有source SHA，实际选择在runner manifest中明确记录。没有修改依赖、Dockerfile、Compose或迁移producer。实际host/Docker/image平台记录见选入的`ci/architecture.json`，不冒称Mac宿主或硬件安全认证。

三阶段始终采用当前GitHub run/attempt的精确独立namespace，拒绝已有目标、外部历史卷和非白名单bind。恢复前绑定实际项目labels、镜像、挂载、网络及loopback目标；空库/空存储检查、baseline停写、旧业务/Flow/文件守恒和目标新增业务逐项关联继续保留。这里的rollback是检查点恢复，**不是原地降级，也不涵盖升级后新增写入RPO0**。

## 验证与首个失败

初次source `6725640591784a51164ad1515318a99e3a5f94ed`在workflow dispatch返回HTTP422：job级env不能使用`runner.arch`上下文，未进入有效迁移执行。修复仅将架构来源改为首步骤读取标准`RUNNER_ARCH`并通过GITHUB_ENV传递；平台及数据保护不降低。[官方上下文限制](https://docs.github.com/en/actions/reference/workflows-and-actions/contexts#context-availability)、[标准环境变量](https://docs.github.com/en/actions/reference/workflows-and-actions/variables)作为诊断依据。

迁移producer与入口合计42项本地测试通过；修复上述解析问题后，11项入口测试再次通过，包括shell/嵌入Python编译，以及真实执行平台记录校验的合法输入和错误arch、OS、ID、数量负例。Ruff和diff检查通过。这些不是新镜像内的完整应用回归，实际迁移仍以本轮CI原件为准。

Terra实施限定workflow/test，Sol只读评估既有producer/Compose的ARM兼容性，Astra独立检查固定候选及小范围修复，root集成和回读。独立复审未发现剩余阻塞，不以模型意见代替真实CI。实际模型tokens和账单未知，不把估算当用量。

## 来源、容量与保护

仅最终manifest列出的精确字节为正式证据。GitHub ZIP只在内存核官方大小/digest，紧凑选材直接写入忽略的候选目录；不落盘原ZIP、不复制完整构建树、缓存、raw dumps或整套检查点文件。selection记录原member、大小/SHA和派生项方法，未选全文不称已封存。

新增temp `/private/tmp/arc-arm-migration.sr1d4ffq` 限64KiB/12files，旧六temp加新增合计40MiB；CI选材512KiB/40files，候选/正式各沿用100MiB/1000files。源码放大分母764,861B，超过1GiB且100倍停增。runner30GiB入口、每5s采样5GiB余量；dump单份8MiB/合计32MiB、检查点100文件/32MiB、runner选材1MiB/20files，均非Docker硬配额。

本轮新增定向上游native/source材料采集0；正常CI依赖构建网络不计作取证材料正文。native累计135,836,345B、余6files/26,795,216B输入/3,969,945B文本，旧101/100偏差保留。本地Docker旧容量warning继续保留，没有start/build/pull/prune。固定输入及九旧manifest新SHA复核一致、旧路径无diff；前轮8包1,325payload完整核验和release-gaps的10payload封存核验沿链保留，不宣称本轮重复全读。没有清理、迁移、压缩历史产物或读写原库。

## 待解决与下一步

1. Mac宿主实际运行仍受本地容量/daemon状态约束；ARM管理编辑器、故障和性能没有由此次迁移推定通过。组件参数/代码编辑及clone执行仍未覆盖；按固定Contract和目标平台判断必要项，不随意新增发布门槛。
2. Zep精确2.0.2许可仍待[上游#368](https://github.com/getzep/zep-python/issues/368)回复；Debian供应商处置、默认/API及候选native/source、IBM/vendor/FIPS和完整分发条件继续open。本轮未新扫描，旧132 LF provider记录不继承成此次image扫描或独立漏洞数。
3. 完整技术/分发条件和负责人AD-03决定后才评审默认切换，再推进WP-08版本历史、修改后再审、队列及失败诊断。原库迁移、升级后写入恢复、真实身份/数据、模型/OCR及生产部署继续分别授权。

**AC-19未通过、完整last_verified=null、最终接受pending；残余风险未接受、后端分发未批准、默认未切换、原库未迁移、静态演示未重部署。** 本轮按spec-development实施/验证规范执行；无UI变更或浏览器验收，不加载设计或浏览器skill。
