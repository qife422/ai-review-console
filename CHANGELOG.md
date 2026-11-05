# 更新记录

本文件记录主要功能与交接边界；精确代码差异以 Git 提交为准。开发快照不是正式发布，源码备份不是运行数据库备份。

## 2026-11-05 — 当前 Mac 最小隔离验收方案

- 用户确认暂无现成实例。固定新的 Lima VZ/ARM64 实例、独立稀疏盘和 guest 专用 Docker socket，五案九报告直接走同一栈的 API、worker、Langflow 1.13.1 和 PostgreSQL。
- 核对 Python/PG 的 ARM64 manifest 和压缩层字节，固定两份 Compose/Buildx 插件来源、包大小和 SHA256。LF/API 由既有源码与锁在独立 guest 构建，实际峰值待核。
- 拟用 8 GiB 盘、新根逻辑 9 GiB、实际 6 GiB，记录宿主/guest 余量和分阶段停点。现行项目容量限制继续作为准入依据，拟用例外待后续决定。方案定稿、自查与同步完成，环境创建和回归留待后续授权。 [验收方案](docs/DOCKER_RECOVERY.md#当前-mac-最小隔离验收方案)

## 2026-11-05 — Mac 独立业务目标准入预检

- 按新条件授权核独立Mac目标与资源，沿用ARC-UPGRADE@0.1.0及600分钟累计/既有失败记录。macOS26.5.2 ARM64、8GiB/8CPU、可用约32.53GiB；仅原Desktop两个同socket入口，未连接引擎/读库存。16 app位置、9常见provider根白名单未找到合格独立Mac业务目标，不外推全机/远程均不存在。
- 已定位现有5案9报告入口及API/Langflow双端点、独立PG/source/report/Flow卷绑定条件；区分Mac业务与同版Desktop恢复机制。旧12GiB归属/3GiB增长warning和独立存储证据仍待补齐，不把宿主free或4GiB Linuxprobe例外当业务准入。
- 因独立目标/接入/容量证据缺失，业务回归not_started，非测试失败；未新建/启动/安装/拉取/清理，也未用CI-only脚本绕守卫。只更新四份既有文档，无新Spec或证据包。10固定输入/12旧manifest匹配；默认1.11.6、原SQLite及封存证据按已核范围保持，完整WP-05/AC-19仍open。
- [观察、条件与下一步](docs/DOCKER_RECOVERY.md#mac-业务回归准入复核)：操作者提供一个独立Mac标识/接入/存储后，由Agent按已有授权核实，满足才做虚构业务回归；本轮不创建替代环境。

## 2026-11-05 — 独立 Linux VM 合成恢复验证

- 经批准应用单VM逻辑6GiB/实际增长3GiB例外与累计600分钟，保留同目标成本。六主制品437,586,414B及签名链、四项负控通过；宿主OpenPGP.js6.3.2按另批准5MiB网络修正续传/核验，无全局安装或VM内验签依赖。
- 唯一Lima2.2.1/VZ/plain、Debian12 ARM64新VM实际创建/启动，三DEB仅-x提取并绑定六ELF/依赖。两组五策略同Exit137前置：true4/5恢复、false0/5且时间/计数保持；live-restore同PID重连、AutoRemove自身对象消失。marker读回不作为业务持久化证明。
- 两失败保留：缺/bin/test、误设on-failure恢复期望；诊断后停止新VM，按精确源码补前置条件/预注册期望再复验。最终exit0/59.161秒，已无owned engine进程，VM Stopped，所有现存运行产物保留。
- 观察峰值逻辑5,177,004,203B/分配2,128,277,504B，未触限；QCOW2初估位解析错误已明确修正并保留。原Desktop外部启动及原盘元数据变化经用户确认，本代理未操作原引擎，不能声称全局历史盘不变。
- [结果、失败、保护与后续计划](docs/evidence/linux-vm/README.md)封存17文件129434B；10固定输入/11旧manifest匹配。四份既有文档对齐；无新Spec、完整VM备份或应用代码变化。Mac业务、系统/native/Zep许可及完整AC-19仍open，默认1.11.6和原SQLite按已核范围保持，未批准默认替换/后端发布。

## 2026-11-05 — 最小 Linux VM 固定输入及准入方案

- 按所选路线固定Lima2.2.1/VZ/plain、Debian12日期镜像及Docker CE/CLI28.3.2、containerd1.7.27和Alpine探针的官方URL/预期摘要/大小；六下载合计437,586,414B。静态Docker tgz缺发布者SHA，改用官方APT元数据中可固定摘要的DEB候选；没有下载安装制品或声称PGP已验。
- [既有恢复说明](docs/DOCKER_RECOVERY.md)固定拟议/private/tmp/arc-linux-vm根、guest内部路径及不共享宿主目录/不转发Docker socket的边界；根不存在，未安装、创建或启动。Plain和手动解包策略不替代实际依赖、转换、签名与隔离验收。
- 识别当前100倍源码76,486,100B停点已低于受选下载总量，当前不能准入。提出仅单VM逻辑6GiB/9000倍任一停、实际增长仍3GiB、累计600分钟的待审方案；不修改固定Contract，不应用额度或解除历史warning/完整12GiB缺口。
- 本轮仅更新四份文档，无新Spec/证据包/原库或历史变更；自查和独立复核按实际范围记录，默认1.11.6及完整AC-19状态保持。

## 2026-11-05 — 本机独立环境盘点及准备成本

- 只读检查已有context、精确socket/binary/app/provider目录和常见进程：仅原Desktop两个context指向同一缺失socket，未在有限范围发现合格独立空环境。未连接daemon，不把unknown空状态记成0容器/镜像/卷，也不声称全机绝无VM。
- Data分区本轮可用24,882,925,568B（约23.2GiB），8GiB/8CPU、hv_support=1；只是快照，无清理或容量准入结论。
- 在[既有恢复说明](docs/DOCKER_RECOVERY.md)补最小准备方案、隔离验收字段和成本估算：Linux机制实验准备+验证约60–120分钟，实际磁盘约2–4GiB，上界可能超过3GiB；同版Mac验证另需独立机器/可信旧制品。当前不创建环境、不安装/下载/付费、不扩预算，不以新provider绕增长停点。
- 更新既有状态和索引，自查固定输入/11旧manifest及历史路径差异；无新Spec/复审包或运行验收。默认1.11.6、原数据及历史保护不变，完整AC-19仍open。

## 2026-11-05 — Docker 安全恢复方案核查

- 按新授权继续只读研究，暂不启动Docker。实际确认Desktop4.43.2/build199162、客户端28.3.2；白名单读取daemon.json124B，仅builder/experimental，restart/live-restore缺省，未公开其他值或改配置。
- [恢复方案及前提](docs/DOCKER_RECOVERY.md)记录Moby28.3.2已弃用restart控制的源码推论，区分“候选机制”与“本机已验证”。Desktop启动CLI没有相应开关；live-restore、登录启动设置及启动后竞速stop/update不能替代启动前保护。
- 明确抑制容器自动启动不保证历史存储零变更：恢复流程仍可能处理AutoRemove、状态和挂载点。优先在已有独立空环境验证，当前历史盘不满足启动条件；未另建环境、安装、备份整盘或扩大额度。
- 仅文档更新，无新运行验收/封存包；10固定输入、11旧manifest及旧路径diff核对。默认1.11.6、原始数据和历史产物保护边界保持，460分钟累计不重置；完整AC-19、Zep及系统/native缺口继续open。

## 2026-11-05 — Mac 宿主恢复条件预检

- 核对macOS26.5.2 arm64、8GiB/8CPU、探针时约17.7GiB空闲；Desktop状态和daemon查询均exit1。两个context指向同一缺失socket，失败info中的零值server结构不作为空引擎证据。
- 旧3GiB增长警戒、完整项目12GiB归属及历史容器实际restart policy仍未解决；Docker.raw只读stat不替代内部库存。设置文件open未返回的自有探针已中断，不推断引擎损坏，也未向Docker进程发信号。
- 用户在审阅具体启动风险后明确选择“保持原数据保护，仅同步本轮预检”；Desktop/容器未启动，本机隔离验收未运行，不能记作Mac测试失败或通过。未build/pull/prune、改默认、操作原库或新增native取证。
- [观察、恢复前提及下一步](docs/evidence/mac-host/README.md)封存；固定输入与十旧包保留。460分钟累计不重置，只做相称文档/证据核验和GitHub回读；完整发布仍未通过。

## 2026-11-05 — ARM 隔离迁移与检查点恢复

- 手动迁移入口新增architecture选择，默认仍AMD64；ARM使用原生Linux runner，baseline写入前核host/runner/Docker及LF旧版、候选、API、Web、PG五个实际image平台，保留原namespace、空目标与容量保护。
- [CI42086830311](https://github.com/qife422/ai-review-console/actions/runs/42086830311)，source7877364，全部步骤success。新1.11.6虚构PG检查点恢复到新1.13.1及第三新1.11.6；两目标各新增5案/5文档/3决定/9报告/9任务，旧业务、用户、两Flow及15文件保全。
- 初次6725640 dispatch被422拒绝，修复job级runner上下文后以标准RUNNER_ARCH传递，架构/数据断言不降低。迁移及入口42项测试、修后11项入口测试与独立只读复核通过；不是全套新镜像应用/浏览器回归。
- [结果、未覆盖范围及计划](docs/evidence/arm-migration/README.md)封存。检查点恢复不等于原地降级或升级后写入RPO0；Mac、ARM管理/故障/性能、系统/native许可及完整AC-19仍未完成。本轮不新扫描或采native正文，不跨image继承旧132记录。
- 默认1.11.6、原库、固定输入及九旧封存包不变；同目标预算获批扩至460分钟，既有累计保留；无清理、默认切换、后端分发或静态站重部署。

## 2026-11-05 — 发布缺口与 Zep 精确许可复查

- 重新读取官方PyPI2.0.2元数据、SHA验证wheel/sdist及精确tag；9次请求111,442B，来源指纹与旧记录一致。精确许可仍OPEN，不套当前main/旧oss分支许可、不注入未经证实文本。
- 按服务和精确image拆分缺口：Zep已实证属于默认LF，API为Psycopg3.3.5等native义务；补齐六项发布阻塞、关闭条件与上游澄清草稿，封存时尚未发送。随后经用户单独授权，已按批准稿发布[上游issue #368](https://github.com/getzep/zep-python/issues/368)，标题及正文回读一致，待维护者回复；Zep许可仍OPEN，旧封存包不修改。
- 本机Docker daemon不可连接，image/cache内部容量盘点仍unavailable；只读核Docker.raw分配及五旧temp，不start/build/pull/prune或清理。本轮没有新增native目标读取、运行时变更、扫描或重复业务测试。
- [本轮结论与后续行动](docs/evidence/release-gaps/README.md)封存；固定输入/八旧包保留，完整发布、默认切换和后端分发仍未批准。
- 用户确认更新hook全部通过后恢复文档同步；同目标累计预算明确扩至400分钟，仅收尾两份文档、自查及GitHub同步，原计量和修复次数保留。没有新增运行时变更、测试、构建或扫描，不创建额外Spec/状态表/证据包。

## 2026-11-05 — 候选编辑器、恢复与性能专项

- B运行[41983887326](https://github.com/qife422/ai-review-console/actions/runs/41983887326)，source8db7f5f：5项真实故障恢复、PDF部分失败及环境恢复通过；20份1MiB顺序文档、333次混合查询、60份三格式报告全部完成。上传p95 38.28ms、查询p95 83.38ms，Intake最长3.193s、三报告含下载最长2.842s。301项Python单元测试通过。
- A菜单定位/临时根目录拒绝及B编辑器最终登录429均保留为失败；只修正探针和CI，未降低认证、运行环境或原Flow保全检查。C运行[42070564065](https://github.com/qife422/ai-review-console/actions/runs/42070564065)，source54592df，通过虚构副本改名、保存、重载及API回读（C专项success，305项Python/29项前端通过）；此轮明确只验editor，不宣称B故障/性能在C镜像重测。
- [结果、待解决问题与后续计划](docs/evidence/candidate-acceptance/README.md)封存；原SQLite、固定Spec、默认1.11.6、依赖锁和七旧包共1,283payload复核不变。Mac宿主、ARM旧schema迁移、系统/native/Zep/vendor许可及完整AC-19仍open；没有默认切换、原库迁移、后端发布或历史清理。

## 2026-11-04 — 候选 ARM 后端验证

- 确认上一轮自查/远端e1d8a02及88payload后，按授权进入ARM切片；固化334包和4工具的ARM独立SHA锁，原AMD锁不变。
- [锁CI41978766690](https://github.com/qife422/ai-review-console/actions/runs/41978766690)在原生ARM完成严格哈希新装/pip check；59个所选档案SHA不同，版本图不变。
- [完整CI41979142562](https://github.com/qife422/ai-review-console/actions/runs/41979142562)五任务success：271 Python/29前端、默认/候选双架构后端、AMD浏览器；ARM GUI明确跳过。
- ARM334包实清单一致、真实四格式/三决定/九报告通过；两LF候选各132 provider记录/scan exit1，三通知实际SHA一致，完整native/source及分发许可仍open。
- [本轮结果、待解决与计划](docs/evidence/langflow-arm/README.md)封存同步；默认1.11.6、原库和六旧证据包不变。Mac宿主、ARM旧schema迁移、编辑器、故障/性能待补，完整AC-19未通过。

## 2026-11-04 — 候选依赖锁与隔离迁移验收

- 固化1.13.1候选334包完整SHA锁和4个构建工具锁；首次wheel-only失败保留，源码档案以关闭build isolation的严格哈希安装通过，不宣称wheel二进制复现。
- 主CI保留默认1.11.6 AMD/ARM，增加Debian候选AMD；[CI41953014467](https://github.com/qife422/ai-review-console/actions/runs/41953014467)实际通过260 Python/29前端、业务/报告、AMD浏览器；新collector不把RHEL步骤套给Debian，也不重复旧native英文材料。
- [CI41954322019](https://github.com/qife422/ai-review-console/actions/runs/41954322019)在三个新命名空间完成1.11.6虚构检查点→1.13.1升级及第三新1.11.6回滚；各目标新增5案/9报告并核对目标SQL/卷。保留首败，修复物理列序孔洞比较，独立审查和真实复验通过；不涵盖原库或升级后写入零丢失。
- 候选APT/libapt2.6.2实际安装、精确2026补丁项复扫消失；当前仍132个Debian provider记录，原exit1保留。三份MIT/Apache补充通知副本实际镜像回读与repo SHA一致；完整native/source/后端分发材料继续open。
- [结果、待解决和计划](docs/evidence/langflow-transition/README.md)及正式manifest同步；原库/历史卷、Spec/baseline、默认Dockerfile和五旧包1155payload不变。完整AC-19未通过，last_verified=null，未切换默认或发布后端。

## 2026-11-04 — 精简 Langflow 候选隔离验证

- 固定base/LFX1.13.1精简候选，避开未使用集成，纯Psycopg3与显式PG驱动；默认1.11.6/52pins不改。
- 候选[CI41943564415](https://github.com/qife422/ai-review-console/actions/runs/41943564415)通过198 Python/29前端、5组件/2Flow/4格式/3决定/9报告及真实GUI登录；修复实验run参数与必填标签探针，负向retry不冒称成功恢复。
- 原五包在候选中3升级2移除，PyPI匹配0；保留Debian133 provider记录/scan exit1、许可与源码未完成范围。
- 实际取得APSW精确原文及Psycopg LGPL原文，补MIT/sqlitevec source材料；新target实读1/1166B并对账，不跨默认/API镜像关闭vendor问题。
- [已解决、待解决和后续计划](docs/evidence/langflow-candidate/README.md)统一归档；尚未替换默认、迁移原库或批准后端分发。

## 2026-11-03 — v0.2 系统维护与候选评估

- 固定Langflow1.11.6/base digest与52显式Python pins，新增公共UBI10补丁层和可审计RPM/信任记录；两架构60既有软件更新、1新增、无移除。
- Web libexpat固定2.10.0-r0；两架构Web/RHEL扫描在各自范围为0，保留主扫描exit2和剩余Python/Debian记录。
- 最终[功能代码CI41760412382](https://github.com/qife422/ai-review-console/actions/runs/41760412382)通过191Python/29前端、AMD工作流及浏览器、Linux ARM后端；负向重试不冒称成功恢复。
- 补Psycopg/Psycopg2精确配方、IBM REDIST/notices/English协议；Zep、native/source、完整后端分发条件仍open，v0.2完整发布验收未通过。
- 候选元数据评估保持当前运行时；统一状态、残余问题与[后续计划](docs/evidence/runtime-maintenance/README.md)，历史证据与原库不变。纯文档封存提交使用[skip ci]，不把跳过视为通过。

## 2026-10-31 — v0.2 兼容与许可补验

- 先完成镜像/缓存精确盘点和二次回读：本地 layers/镜像/cache 集合与大小未增长；历史归属仍不足，继续暂停本地 build/pull，不 prune 或清理历史。
- OAuthlib 4.0.0、datamodel-code-generator 0.81.0、OTel 1.45.1/0.66b1 成套升级；原 29 pins 保留，另固定两个必需 exporter 包，共 52 pins。
- 新增离线兼容/安全探针；首次 a59 的低层解析器长度断言失败已保留，按精确上游源码改测入站传播器及分段头合计上限，没有降低阈值。最终 a64 的 [CI 41263397231](https://github.com/qife422/ai-review-console/actions/runs/41263397231) 实际通过 161 Python、29 前端、真实 Flow/报告、双主题双尺寸浏览器、pip check 与新探针。
- 补入两份许可原文及 Langflow 镜像三份随包材料，实际哈希与采集额度已核实；排除误选源码/pyc。补齐真实 native 版本、路径哈希、源码校验与缺项，100 路径计划实际读 101 的偏差明确保留。
- Langflow 剩余 Python 包级匹配由 8 个缩至 5 个；上游上限、无明确修复、系统项、Zep 精确许可及完整 native/二进制分发材料仍未闭环。AC-19 未通过，完整技术和最终接受仍待定，没有部署真实后端或重部署静态站点。
- 已解决、待解决和下一步统一在 [本轮补验](docs/evidence/release-compatibility/README.md)；旧证据逐文件核对不变，最小增量证据及状态同步 GitHub。

## 2026-10-31 — v0.2 依赖修补与发布检查

- 应用运行锁修补 certifi、Pillow、pypdf，33 包审计由本轮 67 原始结果 / 66 alias 组变为 0；前端 Vite/Vitest 及相关 family、source-map-js/undici 修补后 npm 全量及运行范围均 0，保留无关 pin。
- 固定 Python 3.12.16、Nginx 1.30.6、PostgreSQL 16.15 digest，修补 API pip 26.2.2、Web curl/libcurl 8.23.0 与 brotli 1.2.1；保留 Langflow 1.11.6，加入 25 个有依据的兼容 pin，真实 installed metadata/pip check 与 Flow 均复核。
- 最终代码 `fac92ea` 的 [CI 41259579902](https://github.com/qife422/ai-review-console/actions/runs/41259579902) 实际全部 success：154 Python、29 前端、四格式/三决定/九下载、负向重试、双主题双尺寸浏览器。字体改用仓库固定 Noto，保留字节 SHA 与四图人工观察。
- 新增不下载大漏洞数据库的有界 OSV 镜像包级扫描，覆盖精确运行的 API/Langflow/Web/PostgreSQL；Red Hat 以实际 content_set、CPE、epoch 及架构补扫。默认 unknown 的原 exit 2 保留，合并 RPM 补扫的覆盖范围按同 ID 和相等条目集合核实，不改写为全绿。
- 普通前端构建携带实际 24 个 bundle 依赖许可、Plex OFL 和项目许可；新增真实镜像许可文本采集。Zep 2.0.2、IBM driver 及完整 native/二进制材料仍未关闭，没有给出镜像分发批准或风险接受。
- 修补与检查结果不等于发布通过：最终镜像仍有已记录的包级匹配；Langflow 8 个 Python 包和系统项的具体约束、兼容工作或缺补丁依据，以及下一步均见 [发布验收记录](docs/evidence/v02-release/README.md)。不把跨架构/服务口径的计数差直接当漏洞修复数量。
- 本地磁盘空间故障已如实保留；按负责人明确授权，仅删除本轮中止的单个 Grype DB 缓存 2,966,994,944 字节，恢复 Docker/本机 pip；原库、历史卷及旧证据不清理。最新原生镜像重新通过真实工作流，故障前 5 个虚构案件及 9 份报告仍可核验。active=0 后停验收服务，库卷和其他缓存保留。
- Docker 报告量的增长代理达到警戒后停止进一步构建，归属/容量局限与待处理状态单列；未自动 prune。代码、固定证据和文档同步 GitHub，不发布真实后端。

## 2026-10-28 — v0.2 收尾验收与状态对齐

- 更新活动状态及 Spec 索引，保留已批准 `ARC-UPGRADE@0.1.0` 的固定字节；明确已实现、已验证、发布未通过和最终接受待定的范围。
- 修复同页切换案件链接时 URL 与内容不一致的问题：监听 hash/history 变化，取消旧请求，防止旧案件响应覆盖新案件。同时保持“跳到正文”不改变当前案件并正确聚焦 main。前端全量 29 项及实际浏览器同页切换/后退/证据跳转、键盘焦点专项验证通过。
- 修复 CI 中文截图缺字：安装并验证 Noto CJK 字体；真实浏览器截图已人工查看。保留缺字观察和修复后的 CI 证据。
- 快速回归 Python 124 项及单独 PostgreSQL 4 项通过，前端 29 项、TypeScript、Ruff 通过；真实四格式 Intake、三种决定、九次下载与哈希核验通过。
- 实测执行前/回调后 SIGKILL、服务连接失败、401 和恢复；修复验收脚本把合法 429 自动重试误判为失败的过严断言，保留原失败记录与补验结果。
- 新增真实 PDF 部分失败验收：仅注入临时坏字体，保留 JSON/HTML 和人工决定；三次失败后恢复原 Langflow 环境，专用重试 PDF，已就绪报告的 ID/时间/哈希/字节不变。
- 恢复脚本改为显式绑定本轮 manifest、数据库与镜像；修复复制新卷的权限问题，并在复制前再次拒绝非空目标。完整数据库逐表指纹一致；恢复运行仅验证明确选定的 3 案件 / 12 文件 / 208,426 字节与 9 次报告下载，不宣称其他文件已恢复。
- 20 份 1 MiB 文档混合负载复测：查询 p95 `0.118757s`、上传 p95 `0.094931s`、Intake 最大 `3.420485s`，本轮目标全部达到。此前约 1.42s 的失败记录未改写，不据此推断当时根因。
- 发布检查未通过：Python 三包共 59 组去重 advisory 匹配；npm 五个受影响包，`omit=dev` 仍有一个 high 标记（可达性未据此推定）；镜像 Scout 需要 Docker 登录，许可证库存仍有待复核项。未升级依赖、放宽验收或接受残余风险。
- 最终代码 `540fd4c` 的 [CI 40819513529](https://github.com/qife422/ai-review-console/actions/runs/40819513529) 已实际完整通过。最小证据、AC 映射、实际命令/来源/哈希和后续顺序见 [验收记录](docs/evidence/v02-acceptance/README.md)。仅把该 manifest 选入的文件作为本轮证据；构建树、缓存、运行数据库和备份 dump 不提交。

## 2026-10-28 — 仅虚构数据的在线演示

- 发布 [公开交互演示](https://ai-review-console-demo.adeptbread257.chatgpt.site)，使用独立静态托管，不部署真实业务后端。
- 新增显式启用的前端演示适配器：四个预置虚构样本、模拟审查、版本绑定人工决定及浏览器内 JSON/HTML 报告；HTML 支持浏览器打印另存 PDF。正常开发模式保留原 API 路径。
- 演示不接受本机文件，业务状态仅保留在页面内存；刷新或重置恢复初始状态。CSP 禁止业务网络连接，构建不读取本机 `.env`。
- 保留现有 Carbon 界面，增加明确的模拟说明和移动端入口；恢复方法、既有 Site 标识及发布版本见 [在线演示说明](docs/ONLINE_DEMO.md)。
- 本地 TypeScript 检查和前端 5 文件 / 28 项测试通过；最终静态包完成预置样本、人工决定、JSON/HTML 下载与字节哈希、重置及手机双主题检查。Sites 回读部署状态为 `succeeded`。浏览器实际打印/保存 PDF 未验收；以上不替代原完整系统剩余验收。

## 2026-10-15 — 公开展示

- 经负责人明确授权，将 GitHub 仓库改为公开，便于分享项目说明、历史虚构截图与源码。
- 恢复指南改用匿名 `git clone`；源码读取不要求登录，推送仍需写权限。
- 保留原有提交、固定 Spec、证据字节和开发快照边界；未公开运行数据库或密钥，未部署公网服务，也未宣称补完剩余验收。

## 2026-10-13 — v0.2 开发快照整理

- 为 GitHub 备份整理项目功能、技术栈、历史截图、安装入口、恢复方法和更新流程。
- 保留已有本地提交及当前升级代码，不重新命名项目，不改写固定 Spec 和历史证据。
- 上传、持久化任务、真实 Langflow Intake、版本绑定人工决定、Decision 报告与下载构成已实现的关键路径；评分仍为规则制，不包含 LLM/OCR 或生产身份系统。
- 保存近期多行 JSON 传输、中文 PDF、重试代次、旧报告回调、启动通知行锁、统一队列容量和真实请求流量上限等修复代码；最后一轮修改后的完整回归仍待继续。
- 仓库中的离线 SBOM/许可证信息是候选记录。在线漏洞审计尚未获本轮执行结果；旧镜像库存不能代替当前源码的发布扫描。

备份前快速检查：Python `124 passed, 4 skipped`（未配置隔离 PostgreSQL 的四项测试跳过）；前端 `15 passed`；Ruff、TypeScript 和 `git diff --check` 通过。它们不代替下列整栈、故障、性能或发布验收。

### 后续接续点

- 复跑最后一轮边界修复的回归测试和真实两条 Flow，核验三格式报告及部分失败重试。
- 完成执行前/回调后的真实容器中断、连接故障、401/超时/配额状态与恢复验证。
- 完成隔离恢复目标的服务启动及报告下载检查；不切换或覆盖原数据库/卷。
- 复测性能：此前 20 份 1MiB 文档均完成，但大文档查询 p95 曾为约 1.42 秒，超过 500ms 目标；保留原失败记录，不用无负载复测替代它。
- 检查 GitHub Actions 的实际运行结果；完成经授权的在线漏洞审计与最终证据绑定后，再申请完整技术验收。

以上待办不阻止保存开发快照，但阻止把它宣传为验收完毕或生产就绪。临时目录引用仅是原机器上的来源记录，新电脑不得假设这些路径仍存在。

## 更早历史

仓库保留的第一份 Git 检查点为 `2acc665`，是升级过程中的源码检查点，不是升级前完整备份。2026-09-01 的历史演示验证见 `docs/VERIFICATION.md`，其结果仅适用于当时输入和运行环境。
