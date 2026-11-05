# Docker 安全恢复方案核查

核查日期：2026-11-05（America/Los_Angeles）；源码基线 `847cfa9e67f5632ecc16f602e8e24e4020065abd`。沿用 `ARC-UPGRADE@0.1.0`、WP-05及同目标460分钟累计预算。用户本轮只授权排查方案、确认条件和GitHub同步，**暂不启动Docker**。本文件是恢复决策说明，不是新Spec、可直接执行的启动脚本或AC运行证据；前轮[Mac预检](evidence/mac-host/README.md)及其封存包不改写。

## 结论

找到一个有上游源码依据的**候选控制机制**：Moby 28.3.2仍保留已弃用的daemon `--restart=false`，配置解析链也支持研究 `daemon.json` 中布尔值 `"restart": false`。但它尚未在本机Desktop启动链验证，**不能据此批准启动当前历史数据盘**。

关键区别：阻止符合restart policy的容器自动启动，不代表daemon以只读方式打开历史存储。恢复代码仍可能整理状态、准备挂载点，或清理符合条件的AutoRemove容器。本机历史容器元数据、Swarm/Kubernetes、扩展及外部启动器情况不可读，当前无法证明旧盘启动符合“原始数据和历史产物不变”。[Moby恢复流程](https://github.com/moby/moby/blob/v28.3.2/daemon/daemon.go#L452-L604)

**当前可确认的安全决定是保持现有Desktop关闭。** 优先在已存在、明确独立且没有历史数据挂载的空环境验证候选机制；若没有这样的环境，则先由环境操作者提供条件。不因方案研究自动创建新VM/磁盘、安装替代引擎、切换context或扩大产物额度。

## 本机只读适用性

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

## 两条路线及启动前条件

**路线A：先在独立空环境验证，优先保留。** 环境操作者提供已经存在的独立Docker环境，须明确机器/VM、daemon/socket、data-root/containerd存储、独立磁盘和共享目录边界，无原始项目路径、历史Docker.raw或历史卷挂载。远端Linux实验可以验证Moby机制；要证明Mac Desktop传递机制，还需相同Desktop4.43.2/build199162的独立Mac环境，不能跨平台继承结论。

Agent先核实该环境归属和资源预算，再在新授权下只用虚构数据验证：配置解析是否接受布尔false、实际daemon/build与有效配置；always、unless-stopped及on-failure等策略的启动抑制；AutoRemove/已运行任务的处理；Swarm/Kubernetes/扩展/外部启动器的适用边界。对照组也只能在该空环境。观察所有预期旧容器均未运行、写入标记未变化，并记录例外和局限。配置`--validate`只证明语法/冲突检查，不能替代实际恢复验证；不启动原盘做对照。实验镜像来源、增长和产物上限需提前明确，不自动build/pull。

**路线B：恢复现有Desktop，当前不具备执行条件。** 即便路线A证明restart控制有效，还需在启动前有可信证据确认原盘AutoRemove/任务及编排行为、Desktop实际配置路径和其他启动器；否则不能靠“先启动再inspect”补这个缺口。若恢复过程需要写旧存储、调整旧容器策略或离线读取/复制旧盘，应先说明精确操作、规模和回滚方式，取得相应决定；当前“不启动、原数据和历史不变”约束继续优先。不能保证旧历史不变时，不选择此路线。

两路线都不能解除旧容量停点：项目归属≤12GiB、单WP净增长≤3GiB仍适用；历史6个image metadata缺口和共享层归属尚未关闭。前轮17.7GiB宿主余量、8GiB内存以及CI的30GiB入口均不自动成为本机准入结论。另建环境不是绕过共享预算/增长规则的授权。

## 本轮交付与下一步

已完成：版本及白名单配置核对、官方文档/固定版本源码研究、候选机制与两条路线的条件说明。未完成：候选的隔离启动验证、当前历史盘的安全恢复、本机5案/9报告验收。没有新AC-17运行证据；AC-19仍not passed，完整last_verified=null、最终接受pending；Zep及native/系统缺口不变。

**下一项安全动作由环境操作者提供已有独立空环境的具体标识与隔离边界，Agent再核查能否承载路线A。** 若暂没有环境，维持当前Desktop关闭，保留方案；本轮没有运行中的等待任务、支持工单或自动监控。未联系Docker维护者，外部沟通不从研究授权推定。

本轮只新增本说明并更新当前状态、变更日志和Spec索引。新增正文限64KiB，不生成temp/缓存、构建树、证据包或全盘副本；既有更严小包限制及绝对1GiB或源码100倍任一停点保留。10固定输入、11旧manifest和旧路径diff核对；不将manifest核对夸大为重读全部历史正文或Docker卷全量审计。root负责资料和集成，Sol负责本机只读适用性，Astra按独立只读职责复核最终说明；实际模型token/账单未知，累计成本不清零。此范围不需新增领域或UI skill。
