# 依赖许可证核实

核实日期：2026-10-31（America/Los_Angeles）。适用 `ARC-UPGRADE@0.1.0` 的 `RELEASE-001 / AC-19`。本记录区分许可证识别、应履行的分发条件和实际履行状态，不把 SBOM 中的 `recorded` 或自动扫描器的 `review` 标签当作分发批准。

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

## 尚未关闭的镜像分发事项

1. **`zep-python 2.0.2` 的精确版本许可仍未确认。** 已读取安装 wheel 的文件清单、[精确 PyPI 版本](https://pypi.org/project/zep-python/2.0.2/)、SHA-256 固定的 sdist，以及[官方 `v2.0.2` tag 对应源码](https://github.com/getzep/zep-python/tree/c5f9144aa065706294c7e43ae1b954fd0a8d9039)。这些输入没有许可声明或 LICENSE。旧 `oss` 分支存在 Apache-2.0 文本，但它不是此 release 的充分许可依据。完整 Langflow 镜像对外分发前，需取得上游对该版本的明确许可依据，或评估许可明确的替代依赖/上游版本并重新验证。
2. **镜像内原生库、GPL/LGPL 组件的完整分发材料仍需落实。** 已确认相关条款及包内文本存在；尚未制作并验证覆盖所有对应版本的源码交付/获取材料，也未把 Python wheel 自带的全部原生库逐一归属。当前不能把“上游有源码链接”写成“我们已履行全部二进制分发义务”。
3. **本记录不授权公开后端镜像或接受残余风险。** 本轮许可核实支持源码与既有静态展示范围；完整后端镜像的分发批准保留未完成，待第 1、2 项关闭后按精确制品复核。

以上待解决项不以删除既有证据、忽略 unknown 或把所有依赖统称 MIT 的方式关闭。当前公开站点仍是仅虚构数据的前端沙盒，不包含这些后端库。
