# Docker 安全恢复方案核查

更新：2026-11-05（America/Los_Angeles）。沿用ARC-UPGRADE@0.1.0和WP-05，固定Contract字节不变；计划基线cad3703，实施前方案由Git保留。[本轮Linux实证](evidence/linux-vm/README.md)已封存；本文件继续作为恢复决策入口，不另建Spec。

## 当前结论与授权

已批准的单独 Linux VM 工作包完成机制实验，实例已停止保留。该例外对应 `cad3703` 及原实验根。用户已确认没有现成的独立 Mac 验收实例，本轮授权限于核算各阶段容量、整理待确认范围、自查与 GitHub 同步。当前业务回归状态为 `not_started`。

结论只覆盖Linux/Moby28.3.2恢复机制：restart=false可在本实验前置条件下抑制符合策略的已停止容器恢复；它不终止live-restore存活任务，也不保证daemon对存储只读。Mac Desktop配置传递、原历史盘保护及本机业务验收仍未通过；不能据此启动旧盘或认定完整AC-19通过。

原Desktop是外部状态：只读检查发现其backend于12:59:12启动，早于Lima create13:11、首次start13:14。用户确认由自己或另一任务启动。原Docker.raw分配量及mtime与此前快照不同，本代理未连接其socket、启停或修改原引擎；不能声称原Desktop一直关闭或全局历史盘字节未变。原SQLite等10固定输入及11旧manifest仍匹配，具体范围见新包protection.json。

## 当前 Mac 最小隔离验收方案

2026-11-05，source `31d1eac5b621e06928a22351c45542910caa7602`。沿用 `ARC-UPGRADE@0.1.0` / WP-05，累计预算 600 分钟，接续约 504 分钟及既有失败计数 2。选定一个新的 Lima 2.2.1 VZ 实例，Debian 12 ARM64、2 vCPU、拟配 3 GiB 内存和 8 GiB 稀疏系统盘。8 GiB 是待验证的配置值。验收目标是在这台 Mac 承载的 Linux 容器内完成候选 1.13.1 的五案九报告，覆盖边界沿用上一轮的业务准入复核。同版 Docker Desktop 配置传递仍是独立验收项。

| 边界 | 拟固定的位置与配置 |
|---|---|
| 实例与盘 | 新根 `/private/tmp/arc-mac-acceptance`，目录独占且权限 0700。进程级 `LIMA_HOME=/private/tmp/arc-mac-acceptance/lima`，实例 `acceptance`。VZ 系统盘预期 `/private/tmp/arc-mac-acceptance/lima/acceptance/disk`，创建后须按实际实例元数据回读路径、所有权和唯一磁盘关系。原 `probe` 的盘与日志单独保留。 |
| 主机接入 | Lima `plain: true`，空 `mounts`、`additionalDisks`、`portForwards` 和 `provision`，禁用内置 containerd、Rosetta、主机 SSH agent 和代理环境转发。仅实例自己的 loopback SSH，生成独立 SSH key。主机暂存和日志限于新根。只读核 `/private/tmp` 实路径及新根不存在后方可进入未来创建阶段。 |
| 引擎与 socket | 仅 guest 内 `unix:///run/arc-acceptance/docker.sock`，containerd 为 `/run/arc-acceptance/containerd.sock`。Docker `data-root=/var/lib/arc-acceptance/docker`，containerd root/state 分别 `/var/lib/arc-acceptance/containerd`、`/run/arc-acceptance/containerd`，PID 和 exec-root 同归 `/run/arc-acceptance`。引擎手动启停，CLI 每次显式使用该 socket 和独立 `--config /opt/arc-acceptance/cli`。宿主无需 Docker socket 或 context。 |
| 业务与数据 | 单 Compose 项目 `arc-mac-acceptance`，API、worker、Langflow、PostgreSQL 和三项一次性初始化任务。每个业务卷由本项目新建，依次核 `postgres-data`、`source-documents`、`report-artifacts`、`flow-config` 的 labels、driver、options、Mountpoint 与实际挂载。唯一 bind 是 guest 源码内 `docker/postgres-init.sql` 的只读挂载。运行期使用 guest 内部网络，应用与数据库端口留在容器网络，五案脚本从 API 容器内执行。 |

2026-11-05 14:00（America/Los_Angeles）以 `lstat` 口径确认新根尚不存在，`/private/tmp` 实路径同名且模式 1777。将已有 `probe.yaml` 的隔离设置作为配置输入，创建前核拟用模板，启动前再核实际实例配置。Lima 的 plain 模式仍支持显式静态转发和 provision，所以这两项保留空列表。业务运行前校验 DockerRootDir、两个 socket、ARM64、卷和网络，发现对象归属不明时停止。 [Lima plain 模式](https://lima-vm.io/docs/config/plain/)

#### 制品与镜像

宿主 Lima 程序、Debian 12 genericcloud ARM64 基盘和三份 Docker DEB 取自 `/private/tmp/arc-linux-vm` 中此前已验证的制品。按下文既有来源和摘要重新核对可读性及字节，仅读输入文件。CE/CLI 固定 28.3.2，containerd 固定 1.7.27。新实例仍采用本地基盘位置和固定 SHA512。guest 中解包到 `/opt/arc-acceptance/engine`，明确 CLI 插件搜索目录并回读所选二进制，启停走自有进程。业务需要 bridge、DNS 和 BuildKit，首次引擎核验须验证 guest 的依赖与实际网络行为，机制实验的无网络设置不能直接搬用。 [Docker Debian 制品说明](https://docs.docker.com/engine/install/debian/)

新增两份插件 DEB 已在原签名链绑定的 `docker-Packages.gz` 中定位。2026-11-05 HEAD 均为 200，长度与索引一致。以后取 payload 时按原链验证索引、完整 SHA256、架构和依赖。

| ARM64 插件 | 固定制品字节 | SHA256 |
|---|---:|---|
| [Buildx 0.25.0-1~debian.12~bookworm](https://download.docker.com/linux/debian/dists/bookworm/pool/stable/arm64/docker-buildx-plugin_0.25.0-1~debian.12~bookworm_arm64.deb) | 13,606,056 | `a73cd5050cd87d0a12dbe0c4ef6e5b2d08786f459c4d68bb235bfa45182cfa1c` |
| [Compose 2.38.1-1~debian.12~bookworm](https://download.docker.com/linux/debian/dists/bookworm/pool/stable/arm64/docker-compose-plugin_2.38.1-1~debian.12~bookworm_arm64.deb) | 12,225,696 | `ac4e7fa0a19921d7a67bac92f13d1f6a8137e4aed50cff4a08ba737539f1a027` |

| 业务镜像 | 固定来源及验证 |
|---|---|
| Python 公共基底 | `docker.io/library/python:3.12.16-slim-bookworm`，索引 `sha256:e697c81897302a4c4333bade000d98038fbb21eb064f8ee1fd42d02ebcd9d337`，Linux ARM64 manifest `sha256:e0b3f8d16a5ccfbe602d5c94297e5dbcda2ec256edca2b80fcd44e39e1ff6feb`，压缩层 44,923,606B。供 Langflow/API 共用。 |
| PostgreSQL | `docker.io/library/postgres:16.15-trixie`，索引 `sha256:1beaa3084eee2676f20a9cd9928f0bf2c5bf674f8e49f81017912183d377c61c`，Linux ARM64 manifest `sha256:624b15a3c9e7b8930c8c1d3ff617a3135f92e06bb47df7a4fea49869ccd3a775`，压缩层 158,919,251B。 |
| Langflow 1.13.1 / API | 在新 guest 用 source `31d1eac` 的 `docker/langflow-candidate.Dockerfile` 和 `docker/api.Dockerfile`，指定 `linux/arm64`，使用该引擎的 Docker driver 顺序构建。LF 取既有 ARM64 334 包和 4 工具哈希锁，API 取 `requirements.lock`，由 API image 同时承载 worker 和初始化任务。记录实际 image ID、层、包清单及构建容量。 |

Docker 官方 Registry 的索引及 ARM64 子 manifest 已逐级核 SHA，两个公共基底的压缩层合计 203,842,857B。旧 CI 中的项目 image ID 绑定旧构建，当作来源和行为参考。仓库工作流提供构建入口和结果，成品镜像归档未封存。新构建前须核 Debian APT 解析的包和 API/PyPI 安装物的实际来源及大小。LF 的哈希锁、API 的版本锁及 APT 动态解析各有不同的复现边界。 [官方 Python 镜像](https://hub.docker.com/_/python) · [官方 PostgreSQL 镜像](https://hub.docker.com/_/postgres) · [Buildx Docker driver](https://docs.docker.com/build/builders/drivers/docker/)

未来只复制该 Git 提交的 Dockerfile 所需源码、经核为虚构的公开 fixture、锁、许可证及 `docker/postgres-init.sql`。先验选材清单和 SHA，排除真实数据、历史产物、Git 元数据、现有 `.env` 和缓存。以 `docker-compose.yml` 与 `docker/compose.candidate.yml` 为依据，在 guest 新根审阅单独的有效配置，保留七项所需服务和四个卷，删除端口映射。构建阶段允许经核定的官方依赖出口，运行阶段使用内部网络。构建和 Compose 子进程统一使用 guest 专用 `DOCKER_HOST` 和独立 CLI 配置，核 Buildx 的 Docker driver 与目标 endpoint。启动前校验本地标签对应刚记录的 image ID，采用 `--no-build --pull never`。先起 PostgreSQL 并完成 `storage-init` 与 `migrate`，再起 Langflow 并由 `flow-init` 写入新 Flow manifest，最后起 API 和 worker。

验证脚本显式绑定 API 容器的 `http://127.0.0.1:8000` 和同栈 `LANGFLOW_URL=http://langflow:7860`，指定 `--expected-langflow-version 1.13.1 --benchmark-count 0`。向该次验证进程注入本栈生成的合成 `LANGFLOW_SUPERUSER` 和 `LANGFLOW_SUPERUSER_PASSWORD`，凭据留在新 guest。客户端会跳过 Compose 中的演示 API key，故须检查此认证步骤。结果需核 5 组件、2 Flow、5 案、9 报告及前后图指纹。Web/浏览器、迁移和性能另列验收范围。 [业务验证入口](../scripts/validate_langflow.py)

#### 分阶段容量核算与确认项

2026-11-05，核算基线 `7ec30638c72168ec8d6d6b3485f56dff7edb6f3f`。现行项目 Docker 归属 ≤12 GiB、单 WP 净增长 ≤3 GiB、缓存增长 ≤2 GiB，缓存总量 4 GiB 或 100,000 项为警戒。派生产物继续沿用本项目较严的 1 GiB 或源码 100 倍任一触发停增口径，当前分母 764,861B，对应 76,486,100B。临时验证输出沿用单 WP 256 MiB / 10,000 项。原 Desktop 的镜像、卷和共享层仍待归属。此前机制 VM 例外绑定原实验根。 [固定 Contract](UPGRADE_SPEC.md#16-产物容量证据与磁盘边界)

**下载。** 冷启动按已封存的 ARM64 选档，334 个 runtime 档与 4 个工具档按 SHA 去重后为 334 档。官方文件 HEAD 全部返回长度，合计 356,369,322B。加 Python/PG 压缩层 203,842,857B 及两插件 25,831,752B，最小已知输入为 **586,043,931B（558.90 MiB）**，超前拟 512 MiB 共 49,173,019B。工具包在两次独立 pip 调用各取一次时，另预算 2,738,001B。此口径按所选制品而非实际联网次数。

- ARM64 选档来自 `resolution.json`（117,623B，SHA256 `089a5e76001e8225dc40b7f0dd474d86693015b71c7ce3d300069d49db7f0907`）与 `build-resolution.json`（1,840B，SHA256 `f54d012779faa7fc62f5b1b27a93aac286cd97d0acf10de0a05807671885093f`）。由原件取 URL、SHA 后合并同档，核官方 `files.pythonhosted.org` 的 HEAD Content-Length，再按 SHA 排序，对含大小的规范 JSON 求 SHA256 `21428633fdbc5c569890656a7ab16ac498d78f92357bee64e6ec24735a0fb002`。本轮取元数据，清单未作为新证据包落盘。 [ARM 选档原件](evidence/langflow-arm/ci/lock/)
- API 的 33 项固定版本和 Dockerfile 固定 pip 共 34 项。官方 PyPI release 元数据按 CPython 3.12.16 / Linux ARM64 / glibc 2.36 兼容性，每项取兼容 wheel 与同版 sdist 中最大一档，合计 102,519,081B。该数覆盖每项单档的预算，实际 pip 选档、Hatchling 隔离构建依赖及重传需另外锁定。APT 已核 bookworm ARM64 主索引 `Packages.xz` 为 8,689,464B，安全仓库 apt 2.6.2 与 libapt-pkg6.0 2.6.2 的 DEB 分别为 1,309,688B、814,180B。`libpq5` 版本、传递依赖与索引传输格式取决于最终解析。 [PyPI](https://pypi.org/) · [Debian bookworm ARM64 主索引](https://deb.debian.org/debian/dists/bookworm/main/binary-arm64/) · [Debian APT 安全仓库](https://deb.debian.org/debian-security/pool/updates/main/a/apt/)

拟将本次新增网络接收上限调为 **1 GiB**。已定位输入及工具重复计 588,781,932B，另分配 API（含构建依赖）128 MiB、APT（含索引）128 MiB、registry 元数据和受控重传 128 MiB，合计规划 991,435,116B，余 82,306,708B 缓冲。各项是准入预算。执行前要冻结目标 URL/哈希/长度及重传上限，明确同一计数器涵盖所有取件路径。预取按清单逐件核字节，镜像拉取逐层核 manifest，依赖解析需回读完整选档和来源。若直接联网构建不能核算隐式下载或自动重试，先完成有界取件或暂停构建。

**解包、构建和运行。** 已有 Debian QCOW2 映射上界 1,200,029,696B。三份引擎包实际展开文件为 230,313,720B，两插件的签名索引 Installed-Size 合计 147,307,520B（安装量参考）。五份归档留存时占 80,522,632B。上述四项合计 1,658,173,568B，另需核开机及文件系统开销。镜像 manifest 压缩大小无法换算成可信的展开上界。以下分配的是 8 GiB guest 内可接受的**阶段新增峰值**，用来判定是否准入。

| 阶段 | 新增峰值预算 | 累计 guest 占用预算 | 进入前须核实 |
|---|---:|---:|---|
| 基盘转换、空 VM 和引擎 | 2,048 MiB | 2,048 MiB | 独立盘布局、仅一个 8 GiB 可写盘、引擎/插件归档及展开、底盘和首次开机写入。压缩 QCOW2 的临时副本计入宿主盘外开销。 |
| 公共基底拉取和解包 | 768 MiB | 2,816 MiB | Python/PG 去重压缩层、展开文件和可能共存的层、临时写入及元数据。 |
| API 构建 | 512 MiB | 3,328 MiB | 单次取件及展开、构建隔离依赖、生成 wheel 和临时副本、BuildKit 中间层、输出与同时保留的缓存。 |
| Langflow 构建 | 1,792 MiB | 5,120 MiB | 334 档和工具的展开量、sdist 构建及中间产物、APT 事务与索引、输出和 BuildKit 保留层。API 留存量继续累计。 |
| 五案九报告 | 768 MiB | 5,888 MiB | PG/Flow/source/report 合计 512 MiB，含 PG WAL。source/report 单独观察 64 MiB / 100 文件。另预留日志 128 MiB 和容器写层等 128 MiB。按七容器每个 8 MiB × 2 的日志轮转配置预算，核轮转延迟及其他日志。 |
| guest 余量缓冲 | 256 MiB | 6,144 MiB | 以文件系统实际容量扣除 2 GiB 后的余量为准，6,144 MiB 是 8 GiB 原始盘对应的名义上限。若分区和文件系统开销挤占余量，先下调阶段预算再判定能否准入。 |

展开前读取受信档案的成员尺寸和数量，核目标文件系统的实际占用。构建还须核写入中的中间层与失败保留开销。阶段表只给预算分配。未能从输入、实际读数及可约束的生产者推出峰值上界时停在该阶段入口。构建缓存增长仍限 2 GiB，缓存与镜像共享层去重记账。运行前核卷绑定及空状态，按原 API 文档上限执行。`docker system df -v` 与 `docker buildx du` 仅在独立引擎作归属核对，最终空间以 guest 文件系统和宿主实际分配双读数为准。 [Docker 空间](https://docs.docker.com/reference/cli/docker/system/df/) · [BuildKit 缓存](https://docs.docker.com/reference/cli/docker/buildx/du/) · [日志轮转](https://docs.docker.com/engine/logging/drivers/local/)

**宿主预留和停点。** 2026-11-05 14:10 的 Data 卷可用 29,447,249,920B（约 27.42 GiB）。原机制根只读 `lstat` 递归 369 项，逻辑 4,837,486,624B，实际分配 2,038,247,424B。新根尚不存在。8 GiB 可写盘加 1 GiB 盘外文件给出 9 GiB 逻辑计划。guest 删除、稀疏及 guest `df` 均不能证明实际只占 6 GiB。改以全部盘范围 8 GiB、宿主旁路文件 1 GiB、分配与停机缓冲 1 GiB，提出 **新根实际占用 10 GiB 的保守规划包络**。该上界有赖于单盘、有限旁路文件和阶段核验，采样本身无法提供硬配额。日常工作目标仍为 6 GiB，5.5 GiB 观察停点保留。若希望按 6 GiB 作保证，须先有可验证的硬限或更小可写盘。

宿主入口改为 ≥24 GiB（12 GiB 保留 + 10 GiB 新根 + 2 GiB 外部波动缓冲）。每阶段以当前已分配量 A、该阶段额外峰值 P、发现和停止延迟增长 S 核 `A+P+S≤10 GiB`，并核宿主可用量 ≥`14 GiB+P+S` 和 guest 预计余量 ≥2 GiB。应先判定工作目标 6 GiB 能否容纳该阶段。若在 5.5 GiB 停增处仍有生产者，0.5 GiB 内停止的承诺须有 S 的证据。采样每秒，低于宿主 14 GiB、guest 内存低于 512 MiB、出现 OOM/内存压力告警、对象归属不符或下一步峰值未知，均停止自有生产者和实例并保留产物。拟用宿主盘外文件限 1 GiB / 20,000 项，其中新诊断输出限 64 MiB，选材限 1 MiB / 20 项。同 WP 历史临时输出计入现行总限额。

**请确认的单次执行范围。** 仅针对 `/private/tmp/arc-mac-acceptance` 的一个 Lima 实例与其 guest 专用 socket。拟例外为下载接收 ≤1 GiB、逻辑 ≤9 GiB、实际规划 ≤10 GiB。新根及该实例的 guest 产物拟按这套包络单列准入，替代其所受的 3 GiB 单 WP 净增长及 1 GiB 或源码 100 倍停点。其他产物和缓存仍按现行限制计量。原机制根按当前分配加新根上界，两根约 11.90 GiB（合计拟限 12 GiB，执行前刷新）。两根之外的同 WP 产物与共享层继续单列，旧项目 12 GiB 归属和缓存总量 4 GiB 警戒保留。例外需要明确允许在旧归属未闭合期间对该目标单列准入，且计量仍保留历史消耗。

在上述例外获准且逐阶段满足入口后，执行范围包括取得并核验固定制品，创建和启动唯一实例，解包引擎，拉取两基底，顺序构建 API 和候选 Langflow，初始化四个空卷，运行一次五案九报告，停止自有实例并保留产物，最后选材、自查与 GitHub 同步。执行前需确认完整下载清单、峰值和停止控制，使用原 600 分钟账本。执行阶段暂估 45–75 分钟，取 75 分钟与账本余量中较小者，并预留收尾。额外镜像、第二实例、扩盘、清理、旧 Desktop/原盘、默认替换和发布需分别决策。

本轮仅完成分阶段核算与确认稿，拟用新根尚不存在，业务仍为 `not_started`。Sol 读取元数据与封存输入，Astra 复核上界逻辑，root 集成并自查。完整 WP-05、AC-19、Mac 业务回归及发布许可仍待完成。

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

用户随后确认暂无现成独立目标。当前 Mac 的新实例方案及其容量决定见上节。

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

- 当前 Mac 独立业务回归为 `not_started`。用户先决定[单目标容量例外和分阶段执行范围](#分阶段容量核算与确认项)。获准后由 Agent 冻结取件清单和停止控制，逐阶段核峰值、磁盘、socket 和四个新卷，再执行一次虚构回归。同版 Desktop 配置传递验证另列。
- 由Agent依[发布缺口矩阵](evidence/release-gaps/README.md)补系统/原生库source、通知及提供方式，精确Zep2.0.2问题仍依维护者对[#368](https://github.com/getzep/zep-python/issues/368)的可用澄清；本轮没有新增target native采集或新漏洞扫描，不将VM依赖安装当应用发布闭项。
- 完整WP-05/AC-19、负责人AD-03和最终接受仍待完成，再决定默认升级及WP-08。默认1.11.6、原SQLite、固定Contract/baseline/锁和11旧包按已核范围保持；不把此机制实验当AC-17业务迁移、Mac或完整发布通过。

历史有限盘点仅发现原Desktop两个context指向同一socket，未找到合格独立空环境；范围、主机版本和当时只读数据见[旧Mac预检](evidence/mac-host/README.md)及cad3703方案，不外推全机绝无VM。旧静态演示站及发布后端授权边界不变，本轮未重部署站点。
