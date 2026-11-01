"""Render reviewable docs from observed final results, before explicit sealing."""
from pathlib import Path
from datetime import datetime, UTC
import hashlib
import json

ROOT=Path('/Users/ffq/Documents/aicoding项目/AI Review Console 开发')
RUN=Path('/private/tmp/arc-release-followup.rLeRu5')
CANDIDATE=ROOT/'artifacts/evidence-candidates/release-compatibility'

def sha(data): return hashlib.sha256(data).hexdigest()

def main():
    obs=json.loads((RUN/'final-observation.json').read_text())
    assert obs['conclusion']=='success' and obs['head_sha']=='a64ab476c8acfaa36a3d6cc260a4c6c286bad380'
    assert obs['offline_probe_passed'] and obs['real_workflow_and_browser_passed']
    assert obs['langflow_python_affected_packages']==5
    assert obs['license_quota_skips']==0 and obs['license_supplement_hashes_match']
    report=(RUN/'report-draft.md').read_text().replace('FINAL_CI_RESULT',obs['report_ci_text']).replace('FINAL_ARTIFACT_RESULT','候选与正式包各小于 100MiB / 1,000 文件，本轮 temp 小于 40MiB；实测大小、文件数、源码输入及指纹见 manifest。manifest 未选入的 ZIP、缓存、原始全局 snapshot 和构建目录保留原分类。旧两个正式包逐文件复核，原库及固定输入指纹均不变。未授权清理、压缩或迁移。')
    assert 'FINAL_' not in report
    with (CANDIDATE/'README.md').open('x') as stream:stream.write(report)
    state=(RUN/'state-draft.md').read_text().replace('FINAL_CI_SHORT',obs['ci_short_text']).replace('FINAL_SCAN_SHORT',obs['scan_short_text'])
    readme=(ROOT/'README.md').read_text()
    begin=readme.index('2026-10-31 已修补应用 Python')
    end=readme.index('## 基于 Langflow',begin)
    replacement=f'''2026-10-31 保留上轮应用与前端依赖修补，本轮进一步升级 OAuthlib、datamodel-code-generator 及 OpenTelemetry，Langflow 仍为 1.11.6，共 52 个显式 pin。代码 `a64ab47` 的 [完整 CI](https://github.com/qife422/ai-review-console/actions/runs/41263397231) 已通过 **{obs['python_passed']} Python / {obs['frontend_passed']} 前端测试**、离线兼容探针、真实工作流和浏览器验收。镜像包级扫描与实际许可文本已复核；本地容量警戒期间使用隔离 CI，没有新增本地构建或清理历史缓存。

**发布检查 AC-19 仍未关闭**：本轮 Langflow 受影响 Python 包由 8 个缩至 5 个，部分系统包仍有记录；Zep 精确许可及完整原生/二进制分发材料尚未闭环，未接受剩余风险或批准完整后端镜像分发。已解决项、具体约束和后续关闭条件见 [本轮兼容与许可补验](docs/evidence/release-compatibility/README.md)；[前次发布检查](docs/evidence/v02-release/README.md)、[更早收尾记录](docs/evidence/v02-acceptance/README.md)及固定 Spec 保持原字节。

'''
    readme=readme[:begin]+replacement+readme[end:]
    index=(ROOT/'docs/SPEC_INDEX.md').read_text()
    row='| ARC-UPGRADE | AI Review Console 完善及后续升级 | approved / 0.1.0，固定字节不变 | implementing；WP-05 发布问题未关闭，continuous；完整 last_verified=null，最终接受 pending | `a64ab47` / CI `41263397231` success：'+str(obs['python_passed'])+' Python、29 前端、真实四格式/三决定/九报告、双主题双尺寸浏览器及离线兼容探针；52 pins/pip check/精确镜像扫描与许可副本复核。AC-19 残余发现与分发材料未通过 | [UPGRADE_SPEC.md](UPGRADE_SPEC.md) | 依 [本轮补验](evidence/release-compatibility/README.md) 处理上游上限、无明确 fixed 事件、Zep/native及厂商材料；本地构建保留容量警戒，条件关闭后申请完整技术及最终接受 |'
    lines=index.splitlines();matches=[i for i,s in enumerate(lines) if s.startswith('| ARC-UPGRADE |')];assert len(matches)==1
    lines[matches[0]]=row
    index='\n'.join(lines)+'\n'
    index=index.replace('按固定 [发布验收](evidence/v02-release/README.md)','按固定 [本轮补验](evidence/release-compatibility/README.md)')
    changelog=(ROOT/'CHANGELOG.md').read_text()
    marker='## 2026-10-31 — v0.2 依赖修补与发布检查'
    assert marker in changelog
    addition=f'''## 2026-10-31 — v0.2 兼容与许可补验

- 先完成镜像/缓存精确盘点和二次回读：本地 layers/镜像/cache 集合与大小未增长；历史归属仍不足，继续暂停本地 build/pull，不 prune 或清理历史。
- OAuthlib 4.0.0、datamodel-code-generator 0.81.0、OTel 1.45.1/0.66b1 成套升级；原 29 pins 保留，另固定两个必需 exporter 包，共 52 pins。
- 新增离线兼容/安全探针；首次 a59 的低层解析器长度断言失败已保留，按精确上游源码改测入站传播器及分段头合计上限，没有降低阈值。最终 a64 的 [CI 41263397231](https://github.com/qife422/ai-review-console/actions/runs/41263397231) 实际通过 {obs['python_passed']} Python、29 前端、真实 Flow/报告、双主题双尺寸浏览器、pip check 与新探针。
- 补入两份许可原文及 Langflow 镜像三份随包材料，实际哈希与采集额度已核实；排除误选源码/pyc。补齐真实 native 版本、路径哈希、源码校验与缺项，100 路径计划实际读 101 的偏差明确保留。
- Langflow 剩余 Python 包级匹配由 8 个缩至 5 个；上游上限、无明确修复、系统项、Zep 精确许可及完整 native/二进制分发材料仍未闭环。AC-19 未通过，完整技术和最终接受仍待定，没有部署真实后端或重部署静态站点。
- 已解决、待解决和下一步统一在 [本轮补验](docs/evidence/release-compatibility/README.md)；旧证据逐文件核对不变，最小增量证据及状态同步 GitHub。

'''
    changelog=changelog.replace(marker,addition+marker,1)
    docs={'README.md':readme,'docs/SPEC_INDEX.md':index,'CHANGELOG.md':changelog,'docs/CURRENT_STATE.md':state}
    draft=RUN/'final-docs';draft.mkdir(exist_ok=False)
    impact=[]
    for name,content in docs.items():
        p=draft/name;p.parent.mkdir(parents=True,exist_ok=True)
        with p.open('x') as stream:stream.write(content)
        impact.append({'path':name,'tested_source_sha256':sha((ROOT/name).read_bytes()),'planned_final_sha256':None if name=='docs/CURRENT_STATE.md' else sha(content.encode()),'effect':'README enters package description and API COPY; business/test/dependency/Flow code unchanged by this documentation followup' if name=='README.md' else 'status/index/history documentation; current state manifest reference filled after seal'})
    obj={'created_at':datetime.now(UTC).isoformat(),'tested_source_commit':obs['head_sha'],'tested_ci_run':obs['run_id'],'method':'Render reviewable docs from actual CI evidence before sealing; apply after seal; Git binds final current state to avoid self-reference','files':impact,'exact_image_claim':'Only CI-built IDs from the tested source; subsequent README metadata/docs are not claimed to be those same image bytes','full_old_fault_restore_performance_rerun':False,'production_static_site_or_backend_deployment':False,'fixed_spec_and_old_evidence_modified':False}
    with (CANDIDATE/'environment/documentation-impact.json').open('x') as stream:stream.write(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'draft_docs':str(draft),'report_ready':True,'observed_ci':obs['run_id']}))

if __name__=='__main__':main()
