"""Post-run evidence checks and report clarification. ZERO new fits/dev predictions."""
import os
os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',RAYON_NUM_THREADS='1',TOKENIZERS_PARALLELISM='false',CUDA_VISIBLE_DEVICES='-1')
from pathlib import Path
import datetime,hashlib,importlib.util,json,csv,sys,subprocess,collections
import numpy as np
import joblib
from threadpoolctl import threadpool_limits
P=Path(__file__).parent;ROOT=P.parents[1]
def load(n):return json.loads((P/n).read_text(encoding='utf8'))
def save(n,v):(P/n).write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    if (P/'evidence_validation.json').exists():raise RuntimeError('No overwrite: final verification already completed')
    cfg=load('config.json');done=load('completion.json');audit=load('audit.json');lock=load('execution_lock.json');train_complete=load('TRAIN_COMPLETE.json')
    assert done['fits_started']==45 and done['dev_evaluations']==1
    assert all(sha(P/n)==h for n,h in lock['source_sha256'].items())
    assert all(sha(ROOT/n)==h for n,h in audit['sources_sha256'].items())
    assert all(sha(P/'models_LOCAL'/n)==h for n,h in train_complete['model_sha256'].items())
    records=[json.loads(l) for l in (P/'run_log.jsonl').read_text().splitlines()]
    fits=[r for r in records if r['event']=='FIT_START'];ends=[r for r in records if r['event']=='FIT_END'];devmark=next(r for r in records if r['event']=='FINAL_DEV_EVALUATION_START')
    assert len(fits)==len(ends)==45 and not any(r['event']=='FIT_FAILED' for r in records)
    assert all(r['utc']<devmark['utc'] and r['utc']<cfg['stop_new_fits_utc'] for r in fits+ends)
    assert all(r['num_threads']<=1 for r in train_complete['threadpools'])
    spec=importlib.util.spec_from_file_location('message_evidence_validation',P/'run.py');c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
    from tokenizers import Tokenizer
    tok=Tokenizer.from_file(str(ROOT/cfg['tokenizer']))
    messages=[json.loads(l) for l in (P/'actual_messages_LOCAL.jsonl').read_text().splitlines()]
    assert len(messages)==473*5
    pred=np.load(P/'predictions_LOCAL.npz');seen=set();bycase={};max_m3_delta=0.
    for r in messages:
        key=(r['case'],r['method']);assert key not in seen;seen.add(key)
        i=int(r['case'][1:]);m=r['method'];parsed=c.parse(r['wire']);assert parsed==r['parsed']
        assert len(tok.encode(r['wire'],add_special_tokens=False).ids)==r['tokens']
        assert not set(parsed)&{'student','target_score','target_assessment_LOCAL','gender_F','disability_Y'}
        if m in ['M1','M2']:assert r['tokens']<=64
        if m=='M3':
            assert list(parsed)==['predicted_score'];assert parsed['predicted_score']==pred['forecast_M3'][i]
            assert parsed['predicted_score']==float(f'{pred["forecast_M4"][i]:.1f}')
            max_m3_delta=max(max_m3_delta,abs(parsed['predicted_score']-pred['forecast_M4'][i]))
        bycase.setdefault(r['case'],{})[m]=r
    assert len(bycase)==473 and all(len(v)==5 for v in bycase.values())
    assert max_m3_delta<=.05000001
    # Saved predictions are verified; never call a predictor on DEV a second time.
    for row in load('method_summary.json'):
        m=row['method'];err=abs(pred['forecast_'+m]-pred['target']);assert abs(err.mean()-row['MAE'])<1e-10
    # Reconstruct TRAIN-only held-out messages from stored fold models. This is
    # explicitly replay evidence, not a second fit or another dev evaluation.
    allrows=json.loads((ROOT/cfg['cache']).read_text());train=[r for r in allrows if r['split']=='train'];dev=[r for r in allrows if r['split']=='dev']
    th={c.pseudo(r['student']) for r in train};dh={c.pseudo(r['student']) for r in dev};assert th.isdisjoint(dh)
    groups=load('crossfit_groups_LOCAL.json');foldsets=[set(g['prediction_group_hashes']) for g in groups]
    assert set.union(*foldsets)==th and sum(map(len,foldsets))==len(th)
    vals=[None]*len(train);foldids=[None]*len(train)
    with threadpool_limits(limits=1):
        for fold,held in enumerate(foldsets):
            idx=[i for i,r in enumerate(train) if c.pseudo(r['student']) in held]
            bundle=joblib.load(P/'models_LOCAL'/('M3_crossfit'+str(fold)+'.joblib'))
            views=[c.parse('\n'.join(k+'='+v for k,v in c.raw_pairs(train[i],c.ALL))) for i in idx]
            scores=np.clip(c.predict(bundle,views),0,100)
            for i,score in zip(idx,scores):vals[i]=float(f'{score:.1f}');foldids[i]=fold
    assert all(v is not None for v in vals)
    replay=[{'predicted_score':v} for v in vals]
    worst_mean_drift=0.
    for attr in c.ATTRS:
        for kind in c.KINDS:
            b=joblib.load(P/'models_LOCAL'/('attack_public_plus_message_M3_'+attr+'_'+kind+'.joblib'))
            assert abs(b['median']['predicted_score']-float(np.median(vals)))<1e-12
            x=b['pipeline'][0].transform(c.encode(replay,b['median']));mean=np.asarray(x.mean(axis=0)).ravel()
            drift=float(np.max(abs(mean-b['pipeline'][1].mean_)));worst_mean_drift=max(worst_mean_drift,drift);assert drift<1e-10
    with (P/'M3_train_crossfit_replay_LOCAL.jsonl').open('w',encoding='utf8') as f:
        for i,(r,score,fold) in enumerate(zip(train,vals,foldids)):
            payload='predicted_score='+f'{score:.1f}'
            f.write(json.dumps({'case':f'T{i:04d}','student_pseudonym':c.pseudo(r['student']),'fold':fold,'wire':payload,'tokens':len(tok.encode(payload,add_special_tokens=False).ids),'provenance':'post-run deterministic replay of saved held-out TRAIN fold model; no new fit'})+'\n')
    cases=load('five_cases_LOCAL.json');assert len(cases)==5 and len({r['case'] for r in cases})==5
    for case in cases:
        assert 'student' not in case and not set(c.ATTRS)&set(case)
        for m,details in case['methods'].items():assert details['uploaded']==bycase[case['case']][m]['wire']
    finish=datetime.datetime.now(datetime.timezone.utc);elapsed=(finish-datetime.datetime.fromisoformat(cfg['started_utc'])).total_seconds()
    assert elapsed<=90*60
    validation={'status':'PASS','utc':finish.isoformat(),'whole_session_elapsed_minutes_to_validation':elapsed/60,'evaluation_driver_seconds':done['runtime_seconds'],'traditional_estimator_fits':44,'MI_selection_estimation_calls':1,'counted_fits_total':45,'new_fits_in_validation':0,'new_dev_predictions_in_validation':0,'dev_evaluations':1,'actual_dev_messages_verified':len(messages),'M3_rounded_forecast_verified_rows':473,'M3_max_forecast_quantization_error':max_m3_delta,'train_crossfit_messages_reconstructed':1337,'train_crossfit_unique_prediction_students':len(th),'train_crossfit_student_overlap':0,'train_crossfit_replay_attack_scaler_mean_max_drift':worst_mean_drift,'train_replay_is_not_original_byte_commitment':True,'all_frozen_run_sources_unchanged':True,'all_original_input_sources_unchanged':True,'all_model_files_match_prefinal_dev_commitment':True,'all_native_pools_1_thread':True,'RF_workers':2,'no_GPU':True,'R31_reference':'BLOCKED_MISSING_SOURCE','data_or_model_downloads':0,'paid_calls':0,'external_student_data_uploads':0,'no_followup_queue':True}
    save('evidence_validation.json',validation)
    save('interface_test_results.json',{'command':'./run.cmd test experiments/mmfopd_message_necessity_20261027_01/test_contract.py -q -p no:cacheprovider','passed':4,'failed':0,'seconds':6.15,'warning':'PytestConfigWarning: Unknown config option cache_dir when cache provider disabled; no test failure','real_data_or_model_fits_in_tests':0})
    # Interpret existing results only; no extra thresholds, methods or sample filters.
    note='''

## 最终解释：是否还需要新算法？

本轮有“原字段/分箱消息减量会损失预测精度”的现象，但这不构成必须研发复杂算法的证据：本地已能完成同一授权任务，M3在仅上传一个预测值时保持M4的效用。M4相对M0改善15.437分，95%[13.094,17.646]；M3相对M4误差差−0.000875分，配对95%[−0.003859,0.002448]，通过预设1分参考。

M1相对M4损失2.593分，95%[1.630,3.460]；M2损失2.202分，95%[1.147,3.481]，两者都没有通过。M2−M1为−0.391分，95%[−1.114,0.521]，没有证明优于M1；按同一1分探索性参考，摘要保留了三字段层级的效用，但没有达到完整信息参考的精度。

结果-only不是零泄漏。M3性别RF AUC0.565，相对Public增量0.065，95%[0.006,0.119]；残疾RF AUC0.527，增量0.027，95%[−0.073,0.152]。M3满足授权预测目的后不需要再上传原始字段：已知同一Y_auth时，M4的额外性别RF推断增量为0.277，95%[0.200,0.365]。该对照使用预测结果，不是隐藏真实未来成绩。M3在授权结果条件下增量为0是视图相同的代数事实，不是新的隐私保证。

粗分箱也没有在每个有限攻击器上单调降低AUC：例如性别LR，M1为0.511、M2为0.565。M2是同来源字段的确定性粗化，类别编码可能使有限LR更容易利用非线性关系；不能把某个攻击器变强解释为信息论信息量增加或反向声称另一个攻击器下降就是安全。

M4包含课程和日程，均按新增披露计费；本轮没有逐字段消融，不能把全部性别信号归因给某一个课程字段。若部署接收端事实上预先知道这些信息，Public基线与增量风险会变化，需要先核实真实接口，本轮不追加实验。单一成绩/提交代理及20名残疾阳性开发学生不足以推广到真实云端教学或其他受保护属性。

本轮建议：在这一授权目的下采用结果-only接口，停止该任务上的复杂画像披露算法搜索。旧MM-FOPD的组件有效性结论没有被改变；其他需要理由、源证据或互动的任务尚未验证。所有消息和逐例输出仅留本机，不同步外部。
'''
    result=(P/'RESULT.md').read_text();result=result.replace('总耗时'+f'{done["runtime_seconds"]:.2f}'+'秒','评估驱动实跑'+f'{done["runtime_seconds"]:.2f}'+'秒（不含前期审计、编码和报告工作）')
    result+=note+'\n全过程至最终证据核验约'+f'{elapsed/60:.2f}'+'分钟，未用满预算追加训练。参见evidence_validation.json。主程序与协议未改；本节由只读后处理finalize.py生成。\n'
    (P/'RESULT.md').write_text(result,encoding='utf8')
    meeting=(P/'MEETING_ONE_PAGE.md').read_text();meeting=meeting.replace('另评估已知共同授权预测Y_auth后的增量；','已知共同授权预测Y_auth后，M4额外性别RF AUC增量0.277，95%[0.200,0.365]；M3重复结果不增加视图。')
    (P/'MEETING_ONE_PAGE.md').write_text(meeting,encoding='utf8')
    reproduce=(P/'REPRODUCE.md').read_text();reproduce+='\nPost-run verification (no new fit or dev prediction):\n\n```powershell\npython -B experiments/mmfopd_message_necessity_20261027_01/finalize.py\n```\n\nThe optional TRAIN-only crossfit replay checks saved fold models and attack scaler statistics. It is explicitly reconstructed evidence, not a claim that original train-wire bytes were committed before fitting. Interface tests passed4/4; the recorded cache_dir warning is caused by disabling pytest cache provider.\n'
    (P/'REPRODUCE.md').write_text(reproduce,encoding='utf8')
    manifest={'classification':'LOCAL_ONLY_REAL_STUDENT_LOGS','generated_utc':finish.isoformat(),'files':{p.relative_to(P).as_posix():{'sha256':sha(p),'bytes':p.stat().st_size} for p in P.rglob('*') if p.is_file() and p.name!='manifest.json' and '__pycache__' not in p.parts},'external_uploads':0,'contains_pseudonymized_real_student_records':True,'do_not_publish_wholesale':True}
    save('manifest.json',manifest)
    print(json.dumps({k:v for k,v in validation.items() if k not in ['threadpools']},indent=2))
if __name__=='__main__':main()
