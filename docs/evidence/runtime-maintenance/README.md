# v0.2 系统维护与运行时评估

主体系统/依赖验证日期：2026-11-02；定向许可修复与收尾同步：2026-11-03（America/Los_Angeles）。沿用 `ARC-UPGRADE@0.1.0` / WP-05。固定 Spec、原库、历史卷和三个旧封存包保持原字节；本轮没有部署真实后端或更新公开静态沙盒。

本轮有限切片已完成：在固定Langflow1.11.6上实施系统维护、修复Web libexpat并完成双架构回归；评估候选版本及补齐精确许可证材料。**v0.2完整发布验收仍未通过**：AC-19、Zep/native/完整后端分发条件和残余扫描记录保留open；没有接受残余风险。

| 功能检查点 | 实际结果 |
|---|---|
| `2e45bee` / CI41586599463 | 188 Python/29前端；系统维护修复后首次双架构成功 |
| `1858480` / CI41588865769 | 191 Python/29前端；Web libexpat2.10.0修复、定向notices补采成功 |
| `adb93c4` / [CI41760412382](https://github.com/qife422/ai-review-console/actions/runs/41760412382) | 191 Python/29前端；AMD完整工作流/浏览器、Linux ARM后端全部成功，精确English协议补采成功 |

最后两个检查点分别执行于11-02与11-03，扫描数据按各自查询快照理解；测试绿色不等于零漏洞或完整后端可分发。

## 版本候选与实际选择

| 候选 | 当前 Python 3.14 分支的约束 | 本轮结论 |
|---|---|---|
| 稳定 1.13.0 | Pillow >=12.3,<13；filelock >=3.20.1,<4；setuptools >=83,<84 | 三项上限仍在 |
| RC 1.13.1rc2 | filelock >=4.2.1,<5；Pillow/setuptools 上限仍在 | 只能解除 filelock；属于预发布 |
| 开发 1.14.0.dev14 | Python >=3.11,<3.16；同样仅放开 filelock | 不能据开发版名称判定三项已解 |

候选快照采集于2026-11-02，不代表未来最新版本。这些来自官方精确版本的 langflow/base/lfx 元数据，URL、采集时间、package/version identity、Requires-Dist、Requires-Python 和原始响应 SHA 均保留在 `python/`。仅保存有关派生字段，未把缺失的 raw body 伪造为原始响应；一次 HTML challenge 的失败也保留。这里没有运行候选的安装解析、真实镜像或迁移，因此不标“候选兼容通过”。

当前继续固定 Langflow 1.11.6、原 base digest 和 52 个显式 Python pins。更换固定运行时需按 Spec AD-03 先提出具体候选和重测范围。1.13 元数据中的 bundles/extras 拆分提供未来不含 Zep 的评估路径，但直接在旧胖镜像上 pip 升级不会卸载所有历史集成；官方 Docker 实际 extras 和最小 base 能否保留管理 UI/API 仍需验证。IBM provider 也不能据 bundles 变化视作移除。

## 系统补丁、信任与回归

Python3.12.16/bookworm、nginx1.30.6/alpine、PostgreSQL16.15/trixie 的维护 tag/digest 与此次官方镜像元数据相同，没有进行无依据的 tag 轮换或跨发行版迁移。Web 先前扫描0不是未来永久保证；Debian no-DSA/postponed 记录不靠一次 apt 命令宣布关闭。

在固定 Langflow 镜像新增公共 UBI10 系统补丁层。构建前只接受已启用的 UBI BaseOS/AppStream、官方 HTTPS CDN、Red Hat 本地 key、TLS 和 RPM GPG 校验；所有其他 repo 在每次命令显式禁用。先刷新元数据再更新，镜像中保留前后 RPM NEVRA/架构/签名头、repo/key 指纹、事务原文及 manifest。原始供应商 RPM 许可/源码材料仍按精确制品理解；签名成功并不等于全部分发义务完成。

首源码 `bb34edb` 的 CI `41586088930`：185 Python / 29 前端通过，但 microdnf 首次 repolist 因不支持 global gpgcheck setopt 失败，业务回归未执行。对照官方 microdnf3.10.1 原字节，错误文本的47字节及 SHA 与 CI 记录完全匹配。修复为官方支持的 `repo_id.gpgcheck=1` / `repo_id.sslverify=1`，保留同等强制校验，并在以后失败时输出有界 stderr；没有放宽验收或盲重跑。标准化换行的临时 C 副本不入包，选择 git blob 完全匹配的 `.original.c`。

最后实际CI再次测得：两架构从226条RPM记录变为227条（软件223→224，均另含3个公钥），60个既有软件EVR变化、新增perl-Unicode-Normalize、无移除。glibc变为2.39-145.el10_2，openssl-libs变为3.5.8-2.el10_2，expat为2.7.3-1.el10_2.7，Python3.14为3.14.8-1.el10_2。前后输入、签名头和事务原件按11-02详细包保留，11-03新计算及输入指纹在`ci/native-close/selection.json`；不能把派生选择字段冒称保存了第四轮全部原件。

两架构RHEL补扫：224软件包及3公钥，provider IDs/匹配/映射、查询、详情unknown均0。主扫描原exit2和227个RPM unknown保留；在同一exact LF image ID上核对默认RPM集合、系统post-update fullEVR及补扫集合，清单内合并unknown0。该覆盖不包含全部文件系统、静态或内嵌二进制，也不是可利用性证明。

Web在两架构均安装libexpat2.10.0-r0，11-02原先2.9.0-r0的4个Alpine provider IDs不再匹配，最后11-03扫描仍为0。API126个Debian IDs、PostgreSQL130个Debian IDs；LF仍有5个Python包/81 IDs/59 alias组（Pillow12.3.0、filelock3.32.0、chromadb1.5.9、setuptools83.0.0、couchbase4.6.2），全镜像provider ID并集236。IDs/alias组不是独立CVE或可利用漏洞数量；旧114/116/23RHSA是历史快照，不能据跨日差值声称修复数量。

最后191 Python测试0失败/错误/跳过，29前端测试通过；两个runtime的52pins、pip check及离线兼容探针通过。两架构实际运行5组件、两Flow、4格式、3决定、9次报告下载。失败重试属于预期仍失败的负向用例：同case/version、一次手动重试代次去重，并未证明成功案件的故障恢复。AMD浏览器CLI结果passed；未选本轮新PNG，人工视觉检查仍明确属于前一2e45来源的4张图。ARM明确未执行浏览器和第二份定向native。旧全故障、隔离恢复及性能没有在新系统补丁下完整重跑。

## 许可证材料进展与未关闭项

精确 recipe 已绑定 immutable commit：API 的 `psycopg-binary 3.3.5` 对应 Psycopg3 构建输入 PG18.6/OpenSSL3.5.8，并有 socketdir/GSS 两项补丁来源；LF 旧样本的 libpq17.9/OpenSSL3.5.6 属于 **psycopg2-binary2.9.12**，其自身精确配方与版本输入匹配。Psycopg3.3.4 配方不能跨 owner 用来声称同一个 wheel 存在构建矛盾。版本与 recipe 吻合是材料补充，仍不单独证明完整 source/binary 对应、FIPS 厂商 NVR 或缓存来源。

首次AMD实采10文件/40,177,611B，包括ibm_db3.2.9实际driver、V11.5REDIST、SWID及相关owner字段；SWID记录产品11.5.0，不能从setup默认值认定实际二进制fixpack。第三轮新增notices23,445B，记录LI L-XHUG-BAFKQ7和第三方声明；该notices标识与最后英文LI标识不同用途，不把它当作现行完整协议ID；同轮仅在批准的两处psycopg native目录列名，均未见libcrypto.so.1.*，这一观察仅限该AMD镜像和目录，不消除旧ARM的FIPS/source问题。

最后将英文选择器纠正为实际`license/UNIX/odbc_LI_en`，唯一新增读取55,713B，SHA-256 `0e83c4ba0bc0da1a24fd6a828002575acf4933e48f43cb5569ad02436ff5fb6e`。正文标明IBM Data Server Driver v11.5.9、LI L-ASUX-ZXSTFM并附IPLA；可以关闭英文协议漏选/缺失，协议标识不等于对libdb2二进制fixpack的独立测定。正文列出随增值应用的object-code分发范围、仅支持该应用、版权/notices保留、营销商标授权和终端协议等条件，仍需逐项核对履行；取得文本不代替负责人接受，也不自动证明完整镜像满足REDIST清单。

全批额度未重置：本轮共12文件/40,256,769B；加此前95,522,697B，已知累计135,779,466B，剩8文件/26,852,095B输入/4,026,824B文本。本次没有重读40MB driver、notices或METADATA/RECORD，不读任何entitlement .lic，不执行native代码。固定基线保留第三轮manifest及嵌套前轮原文/SHA链；最后真实材料与producer指纹见`ci/native-close/amd64/release/native/`。

Zep2.0.2 精确许可、FIPS/部分 native 对应源码、IBM driver 全量 redistributable 文件合规及完整后端分发条件均不能由源码链接、包字段或 CI 绿色自动关闭。本项目当前公开的是源码和虚构数据静态沙盒，没有发布完整后端镜像，也没有接受剩余风险。

## 保护、容量和证据范围

本地 Docker socket 当前不可连接，不能据旧盘点宣称当前 layers/容器数量已验证；原容量 warning 继续保留。没有启动本地 Docker、build/pull、prune、历史缓存清理或迁移。宿主可用空间、原始输入指纹见 `capacity/` / `environment/`。

两种 CI profile 各自记录架构与 df，12GiB 以下在安装/构建前停止；后续 collector 仍有6GiB入口与5GiB运行余量门禁。AMD 执行完整业务、浏览器及本轮定向 native 材料；Linux ARM 执行后端/Flow/系统扫描，明确不运行 Chrome/UI 和第二次 targeted native。Linux ARM 云证据不代表 Mac 宿主已验证。

本轮定向 native 全批20文件/64MiB输入、4MiB文本；此前101路径/95,522,697B的偏差保留，本轮没有重新完整遍历 native 树或抹掉旧偏差。候选/正式各100MiB/1,000文件，新temp40MiB，双架构CI合计选择20MiB/200文件；完整性与实际用量见manifest。ZIP、未选文件、cache、构建树和运行数据库不因所在目录或文件后缀取得证据资格。

仅外层 manifest 选中固定字节为正式证据。为避免重复增长，两架构 artifact 可在 ZIP 内核对所有 child manifest，而只选必要原件/一种SBOM/相关诊断；未选0字节输出与冗余派生格式明确记录，不能据外层包推断包含整个CI artifact。第三轮差异使用可逆的字节复制/插入记录：保留前次原件与全部引用闭包，可离线重建选定新原件并校验完整SHA，而非将语义相近冒称整文件相同。重放器见 `ci/delta/replay_delta.py`，第四轮仅选单文件许可补采与必要运行摘要，未选材料的范围保留在选择记录。所有旧正式包逐文件验证原指纹，原 SQLite、固定 Spec/baseline 未写入。活动状态与文档提交影响单独记录。

## 下一步与结束条件

1. WP-05 继续处理剩余五个 Python 包的上游修复/版本上限，按供应商状态区分当前可修、无已知修复和适用性未明；出现明确支持候选后再做隔离解析、五组件/两Flow、认证、迁移/恢复和报告回归。稳定版无收益时保持当前固定运行时。
2. 取得 Zep 精确许可依据，或验证一个明确不含该集成的受支持 fresh runtime；补齐 FIPS/厂商源码、准确 wheel 构建来源与 IBM 文件白名单。未关闭前完整后端镜像分发仍 pending。
3. 发布条件、完整技术验收及负责人最终接受完成后，沿现有 WP-08 改进版本历史、修改后再审、队列筛选、失败诊断和受控恢复。LLM、OCR、真实身份/权限、真实数据及生产部署仍属独立阶段。

本轮结果与未通过项分别陈列。Contract仍approved，WP-05 delivery implementing，完整last_verified=null，最终接受pending。主skill沿用spec-development；本轮无UI改动，使用已有CI浏览器回归，没有叠加设计或近似审查skill。
