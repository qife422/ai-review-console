# v0.2 依赖兼容与许可补验

日期：2026-10-31（America/Los_Angeles）。沿用已批准 `ARC-UPGRADE@0.1.0` / WP-05；固定 Spec、旧正式证据和原数据库均不改。源码提交 `a64ab476c8acfaa36a3d6cc260a4c6c286bad380`，实际 CI [41263397231](https://github.com/qife422/ai-review-console/actions/runs/41263397231)。本包是本轮增量，先前故障/恢复/性能结论保留在其原环境，不重新标为当前依赖的完整验收。

## 已解决与验证

- OAuthlib 升至 4.0.0、datamodel-code-generator 升至 0.81.0；OpenTelemetry 现有 19 个包成套升至 1.45.1 / 0.66b1，并明确固定新增必需的两个 exporter 传递包。Langflow 保持 1.11.6，原 29 个显式 pin 不变，现在共 52 个显式 pin。基于实际 metadata 和官方精确版本候选的默认 active 图在 arm64 / amd64 均未发现冲突；真实安装一致性由新 CI 分开核实。
- 新增无网络、只读根、32MiB tmpfs 的离线兼容探针：OAuth PKCE/state/token/revocation、JSONP 参数移除；固定虚构 schema 生成、导入及合法/非法输入；OTel 内存 span、线程上下文、ASGI/FastAPI instrumentation、超大 tracestate 处理。它不测试远程模型、外部 OAuth provider 或遥测服务连通。
- 补入 dnspython 2.9.0 ISC 与 FastMCP 3.4.10 Apache 原文，LFX 1.11.6 使用同版本 Langflow MIT 文本；Langflow 镜像显式带入 `licenses/`，三份副本纳入精确镜像采集。修正许可启发式，把名称含 license 的源码/pyc 显式排除，真实缺原文仍报告缺失。
- 新选 23 包中 22 包有自身许可文本。`opentelemetry-util-http 0.66b1` 没有 dist 内原文；精确 PyPI、同 `v0.66b1` 包声明和版本文件确认其 Apache-2.0 来源，同 tag 根 LICENSE 与镜像内 `opentelemetry_instrumentation-0.66b1.dist-info/licenses/LICENSE` 的 SHA-256 均为 `c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4`，形成实际随包共享文本映射。原始采集的 own-text 缺失状态不改写，全部许可材料和完整分发批准仍是不同结论。
- 在已有 arm64 精确 API/Langflow 镜像只读核实原生库路径、哈希及可调用版本；补出 libpq、OpenSSL、Pillow/lxml 子库、源码档案校验与逐项材料缺口。未下载整份源码树；上游链接不代表已交付全部对应源码。

## 回归与扫描

第一次 `a59dc31` / CI `41262700501` 的单元、真实 Flow 和浏览器已通过；两个精确镜像 `pip check` 也通过，但离线探针在超长 tracestate 断言失败，后续扫描和许可证采集未执行。核对上游精确 1.45.1 源码确认：8,192 字符合计上限由 `TraceContextTextMapPropagator.extract` 实施；低层 `TraceState.from_header` 修成线性解析，不承担该总长度限制。探针修正为真实入站入口，保留超限丢弃标准，并检查分段头合计超限。没有调低安全要求或改依赖 pin。原失败 stdout/stderr、manifest 和准确源码诊断均保留。

最终代码 `a64ab47` 的 [CI 41263397231](https://github.com/qife422/ai-review-console/actions/runs/41263397231) 实际全部 success：**161 Python / 29 前端**，JUnit fail/error/skip 均为 0；真实四格式 Intake、三种决定、九次报告下载及哈希、失败重试、双主题双尺寸与键盘浏览器通过。API/Langflow pip check 均为 0，52 个显式 pin 在实际 inventory 全部精确。

[离线探针](ci/final-a64ab47/selected/release/dependency-compatibility.stdout) 正常模式通过：OAuthlib JSONP 参数移除，生成模型 1 有效/3 无效校验；OTel 单头和双头合计 8,351 字节均丢弃 tracestate 并保留 trace_id。实际导入的两个模块 SHA 与官方 v1.45.1 tag 完全相同。网络禁止；scratch 447B/1 文件。远程 exporter / OAuth provider 连通未测试。

实际 Linux/amd64 结果：Langflow 原 8 包 / 90 IDs / 65 alias 组缩至 **5 包 / 81 IDs / 59 组**；OAuthlib、datamodel-code-generator、OTel API 本轮无命中。API 114 个 Debian IDs、PostgreSQL 116、Web 0；Langflow 另 23 个 RHSA。全局 provider ID 并集 **245**，不能当独立 CVE/可利用性计数。默认 226 RPM unknown 与原 exit 2 保留，由同一 image ID、字节相同 OS 清单的补扫覆盖 223 软件包及 3 公钥；清单内合并 mapping/query/detail unknown=0，补扫 exit 1 保留。包级匹配及厂商适用性仍需处理，不是完整文件系统/内嵌静态库或可利用性审计。

[许可复核](ci/license-final-review.json) 实际记录 **96/100 份文本 / 867,805B**，额度余 4，无任何 skip；4 个误选源码/pyc 明确 excluded。Langflow 三份补充原文均 recorded 且与仓库 SHA 相同。23 个新 pin 中 22 个有自身文本，util-http 的同源共享文本映射如上；Zep 与 native/完整分发事项仍未通过。许可证采集成功不构成分发批准。

最终来源、图像与子 manifest 完整性见 [最终摘要](ci/final-a64ab47/final-summary.json)、[扫描摘要](ci/final-a64ab47/scan-summary.json)、[兼容复核](ci/compatibility-final-review.json)；原始命令和服务 ID 在 [collector manifest](ci/final-a64ab47/selected/release/manifest.json)。

## 容量与保护

首先盘点 Docker Engine 的精确字节和共享字段。全局 image layer 记账 21,874,078,300 字节；非 shared build-cache 为 2,413,293,031 字节；两者合计 24,287,371,331 字节。97 条 shared cache 不能再次相加。已知 ARC 集合含 11 个可见 image ID（补上两个 PostgreSQL digest），另有 6 个历史引用 ID 缺元数据；可见集合逻辑大小上界 12,402,337,646 字节、全局独占内容下界 4,763,875,182 字节，均不是精确项目物理总量。

当前与旧四舍五入全局基线的差约 2.900GiB，不抹掉此前超过 3GiB 的增长警戒，也不证明完整项目低于 12GiB。因此本轮没有本地 build/pull 或 Docker 构建缓存扩张，使用隔离 GitHub runner 回归；没有 prune、删除、迁移历史镜像或缓存。本轮先前获准删除的单个 Grype DB 已在上轮处理，本次不复用该授权扩大清理。

原生许可采集计划为全批 100 路径，实际 producer 按每镜像限制实现，合计读取 101 路径 / 95,522,697 字节，超 1 路径的偏差保留。未继续补读掩盖偏差；它不使结果成为全批 100 路径合规记录。完整 source/byte correspondence、AMD64 IBM driver 不以 ARM 结果代替。

候选与正式包各小于 100MiB / 1,000 文件，本轮 temp 小于 40MiB；实测大小、文件数、源码输入及指纹见 manifest。manifest 未选入的 ZIP、缓存、原始全局 snapshot 和构建目录保留原分类。旧两个正式包逐文件复核，原库及固定输入指纹均不变。未授权清理、压缩或迁移。

## 尚未解决与后续顺序

| 事项 | 状态和原因 | 下一步与关闭条件 |
|---|---|---|
| Pillow / filelock / setuptools | 受当前 Langflow / lfx 反向上限约束，所需修复版本不满足；不强装或忽略声明 | WP-05 优先评估上游明确支持的新运行时/最小集成范围，固定候选、依赖图和镜像；重跑探针、两条 Flow、报告与故障回归后才关闭 |
| chromadb / couchbase | 当前精确版本匹配尚无已确认适用 fixed 事件；包名匹配不证明本项目可利用 | 跟进官方修复和厂商适用性，形成精确版本/可达性依据；有候选后绑定新镜像扫描。不能把无补丁写作已修 |
| Debian / RHEL 系统记录 | 实际包级发现仍存在，RHEL 补扫覆盖不是漏洞清零 | 按基础镜像及发行版厂商补丁逐项处理，保留 epoch/content_set/CPE 和 architecture；新 digest 必须回归 |
| Zep 2.0.2 精确许可 | 当前 extras exact pin；未找到兼容且包身份/许可都充分的直接替代。`v2.0.0` tag 的包名实际为 zep-cloud，不能转用为 zep-python 许可 | 取得精确 release 许可依据，或评估受支持的不含该 extra 运行时并重测；不替上游补造许可，不未经授权向上游发消息 |
| 原生与完整二进制分发材料 | 厂商 FIPS source/patch、若干 native 对应源码与 notices、AMD64 IBM driver 条款、完整 GPL/LGPL 等交付仍不足 | 按 [依赖许可矩阵](../../DEPENDENCY_LICENSES.md) 固定文件和版本、落实实际材料及源/二进制对应，再复核精确制品；完整后端分发仍未批准 |
| 本地 Docker 容量 | 历史归属和物理容量仍不能完整证明在门槛内 | 维持暂停增长；下次本地扩张前先补归属/峰值估算，任何清理、迁移或额度改变另需相应明确决定 |

维护者继续按现有 WP-05 处理这些事项。运行时/集成候选若改变固定 Contract 的边界，先记录 delta 和取得对应决定，再实施。包/许可/容量有新证据时复验；全部发布条件解决后申请完整技术及负责人最终接受，再进入既有 WP-08 的版本历史、再审、队列和诊断。LLM、OCR、真实数据、生产身份/部署仍依固定 Spec 独立选择。没有另建重复路线图。

## 证据适用范围

本包 manifest 选入的固定字节才是正式证据；子文件中的 pending/candidate/exit 2 是其真实采集阶段状态，不重写。`selection.json` 记录精确来源，`producers/` 保存相关脚本，CI 子 manifest 提供 image ID 和实际命令。全局 Docker raw snapshot 仅保留私有来源哈希；公开材料是 ARC 子集与聚合。

上轮 [v02-release manifest](../v02-release/manifest.json)（SHA-256 `c2a9cba23f3653e7c507654631f74568ee7490f80212ffe382c92323a4547f36`）和 [v02-acceptance](../v02-acceptance/manifest.json) 保持原字节。旧故障、隔离恢复、性能结果不重标为新依赖下重跑；本次没有重做本机 arm64 整栈构建，也没有重部署静态站点。

Contract 仍 approved，delivery 为 implementing / WP-05 open；AC-19 未通过，完整 `last_verified=null`，负责人最终接受 pending，残余风险未被接受。主 skill 为 `spec-development` 的 implement/verify；无 UI 改动，不加载设计或重复浏览器 skill。浏览器回归使用既有 CI 脚本。
