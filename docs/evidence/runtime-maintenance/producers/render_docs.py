"""Render docs and their packaging impact only from actual final observations."""
from pathlib import Path
from datetime import datetime,UTC
import json,hashlib

ROOT=Path('/Users/ffq/Documents/aicoding项目/AI Review Console 开发')
RUN=Path('/private/tmp/arc-runtime-maintenance.wT9huB')
CANDIDATE=ROOT/'artifacts/evidence-candidates/runtime-maintenance'

def sha(data):return hashlib.sha256(data).hexdigest()

def main():
    obs=json.loads((RUN/'final-observation.json').read_text())
    assert obs['code_ci_conclusion']=='success'
    replacements={'FINAL_RESULT':obs['report_result'],'FINAL_REGRESSION':obs['report_regression'],'FINAL_NATIVE':obs['report_native']}
    report=(RUN/'report-draft.md').read_text()
    for key,value in replacements.items():report=report.replace(key,value)
    assert 'FINAL_' not in report
    with (CANDIDATE/'README.md').open('x') as f:f.write(report)
    state=(RUN/'state-draft.md').read_text()
    for key,value in {'FINAL_SOURCE':obs['source_commit'],'FINAL_RUN':str(obs['code_ci_run']),'FINAL_CI_SHORT':obs['ci_short'],'FINAL_SYSTEM_AND_SCAN':obs['state_scan'],'FINAL_NATIVE_SHORT':obs['state_native']}.items():state=state.replace(key,value)
    readme=(ROOT/'README.md').read_text();begin=readme.index('2026-10-31 保留上轮应用与前端依赖修补');end=readme.index('## 基于 Langflow',begin)
    update=f'''2026-11-03 已归档在固定 Langflow1.11.6 上完成的公共 UBI 系统维护及定向许可补采，并修补 Web libexpat；原52个显式Python pins保留。[功能代码 CI](https://github.com/qife422/ai-review-console/actions/runs/{obs['code_ci_run']}) 实际通过 **{obs['python_passed']} Python / 29 前端测试**、AMD64完整工作流/浏览器、Linux ARM64后端工作流。两架构系统包和镜像审计的具体范围、签名、版本与结果见[系统维护记录](docs/evidence/runtime-maintenance/README.md)。Linux ARM云验证不等于Mac宿主验证。

**v0.2仍未完成完整发布验收**：Langflow仍有5个Python包的扫描匹配，Debian残余记录、Zep精确许可和完整native/二进制分发材料仍待关闭。稳定/RC/开发Langflow候选没有同时解除三项上限，当前保持固定运行版本。后续按现有计划推进版本历史、修改后再审、队列效率和诊断；模型/OCR/生产化另行选择。已解决、未解决和关闭条件统一见[本轮证据与计划](docs/evidence/runtime-maintenance/README.md)，历史证据保留原字节。

'''
    readme=readme[:begin]+update+readme[end:]
    index=(ROOT/'docs/SPEC_INDEX.md').read_text().replace('2026-10-31（America/Los_Angeles）','2026-11-03（America/Los_Angeles）')
    lines=index.splitlines();matches=[i for i,line in enumerate(lines) if line.startswith('| ARC-UPGRADE |')];assert len(matches)==1
    lines[matches[0]]='| ARC-UPGRADE | AI Review Console 完善及后续升级 | approved / 0.1.0，固定字节不变 | implementing；WP-05发布问题open，continuous；完整last_verified=null，最终接受pending | '+obs['source_commit'][:7]+' / CI '+str(obs['code_ci_run'])+' success：'+str(obs['python_passed'])+' Python/29前端，AMD完整业务/浏览器与Linux ARM后端通过；固定1.11.6/52pins，系统维护与定向材料实证。AC-19残余与分发条件未通过 | [UPGRADE_SPEC.md](UPGRADE_SPEC.md) | 依[本轮系统维护](evidence/runtime-maintenance/README.md)关闭上游/供应商/许可问题；完成发布门槛后沿WP-08做版本历史、再审与诊断 |'
    index='\n'.join(lines)+'\n'
    changelog=(ROOT/'CHANGELOG.md').read_text();marker='## 2026-10-31 — v0.2 兼容与许可补验';assert marker in changelog
    entry='''## 2026-11-03 — v0.2 系统维护与候选评估

'''+obs['changelog_text']+'\n\n'
    changelog=changelog.replace(marker,entry+marker,1)
    license_doc=(ROOT/'docs/DEPENDENCY_LICENSES.md').read_text()
    license_doc=license_doc.replace('本轮在已存在的 Linux/arm64 API','前次2026-10-31在已存在的 Linux/arm64 API',1)
    old='3.3.5 配方指定 libpq 18.6 / OpenSSL 3.5.8；**3.3.4 tag 配方默认 18.0 / 3.5.4，与既有 Langflow 实读的 17.9 / 3.5.6 不同**。二者均使用构建缓存及 manylinux 基础环境；不能从 tag、配方或版本吻合推断实际 wheel 的完整厂商来源。'
    new='3.3.5 配方指定 libpq18.6/OpenSSL3.5.8。既有LF的17.9/3.5.6实际owner为 **psycopg2-binary2.9.12**；其[精确immutable构建workflow](https://github.com/psycopg/psycopg2/blob/3a6d9d6ddc6b53eaa80b712f5fa6b23abbdc38db/.github/workflows/packages.yml)与版本输入吻合，[构建脚本](https://github.com/psycopg/psycopg2/blob/3a6d9d6ddc6b53eaa80b712f5fa6b23abbdc38db/scripts/build/build_libpq.sh)仅含socketdir修改。Psycopg3.3.4属于不同owner，其默认18.0/3.5.4不能作为同一wheel的构建矛盾。各配方仍涉及cache及manylinux环境，版本吻合不证明完整厂商source/binary对应。'
    assert old in license_doc
    license_doc=license_doc.replace(old,new,1)
    license_doc += '\n## 本次系统维护后的定向材料结果\n\n'+obs['license_doc_text']+'\n\n完整范围及指纹见[系统维护证据](evidence/runtime-maintenance/README.md)。历史ARM矩阵仍限原image IDs，本次AMD材料不以跨架构旧值代替。\n'
    notices=(ROOT/'THIRD_PARTY_NOTICES.md').read_text()
    old_notice='Exact Psycopg 3.3.5/3.3.4 upstream build recipes have now been located and fingerprinted. They do not establish correspondence for the installed wheels or their vendor OpenSSL 1.1.1k FIPS libraries. The IBM Python wrapper\'s Apache-2.0 license is distinct from bundled clidriver agreements and redistribution lists; these require exact AMD64 artifact inspection. Zep 2.0.2 remains unresolved.'
    new_notice='Exact Psycopg 3.3.5 and Psycopg2 2.9.12 build recipes and patches have been fingerprinted against their respective package owners. Exact AMD64 driver and legacy native material observations are recorded in docs/DEPENDENCY_LICENSES.md. Recipe/version matches, library build IDs and package licenses do not by themselves complete vendor-source correspondence or backend binary redistribution approval. The IBM wrapper license is distinct from clidriver terms; Zep 2.0.2 remains unresolved.'
    assert old_notice in notices
    notices=notices.replace(old_notice,new_notice)
    docs={'README.md':readme,'CHANGELOG.md':changelog,'docs/CURRENT_STATE.md':state,'docs/SPEC_INDEX.md':index,'docs/DEPENDENCY_LICENSES.md':license_doc,'THIRD_PARTY_NOTICES.md':notices}
    dest=RUN/'final-docs';dest.mkdir(exist_ok=False);impact=[]
    for name,text in docs.items():
        p=dest/name;p.parent.mkdir(parents=True,exist_ok=True)
        with p.open('x') as f:f.write(text)
        impact.append({'path':name,'tested_sha256':sha((ROOT/name).read_bytes()),'planned_sha256':None if name=='docs/CURRENT_STATE.md' else sha(text.encode()),'packaging':'README description/API COPY; notices and dependency doc API/Langflow COPY' if name in ['README.md','THIRD_PARTY_NOTICES.md','docs/DEPENDENCY_LICENSES.md'] else 'status/history/index only'})
    write={'at':datetime.now(UTC).isoformat(),'tested_source_commit':obs['source_commit'],'actual_ci_run':obs['code_ci_run'],'files':impact,'followup_scope':'Only6documentation files plus sealed evidence; no business/dependency/CI/Flow/source/runtime configuration change','ci_policy':'[skip ci] skips pure documentation commit, not a passing check; avoids repeated native material inputs; functional code CI actually passed first','policy_source':'https://docs.github.com/en/actions/how-tos/manage-workflow-runs/skip-workflow-runs','exact_image_claim':'Only recorded functional-code images were built/scanned; these later metadata/document bytes are not claimed to be those images','current_state_hash':'Filled with sealed manifest after seal; Git fixes final bytes'}
    with (CANDIDATE/'environment/documentation-impact.json').open('x') as f:f.write(json.dumps(write,ensure_ascii=False,indent=2)+'\n')
    with (CANDIDATE/'producers/render_docs.py').open('xb') as f:f.write(Path(__file__).read_bytes())
    print(json.dumps({'draft_docs':str(dest),'report_rendered':True,'ci':obs['code_ci_run']}))

if __name__=='__main__':main()
