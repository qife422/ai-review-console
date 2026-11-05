# Docker 安全恢复方案核查

核查日期：2026-11-05（America/Los_Angeles）；首次方案基线 `847cfa9e67f5632ecc16f602e8e24e4020065abd`，本轮已有环境盘点基线 `01b85a4108e5701fd2d1bbaee924b6a1fb24e925`。沿用 `ARC-UPGRADE@0.1.0`、WP-05及同目标460分钟累计预算。本轮授权只读排查本机已有独立空环境、核对隔离边界，无合格项时整理最小准备方案及成本，再同步GitHub；**不启动引擎、不创建新环境**。本文件是恢复决策说明，不是新Spec、可直接执行的启动脚本或AC运行证据；前轮[Mac预检](evidence/mac-host/README.md)及其封存包不改写。

## 结论

找到一个有上游源码依据的**候选控制机制**：Moby 28.3.2仍保留已弃用的daemon `--restart=false`，配置解析链也支持研究 `daemon.json` 中布尔值 `"restart": false`。但它尚未在本机Desktop启动链验证，**不能据此批准启动当前历史数据盘**。

关键区别：阻止符合restart policy的容器自动启动，不代表daemon以只读方式打开历史存储。恢复代码仍可能整理状态、准备挂载点，或清理符合条件的AutoRemove容器。本机历史容器元数据、Swarm/Kubernetes、扩展及外部启动器情况不可读，当前无法证明旧盘启动符合“原始数据和历史产物不变”。[Moby恢复流程](https://github.com/moby/moby/blob/v28.3.2/daemon/daemon.go#L452-L604)

**当前可确认的安全决定是保持现有Desktop关闭。** 本轮有限只读盘点未发现可认定为“可用、独立、空”的本机环境，详见下文范围；不能把未发现扩大为整台机器绝无其他VM。下一步是环境/资源选择，不再重复扫描相同路径或启动原盘试探。不因方案研究自动创建新VM/磁盘、安装替代引擎、切换context或扩大产物额度。

## 本机只读适用性（前轮快照）

Sol执行有界只读查询，root核对官方资料；未重复前轮失败的daemon查询或挂起的settings-store正文读取。

| 查询与方法 | 实际结果 | 不能据此推定 |
|---|---|---|
| `/usr/bin/plutil -extract CFBundleShortVersionString raw -o - /Applications/Docker.app/Contents/Info.plist`，同样读取CFBundleVersion | Desktop **4.43.2 / build199162** | 不是desktop插件版本；不能证明当前服务端已运行 |
| `/usr/local/bin/docker --version` | 客户端28.3.2 / build578ccf6 | 不作为实际daemon版本回读 |
| `docker desktop start --help` | 仅detach、timeout | 二者不抑制容器恢复；timeout也不保证后台启动操作已撤销 |
| `docker desktop --help`、`engine --help`、`enable/disable --help` | 未列engine或daemon配置编辑命令；engine帮助仅回顶层，enable/disable只列Model Runner | 不将顶层help exit0视为支持engine命令；`docker --config`是client配置目录 |
| `/Users/ffq/.docker/daemon.json`，单独子进程≤8秒，NOFOLLOW及inode/regular/64KiB上限检查，只输出键名、指定布尔项及SHA | 124B；SHA-256 `27369c832f1be7d067b379f3236a203993e7bec45135e58829a9273c3209f53c`；顶层仅builder、experimental；restart及live-restore均缺省 | 没有修改配置、公开其他值或证明Desktop实际使用了它；缺省不等于已禁止恢复 |
| 精确路径`/Applications/Docker.app/Contents/Resources/bin/dockerd`的lstat | 不存在 | 不证明整个app里没有Linux引擎；未搜索或解包app/VM |

CLI查询由`/usr/bin/python3`对子进程逐项设置8秒超时、capture_output，均完成，无新挂起进程。这里只保留命令、结果及读取方法的派生摘要，不声称封存了全部原始输出。没有读取Docker.raw内容或历史卷；原SQLite仅按既有保护清单读取字节做SHA核对，没有数据库查询、迁移或其他执行。

[Docker 4.43.2官方发布记录](https://docs.docker.com/desktop/release-notes/#4432)列出随版本升级的Engine28.3.2，提供源码选版依据；这仍不替代本机实际daemon build、Desktop传参/配置过滤及启用后的有效配置回读。

## 机制和排除项

| 方案 | 核查结论 | 当前决定 |
|---|---|---|
| 已弃用的daemon restart控制 | [flag注册](https://github.com/moby/moby/blob/v28.3.2/cmd/dockerd/config.go#L65-L74)仍存在且默认true；[解析与合并](https://github.com/moby/moby/blob/v28.3.2/daemon/config/config.go#L401-L516)会处理匹配bool flag；因此即使AutoRestart字段标为`json:"-"`，也不能仅凭该tag断言配置必定无效。推论是`"restart": false`值得隔离验证；非Desktop官方安全恢复承诺 | 不写daemon.json、不把flag传给Desktop、不在旧盘试验；准确build、配置接受/传递和实际抑制效果均待验证 |
| `live-restore` | 用于让现有容器跨daemon中断继续存活，不是全局禁止容器启动。[官方说明](https://docs.docker.com/engine/daemon/live-restore/) | 不作为安全恢复开关；也不尝试打开/关闭该项 |
| 禁止登录时启动Desktop、只开Dashboard、Resource Saver | 分别控制宿主登录启动、界面或空闲VM，不是当前启动时的容器restart policy禁用。[设置说明](https://docs.docker.com/desktop/settings-and-maintenance/settings/) | 不以这些设置代替容器恢复控制 |
| 启动后立即stop/update restart=no | 官方[update](https://docs.docker.com/reference/cli/docker/container/update/)是容器配置写入，且发生在daemon可访问之后；无法消除第一次启动到命令执行之间的写入窗口 | 不执行批量stop/update，不用事后竞速补启动前证据 |
| Compose未设置restart，或历史容器曾手工stop | 实际旧容器策略不由仓库文件证明；`always`仍可在daemon重启时恢复，`unless-stopped`依赖既有状态；服务编排/外部启动器另有入口。[策略说明](https://docs.docker.com/engine/containers/start-containers-automatically/) | 不假定全部旧容器已安全禁用；不自动修改历史容器配置 |
| authz插件、断网、改socket/context | API访问控制或网络隔离不证明daemon内部恢复被禁止；指向同一socket的数据仍共享 | 不作为旧卷无写入保证；不安装插件或改全局配置 |
| 离线改hostconfig、移动/复制Docker.raw、换data-root或恢复出厂 | 涉及历史内容写入/迁移、额外磁盘或清理；没有本轮授权，也缺准确库存/容量证明 | 不执行、不生成整盘备份，不通过新目录绕过增长停点 |

## 本机已有环境盘点（本轮）

本轮不是provider全盘普查：root检查client context、精确socket/常见binary路径、进程及宿主容量；Sol检查精确app和provider元数据路径。没有调用provider的status/list、连接任何daemon socket或读取VM磁盘正文，避免未知的初始化或自动唤醒。CLI/进程子查询限8秒，Sol元数据子脚本限10秒；现有Docker的VM根仅列一层、上限16项，其他provider根若存在最多列一层40项，不递归或跟随目录链接扩大范围。所有查询完成，无新挂起进程。

| 检查范围与实际方法 | 结果 | 隔离与空环境结论 |
|---|---|---|
| `/usr/local/bin/docker context ls --format '{{json .}}'`，exit0，无stderr | 仅default和desktop-linux，当前为后者 | context名字不同不代表存储隔离；没有第三个独立endpoint |
| 两context的endpoint及六个精确socket路径lstat/readlink | default的`/var/run/docker.sock`是指向`/Users/ffq/.docker/run/docker.sock`的链接，目标缺失；后者及`~/.colima/default/docker.sock`、`~/.orbstack/run/docker.sock`、`~/.rd/docker.sock`、`/var/run/podman/podman.sock`均不存在 | 两context仍是同一原Desktop入口；没有在这些路径发现可连接的独立socket，未发起连接 |
| PATH查找9个命令：colima、limactl、podman、orb、rdctl、prlctl、vmrun、multipass、utmctl；另对`/opt/homebrew/bin`、`/usr/local/bin`、`/opt/local/bin`下27个同名精确路径lstat | 均未发现 | 仅是这些入口不存在，不断言其他位置未安装 |
| `/Applications`及`~/Applications`下8种精确app名：Docker、OrbStack、Podman Desktop、Rancher Desktop、UTM、Parallels Desktop、VMware Fusion、Multipass，共16处 | 只有`/Applications/Docker.app`存在 | 已知原Desktop不是新的独立空环境；不运行或解包app |
| 下列9个provider元数据根lstat | 全部不存在，无目录正文需列取 | 没有可进一步核对disk、共享目录或空状态的候选 |
| 原Desktop的`~/Library/Containers/com.docker.docker/Data/vms`一层元数据 | 仅目录`0` | 这是原历史环境，不因daemon未运行认定为空；不读其磁盘内容 |
| `/bin/ps -axo pid=,comm=`的常见provider/VM进程名匹配 | 仅观察到PID572的`com.docker.vmnetd`帮助进程 | helper存在不证明有可用daemon，也不证明整机没有其他未匹配进程 |
| DOCKER_HOST、DOCKER_CONTEXT、DOCKER_CONFIG、CONTAINER_HOST、LIMA_HOME、COLIMA_HOME、XDG_CONFIG_HOME、XDG_DATA_HOME | 当前执行环境均未设置 | 未发现这些变量导向的自定义入口；未读取凭据、TLS材料、SSH配置或探测远端 |

精确provider根（`~`在本轮均为`/Users/ffq`）：

```text
~/.colima
~/.lima
~/.orbstack
~/.config/containers/podman/machine
~/.local/share/containers/podman/machine
~/Library/Group Containers/HUAQ24HBR6.dev.orbstack
~/Library/Application Support/OrbStack
~/Library/Application Support/rancher-desktop
~/Library/Containers/com.utmapp.UTM/Data/Documents
```

宿主本轮快照：Data分区总245,107,195,904B，可用24,882,925,568B（约23.2GiB）；内存8,589,934,592B、8逻辑CPU；`sysctl -n kern.hv_support`为1。可用容量与前轮17.7GiB不同属于观察时点差异，本轮未做清理，不推断变化原因。硬件支持虚拟化不表示环境已经存在，余量增加也不解除旧12GiB/3GiB容量停点。

因此，当前没有合格对象可核实其独立data-root、containerd存储、VM磁盘、共享目录及无历史容器/卷状态。**这些字段是unavailable，不能填写“0容器、0镜像、0卷”或“隔离已通过”。** 未覆盖自定义路径、其他账户/磁盘、未知provider及未配置远端；如环境操作者提供精确标识，再做针对性只读核查，不无界搜索。

## 两条路线及启动前条件

**路线A：先在独立空环境验证，优先保留。** 环境操作者提供已经存在的独立Docker环境，须明确机器/VM、daemon/socket、data-root/containerd存储、独立磁盘和共享目录边界，无原始项目路径、历史Docker.raw或历史卷挂载。远端Linux实验可以验证Moby机制；要证明Mac Desktop传递机制，还需相同Desktop4.43.2/build199162的独立Mac环境，不能跨平台继承结论。

Agent先核实该环境归属和资源预算，再在新授权下只用虚构数据验证：配置解析是否接受布尔false、实际daemon/build与有效配置；always、unless-stopped及on-failure等策略的启动抑制；AutoRemove/已运行任务的处理；Swarm/Kubernetes/扩展/外部启动器的适用边界。对照组也只能在该空环境。观察所有预期旧容器均未运行、写入标记未变化，并记录例外和局限。配置`--validate`只证明语法/冲突检查，不能替代实际恢复验证；不启动原盘做对照。实验镜像来源、增长和产物上限需提前明确，不自动build/pull。

**路线B：恢复现有Desktop，当前不具备执行条件。** 即便路线A证明restart控制有效，还需在启动前有可信证据确认原盘AutoRemove/任务及编排行为、Desktop实际配置路径和其他启动器；否则不能靠“先启动再inspect”补这个缺口。若恢复过程需要写旧存储、调整旧容器策略或离线读取/复制旧盘，应先说明精确操作、规模和回滚方式，取得相应决定；当前“不启动、原数据和历史不变”约束继续优先。不能保证旧历史不变时，不选择此路线。

两路线都不能解除旧容量停点：项目归属≤12GiB、单WP净增长≤3GiB仍适用；历史6个image metadata缺口和共享层归属尚未关闭。前轮17.7GiB宿主余量、8GiB内存以及CI的30GiB入口均不自动成为本机准入结论。另建环境不是绕过共享预算/增长规则的授权。

## 无合格本机环境时的最小准备方案与预计成本

以下均是**待选择的准备计划，当前没有创建/安装/付费授权**。建议先做Moby机制的小实验，不把Langflow/API/PG全栈带入第一步；Mac Desktop配置传递仍是后续独立验证。数字是工程估算，受制品来源、下载速度和初始化体积影响，不是已测最低配置或资源准入批准。

| 候选准备方式 | 最小任务及边界 | 预计新增成本与限制 |
|---|---|---|
| 本机一个专用Linux arm64 VM（例如Lima；仅技术候选） | 只装精确Moby28.3.2及一个小型合成写入探针镜像；2vCPU、2GiB guest RAM起步估算，单实例手动启动；独立VM根/磁盘、独立Unix socket、禁用宿主目录共享，不接原Desktop/历史卷 | 准备30–60分钟、机制验证另30–60分钟，合计60–120分钟；下载约0.5–1.5GiB，初期实际磁盘约2–4GiB，逻辑磁盘8GiB是拟议配置。**上界可能超过单WP3GiB，当前不具备准入**；需先固定制品/测量计划及容量决定，不自动安装或下载。本机8GiB内存共享给macOS和应用，2GiB guest不证明余量充足 |
| 操作者提供一台已有空闲、独立的Mac | 需可信Desktop4.43.2/build199162安装制品及校验依据；无原Mac磁盘/卷/共享目录，才验证Desktop配置传递 | 在制品和机器已经具备时，准备约45–90分钟、验证另45–90分钟，合计90–180分钟；实际磁盘预留估计5–15GiB、VM内存按精确版本配置核对。不能把这组估算当作原目标资源额度扩张；旧版本官方制品可得性尚未确认，等待时间未知 |

本地已有硬件且选择无需订阅的工具时，可把新增采购支出暂估为0；这不包含实际模型计费、电力、网络或人工，也不表示已确认所有工具许可。没有为缺少设备建议购买Mac或租云；若后来改用付费/远端资源，先取得精确报价和对应授权。模型token/账单不可读，不能承诺本轮或后续“总成本为0”。

Lima只是候选实现，不能照搬默认模板：[官方配置](https://lima-vm.io/docs/config/)默认4CPU/4GiB/100GiB，且挂载宿主home；[官方usage](https://lima-vm.io/docs/usage/)说明可关闭宿主挂载。未来实施前要核选定版本的最终合并配置和guest挂载表，确认home、项目根、Docker.raw及历史卷均未暴露；不以“home只读”代替“不共享”。独立socket只通过本次命令显式指定，不改全局context、不接管`/var/run/docker.sock`、不开自动启动或宿主特权端口。[Docker权限说明](https://docs.docker.com/desktop/setup/install/mac-permission-requirements/)也表明全局socket/CLI链接与helper是额外共享边界，另建macOS账户不自动证明独立。

若选择准备VM，Agent需先把**精确新路径、制品来源/SHA、安装副作用、下载/实际占用上限、保留规则及停止方法**提交为同一已有计划的可审阅补充，再取得创建/安装/有限下载及累计预算决定。新产物计入原目标，不以新provider或新路径规避既有增长警戒；限额不能证明时不开始。停止仅停止已核归属的新实例；不自动删实例、磁盘、缓存或证据。远端Linux或新Linux VM只能验证Moby层，不能关闭Mac Desktop实际版本验证或原历史盘恢复条件。

## 本轮交付与下一步

已完成：前轮版本/白名单配置及源码研究，本轮已有环境有限盘点、隔离字段缺口和最小准备成本说明。未完成：独立空环境准入、候选的隔离启动验证、当前历史盘安全恢复、本机5案/9报告验收。没有新AC-17运行证据；AC-19仍not passed，完整last_verified=null、最终接受pending；Zep及native/系统缺口不变。

**下一步由用户/环境操作者选择已有外部独立空环境，或选择另行准备最小Linux VM；Agent在得到具体环境标识或方案选择后补精确准入和成本。** 本轮没有合格的本机既有对象，不能直接进入机制验证；当前约434/460分钟起的剩余预算也不能自动覆盖上述60–180分钟实验。保持原Desktop关闭，不重复相同盘点，不创建环境或启动任何引擎。没有运行中的等待任务、支持工单或自动监控；未联系维护者或申请云资源。

本轮只更新本说明、当前状态、变更日志和Spec索引；文档净增限32KiB，不生成temp/缓存、构建树、证据包或全盘副本。既有更严小包限制及绝对1GiB或源码100倍任一停点保留。10固定输入、11旧manifest和旧路径diff核对；不将manifest核对夸大为重读全部历史正文或Docker卷全量审计。root负责context/边界/成本和集成，Sol负责provider有限盘点，Astra按独立只读职责复核最终说明；实际模型token/账单未知，累计成本不清零。此范围不需新增领域或UI skill。
