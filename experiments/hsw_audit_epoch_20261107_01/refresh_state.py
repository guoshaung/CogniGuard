from bootstrap import R,E
import json,datetime
rows=[json.loads(l) for l in (R/'RUN_MANIFEST.jsonl').read_text().splitlines() if l.strip()]
started={r['task_id'] for r in rows if r.get('event')=='STARTED'}
delivered={r['task_id'] for r in rows if r.get('event')=='DELIVERED'}
failed={r['task_id'] for r in rows if r.get('event')=='TECH_FAIL'}
delivered_rows=[r for r in rows if r.get('event')=='DELIVERED']
exits=[r for r in rows if r.get('event')=='STAGE_EXIT']
blocked=bool(exits and exits[-1]['status'] in {'MEMORY_GUARD','RESOURCE_LIMIT','DISK_LIMIT','ADMISSION_OR_STAGE_FAILURE'})
open_stages=[p.name for p in R.glob('generation_*') if p.is_dir() and (p/'LOADED.json').exists() and not (p/'EXITED.json').exists()]
state={'task':'HSW-AUDIT-EPOCH-01','stage':'GENERATION_ACTIVE' if open_stages or started-delivered-failed else 'RESOURCE_WAIT' if blocked else 'CHECKPOINT',
 'updated_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'attempts':len(started),'delivered':len(delivered),
 'natural_EOS_complete':sum(r.get('finish_reason')=='EOS' for r in delivered_rows),
 'technical_truncated_snapshots':sum(r.get('finish_reason')!='EOS' for r in delivered_rows),
 'technical_failed':len(failed),'started_incomplete':sorted(started-delivered-failed),
 'tokens_recorded_completed':sum(r.get('tokens',0) for r in rows if r.get('event') in {'DELIVERED','TECH_FAIL'}),
 'stage_wall_recorded':sum(r['wall_seconds'] for r in rows if r.get('event')=='STAGE_EXIT'),
 'generation_attempt_limit':96,'user_outer_limit':256,'GPU_calls':0,'paid_API_calls':0,'RQ2':'FROZEN',
 'results_before_detection':'Every newly delivered parent requires its own quality lock before public scoring; old round01 retained',
 'open_stages':open_stages,'user_choice':'KEEP_7B_WAIT','RAM_admission_GiB':6.5,'3B_fallback_authorized':False,
 'new_root':'D:/pycharm/CogniGuard-worktrees/hsw-st','no_original_research_files_written':True}
(R/'STATE.json').write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
(E/'NEXT_ACTION.md').write_text('保持7B及6.5GiB准入线；只恢复从未STARTED的槽位，不能重跑截断失败或改用3B。先核对open_stages/进程与账本，已有运行任务只监测。新输出逐份质量锁后才进入新round公开检测，旧round01不覆盖。S2两DEV来源技术验收后再执行冻结S3；累计模型墙钟7200秒/30000Token/96尝试上限优先。保留PARTIAL检查点，不把报告或内存等待当整体研究完成。\n',encoding='utf-8')
print(json.dumps(state,ensure_ascii=False))
