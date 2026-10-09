# AI Review Console：开发方案

状态：已实现并完成本地集成验证  
基线：Langflow `1.11.6`  
数据：仅虚构演示数据

## 产品目标

交付一个明确“基于 Langflow / Built on Langflow”的 AI 文档审查与决策中心。系统能导入虚构文档，执行解析、脱敏和可解释风险评分，把高风险案件送入人工审批，并导出带审计信息的报告。

该项目是辅助决策演示，不提供法律意见，不自动作出具有法律或商业效力的最终决定。

## 建议架构

```text
Browser
  |
  v
Review Web Dashboard
  |
  v
Review API --------------------> Review PostgreSQL
  |                                  | cases / findings
  |                                  | approvals / audit events
  |                                  | report metadata
  |
  +---- authenticated request ----> Langflow 1.11.6
                                       |
                                       +-- Document Parser
                                       +-- PII Redactor
                                       +-- Explainable Risk Scorer
                                       +-- Approval Task Gateway
                                       +-- Report Exporter
                                       |
                                       +-- immutable Flow JSON

Artifact storage <------------- source documents and exported reports
```

边界说明：

- Review Web 是日常工作台；Langflow UI 是受限的流程编排/管理界面。
- Review API 是浏览器唯一调用入口，负责鉴权、状态机、幂等、审计和 Langflow API Key 保管。
- Langflow 使用独立数据库/Schema，不与 Review API 直接共享内部表。
- 本地演示使用 Docker volume；存储接口保持可替换，未来可接 S3 兼容对象存储。

## 技术栈

- Langflow：`langflowai/langflow:1.11.6`，基础镜像固定为 digest `sha256:5338f6851fbab3d0476f7701dacbe749f58fa81a4c1317ad1d52164ce1231a14`；
- 自定义组件：Python 3.12，使用 `lfx` 当前导入路径；
- Review API：FastAPI、Pydantic、SQLAlchemy、Alembic；
- 数据库：PostgreSQL 16，Langflow 与业务数据逻辑隔离；
- 前端：React + TypeScript + Vite，组件与图表依赖在实现阶段锁定；
- 文档：`pypdf`、`python-docx`、标准库文本解析；
- PDF 报告：ReportLab；
- 测试：pytest、Vitest、Playwright、Docker Compose 集成测试；
- 质量与供应链：Ruff、mypy/pyright、ESLint、secret scan、pip-audit、npm audit、Trivy、Syft。

上述第三方包是候选选择，必须在锁文件生成后核验许可证和漏洞；如发现限制性许可证则替换。

## 领域模型与状态机

核心实体：

- `ReviewCase`：一次审查案件；
- `DocumentVersion`：源文件、哈希、解析结果和版本；
- `Finding`：规则命中、证据位置、严重度和建议；
- `RiskAssessment`：总分、维度分、规则版本和解释；
- `ApprovalTask`：待审批任务及分派状态；
- `Decision`：批准、驳回或要求修改及理由；
- `AuditEvent`：只追加的状态变化事件；
- `ReportArtifact`：导出格式、哈希、生成时间和下载位置。

状态流：

```text
RECEIVED -> PARSED -> REDACTED -> SCORED
                                   |
                    +--------------+---------------+
                    |                              |
              LOW_RISK_READY                PENDING_APPROVAL
                    |                              |
                    |                    +---------+---------+
                    |                    |         |         |
                    |                APPROVED  REJECTED  CHANGES_REQUESTED
                    |                    |         |         |
                    +--------------------+---------+---------+
                                         |
                                      EXPORTED

任一步骤可进入 FAILED；允许从可恢复失败点重试，但所有操作必须幂等。
```

## Langflow 自定义组件

### `SyntheticDocumentParser`

- 输入：受控文件路径、案件 ID、解析选项；
- 输出：统一文档结构、内容哈希、段落/页码位置、警告；
- 格式：PDF、DOCX、TXT、MD；
- 防护：MIME/扩展名双校验、大小与页数限制、路径归一化、超时；
- 不做：宏执行、外部 URL 抓取、首版 OCR。

### `DeterministicPIIRedactor`

- 输入：统一文档结构与脱敏策略版本；
- 输出：脱敏文本、命中清单、稳定占位符和统计；
- 默认规则：虚构姓名、邮箱、电话、证件号、银行账号、地址；
- 不在普通日志或 Flow 导出中保存原文到占位符映射。

### `ExplainableRiskScorer`

- 输入：脱敏文档、规则集版本；
- 输出：0–100 分、维度分、发现列表、证据位置和建议动作；
- 首版为纯确定性算法，确保演示离线可运行、结果可复现；
- 分数阈值和权重来自仓库中的版本化 YAML/JSON，不硬编码在 UI。

### `ApprovalTaskGateway`

- 输入：案件、评估和幂等键；
- 行为：调用 Review API 创建/更新审批任务；
- 输出：任务 ID、状态、创建时间；
- 不等待人工操作，不把审批权限交给 Flow。

### `DecisionReportExporter`

- 输入：案件快照、风险评估、审批决定和审计时间线；
- 输出：JSON、HTML、PDF 及 SHA-256；
- 所有格式显示规则版本、文档指纹、生成时间、虚构数据声明与免责声明。

## Flow 设计

仓库至少提供两个可导入、可版本化的 Flow JSON：

1. `document_review_intake`：解析 → 脱敏 → 风险评分 → 创建审批任务/低风险就绪；
2. `document_review_decision`：读取已确认决定 → 生成报告 → 登记导出物。

另提供一个失败演示 Flow 或固定输入，用于展示不支持文件、解析警告与可恢复重试。

Flow JSON 不保存 API Key；变量只保存环境变量名称。CI 检查导出文件中不存在凭据。

## 仪表盘范围

### 总览

- 待审批数、今日处理量、高风险占比、平均处理时长；
- 风险等级分布、主要风险类别、最近活动；
- Langflow 与 API 健康状态、当前规则/Flow 版本。

### 审查队列

- 按状态、风险等级、类别和提交时间筛选；
- 搜索、排序、分页、空状态、加载状态和错误恢复；
- 清晰标注需要人工处理的案件。

### 案件详情

- 原始虚构文档与脱敏文本并排查看；
- 风险总分、维度分、发现证据和解析警告；
- 批准、驳回、要求修改，理由为必填；
- 审计时间线、Flow 运行 ID、规则版本和文档哈希；
- JSON/HTML/PDF 报告下载。

### 管理与说明

- 只读展示 Flow 和规则版本；
- 数据策略、许可证通知和“Built on Langflow”说明；
- 不在普通用户 UI 中提供任意 Python 编辑能力。

## 虚构数据方案

固定种子生成至少 12 个审查案件，覆盖：

- 低、中、高、严重四档风险；
- PDF、DOCX、TXT、Markdown；
- 自动就绪、待审批、批准、驳回、要求修改、解析失败；
- 多种脱敏命中和风险证据；
- 至少一个幂等重试案例。

所有文件页眉或正文包含 `SYNTHETIC DEMO DOCUMENT`，组织名称、域名、地址、编号和条款均为虚构内容。禁止从真实公司文档改写 fixture。

## 测试与验收

### 单元测试

- 每个自定义组件的正常、边界和失败输入；
- 解析位置映射与内容哈希；
- 脱敏不漏出 fixture 中的预期 PII；
- 风险评分、阈值、规则版本与舍入稳定；
- 审批幂等、非法状态转换与权限；
- 报告内容与文件哈希。

### 契约与集成测试

- 自定义组件能被 Langflow 1.11.6 发现；
- Flow JSON 能导入并通过 API 运行；
- Review API 与 Langflow 的请求/响应契约；
- PostgreSQL 迁移、事件追加和并发审批；
- Docker Compose 冷启动、健康检查和持久化。

### 端到端测试

- 上传虚构文档 → 看到评分 → 完成人工审批 → 下载 PDF；
- 驳回与要求修改路径；
- 解析失败、Langflow 不可用和重试；
- 键盘操作、焦点反馈、对比度、响应式布局和 reduced-motion；
- 页面不显示真实凭据，浏览器网络请求不包含 Langflow 管理密钥。

### 发布门禁

- Python/前端单元与集成测试通过；
- E2E 关键路径通过；
- Ruff、类型检查、ESLint 通过；
- secret scan 无高置信度泄漏；
- Trivy/pip-audit/npm audit 无未批准的高危或严重问题；
- SBOM 已生成，许可证报告无未知或被阻断许可证；
- README、第三方通知、架构图、演示脚本和虚构数据声明齐全；
- Docker 镜像和依赖均固定版本，Langflow 镜像固定 digest。

## Docker 交付

`docker compose up --build` 启动：

- `web`：专业仪表盘；
- `api`：审查、审批、审计和报告 API；
- `langflow`：固定版本的工作流运行时；
- `postgres`：业务库与 Langflow 库逻辑隔离。

默认只把 `web` 暴露给用户；开发环境可通过显式 profile 暴露 Langflow UI。Compose 包含健康检查、非默认密码要求、持久卷和初始化 Flow 的一次性任务。`.env.example` 只含占位值。

## 文档与演示材料

最终交付：

- `README.md`：定位、Langflow 归属说明、架构、快速启动、测试和安全限制；
- `docs/ARCHITECTURE.md`：边界、数据流、状态机和威胁假设；
- `docs/DEMO_SCRIPT.md`：5–8 分钟演示步骤与讲解词；
- `docs/SCREENSHOT_PLAN.md`：需要捕获的界面与状态；
- `docs/DATA_POLICY.md`：仅虚构数据政策；
- `THIRD_PARTY_NOTICES.md` 与 `licenses/`；
- API OpenAPI 文档；
- 可导入的 Langflow Flow JSON；
- 示例报告 JSON、HTML、PDF；
- 可选的一页演示架构图或简短幻灯片。

## 实施阶段

### 阶段 0：工程与合规基线

- 建立 monorepo 目录、版本锁定、质量工具、许可证策略与 CI；
- 创建虚构数据政策、第三方通知骨架和安全默认值；
- 固定 Langflow 镜像 digest，生成首次 SBOM/许可证报告。

验收：空业务骨架可由 Compose 启动；合规和 secret 检查可重复运行。

### 阶段 1：领域模型与虚构数据

- 实现数据库模型、迁移、状态机和只追加审计事件；
- 生成固定种子 fixtures 和预期风险结果；
- 提供 API 基础契约与健康检查。

验收：状态转换、幂等和 fixtures 测试通过。

### 阶段 2：Langflow 组件与 Flow

- 实现五个自定义组件；
- 创建 Intake 与 Decision Flow；
- 完成组件单元测试和 Langflow 导入/运行集成测试。

验收：纯离线、无真实模型密钥即可完成完整审查流程。

### 阶段 3：审批与报告

- 完成审批 API、并发控制、权限检查和审计时间线；
- 生成 JSON/HTML/PDF，并登记哈希；
- 覆盖重试和失败恢复。

验收：高风险案件必须经人工决定才能产生最终报告。

### 阶段 4：专业仪表盘

- 实现总览、队列、案件详情、审批和报告中心；
- 补齐 loading、empty、error、disabled、success 状态；
- 完成响应式、键盘和可访问性基础要求。

验收：核心操作无需进入 Langflow IDE。

### 阶段 5：验证、Docker 与演示

- 完成 E2E、故障注入、容器健康检查和冷启动验证；
- 完成 README、架构文档、演示脚本、截图和示例报告；
- 运行最终漏洞、许可证、SBOM 和 secret 检查。

验收：在干净环境中按 README 一条 Compose 命令启动并完成演示路径。

## 建议的首版非目标

- 真实公司数据或生产系统接入；
- 法律合规结论或自动最终决策；
- 公网开放的多租户 SaaS；
- OCR、手写识别、复杂表格恢复；
- 企业 SSO、细粒度组织级 RBAC；
- 外部 LLM 为必需依赖；
- 修改或 fork Langflow 上游前端。

这些能力可在首版验证后单独评估，不能以“演示可用”替代其安全与合规设计。
