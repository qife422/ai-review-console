# 在线演示

体验链接：<https://ai-review-console-demo.adeptbread257.chatgpt.site>

在线版保留 AI Review Console 的 Carbon 界面，供访客选择预置虚构样本，体验脱敏、风险证据、人工决定及 JSON/HTML 报告下载。HTML 可通过浏览器打印另存 PDF；本次没有验收实际打印或保存 PDF。

## 演示范围

- 四个预置虚构 TXT 样本；不提供本机文件选择器，适配器拒绝任意外部 File。
- 进度、发现和评分为明确标注的演示预设，真实工作流 ID 为空；不调用模型或 Langflow。
- 决定与报告在当前页面内存中模拟，刷新或“重置演示”恢复初始四个案件；访客互不共享业务状态。
- 无业务 API、数据库、连接器、密钥或收费调用。静态页面 CSP 使用 `connect-src 'none'`，构建模式不读取本机 `.env`。
- 托管平台仍可能记录常规访问元数据；请勿在理由等自由文本中输入真实个人信息、客户内容或秘密。

## 本次发布

| 项目 | 值 |
| --- | --- |
| 发布时间 | 2026-10-28 21:54 UTC |
| Sites 项目 | `appgprj_6ae26ac1f3888191b1ac30ce560137e7` |
| Sites 版本 | `appgprj_6ae26ac1f3888191b1ac30ce560137e7~appgver_bca0b783ab708191952e074128ea931d`（1） |
| 部署 | `appgdep_6ae26ef743c48191ab3225ba05ecb0f4` |
| 部署回读 | `succeeded`，公开访问 |
| Sites 源码提交 | `b982dd1582e4523bc3eb50ac7651acb414fbf964` |
| 发布目录 | `online-demo/out/` |
| 静态目录规模 | 100 文件，2,887,147 字节；不含外层托管配置 |
| 入口 HTML SHA-256 | `463100afa27ef27e429d56bb55874a6ec0ce07a8e2b672dd8b9963ec5a4445c6` |
| JavaScript SHA-256 | `6b3d44a3b8370b11db298b965fd57506a2f547c08afcbc931bedae34a4e7ac47`（`assets/index-DgPIDohw.js`） |

发布目录包含字体和第三方许可证。以上是发布定位与完整性记录，不代替原业务系统的验收证据。旧预览 `online-demo/dist/` 与 `.build/` 不是本次发布输入；本机临时归档、缓存和截图不作为跨电脑可用的恢复来源。

## 从 GitHub 重建

原始 TS/React 源码、锁文件、测试和构建脚本由父 GitHub 仓库保存。`online-demo/` 是独立 Sites 源码检出与生成目录，父仓库忽略整个目录，避免误提交 Git 链接或缓存；重建不依赖旧电脑上的该目录。

在全新克隆中使用 Node.js 22：

```bash
git clone https://github.com/qife422/ai-review-console.git
cd ai-review-console
npm --prefix frontend ci
npm --prefix frontend run lint
npm --prefix frontend run test -- --run
node frontend/scripts/build-public-demo.mjs
python3 -m http.server 4176 --bind 127.0.0.1 --directory online-demo/out
```

访问 `http://127.0.0.1:4176/`。构建脚本显式启用 `VITE_PUBLIC_DEMO=true`，输出到 `online-demo/out/`，暂存于 `.compile/`；普通 `npm run build` 不启用演示模式。构建为可再生产物，不保证不同工具链下字节哈希一致。

重复构建遇到已存在的 `.compile/` 或 `out/` 会停止，避免自动覆盖。后续更新需先盘点并选择明确的构建目标；不自动删除旧产物。单个静态包上限 25 MiB / 500 文件，且不超过前端源码、锁文件及许可证总字节的 20 倍；预览与 QA 临时产物合计上限 100 MiB。任一阈值触发时停止增长并盘点。

## 更新同一线上站点

使用上面的既有 Sites 项目继续更新，勿重复创建站点。恢复托管配置时，在对应 Sites 源码检出根目录的 `.openai/hosting.json` 保存：

```json
{
  "project_id": "appgprj_6ae26ac1f3888191b1ac30ce560137e7",
  "static": { "directory": "out" }
}
```

先检查源码差异、运行相称测试、构建并在浏览器验证最终静态包，再将静态目录、配置和许可证同步到既有 Sites 项目，保存新版本并部署。以原生部署结果中的 `succeeded` 和返回 URL 为准，再更新本页与 CHANGELOG。无需部署父项目的 FastAPI、数据库或 Langflow，也不要打包 `.env`、SQLite、Docker 卷或业务文件。

本地通过的验证：前端 5 文件 / 28 项测试、TypeScript；最终静态包在浏览器完成载入预置样本、等待模拟评分、记录要求修改、JSON/HTML 下载及内容哈希核对；重置恢复四个初始案件，390px 手机浅/深色无横向溢出。该操作过程未发出 fetch/XHR 业务请求。线上发布由 Sites 原生成功结果确认，不宣称完成原系统的整栈、故障恢复或生产验收。
