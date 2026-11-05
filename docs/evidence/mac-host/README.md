# Mac 宿主与 Docker 恢复预检

日期：2026-11-05（America/Los_Angeles）。沿用 `ARC-UPGRADE@0.1.0` / WP-05，核对用户要求的Mac容量和Docker恢复前提。**预检已完成，本机业务验收未启动，不能记作Mac验收通过或失败。** 用户在获知启动可能恢复历史容器后，明确选择“保持原数据保护，仅同步本轮预检”。

## 实际观察

| 项目 | 结果与边界 |
|---|---|
| 宿主 | macOS26.5.2 / Darwin arm64，8GiB内存、8逻辑CPU；Data分区约91%已用，CLI探针时可用18,993,098,752B，约17.7GiB |
| Docker客户端 | 28.3.2，context为desktop-linux；客户端存在不等于服务端可用 |
| Desktop / daemon | 两个只读命令均exit1，Desktop状态不可用、daemon无法连接；info stdout的零值server结构无效，**不表示0容器、0镜像或空引擎** |
| 可见context | default和desktop-linux均解析到同一缺失Unixsocket；没有从当前context/PATH探查中发现可访问的独立daemon；不证明机器所有位置都没有其他VM |
| Docker.raw | 仅stat：逻辑245,106,737,152B、分配29,555,404,800B；未读取正文、挂载、复制或修改。它不是镜像/cache分类容量 |
| 设置读取探针 | regular273B文件的open未返回；确认自有进程后只中断该探针，exit130，未向Docker进程发信号。未完成正文读取、不生成其SHA；原因未知，不推断隐私拒绝或引擎损坏 |

原始CLI响应和首次探针stdout没有封存；`preflight.json`明确为实际工具观察的派生摘要，列出命令、退出状态、方法及局限，不伪称完整原件或虚构原响应哈希。新宿主metadata另由标准平台、sysctl、文件stat及磁盘空间接口取得。

## 为什么没有启动 Desktop

1. 旧容量停点仍有效：历史3.629GB全局代理增长超过3GiB警戒；后续快照仍有6个历史引用image缺metadata，完整项目12GiB条件未证。当前daemon不可用，不能以17.7GiB宿主余量或Docker.raw分配量解除该停点，也不能把旧清单当作当前image/cache/卷盘点。
2. 旧容器实际restart policy目前不可读。Docker的`always`策略可在daemon重启时恢复容器；仓库Compose未声明restart，不等于所有实际历史容器都使用默认策略。[官方策略说明](https://docs.docker.com/engine/containers/start-containers-automatically/)
3. 已安装CLI及[官方start帮助](https://docs.docker.com/reference/cli/docker/desktop/start/)只列detach/timeout，未取得可禁止恢复旧工作负载的启动机制。拟议的`docker desktop start --timeout 60`已具体向用户说明风险，用户选择保持保护，故未执行。

30GiB是前轮CI迁移的入口，不自动成为本机5案验收的新门槛；8GiB内存或17.7GiB余量也不单独作为失败判据。真正缺少的是恢复影响及现有资源归属/容量证据。没有安装替代引擎、另建VM/磁盘或用新目录绕过现有增长警戒。

## 恢复前提和后续执行者

- **用户或环境操作者**提供可验证的“不恢复历史工作负载”恢复途径，或已存在的独立空daemon/VM（独立disk/socket、无历史卷挂载）。本轮决定不授权启动现有Desktop、接受历史卷写入或清理。
- **Agent**在前提和相应授权成立后，先只读核当前image/cache/卷/策略，解析历史缺metadata、共享层和12GiB/3GiB限额；不能证明边界时继续停增长，不自动prune或扩大额度。
- **Agent**仅在容量、目标绑定及准确现有镜像满足后，使用全新本机项目、空卷和loopback端口验证候选1.13.1的组件、两Flow、5个虚构案件/9报告。通用`validate_langflow.py`可用于已核实的本机API；CI-only候选/迁移/故障守卫不通过伪造GITHUB变量或命名绕过。结束只停止自身新容器，保留所有产物。

## 自查与适用范围

本轮只有只读盘点与文档/证据核验，没有Desktop启动、容器创建、migrate/bootstrap、业务测试、build/pull/prune、历史清理、原库操作或target native材料读取。默认1.11.6、固定Spec/锁、原SQLite及十旧封存包保持原范围；新SHA和路径检查见`protection.json`。Docker内部卷的全部字节没有重新读取，不以stat宣称全局字节审计。

新增temp限64KiB/12files，旧七temp加新增限40MiB；紧凑选材128KiB/20files，候选/正式各100MiB/1000files，源码分母764,861B，达到绝对1GiB或源码100倍任一阈值即停止同类产物增长（本轮用户全局规则，保留更严的小包限额）。实际量见`capacity.json`。没有复制整个构建、缓存、磁盘或历史目录。

Sol只读核可用本机入口与CI-only边界，Astra只读核恢复风险边界，root执行探针、定位自有进程和集成。实际模型用量/账单未知，原goal累计预算460分钟不重置。沿用spec-development的保护与证据规范，不新建Spec；无UI实施，不加载设计或浏览器skill。

ARM Linux迁移通过不变成Mac验收；本轮没有新增AC-17运行证据，也不关闭完整AC-19，last_verified仍null，Zep/native/系统分发问题仍open，默认未切换、后端未发布、静态站未重部署。正式证据只由最终manifest固定的精确字节取得资格。
