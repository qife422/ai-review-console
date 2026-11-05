# 依赖许可证核实

核实日期：2026-11-05（America/Los_Angeles）；保留此前各轮已封存核实及偏差。适用 `ARC-UPGRADE@0.1.0` 的 `RELEASE-001 / AC-19`。本记录区分许可证识别、应履行的分发条件和实际履行状态，不把 SBOM 中的 `recorded` 或自动扫描器的 `review` 标签当作分发批准。

## 精确 Zep 许可复查（2026-11-05）

本轮重新核对官方PyPI2.0.2 JSON、wheel和sdist（官方大小/SHA均相符），以及v2.0.2对应commit `c5f9144aa065706294c7e43ae1b954fd0a8d9039`。包元数据未声明许可、档案和完整tag树未发现许可命名文件，tag pyproject与sdist字节相同；仍未取得充分明确的精确发行许可依据，**Zep保持OPEN**。当前main的Apache文本、oss分支1.5.0身份和通用badge不直接作为2.0.2许可。缺少这些字段/文件也不等同于证明所有源码绝无授权信息。

已实证Zep owner为默认Langflow；API已实证Psycopg3.3.5，LF另有Psycopg3.3.4/Psycopg2 2.9.12/IBM driver，分别按精确image判断，不再笼统写“默认/API的Zep”。9次请求共111,442B，档案仅在内存检查、不安装执行；本轮native目标新增读取0，没有新镜像扫描/构建或许可文本注入。新旧来源指纹一致，不把重复复查当作许可改善。详见[发布阻塞、关闭条件与澄清草稿](evidence/release-gaps/README.md)；本轮正式记录已封存，旧许可证据不覆写。此次只完成复查，没有关闭许可或后端分发门禁。

## 交付范围

| 交付 | 实际包含 | 本轮结论 |
|---|---|---|
| GitHub 源码 | 本项目 Apache-2.0 源码、Langflow 许可副本、Noto 字体及 OFL；依赖通过锁文件安装 | 保留项目及第三方归属；本项目 `LICENSE` 不替代各依赖许可证 |
| 公开浏览器沙盒 | 编译后的前端 JavaScript、CSS、IBM Plex 字体及许可目录；没有 Python、Langflow 或数据库运行时 | 应核对实际 bundle 的传递依赖声明，保留 React / Carbon / Plex 等许可；本轮没有重新部署线上站点 |
| 本地后端镜像 | Debian、RHEL/UBI、Alpine 用户空间、Python 包和 wheel 内原生库，以及 Langflow 的大量预装集成 | 已核实下面的缺失元数据及特殊许可；完整镜像对外分发仍有明确待解决事项 |

浏览器沙盒的许可范围不能替代 API / Langflow 镜像的许可检查；同样，容器里的 GPL 工具也不能仅由聚合标签推断本项目所有源码必须改为 GPL。应按各文件、组件、组合方式及实际分发行为判断。

## 已确认的应用依赖与特殊事项

| 项目 | 已核实许可/来源 | 履行方式与边界 |
|---|---|---|
| Langflow / LFX `1.11.6` | 同版本上游 monorepo 根 `LICENSE` 为 MIT；LFX 的同版本 `src/lfx/pyproject.toml` 已核对。Langflow wheel 含 MIT 文本，LFX wheel 遗漏了独立许可元数据和文本 | 随分发保留版权和 MIT 文本；不能因 LFX 元数据为空就认定禁止使用，也不能把 Langflow MIT 套给其全部依赖。[固定版本许可](https://github.com/langflow-ai/langflow/blob/v1.11.6/LICENSE)、[LFX 版本来源](https://github.com/langflow-ai/langflow/blob/v1.11.6/src/lfx/pyproject.toml) |
| `psycopg` / `psycopg-binary` | 精确安装包中的 `LICENSE.txt` 为 LGPL-3.0-only；上游 `3.3.5` 文本已核对 | 保留 LGPL 与其引用的 GPL 文本、醒目归属及库源码获取方式；不限制替换库和为修改库调试而进行的逆向工程。Python 导入和可替换共享库不自动要求把独立应用改为 LGPL，但对外提供镜像仍须核实对应源码及组合条件。[精确许可](https://github.com/psycopg/psycopg/blob/3.3.5/LICENSE.txt)、[官方安装说明](https://www.psycopg.org/psycopg3/docs/basic/install.html) |
| `psycopg2-binary` | 包内许可为 LGPL-3.0-or-later，并包含其特定的 OpenSSL 链接例外 | 保留完整原文和例外；不把该例外扩大到无关库或 `psycopg` 3。wheel 内原生库各有独立条件 |
| `frozendict` / `crc32c` | 包内文本分别确认 LGPL v3、LGPL-2.1-or-later；`crc32c` 另有 Google CRC32C 和 slice-by-8 的 BSD 通知 | 保留所有适用通知，记录库版本和源码位置；完整镜像分发时完成库源码及可替换性检查 |
| `grandalf 0.8` | 包内原文明确提供 GPL v2 **或** EPL v1.0 两种路径 | 自动表中的 GPL 匹配不等于只能采用 GPL；实际分发需明确采用并履行其中一条路径，不通过自动标签代替选择 |
| `certifi` | MPL-2.0，包内另有 CA bundle 来源说明 | 对外分发 MPL 文件/可执行形式时告知对应源码获取方式，保留适用声明；这类义务不会被只匹配 GPL 的启发式发现。[Mozilla 官方说明](https://www.mozilla.org/en-US/MPL/2.0/FAQ/) |
| PostgreSQL / OpenSSL 等 wheel 内原生库 | `psycopg-binary` 实际包含 libpq、两代 libcrypto、libssl、Kerberos、LDAP、SASL 等共享库，不能只统计 Python 包许可证 | libpq 的 PostgreSQL 许可、OpenSSL 3 的 Apache-2.0，以及 OpenSSL 1.1.1 的旧双重许可要分别保留；还须覆盖其余原生库通知。不能仅用新版 OpenSSL 许可概括全部 bundled 库。[PostgreSQL 许可](https://www.postgresql.org/about/licence/)、[OpenSSL 官方版本说明](https://openssl-library.org/source/license/) |
| Noto Sans SC / IBM Plex | OFL-1.1 | Noto 固定字节、版权、OFL、来源及转换方法见 [字体记录](../review_core/assets/README.md)；不得把字体单独售卖，不使用保留名称为未经授权的衍生字体命名。分发 Plex Web 字体时一并提供其 OFL。字体许可不强制生成的报告采用 OFL。[OFL 官方文本](https://openfontlicense.org/open-font-license-official-text/) |

本轮没有修改这些第三方库源码或把它们重新声明为本项目的 Apache-2.0。包升级后，许可识别只在实际版本及包内文本复核一致的范围内沿用；最终镜像版本/内容与证据清单绑定。

## 上轮 unknown / review 的复核

API 基线镜像 `f0cf8dc583f3` 的 17 个 `unknown` 均能读取实际 `/usr/share/doc/<包>/copyright`。上轮解析只抓 `License:` 段，遗漏了自由格式正文，不能据此认定没有许可。保留了原文、精确路径和哈希；其中：

- `base-files`、`debian-archive-keyring` 的支持文件为 GPL-2.0-or-later；keyring 中的密钥另有不受版权保护的声明。
- `gcc-12-base` 版权文件列出 GCC GPL-3.0-or-later 以及文件级例外；`libgcc-s1`、`libstdc++6` 对应运行库有 GCC Runtime Library Exception 3.1，不能丢掉例外只报 GPL。[GNU 官方例外](https://www.gnu.org/licenses/gcc-exception-3.1.en.html)
- `libc6`、`libcrypt1`、`libgcrypt20`、`libsemanage-common`、`libsemanage2`、`libtasn1-6` 的库主要为 LGPL-2.1-or-later；同一版权文件还可能覆盖 GPL 工具、文档或其他贡献。
- `libc-bin` 含 glibc 工具的 GPL 条款；`libselinux1` 原文区分公共领域库与其他 GPL/LGPL 文件。
- `libgssapi-krb5-2`、`libk5crypto3`、`libkrb5-3`、`libkrb5support0` 的 MIT Kerberos 版权正文含 BSD 风格条款和其他逐文件通知；不能压成一个未经验证的许可证标识。

Langflow 基线镜像 `ff0f5cc38074` 的 10 个 `unknown` 中，8 个包内许可文本直接可读：`google-crc32c`、`smolagents`、`agent-lifecycle-toolkit`、`uncurl`、`twelvelabs` 为 Apache-2.0；`llm-sandbox`、`peewee`、`langchain-mongodb` 为 MIT。加上同版本上游来源确认的 LFX，已识别 9 个；余下的 Zep 见下一节。

Web 基线镜像没有 `unknown`。Debian/Alpine 镜像中的 GPL/LGPL 系统包确有保留版权、许可及适用源码提供义务；自动扫描的 `review` 数量不是禁止分发数量，也不是这些义务已经全部履行的证明。

## 本轮已落实的随包许可材料

补充了 [dnspython 2.9.0 ISC 原文](../licenses/dnspython-2.9.0-ISC.txt)（SHA-256 `c3ea3ff5654b329c19d3bc5f7481af623c3dded4a6145585499f843ad3d741cd`）和 [FastMCP 3.4.10 Apache-2.0 原文](../licenses/FastMCP-3.4.10-LICENSE.txt)（`43070e2d4e532684de521b885f385d0841030efa2b1a20bafb76133a5e1379c1`）。它们直接复用上轮已封存的精确版本官方响应，没有改动旧证据。`fastmcp-slim 3.4.10` 的同版本 workspace 声明为 Apache-2.0；LFX 1.11.6 的同版本根 MIT 文本复用 [Langflow 许可副本](../licenses/Langflow-LICENSE.txt)。这些是三个已识别许可组件缺少随包原文的具体补充；最终镜像是否实际携带副本须核对构建后的文件哈希，不由 Dockerfile 文本推断。

## 原生库与对应源码材料矩阵

前次2026-10-31在已存在的 Linux/arm64 API `ec611a3c0364`、Langflow `865e7348409f` 精确镜像中只读核实了声明文件的路径/哈希与可调用的版本接口，未构建、拉取或下载源码树。API 共 51、Langflow 共 50 个 native 文件，总哈希输入 95,522,697 字节。全批原计划 100 路径，实际按每镜像限额实现而合计 101，偏差与原始 producer/输出保留；不能把本次结果说成满足全批 100 路径。新镜像重验要重新绑定这些字节。以下版本是实际接口返回值，SONAME 没有被当作源码版本；运行版本也不证明厂商补丁或完整对应源码。

| 精确组件/实际版本 | 已有许可材料与官方来源 | 精确源码定位及 SHA-256 | 仍未满足的材料/核实 |
|---|---|---|---|
| API `psycopg 3.3.5` / `psycopg-binary 3.3.5`；Langflow `psycopg 3.3.4`、`psycopg2-binary 2.9.12` | 各 dist-info 的 `licenses/LICENSE.txt` / `licenses/LICENSE`，LGPL 条款及 psycopg2 特定例外已实读 | 官方 PyPI：`psycopg-3.3.5.tar.gz` `d0a3d9ccf5788af054cbd745278cb02401b5c312aeaafbf2c6144460aec47da4`；`psycopg_c-3.3.5.tar.gz` `5e11edaa0040a64d0af351a8fd3e276a824cd92fe34abc350cd67aa07ad36c55`；`psycopg-3.3.4.tar.gz` `e21207764952cff81b6b8bdacad9a3939f2793367fdac2987b3aac36a651b5bc`；`psycopg2-2.9.12.tar.gz` `1dedb1c7a1d8552c4a6044c6b1c41a52e6a8e2d144af83eccac758076b1b7c15` | 已定位源码档案，未下载/验证源码可重建此 wheel；C 扩展与 bundled 库的构建脚本、补丁、对应源码及允许替换库的交付方式仍需复核 |
| API libpq **18.6**；Langflow libpq **17.9** | PostgreSQL 许可；`PQlibVersion()` 分别为 180006 / 170009，库路径及字节哈希已记录 | [18.6 官方源码及校验](https://ftp.postgresql.org/pub/source/v18.6/postgresql-18.6.tar.bz2.sha256)：`555610c24d53e4316da5b7d3fc25c279d96856d5e0e23ee308c328c5fa881d9f`；[17.9](https://ftp.postgresql.org/pub/source/v17.9/postgresql-17.9.tar.bz2.sha256)：`3b9a62538a8da151e807a3ddb1198e8605f2032544d78f403ae883d27ecf1ee4` | 这些是官方上游同版本档案校验值；尚未证明 wheel 的补丁/构建对应，也未随镜像交付 libpq 完整通知 |
| API OpenSSL **3.5.8**；Langflow **3.5.6** | `OpenSSL_version(0)` 实读；3.x 为 Apache-2.0 | 官方 GitHub release 的 `openssl-3.5.8.tar.gz.sha256`：`a8f84a39918ec6415ce765d9b429d313ba97b8143169c172e734b9514464f5b2`；3.5.6：`deae7c80cba99c4b4f940ecadb3c3338b13cb77418409238e57d7f31f2a3b736` | 对照原生文件哈希、wheel 构建及 notices；不能仅以 Python 包 LGPL/Apache 代替 OpenSSL 原文 |
| 两镜像另含 **OpenSSL 1.1.1k FIPS** | 实读完整版本字符串；旧双重 OpenSSL/SSLeay 条款，不能套用 3.x 的 Apache 文本 | [1.1.1k 官方源码校验](https://www.openssl.org/source/old/1.1.1/openssl-1.1.1k.tar.gz.sha256)：`892a0875b9872acd04a9fde79b1f943075d5ea162415de3047c327df33fbaee5` | 该上游校验值**不证明 FIPS/厂商构建对应**。需取得 wheel 所用厂商 source package、FIPS 模块/补丁与完整旧许可通知；当前保留未满足 |
| API Pillow **13.0.0**；Langflow **12.3.0** | 各包 `licenses/LICENSE` 包含自身及多项原生库条款；native 文件逐项有路径/哈希 | [Pillow 13.0.0 官方 PyPI](https://pypi.org/project/pillow/13.0.0/) sdist `cdcd1ba258178f7356d74170c9a81ba4eab6a5d55748bc402a5a2a6fe6be3510` | 真实接口：FreeType 2.14.3、LittleCMS 2.19、WebP 1.6.0、AVIF 1.4.2、OpenJPEG 2.5.4、zlib-ng 2.3.3；API/LF libjpeg-turbo 为 3.2.0 / 3.1.4.1，libtiff 为 4.7.2 / 4.7.1。尚需每库对应源码/补丁与许可段映射；未报告版本的 XCB、其他 `.libs` 项逐文件保留未知，不能仅按父包 MIT-CMU 完成分发批准 |
| API lxml **6.1.2**；Langflow **6.1.1**，两者编译/运行 libxml **2.14.6**、libxslt **1.1.43** | BSD 主许可及 `LICENSES.txt` 中 ElementTree/PSF 等条款已记录，版本属性实读 | 官方 PyPI sdist：6.1.2 `1055241852f2b02068af4a625a5d32c087db193c12251928af2562ecd2239f18`；6.1.1 `ba96ae44888e0185281e937633a743ea90d5a196c6000f82565ebb0580012d40` | wheel 内静态结合部分仍需核对 libxml/libxslt 对应源码、编译参数和逐文件通知；lxml sdist 本身不是全部原生源码的证明 |
| ReportLab **4.5.1** 的随包字体；项目 Noto / 前端 Plex | ReportLab 内有 DarkGarden GPL、其他字体条款；项目实际 PDF 使用固定 Noto，字体二进制/OFL 哈希未变；Web 已携带 Plex OFL | ReportLab 官方 PyPI sdist `9fdf68f4de9171ec66acb4a5feed8f8ca2af43479e707a6fbb0daa75d88e5494`；Noto 来源、转换与 SHA 见字体记录 | 不因当前报告仅使用 Noto 就忽略完整镜像仍携带的 ReportLab 字体。需按实际分发文件保留相应文本并满足所选条件 |
| AMD64 CI 新增 `ibm_db 3.2.9` 与 clidriver | Python 源码同版本 tag 为 Apache-2.0；官方同版本说明 wheel 包含 clidriver，二者分开判断 | [官方 PyPI 3.2.9](https://pypi.org/project/ibm-db/3.2.9/) sdist `0ad6dc4575519a5563fd7f845fc6bc00d688020e1d3ae78d382e79183bc32b0b`；精确 Python tag 的 LICENSE 已读取 | ARM64 当前没有该包，不拿 ARM 结果代替 AMD64 driver 检查。clidriver 的实际文件、版本、`license/` 条款及分发条件需在 AMD64 精确制品读取；Python sdist 不覆盖 driver。官方区分 LUW 与 z/OS/IBM i 的连接许可，当前未启用这些集成或购买许可 |

上述 PyPI 源码可通过 `https://pypi.org/pypi/<包>/<精确版本>/json` 的 `urls` 中 `packagetype=sdist` 找到下载地址，再按已记录 SHA-256 校验；PostgreSQL/OpenSSL 的官方校验响应、URL、响应哈希和获取时间另行记录。这里只取得元数据和小体量许可/校验文本，未下载上述源码档案；**已定位官方源码、文件哈希、许可副本、实际交付及源/二进制对应验证是不同事项**。

Debian / RPM / Alpine 的包管理器清单继续绑定各包精确版本、source package / source RPM、架构和原始许可字段；发行版用户空间不是上述 wheel 原生库的对应源码来源。不得用宿主 glibc 或发行版同名库替代 wheel 的独立副本；对 GPL/LGPL 系统包的完整源码交付材料仍保留未完成。

## WP-05 精确构建材料与定向核实

已取得 Psycopg **3.3.5、3.3.4** 同版本 tag 的三个小体量原文：`.github/workflows/packages-bin.yml`、`tools/ci/wheel_linux_before_all.sh`、`tools/ci/build_libpq.sh`。它们记录 wheel 构建入口、上游源码地址、构建参数及 libpq 的 GSS 默认值与 socket 目录修改，关闭“未找到上游构建配方”的材料缺口；没有下载、重建或声称复现源码档案。

| 原文 | 3.3.5 SHA-256 | 3.3.4 SHA-256 |
|---|---|---|
| `packages-bin.yml` | `763c6ab0014cee4c1a1263f2c943dd7683bc6c9a56231b3fc77a41ffcbe168f5` | `e488ff682ed842d4edbcef68ad8197064dd64e75e80d2111513a610f516707c0` |
| `wheel_linux_before_all.sh` | `239552169c742123b245a6a1143740eef78720e495b2f4b1c765c4cbb2eb1b86` | `239552169c742123b245a6a1143740eef78720e495b2f4b1c765c4cbb2eb1b86` |
| `build_libpq.sh` | `2cb45ac4c8bb5e8fc3c738c597817bcb2d224bc66073d10023f15665bee9cb8b` | `c66cc2fbea0e54d7a6ce9abbd0029662e7f7779b8e96ae3ea88f1b93bdb6ccc7` |

来源为 [3.3.5 workflow](https://github.com/psycopg/psycopg/blob/3.3.5/.github/workflows/packages-bin.yml)、[3.3.5 源码构建脚本](https://github.com/psycopg/psycopg/blob/3.3.5/tools/ci/build_libpq.sh)、[3.3.4 workflow](https://github.com/psycopg/psycopg/blob/3.3.4/.github/workflows/packages-bin.yml) 及各 tag 下相同相对路径。3.3.5 配方指定 libpq18.6/OpenSSL3.5.8。既有LF的17.9/3.5.6实际owner为 **psycopg2-binary2.9.12**；其[精确immutable构建workflow](https://github.com/psycopg/psycopg2/blob/3a6d9d6ddc6b53eaa80b712f5fa6b23abbdc38db/.github/workflows/packages.yml)与版本输入吻合，[构建脚本](https://github.com/psycopg/psycopg2/blob/3a6d9d6ddc6b53eaa80b712f5fa6b23abbdc38db/scripts/build/build_libpq.sh)仅含socketdir修改。Psycopg3.3.4属于不同owner，其默认18.0/3.5.4不能作为同一wheel的构建矛盾。各配方仍涉及cache及manylinux环境，版本吻合不证明完整厂商source/binary对应。OpenSSL 1.1.1k FIPS 的 source RPM/NVR、补丁、构建环境关联仍未取得，原有对应源码缺口不关闭。

新增定向采集入口 `scripts/verify_native_materials.py` 供隔离 CI 对 API/Langflow **精确 image ID** 核实：优先收集 AMD64 `ibm_db` 的 `clidriver` 许可、`redist.txt`、版本文件及 driver/旧 OpenSSL 的 ELF GNU build-id。它不执行原生库，不下载、不挂载、不联网；全批累计最多实际读取 20 个文件（包括所读 METADATA/RECORD）、64 MiB 输入、4 MiB 文本、每个文本 256 KiB，输出 JSON 合计小于 2 MiB。目录与 RECORD 名单不是已读取正文；缺失、越界、过大及限额均需显式记录。过大 driver 如仅取得前缀，记录前缀哈希而非完整文件哈希。此次新增输入与前轮 95,522,697 字节合计仍不得超过 200 MiB；前轮 101/100 路径偏差永久保留。

IBM 的 Python [3.2.9 源码声明](https://github.com/ibmdb/python-ibmdb/blob/v3.2.9/setup.py) 为 Apache-2.0，Linux 安装脚本默认请求 clidriver v11.5.9；这不是实际 wheel 的 driver 版本证明，也不是 driver 的许可。IBM 的[分发说明](https://www.ibm.com/docs/en/db2/12.1.x?topic=cli-deploying-database-applications)要求对照分发许可及 `redist.txt` 的允许文件；[连接许可说明](https://www.ibm.com/docs/en/db2/11.5.x?topic=applications-license-requirements)区分常规 LUW 与 Db2 Connect 场景。闭项需实际制品中的 agreement/redist、版本及文件范围逐项对应；许可证密钥或 entitlement 文件不采集。当前未完成该对应，也未授权新购买、启用 IBM 集成或公开后端镜像。

Langflow 1.13.0 的[默认依赖](https://github.com/langflow-ai/langflow/blob/v1.13.0/pyproject.toml)将 `lfx-bundles` 变为显式 extra；[base](https://github.com/langflow-ai/langflow/blob/v1.13.0/src/backend/base/pyproject.toml)仍保留 Zep exact extra，[bundles 1.2.4](https://github.com/langflow-ai/langflow/blob/v1.13.0/src/bundles/lfx-bundles/pyproject.toml)也仍要求 `zep-python==2.0.2`。这仅提供“全新且不选相关 extra”的候选核实路径；现有胖镜像内已安装包不会因为改依赖声明就自动移除。尚未验证该候选镜像不含 Zep、全部项目组件/Flow 兼容，或消除 IBM driver；当前运行基线仍为 1.11.6，Zep 的精确许可继续未知。

## 尚未关闭的镜像分发事项

1. **`zep-python 2.0.2` 的精确版本许可仍未确认。** 已读取安装 wheel 的文件清单、[精确 PyPI 版本](https://pypi.org/project/zep-python/2.0.2/)、SHA-256 固定的 sdist，以及[官方 `v2.0.2` tag 对应源码](https://github.com/getzep/zep-python/tree/c5f9144aa065706294c7e43ae1b954fd0a8d9039)。这些输入没有许可声明或 LICENSE。旧 `oss` 分支存在 Apache-2.0 文本，但它不是此 release 的充分许可依据。本轮进一步核对：当前 `langflow-base` 的 Zep extra 与 `lfx-bundles` 的 all/all-no-torch/zep extra 均精确要求 `zep-python==2.0.2`，官方 `lfx-bundles 1.2.0` 仍如此。1.5.0 的许可明确但还要求 `httpx<0.25`；它不满足当前 exact pin。`v2.0.0` tag 虽有 Apache 文本，同 tag 实际包名为 `zep-cloud`，不能给 PyPI `zep-python 2.0.0` 套用。因此未找到在当前允许反向约束内、许可依据和包身份均明确的可直接替换版本，不能靠忽略 extras 或强降版本关闭。完整 Langflow 镜像对外分发前，需取得 2.0.2 明确许可依据，或在明确范围下选择不包含该 extra 的受支持运行时并重测；没有向上游发送消息/issue。
2. **镜像内原生库、GPL/LGPL 组件的完整分发材料仍需落实。** 已落实上表的真实版本、文件哈希、许可文件、官方源码档案/校验及逐项缺口；厂商 FIPS 补丁、若干原生库的源码版本、AMD64 IBM driver 条款和完整源码交付尚未满足。当前不能把“上游有源码链接”写成“我们已履行全部二进制分发义务”。
3. **本记录不授权公开后端镜像或接受残余风险。** 本轮许可核实支持源码与既有静态展示范围；完整后端镜像的分发批准保留未完成，待第 1、2 项关闭后按精确制品复核。

以上待解决项不以删除既有证据、忽略 unknown 或把所有依赖统称 MIT 的方式关闭。当前公开站点仍是仅虚构数据的前端沙盒，不包含这些后端库。

## 本次系统维护后的定向材料结果

在精确AMD镜像中取得ibm_db3.2.9 driver的REDIST、SWID、notices及实际英文协议。最后唯一补读`odbc_LI_en`55,713B（SHA-256 `0e83c4ba0bc0da1a24fd6a828002575acf4933e48f43cb5569ad02436ff5fb6e`），标识v11.5.9/LI L-ASUX-ZXSTFM并附IPLA。前一notices为LI L-XHUG-BAFKQ7/v11.5，和最后英文LI不同用途，不作为现行完整协议ID。SWID产品11.5.0及协议版本不替代实际libdb2二进制fixpack测定。随增值应用的object-code分发范围、该应用支持限制、版权/notices、商标和终端协议等条件仍需逐项履行；未认定完整后端镜像符合所有REDIST文件范围，也未代替用户接受条款。

同轮只在批准的两处psycopg native目录列名未见libcrypto.so.1.*，限该AMD观察，不关闭旧ARM的FIPS/厂商对应源码问题。精确同镜像owner已交叉核对：API psycopg-binary3.3.5，LF psycopg2-binary2.9.12、psycopg3.3.4、ibm_db3.2.9、zep-python2.0.2。Zep精确许可、完整native对应源码与后端二进制分发条件仍open。最终共享批次12文件/40,256,769B，加此前输入累计135,779,466B，未重置额度或读取entitlement .lic。

完整范围及指纹见[系统维护证据](evidence/runtime-maintenance/README.md)。历史ARM矩阵仍限原image IDs，本次AMD材料不以跨架构旧值代替。

## 精简1.13.1候选的实证范围（2026-11-04）

候选实际image `sha256:bab518885b0099096f7843c3016227644246f3f165e74fbd040f373a4ec8bffb` / source `e73ab92321483403fafd03e721182c5426ae6359` / CI41943564415，334 Python distributions。Zep两包、ibm_db/lfx-ibm、Psycopg binary两包及已知clidriver路径未检出；限metadata/指定路径，不是全FS证明。仍有IBM SDK，实际声明分别为ibm_watsonx_ai1.9.0 BSD-3-Clause、langchain-ibm1.1.2 MIT，不能统称Apache或说全部IBM已移除。

APSW3.53.4.0 own LICENSE1166B实际SHA b85a7dc6463f286c14a638070a14f4888564ac7245dc99a17950ec24cf1a7b9d，与精确source一致，只关闭该原文缺失。base/sqlitevec未采到白名单specimen，LFX通用采集无owntext；已保存精确v1.13.1 MIT及sqlitevec同tag源许可。MIT repo副本仅额外末尾空行，不称全raw同SHA，未保留sameimage project副本独立回读。Psycopg3.3.5实际LGPL原文已保留，纯Python+APT libpq5及runtime150019不自动证明全部ELF/source对应。

SQLite嵌入版本/选项/source、其他native/system与前端静态依赖的完整通知及分发条件仍pending；API旧vendor/FIPS/default1.11.6继续按各自原image处理。仅本轮实读1file1166B，全批余额6files/26,795,216input/3,969,945text，已知135,836,345B。完整原件、source方法、差异与结论见[候选证据](evidence/langflow-candidate/README.md)，没有批准后端二进制分发或替代OSI许可选择。

## 依赖锁与通知交付补验（2026-11-04）

本轮实际candidate image `sha256:69bf80f930187d91082d50a22f5543482aea10a6c1391d64e920b120a18ed3f0`、source `a1190a38e998ce9683495a07028a1b9e589303cf`、[CI41953014467](https://github.com/qife422/ai-review-console/actions/runs/41953014467)，与完整334包SHA锁的名称/版本集合完全一致。4构建工具单独锁定；4个sdist固定源档案并禁用build isolation，不宣称生成wheel的二进制复现或自动满足全部source义务。

| 补充通知 | 新实际image回读 | 范围 |
|---|---|---|
| Langflow/LFX根MIT副本 | 1,066B，SHA `2f6f90f0641ad822aec5d2bccd1f97c569cc0cbaf0ec3754d10290808f3b1f1b`，recorded且与repo逐字一致 | 与精确v1.13.1上游只差末尾空行；关闭本image实际携带副本的证据缺口，不改变前轮缺回读的事实 |
| sqlite-vec0.1.9 MIT | 1,068B，SHA `6ce72bbe12d975bd5286e5ab0a064c069693300c47bccbc57bec18485f1621ea`，recorded且与repo/精确tag一致 | [副本](../licenses/sqlite-vec-LICENSE-MIT.txt)，复用原选存响应；不是wheel owntext证明 |
| sqlite-vec0.1.9 Apache | 10,931B，SHA `a38070a94d4afd9cd710e3ce67bd1de78097cfe1784c1f0109ac95d3c196bfdc`，recorded且与repo/精确tag一致 | [副本](../licenses/sqlite-vec-LICENSE-APACHE.txt)，本轮从[精确官方tag](https://github.com/asg017/sqlite-vec/blob/v0.1.9/LICENSE-APACHE)有界获取，匹配前轮指纹；两种原文均保留，不选择替代许可 |

三份回读是`project_files`明确子集，包含原generic报告SHA/member来源与派生方法，见[collector-license-summary](evidence/langflow-transition/ci/current/collector-license-summary.json)和selection。未把未选的大报告或旧APSW image正文称为本轮新image完整原件。APSW/source、sqlite-vec内嵌SQLite、Debian libpq及其余native精确源码/构建/通知对应、完整前端依赖材料仍待核对。候选未检出Zep/driver不关闭默认/API的Zep精确许可及vendor/FIPS问题；IBM SDK仍按实际包各自条款判断。

候选只做同Bookworm的APT/libapt2.6.2补丁，实际清单和复扫已核；仍有132 provider记录，系统包copyright字段只是标识库存，不等于全部原文/source交付获批。本轮没有target native新增读取，累计135,836,345B，余6files/26,795,216B输入/3,969,945B文本；generic通知和系统库存不当作旧native实读的替代。

[本轮结果及计划](evidence/langflow-transition/README.md)独立记录依赖锁、CI和迁移证据；保持完整AC-19未通过、legal_approval=false、完整后端分发未批准。

## Linux ARM 候选通知回读（2026-11-04）

[CI41979142562](https://github.com/qife422/ai-review-console/actions/runs/41979142562)、source e6f6fe7b908b7fab1b4f85e9f5a4fa22890fc923，ARM LF image sha256:a5939d54d52e42c88138c81d2059386fd31b3c1f66b7373358b35374b6b9627d；AMD LF image sha256:26a433f984fcb8da102faf0a77daa668c4ccfdc3a7177ac17ff961925547d27f。两个image的Langflow MIT及sqlite-vec MIT/Apache三份project副本均recorded，raw SHA、文本SHA和大小与仓库一致。安装清单各334包与平台锁名称/版本一致；不是安装wheel字节复现、wheel own-text修复或全部分发材料批准。

ARM独立解析改用58个aarch64 wheel及magika通用wheel，不能从AMD原生库材料推定其内部库/source相同。当前native_materials=not_collected_this_image；没有新增target native实读，既有共享额度及旧偏差保留。ARM只验证新库后端业务，不继承前轮AMD迁移/故障/性能。两个LF各132条系统provider记录/exit1，四服务provider并集各157，完整后端分发仍未批准。

实际原件/派生项与来源指纹见[本轮证据](evidence/langflow-arm/README.md)及selection；默认/API的Zep、vendor/FIPS和完整native/source义务继续独立open。
