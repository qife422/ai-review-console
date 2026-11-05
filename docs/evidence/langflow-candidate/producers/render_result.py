"""Render the finite isolated experiment result from frozen observations."""
from pathlib import Path
from datetime import datetime, UTC
import hashlib
import json

ROOT=Path('/Users/ffq/Documents/aicoding项目/AI Review Console 开发')
RUN=Path('/private/tmp/arc-langflow-candidate.qya6psom')
FINAL=RUN/'ci/candidate/final'
SOURCE='e73ab92321483403fafd03e721182c5426ae6359'
CI=41943564415
LINK=f'https://github.com/qife422/ai-review-console/actions/runs/{CI}'

def main():
    selection=json.loads((FINAL/'selection.json').read_text())
    inventory=json.loads((RUN/'ci/candidate/second/inventory.json').read_text())
    ref=selection['exact_references'][0]
    assert hashlib.sha256((RUN/ref['exact_original_reference']).read_bytes()).hexdigest()==ref['sha256']
    identity=json.loads((FINAL/'identity.json').read_text());assert identity['source']==SOURCE
    summary=json.loads((FINAL/'summary.json').read_text());assert summary['result']=='passed'
    native=json.loads((FINAL/'native-license-texts.json').read_text());assert (native['read_files'],native['input_bytes'])==(1,1166)
    api=json.loads((FINAL/'api.json').read_text());assert api['anonymous_flows_http']==403 and api['runtime_version']=='1.13.1'
    gui=json.loads((FINAL/'gui/result.json').read_text());assert gui['outcome']=='passed'
    scan=json.loads((FINAL/'metadata/scan/summary.json').read_text())
    assert scan['images']['langflow']['observed_unique_advisory_ids']==133
    assert all(f['query']['package']['ecosystem']=='Debian:12' for f in scan['images']['langflow']['findings'])
    workflow=json.loads((FINAL/'metadata/workflow.json').read_text());assert workflow['result']=='passed' and workflow['langflow_version']=='1.13.1'
    versions={p['name'].lower().replace('_','-'):p['version'] for p in inventory['packages']}
    assert len(versions)==334
    assert versions['pillow']=='13.0.0' and versions['filelock']=='4.2.1' and versions['setuptools']=='84.1.0'
    for n in ['chromadb','couchbase','zep-python','zep-cloud','ibm-db','lfx-ibm','lfx-bundles','psycopg-binary','psycopg2-binary','langflow']:assert n not in versions
    assert len([l for l in (ROOT/'compliance/langflow-candidate-constraints.txt').read_text().splitlines() if l and not l.startswith('#')])==55
    assert json.loads((RUN/'sources/langflow-family-1.13.1-osv-response.json').read_text())=={}
    facts={'source':SOURCE,'run':CI,'conclusion':'success','image_id':identity['image_id'],'platform_scope':'GitHub ubuntu-latest isolated AMD64 profile; no Mac or ARM candidate validation','python':'3.12.16','unit':{'passed':198,'failed':0,'skipped':0},'frontend_tests':29,'python_distributions':334,'mixed_inventory_rows':443,'debian_rows':109,'python_vulnerability_ids':0,'debian_provider_ids':133,'matched_debian_binaries':52,'matched_debian_source_packages':28,'scanner_exit_code':1,'mapping_unknown':0,'query_unknown':0,'detail_unknown':0,'old_five':{n:versions.get(n) for n in ['pillow','filelock','setuptools','chromadb','couchbase']},'pypi_family_query':'Top langflow not installed; supplementary exact1.13.1 query returned0 IDs; source record retained','native_current_read_files':1,'native_current_input_bytes':1166,'native_goal_known_bytes':135836345,'native_new_batch_files':14,'native_new_batch_input_bytes':40313648,'native_remaining':{'files':6,'input_bytes':26795216,'text_bytes':3969945},'default_runtime':'1.11.6 unchanged','release_ac19':'not_passed','full_v02_last_verified':None,'backend_distribution_approval':False,'human_acceptance':'pending','online_demo_redeployed':False}
    report=f'''# 精简 Langflow 候选隔离验证

日期：2026-11-04（America/Los_Angeles）。沿用 `ARC-UPGRADE@0.1.0` / WP-05 / AD-03。结论：**固定1.13.1精简候选可运行，核心回归与管理界面登录通过；尚不替换默认1.11.6，也不代表完整发布验收或后端分发获批。**

## 候选与实际结果

实际代码 `{SOURCE}`，完整[候选CI {CI}]({LINK}) completed/success；实际LF image `{identity['image_id']}`。候选为 `langflow-base==1.13.1`，上游硬依赖 `lfx[sqlite]==1.13.1`；未安装顶层langflow，也未选择complete/bundles/zep/postgresql等可选集成。sqlite是上游硬extra，不能称完全无extras或无native。固定Python3.12.16/bookworm base，APT安装libpq5，显式 `postgresql+psycopg://`，Psycopg3.3.5运行实现为python、报告libpq版本150019。正常运行版本与构建输入共同支持该路径，尚未独立核对所有已加载ELF路径/source对应。

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

扫描只证明指定包名/版本的在线查询；133 IDs不是133个独立或可利用漏洞，unknown severity不等于低风险。原始默认1.11.6 RHEL补扫0与新Debian133来自不同发行版和清单，不能直接做风险升降结论，也没有据此接受残余风险。另对未安装的顶层 `langflow1.13.1` 做一次官方family补充查询，返回{{}}/0 IDs；不将其冒充安装包、不据此覆盖全部alias、静态/内嵌代码或可利用性。

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
3. `{SOURCE[:7]}` / CI{CI}：按实际snapshot修正必填星号，GUI成功；扫描与许可在identity成功后独立采集。补4个有用的许可读取边界测试，默认关闭/字节指纹/符号链接逃逸/超限预读均通过。

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
'''
    state=f'''# 当前状态

更新日期：2026-11-04（America/Los_Angeles）。冷启动以本文件、固定Contract、实际源码和有范围的证据为准。

负责人已批准ARC-UPGRADE@0.1.0及WP-00..05 continuous；本次明确授权精简Langflow候选隔离验证、剩余依赖与许可、回归、结果及计划同步GitHub。用户明确把同目标预算由180扩至250分钟，既有累计保留；只调整时间，不授权历史清理、默认runtime替换、后端发布、许可替代选项或风险接受。工具门禁不覆盖所有MCP/云端路径，登记不授予这些权限。

| 轴 | 当前状态 |
|---|---|
| Contract | approved/0.1.0，固定正文不变 |
| 交付 | implementing；WP-05发布问题仍open；本轮有限隔离实验已完成 |
| 默认运行时 | 1.11.6原base digest+52pins+既有系统补丁；未被候选替换 |
| 精简候选 | langflow-base1.13.1 + lfx[sqlite]1.13.1，Linux AMD64新库；334 Python distributions |
| 候选功能验证 | {SOURCE[:7]} / CI{CI} success：198 Python/29前端；5组件/2Flow/4格式/3决定/9报告、API403/登录/版本、GUI真实登录与两Flow可见 |
| 默认基线验证 | 32eb636 / CI41940799240 success：194 Python/29前端、AMD业务/ARC浏览器及Linux ARM后端 |
| 发布AC-19 | not passed；Debian记录、完整native/分发材料及默认升级范围未闭合 |
| 完整技术验收 | last_verified=null；局部通过按各source/image/profile理解 |
| 最终接受 | pending；未接受残余风险或批准完整后端分发 |
| 保护 | 原SQLite/历史卷、Spec/baseline、四旧封存包不变；无本地Docker增长/清理/迁移 |

## 活动证据

- [精简候选结果、未解决与计划](evidence/langflow-candidate/README.md)，[正式manifest](evidence/langflow-candidate/manifest.json)：SHA-256 `FINAL_MANIFEST_SHA`。
- [候选实际CI]({LINK})，精确source `{SOURCE}`、image `{identity['image_id']}`。后续说明提交不声称是这些精确镜像字节；见[文档影响](evidence/langflow-candidate/environment/documentation-impact.json)。
- [前轮系统维护](evidence/runtime-maintenance/README.md)、[兼容补验](evidence/release-compatibility/README.md)、[发布扫描](evidence/v02-release/README.md)、[早期验收](evidence/v02-acceptance/README.md)原字节保留，仅按原输入/环境理解。

## 已解决与待解决

候选已实际升级Pillow13.0.0/filelock4.2.1/setuptools84.1.0，chromadb/couchbase不在安装清单。55条constraints包含原52中的2项上游floor修订（PyJWT2.15.1/transformers5.10.1）及3个新显式边界，不强制安装未使用集成。PyPI包级匹配0，顶层langflow未安装但其1.13.1 family补查也0；均不是全FS/静态或可利用性保证。

候选扫描443行=334Python+109Debian；52个Debian binary/28source包有133 provider IDs，原exit1保留，mapping/query/detail unknown0。不能把133当独立CVE，不能与旧RHEL0直接比较风险。默认新baseline快照仍LF5包81、API127、PG131、Web0、并集237；完整默认发布尚未通过。

候选未安装Zep、ibm_db/clidriver相关driver、Psycopg binary两包；仅限安装名和已知driver路径。IBM SDK仍在，分别声明BSD-3-Clause/MIT。Psycopg3.3.5纯Python+构建APT libpq5路径正常，runtime报告150019；仍有LGPL/系统native义务。APSW actual owntext1,166B匹配精确source；base/sqlitevec本轮未采到白名单declared specimen，LFX owntext缺记录，已补精确上游MIT及sqlitevec源许可。repo MIT副本仅末尾空行差异，actual镜像副本独立回读未保留；SQLite/source、前端嵌入依赖与完整分发材料仍pending。旧默认及API vendor/FIPS问题未由候选跨环境关闭。

本轮14个新target文件/40,313,648B，加旧95,522,697B=135,836,345B；共享余额6files/26,795,216B输入/3,969,945B文本，旧101/100偏差保留。旧raw继续9→8的固定起算与真实跨CI消耗差异有外部对账，不能把raw旧值当剩余预算。新采集默认false，仅需要时显式true，并先核剩余额度。

## 数据与产物

原SQLite57,344B SHA `980ad5d23d866a52e4101966594e5a24ee67edef08475afc63ff9c3e1f6fca1f`；固定Spec `a77947d0369566cef516641ef918e37d08046afc2edf8215dcff90d49ce01753`、baseline `5ad13f524e74554b9c8cb30b9809ffbbbbed8e3d7fa4ede5625bb1b7d781bf2e`。四旧包全部payload逐文件复核，原库卷未启动、迁移或删除。未把旧故障/恢复/性能继承为1.13.1通过。

新temp `/private/tmp/arc-langflow-candidate.qya6psom` 上限3MiB，连前轮temp合计40MiB；newCI合计1MiB/50files（实选40files/416,324B），sources12files/256KiB；候选`artifacts/evidence-candidates/langflow-candidate/`与正式`docs/evidence/langflow-candidate/`各100MiB/1000files，放大>1GiB且100倍停。ZIP未落盘，scratch/cache/未选whole报告不因目录取得证据资格；保留待授权处置，无清理或整树备份。旧本地Docker容量warning/pending_cleanup保留，本轮未新盘点全部layers/历史归属，也未start/build/pull/prune。

## 下一步

1. 固化候选完整依赖锁与哈希，分类Debian133记录和供应商修复；补自带许可副本/对应源码及完整分发材料，继续按实际目标读数对账。
2. 默认collector仍绑定RHEL事务/补扫与旧native continuation，先适配新发行版且不弱化门槛，再按AD-03提出明确默认升级delta，补ARM/Mac、管理编辑器、旧schema隔离迁移与回滚、故障/恢复/性能；fresh-db成功不替代这些证据。
3. 发布条件和最终决定后才替换默认，再沿WP-08做版本历史、修改后再审、队列和诊断。LLM/OCR/真实身份/真实数据与生产部署独立选择。

普通技术阻塞三轮有证据无进展即停受影响范围；权限/Contract/数据/不可逆/容量即时停。最小阅读：适用AGENTS→本文件→[Spec索引](SPEC_INDEX.md)→活动证据→固定Spec相应WP→源码。
'''
    readme=(ROOT/'README.md').read_text();begin=readme.index('2026-11-03 已归档');end=readme.index('## 基于 Langflow',begin)
    intro=f'''2026-11-04 完成 **精简1.13.1候选隔离验证**：[实际CI]({LINK})通过198 Python/29前端、5组件/2Flow、真实四格式/三决定/九报告及Langflow GUI登录。候选PyPI匹配0，Zep/IBM driver/Psycopg binary与两项未使用集成不在安装清单；Debian133条provider记录和完整分发条件仍未关闭。[完整结果与下一步](docs/evidence/langflow-candidate/README.md)。

**默认仍为Langflow1.11.6，v0.2完整发布验收未通过**。本轮是AD-03隔离实验；未据新库回归直接升级原库或替换默认。后续先补依赖锁、系统/许可材料和旧schema迁移/回滚，再作默认版本决定，之后推进版本历史与再审。原[系统维护记录](docs/evidence/runtime-maintenance/README.md)和其他历史证据保留原字节。

'''
    readme=readme[:begin]+intro+readme[end:]
    index=(ROOT/'docs/SPEC_INDEX.md').read_text().replace('2026-11-03（America/Los_Angeles）','2026-11-04（America/Los_Angeles）')
    lines=index.splitlines();rows=[i for i,l in enumerate(lines) if l.startswith('| ARC-UPGRADE |')];assert len(rows)==1
    lines[rows[0]]=f'| ARC-UPGRADE | AI Review Console 完善及后续升级 | approved/0.1.0，固定字节不变 | implementing；WP-05仍open；完整last_verified=null，最终接受pending | 默认1.11.6基线32eb636/CI41940799240通过194/29；隔离候选1.13.1 {SOURCE[:7]}/CI{CI}通过198/29、完整业务及GUI登录；候选PyPI0但Debian133/native分发未闭合 | [UPGRADE_SPEC.md](UPGRADE_SPEC.md) | 依[候选实证](evidence/langflow-candidate/README.md)补锁定/系统/许可与迁移回滚，再按AD-03决定默认升级；发布条件后WP-08 |'
    index='\n'.join(lines)+'\n'
    changelog=(ROOT/'CHANGELOG.md').read_text();mark='## 2026-11-03 — v0.2 系统维护与候选评估';assert mark in changelog
    change=f'''## 2026-11-04 — 精简 Langflow 候选隔离验证

- 固定base/LFX1.13.1精简候选，避开未使用集成，纯Psycopg3与显式PG驱动；默认1.11.6/52pins不改。
- 候选[CI{CI}]({LINK})通过198 Python/29前端、5组件/2Flow/4格式/3决定/9报告及真实GUI登录；修复实验run参数与必填标签探针，负向retry不冒称成功恢复。
- 原五包在候选中3升级2移除，PyPI匹配0；保留Debian133 provider记录/scan exit1、许可与源码未完成范围。
- 实际取得APSW精确原文及Psycopg LGPL原文，补MIT/sqlitevec source材料；新target实读1/1166B并对账，不跨默认/API镜像关闭vendor问题。
- [已解决、待解决和后续计划](docs/evidence/langflow-candidate/README.md)统一归档；尚未替换默认、迁移原库或批准后端分发。

'''
    changelog=changelog.replace(mark,change+mark,1)
    licenses=(ROOT/'docs/DEPENDENCY_LICENSES.md').read_text()+f'''\n## 精简1.13.1候选的实证范围（2026-11-04）

候选实际image `{identity['image_id']}` / source `{SOURCE}` / CI{CI}，334 Python distributions。Zep两包、ibm_db/lfx-ibm、Psycopg binary两包及已知clidriver路径未检出；限metadata/指定路径，不是全FS证明。仍有IBM SDK，实际声明分别为ibm_watsonx_ai1.9.0 BSD-3-Clause、langchain-ibm1.1.2 MIT，不能统称Apache或说全部IBM已移除。

APSW3.53.4.0 own LICENSE1166B实际SHA b85a7dc6463f286c14a638070a14f4888564ac7245dc99a17950ec24cf1a7b9d，与精确source一致，只关闭该原文缺失。base/sqlitevec未采到白名单specimen，LFX通用采集无owntext；已保存精确v1.13.1 MIT及sqlitevec同tag源许可。MIT repo副本仅额外末尾空行，不称全raw同SHA，未保留sameimage project副本独立回读。Psycopg3.3.5实际LGPL原文已保留，纯Python+APT libpq5及runtime150019不自动证明全部ELF/source对应。

SQLite嵌入版本/选项/source、其他native/system与前端静态依赖的完整通知及分发条件仍pending；API旧vendor/FIPS/default1.11.6继续按各自原image处理。仅本轮实读1file1166B，全批余额6files/26,795,216input/3,969,945text，已知135,836,345B。完整原件、source方法、差异与结论见[候选证据](evidence/langflow-candidate/README.md)，没有批准后端二进制分发或替代OSI许可选择。
'''
    notices=(ROOT/'THIRD_PARTY_NOTICES.md').read_text()+'''\n## Isolated 1.13.1 candidate observations

The experimental langflow-base/LFX1.13.1 image excludes selected Zep, IBM driver and Psycopg binary distributions; default and API images retain their separately scoped obligations. APSW's installed license specimen and Psycopg's LGPL text were recorded. Exact upstream MIT/sqlite-vec source notices supplement explicitly retained installed-text gaps. The fixed repository MIT copy differs only by a trailing blank line; an independent same-image copy readback was not retained. Embedded SQLite/source, system libraries, frontend notices and full backend redistribution remain subject to further verification. See docs/evidence/langflow-candidate/README.md. No license-option or residual-risk acceptance is implied.
'''
    docs={'README.md':readme,'CHANGELOG.md':changelog,'THIRD_PARTY_NOTICES.md':notices,'docs/CURRENT_STATE.md':state,'docs/SPEC_INDEX.md':index,'docs/DEPENDENCY_LICENSES.md':licenses}
    output={'created_at':datetime.now(UTC).isoformat(),'source_commit':SOURCE,'code_ci_run':CI,'code_ci_conclusion':'success','facts':facts,'report':report,'docs':docs}
    with (RUN/'final-observation.json').open('x') as f:f.write(json.dumps(output,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'source':SOURCE,'CI':CI,'docs':len(docs),'facts_asserted':True}))

if __name__=='__main__':main()
