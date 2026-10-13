# 浏览器验收

`verify-ui-cli.mjs` 只驱动 Playwright CLI，不使用 Playwright SDK，也不新增 npm 依赖。

先启动本地 synthetic-only PostgreSQL、API、Langflow、Worker 和 web，等待服务与已发布 Flow 就绪。运行环境需要 Node.js、npx、Playwright CLI 可用的 Chrome；CI 可安装固定 `@playwright/cli@0.1.22` 并执行其 `install-browser chrome`。默认优先使用个人 Playwright skill 的 wrapper，未找到时使用固定版本 npx；也可通过 `ARC_PLAYWRIGHT_CLI` 指定 CLI 可执行文件或 wrapper。

```bash
# 不新建案件：双宽度双主题、键盘、弹窗、空/错误/加载状态
ARC_UI_INTAKE=0 npm --prefix frontend run test:ui

# 默认：额外创建独立虚构 TXT，完成真实 Intake；不作人工决定
npm --prefix frontend run test:ui

# 仅在测试环境允许记录决定时启用：真实决定、三报告与浏览器下载
ARC_UI_APPROVE=1 npm --prefix frontend run test:ui
```

可选配置：`ARC_UI_BASE_URL`（默认 `http://localhost:8080`，仅允许回环地址），`ARC_UI_HEADED=1`（可视浏览器），`ARC_UI_EVIDENCE_DIR`（绝对路径，必须是系统临时目录或 CI `RUNNER_TEMP` 的新子目录，父目录须存在）。拒绝复用已有目录；默认关闭浏览器后保留所有临时证据，不删除案件、任务或文件。

每次运行使用新的系统临时目录和唯一虚构标识，不覆盖历史截图。`result.json` 记录步骤、真实/模拟边界、案件和版本编号、命令数、文件大小与 SHA-256。生成物不是自动封存证据；仍需由发布验收 manifest 关联适用标准后选取。单次上限为 350 条 CLI 命令、25 张截图、64 MiB、500 文件。

真实链路包括 UI 上传、真实 Intake、版本绑定人工决定、真实 Decision Flow 的三格式报告以及每份浏览器下载对登记 SHA-256 的核验。网络断开、加载延迟、下载完整性错误和部分失败报告重试是明确标记的浏览器级模拟：它们验证 UI 行为，不代表真实工作流曾发生对应故障，不替代后端故障与重试验收。

当前脚本覆盖 1440/390 总览、真实案件和三报告双主题、移动导航、上传和决定弹窗的焦点恢复、短理由阻止提交、过滤空结果、网络错误恢复、Skeleton 加载、刷新保留详情、报告独立下载和缺失/失败格式重试排除已就绪 JSON。PDF 中文可读性、长文分页、解析范围与后端实际故障注入仍由对应能力验收负责。
