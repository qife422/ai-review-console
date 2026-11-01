# v0.2 发布验收

日期：2026-10-31（America/Los_Angeles）。Contract：`ARC-UPGRADE@0.1.0`；代码与最终 CI 输入：`fac92ea797c96cd8d12581bf616d0295e8312186`。

本轮完成了兼容范围内的依赖修补、精确镜像的包级扫描、许可证核实和实际回归。**完整 v0.2 发布验收仍未通过，AC-19 保持未关闭，最终接受 pending。** CI 绿色表示测试及资料采集成功，不表示漏洞清零、镜像分发获准或风险已经接受。

## 已解决与已通过

| 事项 | 实际结果 | 证据 |
|---|---|---|
| 应用 Python 运行锁 | 只升级 certifi 2026.10.23、Pillow 13.0.0、pypdf 6.21.4；33 包的 PyPI/PyPA 审计从本轮 67 原始结果 / 66 包-advisory alias 组变为 0 | [审计摘要](dependencies/python/summary.json)、[新锁与实际镜像绑定](environment/dependency-binding.json) |
| 前端依赖 | Vite 8.2.4、Vitest 4.1.12；对应 family、source-map-js 1.2.2、undici 7.30.1；保留无关 pin。npm 全依赖和 omit=dev 均 0 | [最终结果](dependencies/frontend/verified-summary.json)、[版本差异](dependencies/frontend/package-version-delta-final.json) |
| 运行基础与镜像内依赖 | Python 3.12.16、Nginx 1.30.6、PostgreSQL 16.15 固定 digest；API pip 26.2.2；Web curl/libcurl 8.23.0-r0、brotli-libs 1.2.1-r0。Web 包级扫描 0 | [最终扫描复核](ci/scan-review-summary.json)、[详细 triage](image-review/final-triage.json) |
| Langflow 兼容修补 | 保留 Langflow 1.11.6 基础 digest，修补 certifi/pypdf，再加入 25 个有依据的兼容 pin（24 个漏洞相关包及 aiohttp 所需 yarl）。实际 CI inventory 逐项匹配，这 25 包对应最终 OSV 查询均 0 | [选择过程](dependencies/langflow-patches/selection.json)、[最终实际版本核对](image-review/final-triage.json) |
| Python / 前端 / 构建 | 最终 CI 154 Python、29 前端测试，0 fail/error/skip；fresh npm ci、Ruff、生产构建均通过；API 与 Langflow 真实镜像 pip check 通过 | [CI 摘要](ci/final-summary.json)、[JUnit](ci/arc-unit.xml)、[原始日志](ci/verify-job.log) |
| 真实工作流和浏览器 | 四格式 Intake、三种决定、九报告下载和哈希、负向失败/重试、五组件、两 Flow hash 不变；浏览器 28 步 / 212 CLI 命令，1440/390 两主题通过。四图已逐图查看，中文及关键控件正常 | [workflow](ci/selected/workflow.json)、[浏览器结果](ci/selected/browser/result.json)、[逐图观察](ci/visual-review.json) |
| 本机 Linux/arm64 镜像 | 最新 29 个 Langflow 显式 pin、两镜像 pip check、真实四格式/三决定/九下载及失败重试通过；故障前本轮 5 案件仍在、3 个决定及 9 份报告字节不变 | [原生验证](native/workflow.json)、[保全复核](native/preservation.json) |
| 许可识别与随包材料 | 普通前端构建提供 24 个实际 bundle 依赖许可、IBM Plex OFL，Web 另含项目 Apache 文本；选中 API 包 7/7、Langflow 包 42/46 有真实许可文本；其余 4 包逐项复核，未笼统归为 MIT | [最终许可复核](license-review/final-ci-review.json)、[真实镜像材料](ci/selected/release/licenses/manifest.json) |

最终 [GitHub CI 41259579902](https://github.com/qife422/ai-review-console/actions/runs/41259579902) 已实际 completed/success，绑定 `fac92ea`，不是沿用旧提交绿色状态。依赖审计与实际镜像 pin 的逐项绑定见上表；初始审计后仅修正过锁文件生成命令注释，包元组未变化，没有把注释改动冒充重新扫描。

CI 中文字体改用仓库内固定 Noto Sans SC，安装字节 SHA-256 与来源字节均核实，不再依赖 apt 下载字体。[字体记录](ci/selected/chinese-browser-font-version.txt)及四图记录属于当前 CI。早先两次因 apt 等待而取消的 run 保留历史状态，不作为最终通过依据。

## 镜像检查的结果与范围

扫描对象是以下**真实运行的 Linux/amd64 精确镜像 ID**，不是可变 tag，也不是只看本地源码。运行时包清单通过无网络、只读、无业务卷挂载的短时容器采集，再向 OSV 发送包名/版本。Docker Scout 的登录限制不再阻止本轮包级查询；没有登录、复制凭据或配置降级。

| 镜像 | 完整 image ID | 最终匹配 |
|---|---|---|
| API | `sha256:8f2f6f8d6916153043c8388c0f524bfc13c2e7945212dd7329c6e5cc8fdfa4f5` | 140 包中 51 个包匹配 114 个 Debian advisory IDs；运行 Python 包没有剩余 PyPI 匹配 |
| Langflow | `sha256:33960b31a9600466b019713f12a7779d720e94443cd09935d3dc0640ab019dc2` | 774 包中 8 个 Python 包匹配 90 IDs / 65 alias 组；另 50 个 RPM 包匹配 23 个 RHSA IDs |
| Web | `sha256:43c964da1c549cad88ef332222b7739c7e9b7c15e4a8d05829b5db992d8fd231` | 71 包，0 匹配 |
| PostgreSQL | `sha256:74d436cb49d3398cf7b5d7b33635d43623d9e4da4b93c22db453f7d5d81181b1` | 142 包中 63 个包匹配 116 个 Debian advisory IDs |

默认扫描的 exit 2 原样保留：226 个 unknown 全部且仅为 Langflow 的 RPM 项。独立 Red Hat 补扫绑定同一个 image ID、实际 content_set、官方 repository→CPE、RPM epoch/架构/sourceRPM，覆盖相等的 226 项集合：223 软件包与 3 个公钥元数据。两部分合并后，本清单范围内 mapping/query/detail unknown 均 0，**并不把原 exit 2 改写成 0**。[集合/身份核对](ci/scan-review-summary.json)、[RHEL 原始 manifest](ci/selected/release/rhel/manifest.json)。

不同镜像条目有重叠，不能相加当独立漏洞。服务 ID 的并集为 254，不等于 CVE 数或可利用漏洞数。上游未给严重度的项保持 unknown；RHSA 公告不按其引用的 CVE 数计成多个公告。初始 ARM64 与最终 AMD64 的架构、时间和部分包集合不同，不能用两个总数差直接宣称同环境降幅；本轮修补是否生效按具体包/版本与最终查询核对。

检查只覆盖已识别的包管理器及 Python METADATA。**没有完整文件系统、静态二进制、wheel 内嵌库或运行可利用性审计**，不把包级 0 匹配外推成绝对安全。OSV 查询的请求/响应、详情、来源及时间已入选；服务没有提供可重放的统一数据库快照日期。数据来源及其许可说明见 [OSV 官方数据源](https://google.github.io/osv.dev/data/)。

## 未解决项和下一步

下表不是风险接受。负责人尚未批准任何剩余风险，缺项不通过忽略 advisory、修改包 metadata、强装冲突版本或降低 AC 来关闭。

| 优先级 / 事项 | 当前事实 | 后续工作与关闭条件 |
|---|---|---|
| P0：Langflow 上游上限 | Pillow 12.3.0、filelock 3.32.0、setuptools 83.0.0 的记录修复版本被现有 Langflow/LFX 上限阻止；最新 Langflow 1.13.0 仍排除 Pillow 13 | 等待/核实受支持补丁，或先提出有明确影响与重测范围的运行时候选；不强装或篡改约束。实际构建、pip check、Flow、报告和新扫描全部通过后才能关闭 |
| P0：其他兼容升级 | oauthlib 3.3.1→4.0.0 跨 major；datamodel-code-generator 0.71.0→0.81.0 属 pre-1.0 minor，两者当前 reverse 范围允许，但本轮未验证行为兼容；opentelemetry-api 1.44.0 需连同 SDK/semantic-conventions 等 exact 依赖成套升级 | 作为明确的兼容工作包实施和验证，不把“允许解析”当行为兼容，不误标为上游完全禁止。详见 [8 包具体依据](image-review/final-triage.json) |
| P0：无已确认修复事件 | chromadb 1.5.9、couchbase 4.6.2 的返回记录没有精确 PyPI 包的 fixed 事件；不等于证明上游不存在 workaround | 对照上游安全公告、适用条件和受支持方案；新候选须有修复依据及回归。不能凭“更新了版本号”关闭安全项 |
| P0：发行版 / RPM | API、PostgreSQL 与 Langflow RPM 仍有上述包级匹配；多数 Debian 记录未给本发行版 fixed 事件 | 按真实发行版/架构核对厂商公告、backport、适用性和仓库维护补丁；未知项保留。跨发行版 glibc 或上游运行时改动须另定兼容范围 |
| P0：Zep 精确许可 | `zep-python 2.0.2` 的安装 wheel、官方 sdist、精确官方 release tag 均未找到许可；旧 oss 分支许可不能自动套用 | 取得该版本的明确上游许可依据，或评估许可明确的替代/受支持运行时；完成精确制品复核。没有向上游自动发消息或开 issue |
| P0：完整二进制分发材料 | GPL/LGPL/MPL 等条款已识别，但对应源码/获取材料及 wheel 内原生库通知未全部交付；AMD64 另含 IBM clidriver，Python 层 Apache 不能替代 driver 条款 | 逐版本完成原生库、driver 与适用字体/许可材料清单；当前不作完整后端镜像分发批准。源码、浏览器沙盒及后端镜像分别判断 |
| P1：采集器候选过滤 | 许可文件名启发式还选入了 litellm/mem0 的 2 个源码及 2 个 pyc 文件，原始数据保留，人工解释已明确排除；42 个真实许可包统计未因此虚增 | 后续收紧候选后缀并验证；不得把文件名匹配替代法律文本判断。缺包内文本的 dnspython、fastmcp-slim、LFX 已用精确上游确认，Zep 未确认 |
| 下次本地构建前：容量 | Docker 镜像与缓存的全局报告量相对基线代理增量约 3.63GB，超过单 WP 3GiB 警戒；共享层/历史归属仍有局限 | 已停止进一步构建、拉取或缓存扩张，只完成既有镜像验证并停服务。先精确盘点和确定容量处置；没有推断 prune、迁移或扩大额度授权 |

新增 4 个 AMD64 Python 包由既有依赖的架构 marker 引入：Opik 所需三项 tree-sitter、lfx-ibm 所需 ibm-db；它们在 Linux/aarch64 的 marker 为假，没有新启用集成。tree-sitter 系列 MIT 已按精确版本确认；IBM Python 层 Apache 和 driver 条款分开记录。[许可核实](license-review/final-ci-review.json)含原文/来源/hash及适用范围。

先关闭上述发布问题并重新出具受影响证据，再申请完整技术验收及最终接受。随后才按既有 WP-08 做版本历史、再审、队列效率和诊断；模型/OCR、身份权限和生产化仍按原 Contract 的独立决策推进。

## 运行保全、失败与容量处置

原 `review_console.sqlite3` 为 57,344 字节，SHA-256 `980ad5d23d866a52e4101966594e5a24ee67edef08475afc63ff9c3e1f6fca1f`，前后不变。固定 Spec 与旧 baseline、旧正式证据 manifest 指纹也未改。没有对原库/历史卷做迁移、清理或生产切换。测试写入仅在本轮新隔离项目 `ai-review-console-release`，库卷和虚构记录保留。[最终保全](environment/final-preservation.json)。

开工遗漏了宿主机可用空间预检；Grype 漏洞数据库解压又超过缓存增长门槛。实际发生宿主 ENOSPC 和 Docker 构建 EROFS，失败输出保留，没有把失败构建记为完成。下载和构建已停止，改用不下载大型数据库的 OSV 路径。用户随后明确授权，仅删除新生成、无消费者、未入选证据的单个 DB 缓存：`/private/tmp/arc-v02-release-close.p3RyvK/tool-cache/grype-db`，2,966,994,944 字节；精确内容和删除后缺失/空间回读见 [授权处置](environment/authorized-cache-removal.json)。没有顺带清理其他缓存或旧证据。

Docker Desktop 的正常 restart 一度无法退出，精确 GUI/engine 子进程退出后，仅结束无子进程、无 Docker 磁盘句柄的遗留 manager，再恢复启动。没有重置 Docker、修改磁盘设置或删除镜像/卷。本机 pip 回滚状态先核实，再在空间恢复后成功更新至 26.2.2；最终 Docker 健康、队列 active=0、所有验收服务已停止。负向测试的 failed 任务保留，不因验证通过自动清除。

本轮现有缓存约 0.96GB / 48,851 文件，临时、候选/正式证据、镜像和业务卷分开盘点；作者源码与固定上游字体/依赖分开计算。正式清单不含 transport ZIP、完整 dist/node_modules/.venv、镜像导出或数据库 dump。Docker 全局量不冒充精确项目物理容量。[最终盘点](environment/final-inventory.json)、[Docker 增长警戒](environment/docker-growth-warning.json)。除已授权 DB 外，临时数据、候选、镜像/构建缓存及卷保留，`pending_cleanup=true`，不影响已取得证据的真值，也不意味着全版本验收通过。

## 证据身份和局限

正式资格仅由本目录的 `manifest.json` 及其选中内容指纹赋予；`selection.json`、各 producer manifest 保留生成时的原始状态/字段，不据其目录名、扩展名或 CI 绿色推断正式资格。原始日志保留 ANSI、EOF 和空白，分别做源码格式检查与内容哈希核实。

浏览器隐藏 CLI 快照和部分下载原字节没有被 GitHub artifact 默认收录；这里只封存实际取得的四图、result、命令日志及运行时哈希核验结果，不声称保留了那些隐藏文件。未把上轮完整故障/恢复/20×1MiB 性能记录重新标成当前依赖版本的完整新验收；它们仍按 [上轮固定记录](../v02-acceptance/README.md) 的源码/环境范围理解。

本轮没有测试真实公司文档、收费模型/OCR、生产身份/公网后端或生产恢复；没有单独构建替代的 `docker/web-build.Dockerfile` 多阶段路径，实际 Web 验证使用 Compose 的 `docker/web.Dockerfile`。当前在线站点仍按既有独立静态制品理解，不能继承为上述真实后端证据。
