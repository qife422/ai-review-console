# 恢复与更新指南

## 备份范围

当前源码仓库：`qife422/ai-review-console`。经负责人明确授权公开，任何人均可查看和克隆；推送仍须仓库写权限。源码版本以 Git commit SHA 为准，不以压缩包文件名判断。

包含源码、Docker 配置、依赖锁、迁移/验证脚本、测试、固定虚构样本、示例报告、展示截图、许可证、文档与已有提交历史。`.env.example` 只含演示占位配置，不是可恢复的真实凭据。

不包含 `.env` / `.env.*`（保留 `.env.example`）、SQLite 运行库、Docker 数据卷、上传文档、运行生成报告、Python/Node 依赖目录、构建缓存和浏览器临时产物。GitHub 不能替代数据库及源文件/报告的独立加密备份，也不能找回尚未提交或推送的修改。

## 新电脑恢复源码

先安装 Git、Python 3.12、Node.js 22 和兼容的 Docker / Compose。公开仓库读取不需要登录；后续推送更新才需要使用自己的 GitHub 账号认证，不把 token 写进命令、仓库或 README。

```bash
git clone https://github.com/qife422/ai-review-console.git
cd ai-review-console
git status
git log -5 --oneline
```

按照根目录 `README.md` 的“本地开发”安装锁定依赖。完整演示使用其“Docker Compose”命令：先构建前端与镜像，再启动数据库和 Langflow，显式初始化新卷/迁移/发布 Flow，最后启动 API、Worker、Web。默认入口是 `http://localhost:8080`。

这些步骤恢复的是一个**全新的虚构演示运行环境**，不是原电脑中的案件和已生成报告。不要把 Compose project 改成历史项目名，或把 `--allow-existing` 用于原库来绕过保护。

如果另外持有数据库与文件备份，先在明确隔离的数据库和卷内核对内容清单、哈希和 schema 版本，再验证服务启动及版本匹配的下载；切换目标前需人工确认新写入的取舍，不能覆盖当前运行库。仓库内 `verify_restore*.py` 是原机器精确目标的受控演练脚本，并非跨电脑通用导入工具。

## 日常更新与推送

先检查实际修改和忽略规则；只提交源码、文档及获授权的固定资料。不要直接使用 `git add .` 上传所有运行产物。

```bash
git status --short
git diff
# 示例：按本次实际修改选择文件，不原样套用所有路径
git add README.md CHANGELOG.md
git commit -m "docs: describe the latest review workflow"
git push origin main
```

如果修改了代码，推送前运行与变更相称的测试，并在 `CHANGELOG.md` 记录主要行为及未验证范围。`git push` 成功后检查远端提交；“本地已提交”不等于“GitHub 已备份”。另一台电脑继续开发时，先在工作树干净且确认远端分支后执行 `git pull --ff-only`，不要覆盖未提交工作或强制推送。

## 找回历史版本

```bash
git fetch origin
git log --oneline --all
git show <commit-sha>:README.md
```

需要完整旧版本时，从 GitHub 对应 commit 下载或克隆到另一个明确目录，再核对 SHA。不要为恢复而在当前工作目录执行 `git reset --hard`、`git clean` 或删除数据库/卷。旧代码、旧 schema 和旧业务数据未必兼容，源码恢复不等于数据回滚。

## 展示与分享

README 包含功能说明及历史虚构截图，`demo/` 和 `examples/reports/` 可用于演示。仓库链接现可直接分享，无需公开数据库或部署服务。历史提交及候选记录中保留了原机器路径和作者元数据，这些不是新电脑上的有效恢复路径；展示时不要把历史演示、离线扫描候选或源码公开等同于生产验收。

GitHub Actions 可能由推送自动触发。其运行记录与提交绑定；测试通过、技术验收、用户最终接受、生产部署授权仍是不同事项。
