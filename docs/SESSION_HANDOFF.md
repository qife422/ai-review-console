# 开发进度与续接记录（历史）

记录时间：2026-09-01（Asia/Shanghai）

## 当前结论

本记录对应中途暂停点。工作已于同日续接并完成最终验证，当前结果以 `docs/VERIFICATION.md` 和 `compliance/README.md` 为准。交付包含基于 Langflow 的自定义文档解析、确定性脱敏、可解释风险评分、人工审批、报告导出、专业仪表盘、虚构演示数据、测试、Docker 部署、README 与演示材料。项目内已明确声明：基于 Langflow，演示数据完全虚构，不包含任何公司机密。

## 已完成

- 完成 Langflow 技术可行性和上游许可证检查；固定 Langflow `1.11.6`、MIT 许可证文本与镜像摘要。
- 实现 5 个 Langflow 自定义组件：文档解析、PII 脱敏、风险评分、人工审批网关、报告导出。
- 创建并通过真实 Langflow Build API 执行 2 条 Flow：`Document Review Intake`、`Document Review Decision`。
- 实现 FastAPI 审查服务、12 条固定虚构案例、审批审计与 JSON/HTML/PDF 报告导出。
- 实现 React + TypeScript + Carbon Design System 仪表盘，覆盖桌面、移动端、暗色模式和关键状态。
- 完成 Docker Compose 编排、健康检查、Flow 自动导入、README、架构/数据政策/演示文档与截图。
- 已通过：Python 9 项测试、前端 Vitest、Ruff、前端 lint/build、`npm audit --omit=dev`、`pip-audit`、Docker Compose 配置检查、浏览器交互与响应式检查。
- 已生成 Python、Node、API 镜像和 Web 镜像 CycloneDX SBOM；Langflow 整镜像 SBOM 扫描曾因限定时间内未完成而终止，仍是发布前待办。

## 暂停时 Docker 状态

以下状态已于暂停前只读确认：

- `postgres`：healthy
- `langflow`：healthy，映射 `127.0.0.1:7860`
- `api`：healthy
- `web`：运行中，映射 `http://localhost:8080`
- `flow-init`：正常退出，状态码 `0`

容器保持运行，没有执行停止或清理操作。

## 原续接清单（已完成）

1. 已确认容器状态和端点：

   ```bash
   docker compose ps -a
   curl -fsS http://127.0.0.1:8080/api/health
   docker compose logs --no-color flow-init
   ```

2. 已重新运行真实 Langflow 验证：

   ```bash
   python scripts/validate_langflow.py
   ```

3. 已重新生成最终 API 镜像 SBOM，并更新 `compliance/README.md` 中的哈希。

4. 已完成最终回归：

   ```bash
   .venv/bin/ruff check .
   .venv/bin/pytest -q
   npm --prefix frontend run lint
   npm --prefix frontend test -- --run
   npm --prefix frontend run build
   npm --prefix frontend audit --omit=dev
   .venv/bin/pip-audit -r requirements.lock
   ```

5. 已更新 `docs/VERIFICATION.md` 和开发计划状态。

## 已知边界

- 当前身份头和演示账号仅适用于本地演示，不是生产级认证、SSO 或 RBAC。
- Langflow 可执行自定义 Python 代码，不应被当作不可信多租户安全边界；生产环境需要网络隔离、权限控制和供应链门禁。
- Langflow 上游许可证和固定版本已核对，但完整 Langflow 镜像 SBOM/漏洞扫描仍需在发布前完成。
- 当前目录没有 Git 仓库，因此尚无提交记录；现有文件均保留在工作区。
