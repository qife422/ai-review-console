# AI Review Console

AI Review Console 是一个基于 Langflow 的 AI 文档审查与决策中心参考实现。它使用完全虚构的数据演示文档解析、确定性脱敏、可解释风险评分、人工审批与 JSON/HTML/PDF 报告导出。

> **SYNTHETIC DEMO DATA ONLY / 演示仅使用虚构数据**  
> 本项目不包含任何公司机密、客户数据、真实合同、生产凭据或真实决策记录。

## 当前进度与升级计划

当前版本是围绕12个预置虚构案件的演示型参考实现。Langflow组件与示例Flow可独立执行，网页新增文件上传、结果入库、审批后自动执行报告Flow的完整链路仍待完善；当前风险评分使用确定性规则，尚未调用大模型。PDF中文及部分审批/导出边界已列入整改计划。

完善及后续升级见 [Spec计划书](docs/UPGRADE_SPEC.md)，当前候选为 `ARC-UPGRADE@0.1.0`。实施状态、内容指纹与下一工作包见 [当前状态](docs/CURRENT_STATE.md)和[Spec索引](docs/SPEC_INDEX.md)。计划书不代表升级已实施，也不代表生产部署已获授权。

## 基于 Langflow

本项目使用 [Langflow](https://github.com/langflow-ai/langflow) `1.11.6` 作为可视化工作流编排和运行时，并通过五个可信自定义组件实现审查流程。Langflow 是独立的 MIT 许可上游项目；本项目与 Langflow 官方不存在隶属或背书关系。

日常审查使用独立的 Web 仪表盘。Langflow UI 只用于受控管理员查看 Flow，不作为面向终端用户的安全边界。

## 能力

- PDF、DOCX、TXT 和 Markdown 文档解析；
- 邮箱、电话、虚构证件号、账号、地址和人员字段脱敏；
- 0-100 分的透明规则评分与证据定位；
- 批准、驳回、要求修改三种人工决定；
- 只追加审计事件；
- JSON、HTML 与 PDF 报告导出；
- Carbon Design System 专业仪表盘；
- 固定种子的 12 个虚构案件；
- Python、前端和浏览器测试；
- Docker Compose 本地部署。

## 架构

```text
Browser -> Review Web -> Review API -> Review PostgreSQL
                            |
                            +-------> Langflow 1.11.6
                                         |
                                         +-> Trusted custom components
```

详细决策见 [技术可行性与许可证检查](docs/FEASIBILITY_AND_LICENSE.md)和[开发方案](docs/DEVELOPMENT_PLAN.md)。

## 本地开发

要求：Python 3.12、Node.js 22、Docker 28 或兼容版本。

### API

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.lock
.venv/bin/pip install -e '.[dev]'
.venv/bin/uvicorn api.app.main:app --reload --port 8000
```

API 文档：<http://localhost:8000/docs>

### Web

```bash
cd frontend
npm install
npm run dev
```

Web：<http://localhost:5173>

### 测试

```bash
make test
make lint
```

### Docker Compose

复制 `.env.example` 为 `.env`，替换所有 `replace-with-*` 值，然后运行：

```bash
docker compose up --build
```

默认入口：<http://localhost:8080>。Langflow UI 仅绑定本机回环地址：<http://localhost:7860>。
不要把 Langflow 的 `7860` 端口改为公网监听。

Compose 使用仓库中已验证的 `frontend/dist` 静态产物，以避免运行环境依赖 npm 网络。修改前端后先运行 `npm run build`。CI 可使用 `docker/web-build.Dockerfile` 从锁文件完整重建 Web 产物。

启动后可运行 Langflow 端到端验证（检查 5 个组件并真实执行 2 条 Flow）：

```bash
LANGFLOW_SUPERUSER_PASSWORD=change-me \
.venv/bin/python scripts/validate_langflow.py
```

## Langflow 自定义组件

组件位于 `custom_components/review_center/`：

- `SyntheticDocumentParser`
- `DeterministicPIIRedactor`
- `ExplainableRiskScorer`
- `ApprovalTaskGateway`
- `DecisionReportExporter`

生产配置关闭 UI 中任意自定义代码编辑，但保留通过 `LANGFLOW_COMPONENTS_PATH` 加载的仓库可信组件。Flow 文件位于 `flows/`，不得包含任何 API Key。

已生成的 Python、Node 和应用 API/Web 镜像 CycloneDX SBOM 位于 [`compliance/sbom/`](compliance/sbom/)，证据清单与 Langflow 镜像发布门禁见 [`compliance/README.md`](compliance/README.md)。

## 演示数据

运行以下命令可重新生成固定种子演示文档：

```bash
.venv/bin/python scripts/generate_fixtures.py
```

所有示例文件包含 `SYNTHETIC DEMO DOCUMENT` 标识，域名只使用 `example.com` / `.org` / `.net` 保留域。项目输出不构成法律意见或自动决策。

六分钟演示话术、桌面端/移动端截图与示例报告见 [`demo/`](demo/) 和 [`docs/DEMO_SCRIPT.md`](docs/DEMO_SCRIPT.md)。

## 安全限制

- Langflow 能执行 Python，自定义组件只可由可信维护者发布；
- 浏览器永远不接收 Langflow 管理 API Key；
- 演示鉴权头 `X-Reviewer` 不是生产身份认证；
- 公网、多租户、企业 SSO、细粒度 RBAC 和恶意文件沙箱不在本演示范围；
- 正式部署前必须完成身份系统、基础设施隔离、恶意文件扫描、SBOM、许可证和漏洞复核。

## 许可证

本项目自研代码采用 Apache License 2.0。Langflow 采用 MIT License，详见 [第三方通知](THIRD_PARTY_NOTICES.md)及 `licenses/`。
