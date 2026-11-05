# 候选 ARM 验证

日期：2026-11-04（America/Los_Angeles）。沿用 `ARC-UPGRADE@0.1.0` / WP-05 / AD-03；用户确认上一轮自查、GitHub上传后允许进入下一步，本轮先补Linux ARM64独立锁及真实后端回归。默认Langflow **1.11.6**、原SQLite和历史卷不变，没有后端发布、历史清理或默认切换。

本文为本轮候选说明，正式证据只由最终manifest明确选入的精确字节取得资格。完整v0.2验收仍未通过。

## 独立锁与架构选择

[ARM锁CI41978766690](https://github.com/qife422/ai-review-console/actions/runs/41978766690)，source `38edc84d99ed583882e91c1ba57c1fcd7c8fc4dd`，在原生ARM runner的Linux/aarch64、CPython3.12.16实际完成4个工具及完整334包的新环境哈希安装，pip check通过。包名和版本与前轮AMD基线完全一致；未降级、忽略依赖或替换第三方metadata。实际安装receipt、固定archive来源/SHA及GitHub artifact digest验证见`ci/lock/`。

ARM运行锁SHA `1d83205f67800760e0e1e2542bfec26071af9d5c0f37a8ab89a9da1c0e1a0028`，保存在`compliance/langflow-candidate-arm64.lock`；4工具另存`langflow-candidate-build-tools-arm64.lock`。原AMD两个锁名称和字节保留。334项中59个所选档案SHA不同：58个文件名为aarch64 wheel，magika1.0.3由AMD wheel改选py3-none-any；其余275档案SHA相同。此为解析元数据比较，不代表读取了59个native二进制，也不宣称wheel字节复现。4个sdist仍锁源档案，构建工具固定且禁用build isolation。

候选Dockerfile按BuildKit TARGETARCH显式选择各自两个锁，pip前核实实际Python machine；未知/缺失架构失败，不猜测架构。常规CI保留默认AMD/ARM及候选AMD，增加候选ARM，Debian12走主扫描/许可证采集，RHEL专用步骤明确not_applicable。各lane为独立GitHub托管VM/daemon，项目名依赖该环境隔离前提；不宣称同daemon同时运行同arch的两个lane。

## 实际运行结果

[完整CI41979142562](https://github.com/qife422/ai-review-console/actions/runs/41979142562)，source `e6f6fe7b908b7fab1b4f85e9f5a4fa22890fc923`，5任务全部success：271 Python（0失败/错误/跳过）、29前端，默认1.11.6及候选1.13.1各AMD64/ARM64。两个候选均真实完成5组件/2Flow、四格式、三决定、九报告及负向失败/重试去重。实际ARM LF image `sha256:a5939d54d52e42c88138c81d2059386fd31b3c1f66b7373358b35374b6b9627d`；AMD LF image `sha256:26a433f984fcb8da102faf0a77daa668c4ccfdc3a7177ac17ff961925547d27f`。各自334包名称/版本集合missing/extra/changed均为空，来源见ci/runtime/selection.json。

ARM只验证后端/API/Flow/报告，浏览器步骤明确跳过；AMD继续执行ARC业务界面的键盘与报告下载回归。这里没有Mac宿主或Langflow管理编辑器验收。前轮AMD隔离检查点升级/回滚仍仅绑定[原source/run/image](../langflow-transition/README.md)，不继承成ARM迁移、故障或性能通过。

两候选实际镜像各443库存行，334Python+109Debian；各52binary/132 provider记录；132仅为LF image，各候选profile四服务provider并集为157，不与默认RHEL profile计数混用。主扫描exit1保留、RHEL补扫not_applicable，mapping/query/detail unknown0。ARM的全部匹配均为Debian，PyPI包级匹配0；133→132的APT补丁解释仍引用前轮精确范围，不把架构间相同计数当作全部风险等同。ARM实际APT/libapt均2.6.2；三份Langflow MIT/sqlite-vec MIT+Apache补充副本在两个候选image均recorded、大小/raw SHA/文本SHA与仓库一致，legal_approval=false。完整native/source对应及默认/API的Zep/vendor/FIPS材料仍open。

`prior-materials`持续记录当前image native正文未采集，引用旧材料不跨image变成新证据。共享native累计135,836,345B，余6files/26,795,216B输入/3,969,945B文本，旧101/100偏差保留；本轮target native新增读取0。通用metadata/通知及系统库存另有限额，不替代native/source对应材料。

## 自查、来源与产物

上一轮e1d8a02的本地/远端main一致，88payload逐size/SHA核对通过。默认Dockerfile（52inline pins）、原AMD两锁、原SQLite和固定Spec/baseline继续保留，具体新复核见environment记录；旧六个封存包不覆写。本轮只是隔离新数据库和虚构输入，不挂载原库/历史卷。

新temp `/private/tmp/arc-langflow-arm.tlmz8anp` 限1MiB，旧三temp加新总40MiB；CI选择600KiB/40files，source64KiB/4files，候选/正式各100MiB/1000files，超过1GiB且源码100倍停止增长。ZIP仅内存校验GitHub size/digest，原pip报告、sdist/wheel档案、安装树与完整构建输出不落入正式证据；不删除、迁移或压缩历史目录。本地不start/build/pull/prune Docker，旧容量warning继续保留。

成功/失败、原件/派生项各按selection标识，原始大报告只保留来源路径/大小/SHA时不会称其全文已封存。主机和runner容量、源码指纹及实际范围见environment与manifest；状态/索引仅在正式路径创建并校验后更新。

## 剩余与后续

1. 补Mac宿主实际运行、Langflow管理编辑器、候选故障恢复及性能；ARM旧schema迁移与升级后写入恢复需另有实际证据。
2. 继续处理供应商仍开放的Debian记录、SQLite/系统native对应源码和完整分发通知；默认/API的Zep精确许可、vendor/FIPS材料独立保留，不由候选未安装这些集成关闭。
3. 完整发布条件、技术验收与负责人AD-03决定后才切换默认；之后沿WP-08做版本历史、修改后再审、队列与失败诊断。LLM/OCR、真实身份/数据、生产部署继续独立选择。

AC-19未通过、完整last_verified=null、最终接受pending、残余风险未接受、后端分发未批准。本轮沿用既有spec-development验证规范，不新建Spec；没有UI实现，未加载设计skill。Sol实施锁工具，Terra负责受限CI适配，root集成及交叉核查；实际模型tokens/账单不可取得，估算不当作实际用量。
