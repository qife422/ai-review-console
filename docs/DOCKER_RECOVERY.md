# Docker 安全恢复方案核查

更新：2026-11-05（America/Los_Angeles）。沿用ARC-UPGRADE@0.1.0和WP-05，固定Contract字节不变；计划基线cad3703，实施前方案由Git保留。[本轮Linux实证](evidence/linux-vm/README.md)已封存；本文件继续作为恢复决策入口，不另建Spec。

## 当前结论与授权

用户已批准单独Linux VM容量例外（逻辑≤6GiB、实际增长≤3GiB）和同目标累计600分钟：先有限下载核验签名/制品/依赖，满足后手动安装、创建、启动，只做虚构恢复实验；保留此前约448分钟起的全部累计和修复次数。上一轮已完成此单VM工作包，最终实验通过且唯一新VM停止保留；本轮新授权的Mac业务准入结论见下节。

结论只覆盖Linux/Moby28.3.2恢复机制：restart=false可在本实验前置条件下抑制符合策略的已停止容器恢复；它不终止live-restore存活任务，也不保证daemon对存储只读。Mac Desktop配置传递、原历史盘保护及本机业务验收仍未通过；不能据此启动旧盘或认定完整AC-19通过。

原Desktop是外部状态：只读检查发现其backend于12:59:12启动，早于Lima create13:11、首次start13:14。用户确认由自己或另一任务启动。原Docker.raw分配量及mtime与此前快照不同，本代理未连接其socket、启停或修改原引擎；不能声称原Desktop一直关闭或全局历史盘字节未变。原SQLite等10固定输入及11旧manifest仍匹配，具体范围见新包protection.json。

## Mac 业务回归准入复核

2026-11-05 13:42–13:44（America/Los_Angeles），source dffe3003f4bfe048b5ff1644e022bae59121554e。用户本轮已授权先核实独立Mac目标与容量，条件满足后仅虚构业务回归、自查并同步GitHub。沿用ARC-UPGRADE@0.1.0、同goal600分钟、约497分钟起的累计及失败计数2；没有扩展安装/环境创建/扩盘/清理或原盘操作权限。本轮预检先完成，业务执行条件尚未满足，状态为not_started，不是业务测试失败。

只读事实与方法：

- sw_vers/uname/sysctl确认macOS26.5.2/build25F84、arm64、8GiB RAM/8逻辑CPU、hv_support=1；项目所在卷statvfs可用34,931,625,984B（约32.53GiB），memory_pressure -Q显示free35%。这些是快照，不构成全栈最低配置或容量准入批准。
- docker context ls只读client metadata：仍仅default和desktop-linux；/var/run/docker.sock链接到/Users/ffq/.docker/run/docker.sock，两者是同一原Desktop入口。lstat确认该socket存在；原backend仍为12:59启动的进程。未连接socket、调用daemon查询或据此断言服务健康/空库存，未启停原Desktop。
- Sol在/Applications和/Users/ffq/Applications下核8种精确app名，共16位置，仅原Docker.app存在。9个常见provider元数据根均不存在：.colima、.lima、.orbstack、.config/containers/podman/machine、.local/share/containers/podman/machine，以及用户Library下Group Containers/HUAQ24HBR6.dev.orbstack、Application Support/OrbStack、Application Support/rancher-desktop、Containers/com.utmapp.UTM/Data/Documents。只查白名单和至多一层metadata，不搜索全机/其他账户/自定义磁盘或读取凭据；不能据此说完全没有其他环境。
- 保留的/private/tmp/arc-linux-vm/lima/probe仍是VZ/aarch64/plain、2CPU/2GiB/4GiB配置，lima.yaml SHA96558b5ea1d545451c51080f042de95a7c5caf365062376917b39e1dcd19ea97与前轮匹配。root用已有PyYAML只读核配置；它不是Mac业务栈。本轮未启动/调用provider运行态查询，不用PID文件缺失推断停止或零库存。该运行根逻辑4,837,486,272B、分配2,041,131,008B，旧单VM例外仅限机制实验，不用于带入Langflow全栈。
- 原Docker.raw只stat：逻辑245,106,737,152B、分配27,164,852,224B，mtime_ns=1793913546609114442；未读正文/复制/挂载。整盘分配量不能等同本项目镜像或缓存；原数据由外部任务活动时也不声称全局字节不变。

未满足项是**没有已指认、可接入且能证明独立disk/socket的Mac业务目标**；原engine的新project/新卷名也不足以满足当前历史盘保护要求。该目标的实际镜像、独立PG/source/report/flow-config卷、共享层归属、可用增长及停止保留能力均未核验，不能填成0或按宿主free推定通过。既有项目归属12GiB、单WP增长3GiB及旧warning仍未关闭，现有32.53GiB余量不解除它们。CI的12/20/30GiB是不同流水线入口，不直接设成本机五案最低门槛；8GiB RAM也不是单独失败依据。

本轮目标是Mac宿主上的业务链路；相同Desktop4.43.2/build199162的配置传递/恢复机制验证是另一项证据，不是任意合格Mac业务目标都必须先重做的前置测试。Linuxprobe成功不能代替任一Mac结论。

条件补齐后的最小回归已定位到[现有入口](../scripts/validate_langflow.py)：默认benchmark-count=0，TXT/DOCX/PDF三案与三种决定产出9份报告，另验Markdown和缺标识失败/幂等重试，共5案；同时核5组件、2个真实Flow、精确候选版本、下载hash及Flow前后指纹。只支持AC-02/04/05/13/18所列子项，不独立关闭Mac UI、AC-17或AC-19。候选1.13.1仍须核实际ARM64镜像/334包锁，默认1.11.6不替换。

执行前须把API、Langflow、worker、PG、manifest、source/report存储绑定到同一独立栈：--api-url只绑定API，LangflowClient另读LANGFLOW_URL及认证环境；不能落回localhost默认值或读取原凭据。需要全新postgres-data/source-documents/report-artifacts/flow-config卷、loopback端口、明确空状态、实际driver/options/labels/mount和容量停点；不直接运行带CI-only守卫的迁移/候选脚本，也不伪造GITHUB变量绕过。

目标可位于当前Mac，需具备独立disk/socket及已核资源余量。下一步由环境操作者给出Mac上独立验收实例的标识、接入方式及独立存储位置（无需发送密钥）；Agent随即按已有授权只读核双端点/卷/镜像与容量，满足才执行上述5案9报告，不反复请求继续。若需新建环境或改变容量，先固定精确方案和所缺决定，不能套用Linux单VM例外。本轮未提供该目标，不远程盲探、不新购/下载/安装/创建环境，不在原Desktop上试跑。

本轮只在四份既有文档保存派生观察及方法，不另建Spec、状态表、复审/证据包或临时根；没有新增运行通过证据。先前ps整体输出超过64KiB内存检查而中止，后改为≤256KiB并只输出过滤元数据；未启动测试或重试原engine查询。10固定输入及12旧封存manifest匹配，旧包/默认源码/原SQLite无操作；本轮有效技术修复计数0，沿用此前两实验失败，不把一次工具输出限额等同业务失败。

## 实际合成实验

环境为Lima2.2.1/VZ/plain、Debian12/aarch64、内核6.1.0-53-cloud-arm64，DockerCE28.3.2/e77ff99、CLI28.3.2/578ccf6、containerd1.7.27、runc1.2.5。无Langflow/API/PG全栈或真实业务数据。

两组使用全新data-root、相同策略与初始状态；daemon1停止后、daemon2启动前，严格核五项持久Exit137、非running/Pid0、manual标志、StartedAt/RestartCount，再按固定源码预注册期望。结果为：

| 案例 | restart=true | restart=false |
|---|---|---|
| always，原运行 | 恢复 | 保持停 |
| unless-stopped，原运行 | 恢复 | 保持停 |
| on-failure，原运行且本次停机Exit137 | 恢复 | 保持停 |
| always，已手工stop | 恢复 | 保持停 |
| unless-stopped，已手工stop | 保持停 | 保持停 |

true组四项StartedAt推进；false组五项StartedAt/RestartCount保持，3秒重复观察稳定。此处sleep进程不响应TERM，关机最终KILL产生137；[固定Moby参数](https://github.com/moby/moby/blob/v28.3.2/container/container.go#L497-L501)把持久退出状态交给[策略判断](https://github.com/moby/moby/blob/v28.3.2/restartmanager/restartmanager.go#L75-L85)，解释这个特定on-failure恢复路径。不能用它泛化所有daemon版本或退出条件，亦不以[通用文档](https://docs.docker.com/engine/containers/start-containers-automatically/)的简写替代版本实证。

live-restore组两个既有任务跨daemon关闭仍存在，restart=false重连后PID3505/3584、StartedAt/RestartCount相同。新建AutoRemove对象stop后返回No such object，另一任务仍在。这说明restart=false不是全局停机或存储只读保证。marker读回一致，但入口每次启动重写同值，不能单凭它证明业务持久化或容器文件未写入。

保留两次失败：a1b2在缺失/bin/test上exec127；b1c2虽修探针，却误设on-failure不应恢复，在true组超时。每次先停止新VM、保留结果，再作有因修正。c1d2补固定前置条件/源码期望及现场快照后exit0，59.161秒，186条命令记录；三组均passed。不是通过放松数据、隔离或失败断言消除问题。最终guest无owned engine进程，stop probe exit0，实际回读Stopped。

## 制品与信任校验

以下六项payload均实际完成大小和摘要核验，结束前再次流式复核匹配；合计437,586,414B（约417.3MiB），未使用latest或换包fallback。

| 制品 / 官方URL | 字节数 | 固定摘要 |
|---|---:|---|
| [lima-2.2.1-Darwin-arm64.tar.gz](https://github.com/lima-vm/lima/releases/download/v2.2.1/lima-2.2.1-Darwin-arm64.tar.gz) | 38,328,082 | SHA256 `9e9eacce88f37e185c346bad73aa6136f738d8cdf8c3bb23cd42b071824bc66e` |
| [Debian12 genericcloud arm64 20260923-2610 qcow2](https://cloud.debian.org/images/cloud/bookworm/20260923-2610/debian-12-genericcloud-arm64-20260923-2610.qcow2) | 340,590,592 | SHA512 `89a752d5c7d8e88bee39a57d88d496cca574f7d1e8df5df7a169825435f99feb11ed13ab27ec7bee96fe1584be4ff9479358fbca6cc859efa109f4aba18724c8` |
| [containerd.io_1.7.27-1_arm64.deb](https://download.docker.com/linux/debian/dists/bookworm/pool/stable/arm64/containerd.io_1.7.27-1_arm64.deb) | 22,766,596 | SHA256 `18f49ec1dd1ba34ae76c52fe8c52edaed24f2b72fd3a0e5528546c9705f08ef5` |
| [docker-ce-cli_28.3.2-1~debian.12~bookworm_arm64.deb](https://download.docker.com/linux/debian/dists/bookworm/pool/stable/arm64/docker-ce-cli_28.3.2-1~debian.12~bookworm_arm64.deb) | 14,932,020 | SHA256 `29d54c7e2cf57fa2f0a8619346cb1ee2e74e1af628d2dd608bd561b5d80c51c7` |
| [docker-ce_28.3.2-1~debian.12~bookworm_arm64.deb](https://download.docker.com/linux/debian/dists/bookworm/pool/stable/arm64/docker-ce_28.3.2-1~debian.12~bookworm_arm64.deb) | 16,992,264 | SHA256 `b16fdb4305323e1da85e50c1784049f57d7360c339f1483d01013c8df630aeec` |
| [Alpine3.22.1 aarch64 minirootfs](https://dl-cdn.alpinelinux.org/alpine/v3.22/releases/aarch64/alpine-minirootfs-3.22.1-aarch64.tar.gz) | 3,976,860 | SHA256 `188416d41f9f0c9a6e9427b75149e43ccf3a89587b2d27c9ad506e7ffca78d1c` |

信任链：Lima签名SHA256SUMS→精确发行包→包内固定Debian模板及guest SHA512；这属于Lima发布者对Debian摘要的背书，不是Debian发布者签名。该精确cloud目录没有取得相应Debian签名，不借用其他CD密钥。Docker签名InRelease→精确Packages.gz记录→三DEB的版本/架构/size/SHA；Alpine签名直接覆盖rootfs。三发布者完整指纹、来源及原文hash见inputs/signatures。当前日期、签名子key绑定和默认算法检查通过；吊销仅覆盖已获取的key material，不声称穷尽在线查询。篡改SUMS、错key、篡改InRelease及rootfs四项负控全部拒绝。

因本机无合格现成验签器，用户另批准仅宿主用OpenPGP.js6.3.2，固定npm官方URL/SHA512，现有Node22.17.1，无全局安装/依赖/安装脚本，也不进入VM。首次按4MiB停止，留4194304B，内存超读≤256KiB，未解包执行；用户随后精确批准总网络5MiB并仅续传306287B。最终4500591B，网络上界4762736B（含超读/Range探测），解包17421480B/43成员，均在批准限额；npm两项ECDSA签名通过。原包SHA512及registry key ID在inputs.json。两个验签实现细节修正也保留在运行收据，不关闭算法/有效期检查。

主归档先检查路径/类型/清单才有限解包。Lima Mach-O arm64、codesign严格验证及系统动态依赖检查通过，未清quarantine或安装QEMU；native转换实际完成。Debian基盘虚拟3GiB，专用盘4GiB。三DEB只在新guest用dpkg-deb -x到/opt/arc-engine，不运行maintainer scripts、不apt安装、不启用系统服务。六ELF的SHA逐一绑定已签DEB成员，root所有权/非他人可写/ARM64及ldd无缺库；guest libc6、libseccomp2、libsystemd0及iptables已具备，不补装未知依赖。

## 路径、隔离与保留

| 范围 | 实际边界 |
|---|---|
| 宿主运行根 | /private/tmp/arc-linux-vm，独占新建mode0700；downloads/trust/host/verify/config/results/tmp/lima均在其下，不写全局工具目录或shell profile |
| 唯一VM | 仅进程LIMA_HOME指向根下lima，实例probe；VZ/aarch64、2CPU/2GiB、4GiB盘、plain；无base继承、宿主mount、额外磁盘、静态port forward、Rosetta、包升级或内置containerd |
| SSH | 只用本根生成的key，loopback临时端口，不加载原公钥、不转发agent，不改HOME/CODEX_HOME；不创建/转发宿主Docker socket或改全局context |
| guest输入/引擎 | /opt/arc-inputs及/opt/arc-engine；失败与修正版脚本置不同新run目录，旧输入不覆盖；安装只-x，配置/进程手动运行 |
| guest状态 | /var/lib/arc-engine/probe/<run-id>/<group>，exec/PID/socket在/run/arc-engine/<run-id>/<group>；仅精确自有socket、无宿主路径，容器network=none/无mount/禁止pull |
| 正式证据 | docs/evidence/linux-vm，manifest固定17文件129434B；候选同内容留artifacts/evidence-candidates/linux-vm；无整盘/完整构建树或下载副本入Git |

实际合并配置和三次boot指纹、guest挂载表均检查；未见宿主共享类型或路径，不以不同context名代替存储隔离。Lima默认配置携带禁用的containerd归档URL元数据，plain及system/user=false使其不安装；未执行额外容器下载。没有全出口网络审计，不宣称guest无法访问任何宿主网络服务。

停止只针对已核归属的新实例/自有daemon和任务。VM磁盘、下载、失败目录及现存data-root保留；AutoRemove新对象按实验配置消失，正常停止会结束临时/run状态，不作历史手工清理。临时根可能被系统清理，正式Git小包不能恢复完整VM或原数据库。没有迁移、删除、压缩历史产物，也没有恢复原Desktop配置或操作旧容器。

## 容量和累计成本

用户例外仅覆盖这一个VM根：逻辑≤6GiB或源码9000倍任一停，源码分母764861B；实际增长≤3GiB、2.5GiB预停点、≤20000项、六制品及元数据下载≤512MiB、宿主free≥12GiB。原项目12GiB归属和旧增长warning未因此关闭，不允许把新provider当作绕过办法。例外取代本VM先前不足以下载的100倍/1GiB停点，其他既有更严限制保留。

容量watch epoch3每秒观察；峰值逻辑5,177,004,203B（约4.82GiB）、分配2,128,277,504B（约1.98GiB），最多370项；最终采样逻辑4,837,465,865B、分配2,042,347,520B，宿主free30,593,220,608B。全部epoch最小余量/样本数见capacity.json。未触发停点。小包选材后的少量文本另计；没有自动清理回到阈值继续。

这是观察守卫，不是文件系统硬配额；异常/阈值停止代码经复核，实际本轮没有触发。原QCOW2映射估算先把bit0误当zero、遗漏部分compressed项，创建后且首次boot前修正为1,200,029,696B映射上界；初估617,807,872B及错误原因保留，实际创建/峰值未越限。不隐去错误估算或用稀疏逻辑盘量冒充实际占用。

同目标600分钟计量保留，封存前快照约493/600分钟；本轮两次真实实验失败、两项有因修正已登记，非所有历史CI失败总数。模型token/账单不可读；不冒称实际计费或按角色切换重置成本。新增工具/资源采购为零，不代表模型/网络总成本为零。

## 尚未解决及具体下一步

- Mac业务准入只读复核已完成，缺独立目标/存储归属/容量证据，业务not_started。环境操作者提供目标标识与接入方式后，由Agent按已有条件授权核实双端点/卷/image及增长停点再回归；原Desktop外部运行不自动授权旧卷试跑。相同Desktop版本的配置传递验证另列。
- 由Agent依[发布缺口矩阵](evidence/release-gaps/README.md)补系统/原生库source、通知及提供方式，精确Zep2.0.2问题仍依维护者对[#368](https://github.com/getzep/zep-python/issues/368)的可用澄清；本轮没有新增target native采集或新漏洞扫描，不将VM依赖安装当应用发布闭项。
- 完整WP-05/AC-19、负责人AD-03和最终接受仍待完成，再决定默认升级及WP-08。默认1.11.6、原SQLite、固定Contract/baseline/锁和11旧包按已核范围保持；不把此机制实验当AC-17业务迁移、Mac或完整发布通过。

历史有限盘点仅发现原Desktop两个context指向同一socket，未找到合格独立空环境；范围、主机版本和当时只读数据见[旧Mac预检](evidence/mac-host/README.md)及cad3703方案，不外推全机绝无VM。旧静态演示站及发布后端授权边界不变，本轮未重部署站点。
