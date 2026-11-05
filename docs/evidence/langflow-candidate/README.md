# 精简 Langflow 候选隔离验证

日期：2026-11-04（America/Los_Angeles）。沿用 `ARC-UPGRADE@0.1.0` / WP-05 / AD-03。结论：**固定1.13.1精简候选可运行，核心回归与管理界面登录通过；尚不替换默认1.11.6，也不代表完整发布验收或后端分发获批。**

## 候选与实际结果

实际代码 `e73ab92321483403fafd03e721182c5426ae6359`，完整[候选CI 41943564415](https://github.com/qife422/ai-review-console/actions/runs/41943564415) completed/success；实际LF image `sha256:bab518885b0099096f7843c3016227644246f3f165e74fbd040f373a4ec8bffb`。候选为 `langflow-base==1.13.1`，上游硬依赖 `lfx[sqlite]==1.13.1`；未安装顶层langflow，也未选择complete/bundles/zep/postgresql等可选集成。sqlite是上游硬extra，不能称完全无extras或无native。固定Python3.12.16/bookworm base，APT安装libpq5，显式 `postgresql+psycopg://`，Psycopg3.3.5运行实现为python、报告libpq版本150019。正常运行版本与构建输入共同支持该路径，尚未独立核对所有已加载ELF路径/source对应。

| 验证 | 实际结果 |
|---|---|
| Python / PostgreSQL单元回归 | 198 passed，0失败/错误/跳过；1个上游弃用warning |
| 前端 | 29 tests通过，lint/build通过 |
| 可信组件及真实Flow | 5组件、2Flow；4格式、3决定、9次报告下载通过；共享Flow前后hash不变 |
| 负向用例 | 缺虚构标识仍failed/unscored；同case/version的一次手动重试去重通过，不声称成功恢复 |
| API鉴权与版本 | 匿名Flow访问403、登录token非空但未落盘；实际OpenAPI版本严格1.13.1 |
| Langflow管理GUI | 新会话真实填写登录表单，两条已发布Flow可见；10次CLI命令；未检查编辑器修改 |
| 依赖一致性 | 实际334个Python distributions，pip check通过；不拿它与777条RPM+Python混合库存比较百分比 |
| 包级扫描 | 334 Python+109 Debian=443行；PyPI匹配0，Debian52 binary/28 source包有133 provider IDs；原exit1保留，mapping/query/detail unknown均0 |

### 原依赖约束的关闭范围

| 原默认运行时问题 | 候选实际状态 | 结论 |
|---|---|---|
| Pillow12.3.0 / <13 | 13.0.0 / 上游>=13,<14 | 候选已升级且当次PyPI匹配0 |
| filelock3.32.0 / <4 | 4.2.1 / 上游>=4.2.1,<5 | 候选已升级且当次PyPI匹配0 |
| setuptools83.0.0 / <84 | 84.1.0 / 上游>=84.1,<85 | 候选已升级且当次PyPI匹配0 |
| chromadb1.5.9、couchbase4.6.2 | 安装清单均不存在 | 通过精简移除，未修改其上游代码 |

55条候选constraints来自原52条：PyJWT改为2.15.1、transformers改为5.10.1以满足新上游floor，再增加上述3项显式边界。constraints不会强制安装所有旧集成，未使用 `--no-deps` 或编辑上游metadata。默认镜像原52pins保持。11-02候选快照是历史输入；11-04官方精确1.13.1元数据已放开三项边界，原响应/URL/时间/SHA与pyproject见`sources/`。

扫描只证明指定包名/版本的在线查询；133 IDs不是133个独立或可利用漏洞，unknown severity不等于低风险。原始默认1.11.6 RHEL补扫0与新Debian133来自不同发行版和清单，不能直接做风险升降结论，也没有据此接受残余风险。另对未安装的顶层 `langflow1.13.1` 做一次官方family补充查询，返回{}/0 IDs；不将其冒充安装包、不据此覆盖全部alias、静态/内嵌代码或可利用性。

## Zep与原生许可证

安装清单未检出zep-python/zep-cloud、ibm-db、lfx-ibm、psycopg-binary、psycopg2-binary；已知site-packages/clidriver路径不存在。这只限分发元数据与指定路径，不是全文件系统不存在证明。候选仍包含IBM SDK：ibm_watsonx_ai1.9.0声明BSD-3-Clause、langchain-ibm1.1.2声明MIT；不能说已移除所有IBM包或统一称Apache。API旧Psycopg binary与历史ARM/FIPS材料未由此关闭。

| 材料 | 已取得与限制 |
|---|---|
| APSW3.53.4.0 | 实读dist-info/licenses/LICENSE 1,166B，SHA `b85a7dc6463f286c14a638070a14f4888564ac7245dc99a17950ec24cf1a7b9d`，与精确上游同SHA；关闭该own-text缺失，未证明内嵌SQLite版本/选项/source完整对应 |
| langflow-base / LFX1.13.1 | 本轮base未采到符合白名单的声明specimen，LFX通用collector owntext无记录；取得精确v1.13.1上游MIT。repo副本只多末尾空行，不能称全raw同SHA；构建COPY输入可核，未保留同image project_files独立读回字段 |
| sqlite-vec0.1.9 | 本轮未采到符合白名单的声明specimen；同tag MIT原文及Apache2原文指纹/URL已识别，不声称已把全部许可放进wheel或选择了许可选项 |
| Psycopg3.3.5 | LGPL-3.0-only metadata及实际LICENSE.txt已选存；纯Python路径不自动免除LGPL、系统libpq及其他系统/native义务 |
| 全后端 | SQLite及其他native对应源码、完整通知/源代码提供方式、上游前端嵌入依赖的许可完整性仍需核对；没有完整二进制分发批准 |

本次许可范围复核见`environment/candidate-license-final-review.json`，真实native小原件与generic报告的显式派生子集见`ci/candidate/final/`。没有把未选771,011B generic原报告冒称保留。

### 输入额度真实对账

此前global已知135,779,466B/余8files；本轮默认CI又实际读取相同English55,713B，旧raw仍按固定9→8起算。`ci/default-baseline/native-budget-reconciliation.json`保留此差别：按真实新增读取对账为7files/26,796,382B输入/3,971,111B文本、已知135,835,179B。本候选仅再读APSW1file/1,166B，故现在全批新14files/40,313,648B，加旧95,522,697B=**135,836,345B**；剩**6files/26,795,216B输入/3,969,945B文本**。旧101/100路径偏差仍保留，未重置。

新许可证采集输入默认false，仅此轮显式true；不读binary，scope中限定正文白名单及每包最多2件/全6件256KiB。后续若仅修GUI不得重复true或按最大6件误记实际读取。常规旧CI的固定baseline口径与人工累计账本分开；未来新增target读取前必须再对账，不能把raw旧值当剩余授权。

## 过程与相称验证

1. 首试`32eb636` / CI41940818042：候选build成功，初始化的Compose run误用不支持的--no-build而停止；不是候选API不兼容证明。失败尾部16KiB及其完整decoded-log SHA/byte-span保留。
2. `621a082` / CI41941734467：修3条run命令，显式Psycopg3 URL；全业务与API过关，GUI因真实标签Username */Password *未被正则匹配而失败，尚未扫描。
3. `e73ab92` / CI41943564415：按实际snapshot修正必填星号，GUI成功；扫描与许可在identity成功后独立采集。补4个有用的许可读取边界测试，默认关闭/字节指纹/符号链接逃逸/超限预读均通过。

默认基线另在`32eb636` / [CI41940799240](https://github.com/qife422/ai-review-console/actions/runs/41940799240)实际通过194 Python/29前端、AMD完整业务/ARC浏览器及Linux ARM后端；新快照API127、LF5包81、Web0、PostgreSQL131、provider并集237，RHEL补扫0，主227RPM unknown/exit2原记录保留。这些与11-03历史236并集不混用。

实验修复仅触及候选workflow/override/probe及其测试，使用显式manual CI运行完整对应验证；`[skip ci]`避免重复未变的默认runtime/native采集，不冒称默认新revision已重跑，也未改ci.yml或降低扫描查询。之后纯说明/封存提交同样不把skip当pass，文档COPY/metadata影响另有记录。

## 保护、容量、复查方法

原SQLite、固定Spec/baseline及四个旧正式包全部payload逐文件核对；主docker/langflow.Dockerfile和52pins原字节保持。新runner只用新数据库/虚构输入，没有挂载原库卷、做升级迁移或恢复原业务数据；默认/公开静态沙盒未切换。本地仅调用Compose help/config，没有start/build/pull/prune；旧容量warning保留，不宣称旧Docker现状重新盘点通过。

新named temp上限3MiB，连此前runtime-maintenance temp合计40MiB；new CI选材合计1MiB/50files，source12files/256KiB，候选/正式各100MiB/1000files，源码放大>1GiB且100倍停。实际CI40files/416,324B；私有ZIP仅内存校验，未落盘，pytest scratch/CLIcache/完整未选报告不入证据。候选runner入口20GiB、各阶段5GiB门禁，build600s；不是宣称原collector的6GiB门禁在此新workflow也自动生效。

正式包保留`ci/candidate/second/inventory.json`作为第三轮全48,631B逐字同SHA的唯一引用原件，不能删掉此闭包；新JUnit只选真实计数/原字节SHA，未选原XML就不称原XML已封存。外层manifest只认可明确选中固定字节。恢复原数据、迁移、清理、压缩、整体树备份和后端发布均无本轮授权。

## 后续顺序与结束条件

1. 将候选完整resolved graph/来源哈希固化，逐项分类133 Debian记录的供应商修复状态与适用性；有受支持补丁才做针对性升级，不跨发行版盲清零。补齐LFX/base/sqlitevec的许可通知副本回读、SQLite/系统native对应source与提供方式。继续对账剩6files额度，避免重复取得同一原文。
2. 主collect_release_ci仍绑定RHEL系统事务/补扫和旧native continuation，不能直接把Debian候选Dockerfile换成默认；先按新发行版调整采集器并通过正常CI，不弱化扫描/unknown/许可来源门槛。按AD-03形成默认1.11.6→1.13.1明确候选delta，补Linux ARM/Mac宿主范围、管理编辑器、旧schema隔离迁移/回滚、故障恢复及性能。全部保护原库卷；这些没有被本次fresh-db成功替代。
3. 发布条件、完整技术验收和负责人最终决定后才替换默认；之后沿WP-08做版本历史/修改后再审、队列效率、失败诊断与受控恢复。LLM/OCR/真实权限及生产部署继续独立阶段。

本轮有限隔离实验已完成，项目WP-05仍implementing，AC-19/not_passed、完整last_verified=null、最终接受pending。主skill spec-development；辅助playwright只做真实CLI浏览器验收；无页面设计改动，未叠加近似设计或安全审查skill。
