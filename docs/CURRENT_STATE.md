# 当前状态

更新日期：2026-11-05（America/Los_Angeles）。冷启动以本文件、固定Contract、实际源码及精确范围证据为准。

本轮用户已授权先核独立Mac验收目标及容量，条件满足后仅虚构业务回归、自查同步GitHub。只读预检完成：白名单内仅原Desktop两个同一socket入口，尚无已指认的独立Mac业务目标/独立存储与资源归属证据，故业务not_started（非测试失败）。完整结论、最小5案9报告入口与恢复条件见[恢复说明](DOCKER_RECOVERY.md#mac-业务回归准入复核)。同goal600分钟、约497分钟起累计和既有失败计数2保留；默认1.11.6、原数据、历史保护继续，无安装/创建/扩盘/清理授权扩张。

此前负责人已批准ARC-UPGRADE@0.1.0及WP-00..05 continuous；ARM虚构PG迁移/检查点恢复等有限验证已完成。用户前轮已批准cad3703单VM容量例外（逻辑≤6GiB、实际增长≤3GiB）及同目标累计600分钟，保留约448分钟起的既有累计与修复次数；允许先有限下载核验制品/签名/依赖，满足后仅在独立Linux VM做虚构恢复实验。随后另明确批准宿主验签专用OpenPGP.js6.3.2，并将该同包网络上限精确修正为5MiB（包含≤256KiB超读，仅续传306287B），无全局安装/安装脚本/新依赖，不进入VM。原Desktop、默认1.11.6、原始数据和历史产物继续保护；不授权原Desktop启动、历史清理、默认替换、后端发布或任何非本VM安装。门禁只覆盖工作区shell/文件补丁，不授予权限。

| 轴 | 当前状态 |
|---|---|
| Contract | approved/0.1.0，固定字节不变 |
| 交付 | implementing；WP-05完整发布open；Linux辅助机制已验证；本轮Mac准入预检完成、独立目标/存储/容量证据未满足，条件授权的业务回归not_started；Zep/native及完整验收仍待完成 |
| Mac宿主 | 本轮macOS26.5.2/build25F84 arm64/8GiB/8CPU，可用约32.53GiB；仅原Desktop同一socket的两个别名，未连接引擎或认定空库存；白名单未发现合格独立Mac目标，未覆盖自定义/远程环境 |
| 默认运行时 | 1.11.6，原Dockerfile含52inline pins及既有补丁，字节不变 |
| 精简候选 | base/LFX1.13.1；独立AMD64/ARM64各334包/4工具SHA锁及已验证实际清单 |
| 既有常规CI | e6f6fe7 / 41979142562 success：271 Python/29前端，默认与候选各AMD/ARM后端、AMD业务浏览器；ARM GUI跳过 |
| 管理编辑器 | 通过虚构副本改名、保存、重载及API回读（C专项success，305项Python/29项前端通过）；只覆盖虚构clone画布与UI改名/保存/重载/API回读 |
| 故障与报告恢复 | B41983887326：5项故障及PDF部分失败/专用重试通过；401旧任务failed，人工generation1新任务attempt2恢复 |
| 性能 | B：20×1MiB、333查询、60报告；上传p95 38.28ms、查询p95 83.38ms；Intake最长3.193s、三报告含下载最长2.842s |
| 隔离迁移/回滚 | ARM7877364 / 42086830311与旧AMD480246c / 41954322019各有独立实证；两架构各新1.13.1及第三新1.11.6，目标各新增5案/9报告；不涵盖原库或升级后写入RPO0 |
| 系统与许可 | 旧精确候选各132 LF provider记录；默认LF的Zep/IBM driver及各API/LF精确image的native/source/FIPS分发缺口仍open；本轮未重扫 |
| 发布与接受 | AC-19 not passed；完整last_verified=null；最终接受pending，未接受残余风险或批准后端分发 |
| 保护 | 10固定输入、12既有封存manifest匹配；原Desktop外部活动单独记录；本轮未连接socket、启停/创建环境、build/pull/清理或执行原库，不声称全部历史盘字节未变 |

## 活动证据

- [前轮Linux合成恢复实证](evidence/linux-vm/README.md)，[manifest](evidence/linux-vm/manifest.json) SHA-256 `206c4b959c8ef44d30ef72d9c17a770af2c557234efe7f426fb9e7cadc091808`：六主制品及签名链/负控已验，三DEB只在新guest提取；两组五策略、live-restore/AutoRemove通过，c1d2 exit0/59.161秒，两失败及修正保留。最终VM Stopped，17文件129434B正式小包；固定[恢复说明](DOCKER_RECOVERY.md)记录实际边界/停点。峰值逻辑约4.82GiB/分配1.98GiB，未触限；不是Mac/AC-17业务或AC-19通过，原盘保护不由Linux结论推定。
- [前轮Mac宿主及Docker恢复预检](evidence/mac-host/README.md)，[正式manifest](evidence/mac-host/manifest.json) SHA-256 `9d74ef908847c7007ed1cac0e36d1e9e5e3772b1e5f813b2cdf77e2234e20305`。两个context指向同一缺失socket，info失败后的零值server结构不当作空engine；未启动Desktop或本机业务验收。用户明确保持保护、仅同步预检；不把条件未满足记为Mac测试失败。
- [本轮ARM隔离迁移与检查点恢复](evidence/arm-migration/README.md)，[正式manifest](evidence/arm-migration/manifest.json) SHA-256 `abf078ccd1dbd11aa6908138a89e15d8299c4cc0ab4c5da87d99648d0a18e346`。[CI42086830311](https://github.com/qife422/ai-review-console/actions/runs/42086830311) / source7877364c17f5442df620f8be5c0f6f5a2c6f0d21整体success，Linux/aarch64、runnerARM64、五个image实际arm64。两目标分别1.13.1/1.11.6，各新增5案/5文档/3决定/9报告/9任务，旧业务/Flow及15文件保全；LF候选image sha256:56dfce34864f75eb9e78dd02293a5f5a0bbd778789beef58d08eba3c25f7a07e。首个6725640的422和修复记录保留。
- [本轮发布缺口矩阵、关闭条件和Zep复查](evidence/release-gaps/README.md)：已封存，[manifest](evidence/release-gaps/manifest.json) SHA-256 `cd5b73563dcbe6b257d05765ecf74b7356c41ff2d42bcd0497779fd9657c3872`。9次官方请求111,442B；精确2.0.2许可仍OPEN，未修改runtime或重复应用测试。封存时上游澄清草稿尚未发送；随后经用户明确批准，已按批准稿发布[上游issue #368](https://github.com/getzep/zep-python/issues/368)，发布后回读时open、0回复，待维护者澄清。旧封存包保持原字节，问题提交不构成许可闭项或后端分发批准。
- [本轮编辑器、恢复与性能结果及计划](evidence/candidate-acceptance/README.md)，[正式manifest](evidence/candidate-acceptance/manifest.json)，SHA-256 `d9736e997bf048f2e46337daa65089131f9d84c3613ea5a61143fed41c532fc1`。
- [B运行41983887326](https://github.com/qife422/ai-review-console/actions/runs/41983887326)，source8db7f5f8a5cd6c1634a8c7a0ed40b195ff3ed424：故障、PDF恢复、性能及301项单元通过；整轮因编辑器最终登录429而failed。LF image sha256:b836bf131480cd92747e8e50f54324fd3d76531137a59fa214e32549f2b44966，API/worker sha256:de0ace4c6c71bef46334aa8f360ae8fd3bcde0dab042f0d613dd7a9c4a40c411。
- [C编辑器专项42070564065](https://github.com/qife422/ai-review-console/actions/runs/42070564065)，source54592dff0231ee84b992956e0ea9b99b0eecdc39：通过虚构副本改名、保存、重载及API回读（C专项success，305项Python/29项前端通过）。只修429探针有界等待、helper外层时限、对应测试及手动CI选择；B故障/报告/性能明确跳过，不变成C精确image全项通过。
- [候选ARM证据](evidence/langflow-arm/README.md)及[完整常规CI41979142562](https://github.com/qife422/ai-review-console/actions/runs/41979142562)：source e6f6fe7b908b7fab1b4f85e9f5a4fa22890fc923；两架构334实际清单及三份许可副本回读通过，只按原source/image适用。
- [依赖锁/隔离迁移](evidence/langflow-transition/README.md)、[候选评估](evidence/langflow-candidate/README.md)、[系统维护](evidence/runtime-maintenance/README.md)、[兼容补验](evidence/release-compatibility/README.md)、[发布扫描](evidence/v02-release/README.md)、[早期验收](evidence/v02-acceptance/README.md)保留原字节，各自manifest决定范围。

## 结果边界

既有候选专项证据支持AC-06、AC-07上述故障子项、AC-14及AC-18部分失败/恢复子项与固定Spec顺序规则基准。实际超时/配额全部故障、Mac宿主、ARM管理/故障/性能不由本轮迁移结果推定通过。编辑器不覆盖组件参数/代码编辑或clone执行。

性能环境为Linux AMD64、4 CPU、Docker29.4.2、报告总内存16,759,439,360B，限确定性规则TXT。上传是loopback HTTP端到端保守代理，包含客户端/传输而非单独落盘计时；查询在提交至观察终态窗口采样，非并发吞吐，也不证明每次查询时任务尚在执行；报告包含三格式ready观察及下载校验。实际Flow只含可信规则节点支持AI关闭配置，不是系统出口审计。原件与独立复审在本轮包内；未选全文的XML、日志和报告只保留来源或派生记录，不冒称完整封存。

旧候选APT/libapt2.6.2补丁及通知实际携带按前轮精确image记录；单LF132与四服务provider并集157范围不同，不作独立CVE数量或新image扫描。本轮新增target native读取0；累计135,836,345B，余6files/26,795,216B输入/3,969,945B文本，旧101/100偏差保留。候选未检出Zep不能关闭默认LF的Zep缺口或API其他native缺口。

本轮Mac预检是带命令/方法和时点的派生观察，记于既有恢复说明；没有新的业务运行证据包、测试通过或当前原engine库存。宿主free快照不等于项目容量/原盘写入准入。

## 自查、保护与产物

原SQLite57,344B SHA980ad5d23d866a52e4101966594e5a24ee67edef08475afc63ff9c3e1f6fca1f；固定Spec SHAa77947d0369566cef516641ef918e37d08046afc2edf8215dcff90d49ce01753；baseline SHA5ad13f524e74554b9c8cb30b9809ffbbbbed8e3d7fa4ede5625bb1b7d781bf2e。默认Dockerfile/52pins、requirements.lock和AMD两锁字节未变；本轮10固定输入及十一旧manifest新SHA核对一致，旧包路径无改动；前轮8包1,325payload全读与release-gaps的10payload封存核验沿链保留，不冒称本轮重读全部历史正文。没有原库执行、迁移或挂载。

候选专项temp `/private/tmp/arc-candidate-acceptance.1gcqlp6y` 限768KiB；旧四temp加新增限40MiB，CI选材512KiB/40files、来源64KiB/4files，候选/正式各100MiB/1000files，沿既有源码放大停点。ZIP只在内存校验官方size/digest；完整日志/构建/缓存及未选报告不入包。CI20GiB入口/5GiB取样余量不是Docker硬配额；512MiB/500files只是计划警戒估算，未实施持续卷限额，API实际配置1GiB/5000。容量实测见本轮environment记录。原Desktop旧warning/pending_cleanup保留，本代理未对其start/build/pull/prune，未宣称全layers归属已盘清；本轮获批单VM例外及实际增长另见Linux小包。

前轮本机只读容量复核：Docker daemon不可连接，内部image/shared-layer/cache容量和归属unavailable；未启动服务。Docker.raw逻辑245,106,737,152B、分配29,555,404,800B，非镜像/缓存分类统计。旧五temp合计41,437,427B；新增 `/private/tmp/arc-release-gaps.gsh2c_pd` 临时根限256KiB，合计仍限40MiB。没有新增native目标读取。

缺失receipt.lock时，用户授权的最小补建因账本并发变化在写前取消；正规门禁随后恢复。本代理没有手工改账本/门禁代码、补建锁或重置累计计时，具体记录保留。临时和历史产物没有删除、迁移或压缩。

后续同步曾因门禁源码变更与旧回调指纹不符而停止。现已实际读取最新工作区AGENTS、规则索引及开发范式，保留固定Contract；用户确认四条更新hook全部通过后，接续原目标。只读及正规计量入口现可调用，本次按授权恢复两份文档同步；不把这些观察扩大为所有产品生命周期或MCP/浏览器/云端均已验证。没有自动切换模型、另建Spec或证据包。

前轮ARM只读选材212,734B/11files；新temp `/private/tmp/arc-arm-migration.sr1d4ffq` 限64KiB/12files，旧六temp加新总40MiB，紧凑CI选材直接入候选而非重复落入temp。runner30GiB入口/5GiB取样余量、dump各8MiB/总32MiB、检查点100文件/32MiB，非硬Docker配额；实际大小、来源与保护见新包。没有新增target native读取或本地Docker操作。

前轮Mac只读复核确认旧Docker增长警戒和完整项目12GiB归属仍无法关闭，实际历史restart policy不可读。Docker.raw仅stat、设置正文open未返的自有探针已中断；没有重置/损坏诊断或Docker进程信号。30GiB是既有CI迁移入口，不自动新增为本机5案门槛；17.7GiB余量/8GiB内存不单独作为失败判据。预检选材及容量见新包；不创建替代引擎或磁盘绕过停点。

前轮新增运行根/private/tmp/arc-linux-vm，单VM逻辑6GiB/实际增长3GiB例外及累计600分钟已获批准，其他原阈值不变。observer正常结束、VM停止，无自有后台等待。OpenPGP.js仅宿主验签，5MiB修正、摘要及解包17.4MB/43文件均核。原Desktop于12:59外部启动，用户已确认来源；原Docker.raw分配量/mtime变化见新包，不对其全局不变作保证。Sol实施、Astra独立复核、root实际执行与集成；本轮两失败两修正保留，累计不重置。

## 后续计划

上游沟通已完成：#368由qife422于2026-11-05发布，标题和1748字符正文回读与批准稿一致；正文SHA-256 `665ded10bc7302e118d45ed6204549fc34930b67f9af4439e2a49d41da406cb7`。连接器创建因integration权限403未执行成功，改用已登录CLI发布，再通过连接器GET核实。下一项是由维护者提供精确2.0.2的许可说明；收到后由Agent核对来源、版本及适用范围。当前没有运行中的等待任务或自动监控，不重复提交issue；Zep及完整AC-19继续open。

1. 本轮Mac业务准入预检完成，尚缺已指认独立目标、双端点/新卷绑定及资源归属/增长证据。由环境操作者提供Mac上独立实例标识、接入方式和独立存储位置（可位于当前Mac）；Agent按已有条件授权继续核实，满足后运行现有5案9报告入口（非性能/迁移/完整Mac UI验收）。不在原Desktop旧盘试跑，不伪造CI变量或把Linuxprobe用于全栈。
2. 由Agent按最终制品范围选择一项可闭合的native/source材料或系统处置，保持共享采集与累计预算；Zep精确许可仍依赖维护者回复#368，不能以重复复查代替依据。SQLite/系统native通知和提供方式、默认LF的Zep/IBM driver及各image的vendor/FIPS条件继续open。
3. 完整发布条件、技术验收和负责人AD-03决定后才切换默认，再沿WP-08推进版本历史、修改后再审、队列及失败诊断；模型/OCR、真实身份/数据、生产部署仍有独立选择。

普通技术同一阻塞三轮有证据无进展才停受影响范围；权限/Contract/数据/不可逆/容量立即停。最小阅读：适用AGENTS→本文件→Spec索引→活动证据→固定Spec相应WP→源码。本轮没有重部署静态虚构演示站。
