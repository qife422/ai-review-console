# 候选编辑器、恢复与性能验收

日期：2026-11-05（America/Los_Angeles）。沿用 `ARC-UPGRADE@0.1.0` / WP-05 / AD-03。用户授权补齐1.13.1精简候选的管理编辑器、故障恢复及性能验证；默认 **1.11.6**、原SQLite及历史卷保持不变。此次只使用GitHub托管Linux AMD64上新建的隔离数据库、卷和虚构数据。

## 实际结果与适用范围

| 验证 | 结果 | 精确来源 |
|---|---|---|
| 执行前、回调后SIGKILL及Langflow/callback断连、401 | 5项通过，无重复评估/评分审计 | [B运行41983887326](https://github.com/qife422/ai-review-console/actions/runs/41983887326)，source `8db7f5f8a5cd6c1634a8c7a0ed40b195ff3ed424` |
| PDF部分失败、格式专用重试及环境恢复 | 通过；决定及已有JSON/HTML保留 | 同B运行 |
| 20份1MiB文档、混合查询、60份报告下载 | 严格目标通过 | 同B运行 |
| 管理编辑器 | 通过：虚构clone画布、UI改名/保存/重载及API回读 | [C运行42070564065](https://github.com/qife422/ai-review-console/actions/runs/42070564065)，source `54592dff0231ee84b992956e0ea9b99b0eecdc39` |

每项仅绑定对应source/run/image。B整轮因编辑器最终API登录429而失败，不能标记为整体success；C为editor-only，明确跳过三项已通过family。B到C仅修改编辑器探针的有界登录重试、helper外层时限、对应测试和手动CI选择，应用业务逻辑、Flow、组件、依赖锁及故障/性能生产脚本未变。B/C的Langflow和API镜像实际均不同，不把B结果继承成C精确镜像的完整验收。各服务image ID见对应`ci/*/manifest.json`。

## 故障与报告恢复

5项实际注入均只针对本轮run命名空间。中断worker实际退出137，恢复后的业务评估及评分审计均各1；两项连接拒绝先保持可重试状态再恢复。401旧任务保留failed，人工创建generation1的新任务，实际在attempt2恢复，不宣称第一次尝试成功。执行前中断约96.85s，其他故障约7.40–19.63s。

PDF专用坏字体故障保留决定和可用JSON/HTML，格式失败达到原重试边界；恢复原Langflow镜像、环境、挂载、网络及两个业务Flow后专用重试PDF。已有ready报告的ID、created_at、字节和SHA未变；决定及其审计各1，结束时active任务0。原件JSON记录了运行中下载校验断言；报告原始载荷未选入本地证据，不声称可离线重算全部报告字节。

对应固定Contract AC-06、AC-07的上述实际故障子项、AC-14及AC-18的部分失败/恢复子项；超时/配额映射的单元测试与真实断连场景分开理解，不把局部成功扩大为所有错误场景通过。

## 性能实测

| 指标 | 实测 | 目标 |
|---|---:|---:|
| 上传p95 | 38.28ms | ≤3s |
| 混合查询p95 | 83.38ms | ≤500ms |
| Intake最长 | 3.193s | 每份≤120s |
| 三格式报告最长，含下载校验 | 2.842s | 每份≤120s |
| 输入与结果 | 20×1,048,576B，20份Intake，60报告，333次查询全部成功 | 20顺序样本不丢任务 |

Linux x86_64、4 CPU、Docker29.4.2、Docker报告总内存16,759,439,360B，具体环境原件见`ci/second/performance.json`。查询三路各111次，分别为案件列表、summary、详情；各路p95约84.95/84.68/37.12ms。阈值针对聚合p95，逐路原数据亦保留。

上传计时是loopback HTTP端到端，包含本机传输和客户端开销，是保守代理而非独立服务端落盘计时。查询在提交到观察到终态的时间窗口采样，不证明每次查询抵达时任务仍在执行，也不是并发吞吐测试。报告计时包含决定到观察到三格式ready及下载校验。仅覆盖确定性规则TXT负载；实际原Flow只含5种可信规则节点支持AI关闭配置，不代表全系统出口审计或LLM性能。

## 编辑器、失败记录与自查

C专项整体success，305项Python（0失败/错误/跳过）、29项前端及构建通过。真实GUI显示4节点/3连线，保存toast后重载并由API确认新名称；两个原业务Flow的ID/图SHA前后完全一致。最终helper实际遇到一次429，遵守重试策略后成功，retry_count=1。截图经root人工查看，摄于改名前；不是参数/代码编辑或执行clone的证明。

[A运行41983022104](https://github.com/qife422/ai-review-console/actions/runs/41983022104)保留菜单定位失败；故障脚本拒绝非系统`/tmp`根目录，随后只修正CI根位置，守卫不降低。B实际UI保存/重载后，最终helper再次登录遇429，仍作为失败保留。C仅对429按Retry-After有界等待（缺失/非法用30s，最多3次尝试、90s调度期限，外层120s进程时限）；其他认证错误直接失败，不改变服务限流。

独立复审先关闭旧namespace例外、finally丢失证据及one-shot预执行绑定等发现，再核对B原件和C重试源码。Sol实施运行守卫/故障/性能，Terra实施受限UI/CI，Astra只读独立复核，root集成及证据校验。实际模型tokens和账单无法取得，估算不作实际成本。

原SQLite57,344B、Spec/baseline、默认Dockerfile及原AMD锁实际SHA复核一致；七个旧封存包共1,283个payload逐size/SHA重核通过，旧路径无改动。没有本地Docker start/build/pull/prune、原库执行/迁移或历史清理。门禁恢复时发现账本并发变化，授权锁补建操作在写前取消；随后正规门禁恢复，本代理没有手改运行态或重置累计预算，详见`environment/gate-incident.json`。

## 证据与容量

只有本包manifest列出的精确字节属于正式证据。`ci/first/second/third`的selection分别记录GitHub artifact ID、内存ZIP校验digest、原member路径、大小和SHA。未选中的完整日志、构建树、缓存、底层报告和原ZIP不称已封存；runner manifest中列出原SHA不等于保留正文。

两个Langflow v1.13.1上游测试源码只用于核对真实重命名交互，来源/SHA见`sources/source-record.json`，沿用上游MIT并附`Langflow-LICENSE.txt`；不把上游测试当作本项目已执行的测试。

新增temp限768KiB，旧四temp加新增限40MiB；本轮CI选材512KiB/40files、来源64KiB/4files，候选/正式各100MiB/1000files。沿用源码基线764,861B，超过1GiB且源码100倍停止增长；实际复核见`environment/capacity.json`。CI为20GiB入口、每5s取样5GiB余量，非硬Docker配额；计划中的source/report合计512MiB/500files是警戒估算，未实现持续卷限额；实际API配置为1GiB/5000，不将前者当已执行门禁。没有删除、迁移或压缩。

## 待解决与后续计划

1. 补Mac宿主实际运行与ARM旧schema隔离迁移；ARM管理编辑器/故障/性能未由本轮AMD继承。管理员组件参数/代码编辑及clone执行也未覆盖。升级后新写入恢复与原库迁移另行设计，不宣称RPO0。
2. 按供应商状态继续处理Debian残余、SQLite/系统native对应源码、通知/提供方式，以及默认/API的Zep、vendor/FIPS许可缺口。本轮没有重扫，不把旧候选LF132个provider记录当成本轮新镜像扫描或独立漏洞数。native累计135,836,345B，余6files/26,795,216B输入/3,969,945B文本，旧101/100偏差保留；本轮新增target native读取0。
3. 完整AC-19发布条件、完整技术验收和负责人AD-03默认升级决定后再切换默认；之后沿WP-08推进版本历史、修改后再审、队列和失败诊断。模型/OCR、真实身份/数据及生产部署仍需独立选择。

**v0.2完整发布未通过，last_verified=null，最终接受pending，残余风险未接受，后端分发未批准。** 静态虚构演示站没有重新部署。本轮沿用spec-development实施/验证规范，辅助Playwright做真实CLI交互验收；没有UI实现或视觉改造，不加载近似设计skill。
