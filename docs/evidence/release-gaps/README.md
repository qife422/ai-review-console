# 发布缺口与 Zep 许可复核

日期：2026-11-05（America/Los_Angeles）。沿用 `ARC-UPGRADE@0.1.0` / WP-05 / RELEASE-001、AC-19；用户批准按计划继续发布门禁收尾。此轮完成精确许可复查、服务归属纠正、可关闭条件及后续行动清单，**没有关闭Zep许可或完整发布门禁**。默认1.11.6、原库和历史证据不变。

## 定向复核结果

重新从官方PyPI取得2.0.2元数据和两个发行档案，校验官方大小/SHA后仅在内存检查文件清单、包元数据及sdist pyproject；档案不落盘、不安装、不执行代码。官方tag仍指向`c5f9144aa065706294c7e43ae1b954fd0a8d9039`，完整80项tree未截断，pyproject与sdist字节相同。wheel/sdist元数据未声明许可、档案和tag树未发现许可命名文件；这不是证明所有源码绝无授权信息，但仍不足以确认精确发行包的许可。

当前主分支Apache-2.0文本和oss分支1.5.0不能直接覆盖2.0.2。新旧PyPI响应、发行档案及tag来源指纹相符；此次复查提供当前事实，不代表原问题已改善，也不再重复相同输入的等价尝试。`zep-recheck.json`记录9次请求、111,442B及每个URL/status/size/SHA、派生字段与完整档案member清单；未保留的原始响应/档案不冒称全文已封存。另做2次只读issue搜索，共40,476B；相关[issue304](https://github.com/getzep/zep-python/issues/304)是zep-cloud元数据问题，当前0回复，不能作为2.0.2许可依据。合计11次请求151,918B，未重复发送问题。

Zep的已实证owner是**默认Langflow**；API的已实证owner为psycopg-binary3.3.5，不能笼统写成“默认/API都含Zep”。精确历史image、来源SHA及各次运行绑定见`profile-bindings.json`。候选在原精确image范围内未检出Zep，只能支持候选路径，不会消除默认image中该包的问题。

## 发布阻塞与关闭条件

| 项目 | 已有证据与缺项 | 可关闭条件 | 下一动作 |
|---|---|---|---|
| 默认LF：Zep2.0.2 | 精确wheel/sdist/tag仍缺充分明确许可依据；本轮复查仍OPEN | 取得维护者或同等权威的精确发行许可依据，保留适用文本并验证目标镜像实际携带；或在负责人批准后采用不含该包且验收完整的运行时 | 使用已备好的上游澄清草稿；目前未发送，不伪造补充许可、不修改包metadata |
| API/LF：native/vendor/FIPS | API Psycopg3.3.5与LF Psycopg3.3.4/Psycopg2 2.9.12分属不同owner；旧ARM FIPS及部分厂商source/build对应仍缺；AMD clidriver英文材料不等于全部文件满足分发条件 | 按实际service/image/arch完成通知、精确源码/补丁/构建关联及提供方式；IBM driver还需实际文件对白名单/协议，不由wrapper Apache许可替代 | 先固定拟分发制品，再选择能关闭具体缺项的最小采集目标；不盲目重读native |
| 候选：SQLite/系统库/前端 | 三份MIT/sqlite-vec副本已在旧精确候选image回读；APSW旧原文与其他native/前端完整对应范围不同 | SQLite/sqlite-vec/APSW、libpq及其他组件的source/build/notices按最终制品闭合；前端按实际bundle核完整通知 | 列最终制品材料包；不把三份副本当成整个镜像分发批准 |
| 安全处置与制品绑定 | e6f6fe7常规候选LF各132 provider记录、扫描exit1；B/C专项没有新扫描，不能拼成某个最终image的全项通过 | 对最终制品执行适用扫描；逐项记录可补丁、上游未修、缺映射/材料及需负责人明确决定的风险；不要求无依据清零 | 复用既有分类拟定处置，再对确定的最终制品集中复验；不跨image继承旧结果 |
| 平台/迁移与技术验收 | Linux双架构后端、AMD历史检查点恢复、B故障性能、C编辑器各有独立证据；Mac/ARM旧schema与部分管理/故障场景未覆盖 | 按固定Contract与目标平台确认必需项并取得实际证据；未覆盖项继续明确列出，不自动将扩展测试变成新门禁 | 先做Mac容量入口和ARM隔离迁移范围判断，再补必要项；原库迁移/升级后写入恢复另行设计 |
| 完整发布/默认切换 | AC-19未通过、完整last_verified=null、最终接受pending | 完整技术与分发条件满足，取得AD-03默认升级决定、最终接受及对应发布授权 | 维持默认1.11.6和原数据；后续WP-08功能在发布缺口处理后排期 |

[上游许可澄清草稿](upstream-license-question.md)已经写好，未向第三方发消息或开issue。它列明两个发行档案、tag、缺少的依据及三个精确问题；需要联系上游时可直接审阅此固定内容。

## 容量、验证与保护

本机Docker daemon当前不可连接，无法重新读取image/shared-layer/build-cache内部容量或归属；没有启动daemon、构建、拉取或prune。精确Docker.raw路径只读stat：逻辑245,106,737,152B，实际分配29,555,404,800B；这两个数字都不是镜像/缓存分类容量，也不代表已完成内部盘点。旧容量warning/pending_cleanup继续保留。当前五个既有temp合计41,437,427B；新增temp限256KiB、全部命名temp限40MiB，详见`capacity.json`。

本轮网络上限512KiB/12请求，原ZIP/tar只在内存；选材限128KiB/20files，候选/正式各沿用100MiB/1000files，源码基线764,861B、超过1GiB且100倍停止增长。没有清理、迁移、压缩或整体复制历史目录。native累计135,836,345B与余6files/26,795,216B输入/3,969,945B文本不变，旧101/100偏差保留；本轮target native读取0。

本轮只修改文档/最小证据，不改业务、依赖、Dockerfile或Flow；不重复未变化的应用测试。验证包含上游身份/档案大小SHA/tag对应断言、服务归属与旧证据比对、链接和manifest完整性、独立只读复核，以及GitHub远端回读。旧业务回归仍按各原source/run/image使用，不称已重跑。部分说明文档是Docker COPY输入，最终文档提交没有构建新镜像，不能把旧image作为最终文档制品。

Sol做服务归属与缺口分析，root做有界采集和集成，Astra只读独立复核；实际模型tokens/账单未知，同目标累计360分钟上限保持。沿用spec-development验证规范；无UI或代码实现，不加载设计或浏览器skill。正式证据仅以最终manifest列出的精确字节为准，缓存、未选响应和目录名不授予证据资格。

**完整发布仍未通过；Zep许可未确认、残余风险未接受、后端分发未批准、默认未切换、原库未迁移、静态演示未重部署。**下一步存在明确外部证据边界：先取得2.0.2许可澄清，或在候选其他发布条件满足后提交AD-03决定；继续重复相同来源不能代替这些证据或决定。
