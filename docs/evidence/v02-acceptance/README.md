# v0.2 收尾验收

日期：2026-10-28（America/Los_Angeles；机器记录使用 UTC，部分为 10 月 29 日）。本轮用户授权状态对齐、v0.2 收尾验收及 GitHub 同步；不新增真实数据、付费模型或生产部署范围。

**结论：功能、故障和恢复检查已取得实际证据；发布检查 AC-19 未通过。完整 v0.2 技术验收及用户最终接受仍未完成。** 公开在线版继续按 [ONLINE_DEMO.md](../../ONLINE_DEMO.md) 的独立纯前端沙盒定位。

## 输入与证据身份

- 固定 Contract：`ARC-UPGRADE@0.1.0`，SHA-256 `a77947d0369566cef516641ef918e37d08046afc2edf8215dcff90d49ce01753`；正文未改。
- 起点：`14d44b1210cff67b6f2bdd60de4523cc56bcb1e8`。CI 中文字体修复提交：`85dddfd43fa51abfa53c5291177dda818397139d`。
- 最终验收修复代码：`540fd4c07cc3ad1b1ce017d3957f06fa0732e5ba`。API/core/组件/Flow/锁文件业务代码与起点一致；本轮修改案件路由、验收脚本、CI 字体和证据 lint 分类。具体输入文件指纹以最终 manifest 为准。
- API 镜像：`sha256:f0cf8dc583f3e7523675748fd1841dd708655ed3783f022fafb9955815a4c95a`；Langflow：`sha256:ff0f5cc380743034c05b4bfcf587be0e714da1610799f0c7c41d45902a5267c4`。先检测旧镜像不一致，再重建 API；运行前 40 个文件的匹配结果保留。随后修改的本地验收脚本单独绑定 producer hash，不声称旧镜像内也包含这些新脚本。本机 Web 镜像/库存早于路由补丁，最终前端由当前源码的 Vite 专项及最终 CI 的生产构建/浏览器验证覆盖；不把旧本机包标成最终前端发布镜像。
- `checks-index.json` 和 `release/index.json` 保存每个选择文件的原来源、方法、范围与 SHA-256；最外层 [manifest.json](manifest.json) 将列出的内容、方法、输入指纹和实际结果封存为本轮证据；只有入选文件具有该身份。目录位置不自动赋予证据资格。

最终代码的 [GitHub CI 40819513529](https://github.com/qife422/ai-review-console/actions/runs/40819513529) 已实际 `success`，verify 与 workflow-browser 均通过。随后仅提交活动文档和本证据包；应用、测试、依赖及 CI 输入仍与该代码提交的逐文件指纹一致。

## AC 结果

`passed` 只表示下列明确范围已有技术证据；不表示生产适用、用户最终接受或未测路径都正常。

| AC | 结果 | 实际证据与范围 |
| --- | --- | --- |
| 01 | passed | `checks/runtime/workflow.json`：TXT/DOCX/PDF/MD 新上传、哈希/版本/任务、后续读取持久化；CI 浏览器键盘上传 |
| 02 | passed | 快速参数化解析/API 测试；真实缺虚构标识输入保持 failed/unscored，幂等重试不变成成功 |
| 03 | passed | DOCX 表格/PDF 页 locator、脱敏完整性单测；`checks/locator/` 实际网页跳转、焦点、视口与证据 offset 核验 |
| 04 | passed | 真实 Langflow 1.11.6 动态输入与新 run；源字节绑定、存储图 before/after hash 不变，五组件可发现 |
| 05 | passed | SQLite API + PostgreSQL 重复 callback、错误 token/版本/哈希与回调竞态；单评估/审计 |
| 06 | passed | `checks/runtime/faults.json` 前四场景中的执行前/回调后实际 SIGKILL，租约恢复且无重复评估/审计 |
| 07 | passed | 实际 Langflow/callback 拒绝连接、401、新 generation 恢复；真实 429 及恢复日志；timeout/429 映射另由契约单测覆盖 |
| 08 | passed | 确定性规则/脱敏测试、低风险零分仍待人工；真实 Flow 输出与新输入绑定 |
| 09 | passed | PostgreSQL 两个并发决定仅一个胜者，单决定/审计/报告任务 |
| 10 | passed | trim/身份/版本/CAS 测试、三种实际 API 决定与浏览器键盘审批 |
| 11 | passed | 无决定、ready/processing/failed/未知状态的正向导出门禁测试 |
| 12 | passed | `checks/pdf/` 三格式字段与长中文四页逐页渲染检查；真实 Flow 三格式下载另有字节哈希 |
| 13 | passed | 三个人工决定触发真实 Decision Flow，九份报告登记与下载字节哈希匹配 |
| 14 | passed | `checks/report-retry/`：实际坏字体仅 PDF 失败，三次后恢复环境并专用补 PDF，原 JSON/HTML 和决定不变 |
| 15 | passed（有范围） | 最终代码 CI 的 390/1440、双主题、键盘与状态检查；新路由 29 项测试及 `checks/router/` 实际同页切换/后退/焦点/证据跳转；最终代码 CI 同时通过 |
| 16 | passed | 探测失败保持 unknown 的单测/浏览器响应模拟；`status-readback.json` 实际端点 checked_at 与 seed 来源回读，不把模拟响应当真实掉线 |
| 17 | passed（有范围） | 原 SQLite 的隔离副本迁移、PostgreSQL 迁移测试及完整 public 表指纹恢复；恢复 API 只读启动与选定文件下载；文件范围见后文 |
| 18 | passed | 最终代码 `540fd4c` 的真实 CI：128 Python、29 前端、四格式/三决定/九下载、失败重试及浏览器，原生回读与选定 artifact 见 `release/final-ci/` |
| 19 | failed / blocked | 三当前镜像新库存已生成；依赖漏洞、镜像查询认证阻塞及许可证复核尚未闭环，不能宣布发布通过 |

AC-20..24 属后续模型、应用增强或生产化，本轮不实施，也不标通过。

## 关键观察与修复

快速检查为 `.venv/bin/python -m pytest -q -ra`（124 passed / 4 skipped）、独立 `tests/test_postgres.py`（4 passed）、Ruff、TypeScript 和前端 29 项。跳过的 PostgreSQL 项在明确隔离库的独立命令中实际运行；MockTransport 不充当真实 Flow。

真实整栈使用 `LANGFLOW_SUPERUSER_PASSWORD` 指向本地虚构环境，运行 `scripts/validate_langflow.py --api-url http://127.0.0.1:8000 --evidence <新文件> --benchmark-count 20`。缺凭据的首次预检失败记录保留，之后显式配置并验证，不把预检当业务失败。

混合负载包含 20 次 1 MiB TXT 上传、真实 Intake 和每次三次详情查询：上传 p95 `0.094931s`、查询 p95 `0.118757s`、Intake 最大 `3.420485s`，无丢任务，三个耗时目标通过。环境在 workflow JSON 中。旧约 1.42 秒失败仍保留；本轮结果不证明旧失败的根因，也不外推为高并发吞吐。

故障首轮四场景通过，第五场景的人工重试实际遇到上游登录 429，随后成功；旧脚本要求 `attempt==1` 导致整轮假失败。修复为 Contract 的 1–3 次，并增加 generation/token/唯一性约束；仅重验该场景，通过记录在 `checks/auth-recheck/`，原失败和 429 日志都保留。

真实报告部分失败仅给隔离 Langflow 临时增加坏字体环境。原 report 三次失败后 finally 恢复原镜像、环境哈希、挂载、网络及两条 Flow 哈希，再专用重试 PDF。只新增一个虚构案件，决定和决定审计均一条；首次脚本模块名预检错误未创建案件，原记录也选入。

浏览器发现同页改 hash 时可能保留旧案件，已修复 hashchange/popstate 同步与旧请求取消/迟到保护。真实浏览器证明 DOCX→PDF 未刷新、仅请求一次新案件，焦点/定位、后退与未知 hash 均正确。另补修 SkipToContent：保持当前案件 hash 并聚焦 main；`checks/router/skip-result.json` 的键盘专项使用明确标记的 fixture/mock API，只验证焦点与路由，不冒充真实 Flow。CJK 缺字是 CI Linux 字体验证环境问题，修复后截图已人工回看。冻结的 producer 快照保持原字节，Ruff 排除 `docs/evidence`；所有可执行项目源码仍接受检查。

## 恢复与保全边界

原 SQLite 为 57,344 字节，前后 SHA-256 为 `980ad5d23d866a52e4101966594e5a24ee67edef08475afc63ff9c3e1f6fca1f`。迁移只对新副本执行。PostgreSQL 完整 public 业务表恢复到 `arc_restore_2ed4123efdbb`，73 个案件，逐表行数与内容 hash 一致，无应用切换。

恢复运行文件包明确选三种决定的三个新案件，12 文件 / 208,426 字节；恢复 API 只读连接、只读挂载，不启动 worker/seed/migrate。九份报告下载匹配；未选文件只保留数据库记录，**不宣称这些文件已恢复或可下载**。这是一份最小运行恢复证明，不是完整文件灾备策略。

第一次复制因 root 丢弃 DAC 权限后无法写入已 chown 的新卷而失败。两个目标卷已实际证明为空；修复只给复制进程增加 DAC_OVERRIDE，按原 plan SHA、原 DB/image/case/file 清单和卷标签重用相同目标。外层与实际复制入口均拒绝非空目标，使用独占写入；没有通过换名、删卷或覆盖来隐藏失败。

原项目数据库/旧卷、固定输入和历史证据保持保护。运行 dump、SQLite 副本和恢复卷留在本机，未纳入 GitHub 证据包；未授权历史清理、压缩或迁移。验收结束后停止本轮启动的服务，保留数据及容器供后续明确启动。

## 发布待解决项与接续计划

| 优先级 | 事项与下一动作 | 完成条件 / 边界 |
| --- | --- | --- |
| P1 / WP-05 | 修补锁文件和镜像中适用的依赖漏洞 | Python certifi/Pillow/pypdf、Node 五包的精确 advisory/修复候选见 `release/dependencies/dependency-triage.json`；评估主版本兼容、同步双端依赖、重建和重跑相称验收后再次审计 |
| P1 / WP-05 | 完成镜像漏洞扫描 | Scout 当前需 Docker 登录，`findings=null` 不能算零漏洞；提供可用认证或明确选择另一可用扫描器后，对精确新镜像查询 |
| P1 / WP-05 | 关闭许可证复核 | Python 锁定包的 LGPL 项及 API/Langflow/Web metadata unknown/review 逐项核实分发义务，形成来源与结论；库存不是许可批准 |
| P1 / WP-05 | 申请完整技术与最终接受 | AC-19 闭环，绑定最终源码/镜像/证据；技术通过、风险接受和用户最终接受独立记录，不自动批准生产 |
| 后续 WP-08 | 修订再审、版本历史、队列效率与诊断恢复 | 沿既有 Spec 增量实施，不另起重复路线图；先稳定 v0.2 |
| 后续 WP-06/07/09 | 可选模型与生产化 | 先定模型/预算/出口/评测；真实身份、数据准入和生产基础设施另行决定 |

Python 33 锁定包中三包匹配 60 条原始记录，按 advisory aliases 去重为 59 组；npm 五个受影响包（3 high、2 moderate），`omit=dev` 仍有 source-map-js high 标记。包管理器的生产标记不等于已证明静态网页可利用；Sass peer/build 链与可达性必须区分。当前不接受这些残余风险，也不自动升级到可能不兼容的版本。

本轮计划 60 分钟；临时输出上限 256MiB/10,000 文件、选入证据 100MiB/1,000 文件，作者源码起点 638,871 字节；大于 1GiB 且大于源码 100 倍的派生产物须停扩盘点，固定依赖/上游镜像另列。只封存 manifest 选入的小日志、JSON、报告及截图，不封存整个构建树/缓存。未授权清理的临时与历史产物继续保留，`pending_cleanup=true`。

## 完整性回读

在仓库根目录执行以下只读检查；它只验证已选文件与输入指纹，不重新宣称功能或发布通过。

```python
import hashlib
import json
from pathlib import Path

root = Path("docs/evidence/v02-acceptance")
manifest = json.loads((root / "manifest.json").read_text())
for item in manifest["files"]:
    data = (root / item["path"]).read_bytes()
    assert len(data) == item["bytes"]
    assert hashlib.sha256(data).hexdigest() == item["sha256"]
print("Selected evidence hashes match")
```
