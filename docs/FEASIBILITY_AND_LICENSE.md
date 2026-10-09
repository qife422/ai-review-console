# AI Review Console：技术可行性与上游许可证检查

检查日期：2026-09-01（Asia/Shanghai）

## 结论

项目可行，建议采用“专业业务界面 + 独立审查 API + Langflow 工作流运行时”的组合架构，而不是直接修改 Langflow 上游前端。

Langflow 负责可视化编排和执行受信任的自定义组件；独立业务 API 负责案件状态、人工审批、审计日志和报告元数据；Web 仪表盘负责面向审查人员的日常操作。这样既能明确证明产品基于 Langflow，也能避免把长期人工审批硬塞进一次同步的 Flow 运行。

许可证初检通过：Langflow 1.11.6 的源码和 Python 包元数据均声明 MIT License，允许使用、修改、分发、再许可和商业使用。分发时必须保留上游版权声明和 MIT 许可文本。完整镜像和全部传递依赖的许可证审计，要在依赖锁文件与最终镜像生成后作为发布门禁执行；本文件不构成法律意见。

## 已核验的上游事实

| 项目 | 结果 | 证据 |
|---|---|---|
| 上游项目 | `langflow-ai/langflow` | <https://github.com/langflow-ai/langflow> |
| 选定基线 | `v1.11.6`，发布于 2026-09-01 | <https://github.com/langflow-ai/langflow/releases/tag/v1.11.6> |
| 源码许可证 | MIT | <https://github.com/langflow-ai/langflow/blob/v1.11.6/LICENSE> |
| Python 包许可证表达式 | MIT | <https://pypi.org/project/langflow/1.11.6/> |
| Python 范围 | `>=3.10,<3.15` | 上游 `v1.11.6` `pyproject.toml` 与 PyPI 元数据 |
| 自定义组件 | 支持 `Component` 子类、声明式输入输出和 `LANGFLOW_COMPONENTS_PATH` | <https://docs.langflow.org/components-custom-components> |
| Docker | 官方镜像支持挂载自定义组件、持久化数据库和加载 Flow | <https://docs.langflow.org/deployment-docker> |
| Flow 导入/导出 | UI 与 API 均支持 JSON/ZIP 导入导出 | <https://docs.langflow.org/concepts-flows-import> |
| API | 支持 Flow 运行、文件、Flow 管理与 API Key 鉴权 | <https://docs.langflow.org/api-reference-api-examples> |

核验时，`v1.11.6` 的 `LICENSE` 文件 SHA-256 为：

```text
48d4a7496209a9e1f2f549384251b69319360c3a38127cf513473590be383359
```

## MIT 许可证的项目义务

- 可以在内部、开源或商业场景中使用 Langflow，并可修改或分发。
- 如果项目分发 Langflow 源码、其重要部分或包含它的制品，应随制品保留 Langflow 的版权声明与 MIT 许可文本。
- MIT License 不提供任何担保；项目 README 和发布材料不得暗示 Langflow 上游为本项目的审查结论背书。
- MIT 文本没有授予商标权。产品只使用“基于 Langflow / Built on Langflow”作事实性来源说明，不把 Langflow 名称或 Logo 当作本产品品牌，也不暗示官方合作关系。

计划中的合规产物：

- 根目录项目许可证；
- `THIRD_PARTY_NOTICES.md`；
- `licenses/Langflow-LICENSE.txt`；
- 最终容器镜像 SBOM（SPDX 或 CycloneDX）；
- Python、Node 和镜像依赖许可证报告；
- 对未知许可证、AGPL、SSPL、BUSL/BSL 及其他限制性条款的阻断或人工复核记录。

当前合规状态：

- **Langflow 直接上游：通过，有保留通知义务。**
- **项目自研代码许可证：已选择 Apache-2.0，根目录保留完整文本。**
- **应用传递依赖：已锁定 Python/Node 依赖并生成 CycloneDX SBOM；当次 `pip-audit` 与 `npm audit --omit=dev` 未发现已知漏洞。**
- **容器基础层：镜像构建可重现，仍需在每次正式发布时使用最新数据库重新扫描。**
- **法律意见：未提供；正式对外商用前应由有权限的法务人员复核。**

## 功能可行性判断

### 1. 文档解析：可行

自定义 Langflow 组件可以接收文件路径或结构化数据，并输出 Langflow `Data`。首版支持 PDF、DOCX、TXT、Markdown；使用许可证宽松的解析库，限制文件大小、页数、扩展名与 MIME 类型。扫描 PDF/OCR 暂列为可选增强，避免首版引入大模型、原生运行时和额外模型许可证。

输出统一为：文档元数据、分页/段落文本、内容哈希、解析警告和可追溯的文本位置。

### 2. 脱敏：可行

首版采用确定性规则，对虚构的姓名、邮箱、电话、证件号、银行账号和地址进行识别与替换。组件同时输出脱敏文本、命中类型、位置和稳定占位符；默认不把原文与脱敏映射写入日志。

NER 或外部模型只作为可插拔增强，不进入离线演示的必需路径。这样测试可重复，也不会要求真实凭据或上传文档到第三方服务。

### 3. 风险评分：可行

采用透明的规则矩阵计算 0–100 分，并输出每条发现、权重、证据位置、解释和建议动作。评分维度拟定为隐私、法律条款、财务、信息安全和内部政策。演示默认使用确定性评分器；可选 LLM 只能补充摘要和建议，不能覆盖规则分数或自动做最终审批决定。

### 4. 人工审批：可行，但需异步分段

人工审批不能通过让一次 Langflow HTTP 请求长时间阻塞来实现。正确模型是：

1. Intake Flow 解析、脱敏、评分，并通过受信任组件创建 `PENDING_APPROVAL` 审查任务；
2. Flow 正常结束，仪表盘展示待办；
3. 审批人在业务 API 中批准、驳回或要求修改；
4. 决策事件触发 Decision/Export Flow，生成最终报告。

审批状态、操作者、理由和时间戳由业务数据库保存，Langflow 数据库不作为业务审计记录的唯一来源。

### 5. 报告导出：可行

自定义组件可把审查记录转换为 JSON、HTML 和 PDF。报告包含文档指纹、规则版本、发现、风险分数、审批决定、审计时间线和“仅含虚构演示数据”声明。PDF 首版采用确定性模板，保证测试稳定；导出文件登记哈希以便校验。

### 6. 专业仪表盘：可行

独立前端通过业务 API 访问案件、指标和审批动作，通过后端服务调用 Langflow API。核心页面包括总览、审查队列、案件详情、规则/Flow 版本、报告中心和系统状态。用户不需要进入 Langflow IDE 完成日常审批；管理员仍可在受限网络中使用 Langflow 查看和编辑 Flow。

## 关键技术与安全边界

Langflow 官方明确说明：它是能执行任意开发者 Python 代码的 IDE/运行平台，不提供同一进程内的多租户隔离。自定义组件编辑器也能执行代码。因此本项目的可行性附带以下强制条件：

- Langflow 只运行仓库中受信任、经过测试的组件；生产环境设置 `LANGFLOW_ALLOW_CUSTOM_COMPONENTS=false`，但仍通过 `LANGFLOW_COMPONENTS_PATH` 加载随镜像发布的可信组件。
- 同时设置 `LANGFLOW_CUSTOM_COMPONENT_ADMIN_ONLY=true`；此功能不能替代容器和网络隔离。
- `LANGFLOW_AUTO_LOGIN=false`、`LANGFLOW_ENABLE_SIGNUP=false`、`LANGFLOW_WEBHOOK_AUTH_ENABLE=true`，并显式提供强随机 `LANGFLOW_SECRET_KEY` 与管理员密码。
- Langflow 端口不直接暴露到公网；只有后端服务和受控管理员网络可访问。
- Web 仪表盘不能把 Langflow 超级用户 API Key 下发给浏览器。
- Langflow、自定义组件和解析器运行在非 root 容器中，收紧文件系统、挂载点、资源上限和出站网络。
- 上传文件先做扩展名、MIME、大小、页数、压缩炸弹和路径处理检查；原始文件与报告使用独立存储路径。
- 日志中禁止写入原始全文、脱敏映射、密码或 API Key。
- 审批与审计依赖应用层鉴权和不可追加修改的事件记录，不依赖 Langflow 的 Flow 可见性作为安全控制。

官方安全说明：<https://docs.langflow.org/security>；自定义组件限制：<https://docs.langflow.org/deployment-block-custom-components>；鉴权建议：<https://docs.langflow.org/api-keys-and-authentication>。

截至检查时，GitHub 已公开多项 Langflow 历史高危/严重漏洞。选定的 `1.11.6` 不落入当时已发布公告列出的受影响版本范围，但这不是“无漏洞”保证。构建与发布必须固定版本和镜像摘要，并执行漏洞扫描；禁止使用浮动的 `latest` 标签。上游公告入口：<https://github.com/langflow-ai/langflow/security>。

## 数据与保密声明

项目只包含虚构数据，不接触、推断或复刻任何真实公司的机密内容：

- 演示组织使用明确虚构名称，例如 `Northstar Example Labs`；
- 邮箱只使用 `example.com`、`example.org` 或 `example.net`；
- 人名、编号、地址、合同和金额均由固定种子生成并标注 `SYNTHETIC`；
- 不提交真实 API Key、访问令牌、客户数据、内部域名、真实合同模板或生产配置；
- README、仪表盘页脚和报告页脚都显示“Demo uses synthetic data only / 演示仅使用虚构数据”；
- CI 增加 secret scan、fixture policy 检查和导出物内容检查。

## 主要风险与缓解

| 风险 | 影响 | 缓解 |
|---|---|---|
| Langflow 可执行任意代码 | 主机或网络资源可能被访问 | 可信组件白名单、不可变镜像、隔离网络、非 root、限制出站 |
| 人工审批被错误建模为同步阻塞 | 超时、重复执行、状态不一致 | 两段式 Flow + 持久化状态机 + 幂等事件 |
| PDF/DOCX 解析不稳定 | 文本错位、评分证据不可追溯 | 限定格式、解析警告、位置映射、恶意样本测试 |
| 规则评分被误认为法律结论 | 误判或过度依赖 | 明确“辅助决策”，保留解释、规则版本和人工决定 |
| 脱敏映射泄漏 | 重新识别风险 | 映射不入普通日志、最小保留、访问控制、测试日志 |
| 上游快速更新或安全公告 | 构建漂移与漏洞暴露 | 固定 `1.11.6` + digest、周期性更新、SBOM、Trivy/pip-audit |
| 依赖许可证遗漏 | 分发合规风险 | 锁文件后生成清单，未知或限制性许可证阻断发布 |

## Go / No-Go

**Go：可以进入开发。** 前提是接受以下边界：首版是单组织、受信任操作员的演示/参考实现；只使用虚构数据；Langflow 不直接暴露给不受信任终端用户；最终发布前必须完成锁定依赖后的许可证和漏洞扫描。
