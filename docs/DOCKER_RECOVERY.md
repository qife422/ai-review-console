# Docker 安全恢复方案核查

核查日期：2026-11-05（America/Los_Angeles）；首次方案基线 `847cfa9e67f5632ecc16f602e8e24e4020065abd`，已有环境盘点基线 `01b85a4108e5701fd2d1bbaee924b6a1fb24e925`，本轮制品/准入方案基线 `fd0473d4b26c32bc70aac3a6f813ab3a9ab73998`。沿用 `ARC-UPGRADE@0.1.0`、WP-05及同目标460分钟累计预算。用户已选择最小Linux VM路线，本轮只固定制品来源、拟议路径、隔离、容量停点及累计预算方案，再自查同步GitHub；**暂不安装、创建或启动环境**。本文件是恢复决策说明，不是新Spec、可直接执行的启动脚本或AC运行证据；前轮[Mac预检](evidence/mac-host/README.md)及其封存包不改写。

## 结论

找到一个有上游源码依据的**候选控制机制**：Moby 28.3.2仍保留已弃用的daemon `--restart=false`，配置解析链也支持研究 `daemon.json` 中布尔值 `"restart": false`。但它尚未在本机Desktop启动链验证，**不能据此批准启动当前历史数据盘**。

关键区别：阻止符合restart policy的容器自动启动，不代表daemon以只读方式打开历史存储。恢复代码仍可能整理状态、准备挂载点，或清理符合条件的AutoRemove容器。本机历史容器元数据、Swarm/Kubernetes、扩展及外部启动器情况不可读，当前无法证明旧盘启动符合“原始数据和历史产物不变”。[Moby恢复流程](https://github.com/moby/moby/blob/v28.3.2/daemon/daemon.go#L452-L604)

**当前可确认的安全决定是保持现有Desktop关闭。** 前轮有限只读盘点未发现可认定为“可用、独立、空”的本机环境，详见下文范围；不能把未发现扩大为整台机器绝无其他VM。本轮已选Linux VM并固定下列输入/准入方案，下一步是评审必要的资源和执行决定，不重新要求选择路线。不因方案固定自动创建新VM/磁盘、安装替代引擎、切换context或扩大产物额度。

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

## 本机已有环境盘点（前轮快照）

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

## 已选最小 Linux VM：固定输入及准入方案

本节取代上文“例如Lima/8GiB逻辑盘”的初步估算作为选定候选；历史观察不覆盖新的方案。固定为**Lima2.2.1、VZ/aarch64、Debian12 genericcloud、2vCPU/2GiB、4GiB逻辑guest盘、plain模式**，只做Moby28.3.2恢复机制实验，不部署Langflow/API/PG，也不验证Mac Desktop配置传递。若基盘虚拟尺寸大于4GiB或依赖不满足，停止，不自动扩大磁盘/改版本。

### 制品清单与校验来源

以下是**从官方元数据固定的预期校验值，不是本机已下载并验过的payload**。版本和URL固定，不使用latest或无digest的fallback。未来逐个下载后必须核字节数和对应SHA；签名、解包清单、可执行文件build及guest依赖仍需实际验收，不把HTTPS元数据回读当成PGP验证或运行通过。

| 制品 / 官方URL | 字节数 | 固定摘要 |
|---|---:|---|
| [lima-2.2.1-Darwin-arm64.tar.gz](https://github.com/lima-vm/lima/releases/download/v2.2.1/lima-2.2.1-Darwin-arm64.tar.gz) | 38,328,082 | SHA256 `9e9eacce88f37e185c346bad73aa6136f738d8cdf8c3bb23cd42b071824bc66e` |
| [Debian12 genericcloud arm64 20260923-2610 qcow2](https://cloud.debian.org/images/cloud/bookworm/20260923-2610/debian-12-genericcloud-arm64-20260923-2610.qcow2) | 340,590,592 | SHA512 `89a752d5c7d8e88bee39a57d88d496cca574f7d1e8df5df7a169825435f99feb11ed13ab27ec7bee96fe1584be4ff9479358fbca6cc859efa109f4aba18724c8` |
| [containerd.io_1.7.27-1_arm64.deb](https://download.docker.com/linux/debian/dists/bookworm/pool/stable/arm64/containerd.io_1.7.27-1_arm64.deb) | 22,766,596 | SHA256 `18f49ec1dd1ba34ae76c52fe8c52edaed24f2b72fd3a0e5528546c9705f08ef5` |
| [docker-ce-cli_28.3.2-1~debian.12~bookworm_arm64.deb](https://download.docker.com/linux/debian/dists/bookworm/pool/stable/arm64/docker-ce-cli_28.3.2-1~debian.12~bookworm_arm64.deb) | 14,932,020 | SHA256 `29d54c7e2cf57fa2f0a8619346cb1ee2e74e1af628d2dd608bd561b5d80c51c7` |
| [docker-ce_28.3.2-1~debian.12~bookworm_arm64.deb](https://download.docker.com/linux/debian/dists/bookworm/pool/stable/arm64/docker-ce_28.3.2-1~debian.12~bookworm_arm64.deb) | 16,992,264 | SHA256 `b16fdb4305323e1da85e50c1784049f57d7360c339f1483d01013c8df630aeec` |
| [Alpine3.22.1 aarch64 minirootfs](https://dl-cdn.alpinelinux.org/alpine/v3.22/releases/aarch64/alpine-minirootfs-3.22.1-aarch64.tar.gz) | 3,976,860 | SHA256 `188416d41f9f0c9a6e9427b75149e43ccf3a89587b2d27c9ad506e7ffca78d1c` |

校验依据：Lima[发布元数据](https://api.github.com/repos/lima-vm/lima/releases/tags/v2.2.1)的asset digest；Debian[SHA512SUMS](https://cloud.debian.org/images/cloud/bookworm/20260923-2610/SHA512SUMS)与[Lima固定模板](https://github.com/lima-vm/lima/blob/v2.2.1/templates/_images/debian-12.yaml)的arm64摘要一致，镜像HEAD200及精确大小已核；Docker[Packages.bz2](https://download.docker.com/linux/debian/dists/bookworm/stable/binary-arm64/Packages.bz2)的精确三条arm64记录；Alpine[官方sha256](https://dl-cdn.alpinelinux.org/alpine/v3.22/releases/aarch64/alpine-minirootfs-3.22.1-aarch64.tar.gz.sha256)。Docker两CE包的完整Version均为`5:28.3.2-1~debian.12~bookworm`。

Docker索引gzip105,283B/SHA256 `02d855d08232537d301c7a958a2a3d4b59c6450c0d70c66d463ef97c9db28913`的size/SHA与[InRelease](https://download.docker.com/linux/debian/dists/bookworm/InRelease)记录匹配；InRelease46,614B/SHA256 `cb2c9a89620b8aa3b444f739c3341efa6038cad2720dd78cdceb9e98e1383c27`。补读同索引bz2为87,024B/SHA256 `c8d16ee78e34a27bb6b15c016a48110649d57ad695e879c56faaed9449b7b694`。尚未读取[Docker签名公钥](https://download.docker.com/linux/debian/gpg)或验证PGP签名；后续信任校验不合格即停，不能刷新索引后静默换包。

排除项：官方Docker28.3.2 arm64静态tgz虽HEAD200/75,224,781B，但未取得发布者SHA（`.sha256`404）；[Docker官方构建文件](https://github.com/docker-library/docker/blob/970a23424906f35f372532787bd20259e5090888/28/cli/Dockerfile)也未给该二进制段摘要，不能挪用buildx/compose或DEB的SHA。Plain模式不运行guest agent及内置containerd，故不选39,528,462B的additional-guestagents包。六制品合计**437,586,414B（约417.3MiB）**；Alpine未来只在guest导入为探针镜像，实际image ID须届时记录，不能从归档SHA编造OCI digest。

### 路径与隔离边界

拟议宿主根固定`/private/tmp/arc-linux-vm`，本轮lstat确认**不存在，未创建**。父目录`/private/tmp`已解析为自身，root拥有、mode1777；未来必须以当前用户独占创建根目录mode0700并核inode/owner，遇任何既存文件/链接即停，不合并、不删除或另起同义目录。这里是工作树外可再生实验运行目录，不是新项目或正式证据；系统可能清理tmp，不能作为持久备份或证据恢复入口。

| 范围 | 固定拟议路径及约束 |
|---|---|
| 受核下载、host Lima解包 | 根下`downloads/`及`host/`；主程序`/private/tmp/arc-linux-vm/host/bin/limactl`，不写/usr/local、Homebrew、Applications、shell profile或全局PATH |
| Lima状态与实例 | 仅本次进程设置`LIMA_HOME=/private/tmp/arc-linux-vm/lima`；实例名`probe`，实例根`/private/tmp/arc-linux-vm/lima/probe`；本根下生成SSH key，不加载用户现有公钥、不转发agent，不改HOME/CODEX_HOME |
| 配置与选材 | 根下`config/`、`results/`，输出选材≤128KiB/20files；未来正式资格仍须按既有证据规则决定，当前不创建证据包 |
| guest安装及配置 | 三DEB只拟在新guest用`dpkg-deb -x`解到`/opt/arc-engine`，不用apt/dpkg安装，不执行postinst或装systemd unit；配置`/etc/arc-engine/daemon.json`，不得拷贝原Desktop配置 |
| guest数据与运行 | `/var/lib/arc-engine/docker`、`/var/lib/arc-engine/containerd`、`/var/lib/arc-engine/probe`；exec/PID/socket均在`/run/arc-engine`，Docker socket为`/run/arc-engine/docker.sock`；只有合成数据 |
| 宿主Docker接口 | **不创建或转发host Docker socket**。未来仅通过该新guest的SSH执行其`/opt/arc-engine/usr/bin/docker`并显式绑定guest socket；不连接原Desktop、不改context或`/var/run/docker.sock` |

Plain模式的[官方边界](https://lima-vm.io/docs/config/plain/)包含不挂载宿主目录、不运行guest agent及内置containerd；仍会运行显式provision和基础SSH设置，因此不能把plain写成“没有任何副作用”。配置固定VZ/aarch64、plain=true、无base继承、仅单个本地已核guest image、无额外磁盘/宿主挂载/静态portForward/自动启动、禁升级包/用户与系统containerd/Rosetta/代理环境传播/SSH agent与现有公钥加载。首次只允许基础SSH进入；不共享home、项目源码、原SQLite、Docker.raw、历史卷或宿主Docker socket，不桥接到原服务。

Guest image只指向根下已核本地文件，不用template:docker/default或远程fallback；[固定版本downloader](https://github.com/lima-vm/lima/blob/v2.2.1/pkg/downloader/downloader.go)说明本地文件不缓存，避免默认`~/Library/Caches/lima`副本。不臆造LIMA_CACHE_HOME重定向；若解析或运行前检查仍有未声明下载/默认缓存/模板继承即停。[Lima native转换代码](https://github.com/lima-vm/lima/blob/v2.2.1/pkg/imgutil/nativeimgutil/nativeimgutil.go)支持不依赖qemu-img的转换，但本机尚无qemu-img且该实际路径未运行验证；若要求额外依赖，停止而不安装QEMU。签名/隔离属性阻止二进制运行时也停止，不自动清除quarantine或降低系统策略。

Guest须先核实际内核、架构、cgroup、libc6≥2.34、libseccomp2≥2.5及libsystemd0。Docker包列有iptables依赖，本小实验拟用bridge=none、iptables/ip6tables/ip-forward/ip-masq/userland-proxy关闭，所有探针container使用network=none；这不等于已验证运行依赖闭包。缺库、缺可执行文件或配置不接受时停止，不自动apt安装、拉registry镜像或扩展包集合。容器与containerd均手动启动，只测试虚构marker/重启策略；不覆盖Swarm/Kubernetes/外部启动器，也不据此批准原历史盘恢复。

### 容量与累计预算：当前有效限制和待审方案

**当前有效：仍是460分钟及原容量规则，没有任何额度被本文件改变。** 沿前轮源码分母764,861B，保守按当前更严的“绝对1GiB或100倍任一触发”约束整个VM物质产物，首个停点为**76,486,100B（约72.94MiB）**，小于六个受选下载的437,586,414B；故当前连完整下载都不能准入。原单WP3GiB、项目Docker12GiB及历史增长warning也没有关闭。上述源码分母沿既有固定计划，不冒称本轮重新测量全部源码。

以下是为下次负责人决定准备的**单VM有限例外提案，未批准、未应用门禁或修改固定Contract**：

- 同目标累计时间拟扩到**600分钟**，保留当前约439/460分钟起的全部累计和修复次数。未来划分：准入/信任/制品核验20分钟，有限下载和解包25分钟，创建及首次隔离验收25分钟，合成恢复实验35分钟，结果/自查/GitHub同步15分钟；合计120分钟，600上限包含余量。普通同因技术修复最多三轮且每轮限10分钟，包含在120分钟内；达到阶段或总停点停止，不另加预算。
- 仅本实验根的**逻辑文件总量≤6GiB，源码放大≤9000倍，两者任一触发即停**；9000×764,861=6,883,749,000B，因此逻辑6GiB更早触发。拟用4GiB guest虚拟盘，与下载/基盘/host解包的逻辑大小合计计量，不把稀疏文件逻辑量写成实际占用。
- **实际分配净增长仍≤3GiB**，2.5GiB预警；下载文件总量≤512MiB（六制品约417.3MiB及有限元数据都计入），所有解包、缓存、副本、QCOW2/raw转换、guest写入和日志纳入同一根，文件数≤20,000。每步前预测峰值、后核st_blocks及宿主free，运行期间拟每秒观察；这只是观察停点，不是已经实现的文件系统硬配额，不能保证零超调。无法证明下一步峰值能容纳时不开始；不以自动删除回到阈值继续。
- 宿主free拟保留≥12GiB，guest内存2GiB/2vCPU；这是本机制小实验的待审停点，不沿用CI30GiB，也不作为已测系统最低要求。内存压力、VM/daemon自有句柄不明或根外写入风险出现时停止新动作，只按已核归属停止自身实例并保留所有产物。
- 该提案还须按项目治理明确是否允许在旧增长warning未解除时，单独开展这个有界、无原盘挂载的机制实验；**不豁免整体项目12GiB归属缺口，不把旧库存标成已盘清**。若固定Contract仍需正式变更，先完成相应决定，当前不改Spec、不以“另建VM”绕过停点。获批前维持原阈值，不执行上述例外。

时间预算与下载/安装/创建/启动权限是不同决定。后续若实施，仅新增这个根及guest内部路径、六制品有限下载、手动合成实验进入范围；原Desktop、默认1.11.6、原始数据、历史卷/缓存/证据和其他VM仍不在范围。停止后不自动删磁盘/缓存/实例，不迁移或压缩历史，不自动恢复配置并重启。实际模型token/账单仍未知，后续模型量级暂估10k–25k token，不当作真实用量；不购买设备或云资源。

## 本轮交付与下一步

已完成：前轮已有环境有限盘点，本轮所选Linux VM的六项主制品预期摘要、拟议安装路径、隔离/停点及累计预算提案。未完成：签名/下载payload核验、实际依赖闭包和转换/首次启动验证、容量例外与创建权限、恢复机制实验及Mac验收。没有新AC-17运行证据；AC-19仍not passed，完整last_verified=null、最终接受pending；Zep及native/系统缺口不变。

**路线已选，无需再选择环境类型。下一步由负责人评审本节有限容量例外、累计600分钟及有限下载/安装/创建/合成实验的具体范围；Agent在相应决定成立后先做准入与制品信任核验。** 目前没有这些执行授权；保持原Desktop关闭，不创建环境或启动任何引擎。没有运行中的等待任务、支持工单或自动监控；未联系维护者或申请云资源。

本轮只更新本说明、当前状态、变更日志和Spec索引；文档净增限32KiB，不生成temp/缓存、构建树、证据包或全盘副本。直接HTTP元数据正文root194,417B、Sol249,138B，共443,555B，在事先1MiB总上限内；仅内存读取，未下载安装制品、VM镜像或容器blob。既有更严小包限制及绝对1GiB或源码100倍任一停点仍有效。10固定输入、11旧manifest和旧路径diff核对，不将manifest核对夸大为Docker卷全量审计。root集成和核Lima/guest/路径，Sol核Docker/探针制品元数据，Astra独立只读复核；实际token/账单未知，累计不清零。此范围不需新增领域或UI skill。
