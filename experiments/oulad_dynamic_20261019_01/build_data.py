"""Student-disjoint, cutoff-limited OULAD snapshots; raw rows always LOCAL."""
from pathlib import Path
import json,hashlib,sys,zipfile,time,collections
import numpy as np
import pandas as pd
P=Path(__file__).parent;ROOT=P.parents[1];sys.path.insert(0,str(P));import design as d
CACHE=ROOT/'.cache/oulad-author-v1'
def load(p):return json.loads(p.read_text(encoding='utf8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(folder,n,z):(folder/n).write_text(json.dumps(z,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf8')
def group(sid):return int.from_bytes(hashlib.sha256(('oulad-group-v1|'+str(sid)).encode()).digest()[:8],'big')%100
def rank(sid):return hashlib.sha256(('oulad-rank-v1|'+str(sid)).encode()).hexdigest()
def build(phase):
 assert phase in ['dev','test'];O=P/(phase+'_data');O.mkdir(exist_ok=True)
 if (O/'execution_lock.json').exists():raise RuntimeError('do not overwrite '+str(O))
 if phase=='test':
  lock=load(P/'independent_protocol.json');assert lock['authorized_by_frozen_dev_gate'] and lock['source_sha256']['build_data.py']==sha(Path(__file__))
 save(O,'execution_lock.json',{'status':'FROZEN_DATA_BUILD','phase':phase,'driver_sha256':sha(Path(__file__)),'protocol_sha256':sha(P/'protocol.json'),'time_rule':'VLE<=t; assessment submission and due<=t-7','test_targets_accessed_before_gate':False})
 info_ids=pd.read_csv(CACHE/'studentInfo.csv',usecols=['id_student','code_module','code_presentation']);info_ids['group']=info_ids.id_student.map(group);info_ids['rank']=info_ids.id_student.map(rank)
 # No final_result or sensitive labels are read to choose the cohort.
 pres='2013J' if phase=='dev' else '2014J';base=info_ids[info_ids.code_module.isin(d.MODULES)&(info_ids.code_presentation==pres)].sort_values(['id_student','code_module']).drop_duplicates('id_student');selected=[]
 for module in d.MODULES:
  for part in (['train','dev'] if phase=='dev' else ['test']):
   lower,upper,cap=(0,60,200) if part=='train' else (60,80,70) if part=='dev' else (80,100,70)
   z=base[(base.code_module==module)&(base.group>=lower)&(base.group<upper)].sort_values('rank').head(cap).copy();z['split']=part;selected.append(z)
 chosen=pd.concat(selected,ignore_index=True);assert not chosen.id_student.duplicated().any();ids=set(chosen.id_student.tolist())
 if phase=='test':assert ids.isdisjoint(set(load(P/'dev_data/cohort_LOCAL.json')['ids']))
 save(O,'cohort_LOCAL.json',{'ids':sorted(ids),'rows':chosen[['id_student','code_module','code_presentation','split','group']].to_dict('records')})
 inventory={'phase':phase,'presentation':pres,'all_studentInfo_rows':len(info_ids),'global_unique_student_ids':int(info_ids.id_student.nunique()),'students_with_multiple_studentInfo_rows':int((info_ids.groupby('id_student').size()>1).sum()),'selected_unique_students':len(ids),'cohort_counts':chosen.groupby(['code_module','split']).size().reset_index(name='n').to_dict('records'),'selection_uses_outcome_or_sensitive_labels':False,'cross_partition_student_overlap':0}
 save(O,'inventory.json',inventory);print('cohort',phase,len(ids),flush=True)
 # The source archive includes heldout rows. Only selected IDs/presentation join this run.
 info=pd.read_csv(CACHE/'studentInfo.csv',usecols=['id_student','code_module','code_presentation','num_of_prev_attempts','studied_credits','gender','disability']);info=info[info.id_student.isin(ids)&(info.code_presentation==pres)&info.code_module.isin(d.MODULES)].merge(chosen[['id_student','code_module','code_presentation','split']],on=['id_student','code_module','code_presentation'],validate='one_to_one')
 reg=pd.read_csv(CACHE/'studentRegistration.csv');reg=reg[reg.id_student.isin(ids)&(reg.code_presentation==pres)];info=info.merge(reg,on=['id_student','code_module','code_presentation'],validate='one_to_one')
 assessments=pd.read_csv(CACHE/'assessments.csv');assessments=assessments[(assessments.code_module.isin(d.MODULES))&(assessments.code_presentation==pres)&(assessments.assessment_type=='TMA')];assert assessments.date.notna().all()
 submissions=pd.read_csv(CACHE/'studentAssessment.csv');submissions=submissions[submissions.id_student.isin(ids)&submissions.id_assessment.isin(assessments.id_assessment)];assert not submissions.duplicated(['id_student','id_assessment']).any();joined=submissions.merge(assessments,on='id_assessment',validate='many_to_one')
 # Stream the 453MB table rather than materialize/extract it. One bounded download.
 vle=pd.read_csv(CACHE/'vle.csv',usecols=['id_site','code_module','code_presentation','activity_type']);vle=vle[(vle.code_presentation==pres)&vle.code_module.isin(d.MODULES)];chunks=[];read_rows=0;start=time.perf_counter()
 with zipfile.ZipFile(CACHE/'anonymisedData.zip') as archive,archive.open('studentVle.csv') as stream:
  for chunk in pd.read_csv(stream,chunksize=250000):
   read_rows+=len(chunk);z=chunk[(chunk.id_student.isin(ids))&(chunk.code_presentation==pres)&(chunk.code_module.isin(d.MODULES))&(chunk.date<=max(d.CUTOFFS))&(chunk.date>=min(d.CUTOFFS)-60)]
   if len(z):chunks.append(z)
 activity=pd.concat(chunks,ignore_index=True).merge(vle,on=['id_site','code_module','code_presentation'],validate='many_to_one');activity=activity[activity.sum_click>0]
 eventgroups={key:z for key,z in activity.groupby(['id_student','code_module'])};gradegroups={key:z for key,z in joined.groupby(['id_student','code_module'])};calendar={m:assessments[assessments.code_module==m].sort_values(['date','id_assessment']) for m in d.MODULES}
 rows=[];excluded=collections.Counter();violations=0;missing_counts=collections.Counter()
 for person in info.to_dict('records'):
  sid=int(person['id_student']);module=person['code_module'];ev=eventgroups.get((sid,module),activity.iloc[:0]);gr=gradegroups.get((sid,module),joined.iloc[:0]);cal=calendar[module]
  for t in d.CUTOFFS:
   if pd.isna(person['date_registration']) or person['date_registration']>t:excluded['not_registered_by_snapshot']+=1;continue
   if not pd.isna(person['date_unregistration']) and person['date_unregistration']<=t:excluded['already_unregistered_by_snapshot']+=1;continue
   future=cal[(cal.date>t)&(cal.date<=t+56)]
   if future.empty:excluded['no_TMA_within56days']+=1;continue
   target=future.iloc[0];targetrows=gr[gr.id_assessment==target.id_assessment]
   if len(targetrows) and int(targetrows.iloc[0].is_banked)!=0:excluded['banked_target_out_of_forecast_scope']+=1;continue
   observed=False;timely=False;y=0.
   if len(targetrows):
    targetrow=targetrows.iloc[0];timely=bool(targetrow.date_submitted<=target.date+7)
    if timely:
     if pd.isna(targetrow.score):excluded['timely_target_missing_score']+=1;continue
     observed=True;y=float(targetrow.score)
   hist=gr[(gr.date<=t-7)&(gr.date_submitted<=t-7)&(gr.is_banked==0)&(gr.score.notna())].sort_values(['date','id_assessment']);due=cal[cal.date<=t-7];used=ev[ev.date<=t];recent=used[used.date>t-14];earlier=used[(used.date>t-28)&(used.date<=t-14)]
   assert not (hist.id_assessment==target.id_assessment).any();assert hist.empty or (hist.date.max()<=t-7 and hist.date_submitted.max()<=t-7);assert used.empty or used.date.max()<=t
   scores=hist.score.tolist();older=float(np.mean(scores[:-1])) if len(scores)>1 else None;latest=float(scores[-1]) if scores else None;recent_clicks=int(recent.sum_click.sum());due_count=len(due)
   submitted_known=gr[(gr.date<=t-7)&(gr.date_submitted<=t-7)&(gr.is_banked==0)].id_assessment.nunique()
   values={'older_score':older,'latest_score':latest,'score_delta':latest-older if older is not None and latest is not None else None,'completion_rate':submitted_known/due_count if due_count else None,'overdue_count':due_count-submitted_known,'clicks_recent':recent_clicks,'clicks_earlier':int(earlier.sum_click.sum()),'active_days':int(recent.date.nunique()),'inactive_days':min(60,t-int(used.date.max())) if len(used) else 60,'forum_share':float(recent[recent.activity_type=='forumng'].sum_click.sum()/recent_clicks) if recent_clicks else None,'content_share':float(recent[recent.activity_type.isin(['resource','oucontent','page','url','subpage','glossary'])].sum_click.sum()/recent_clicks) if recent_clicks else None,'previous_attempts':int(person['num_of_prev_attempts']),'studied_credits':int(person['studied_credits'])}
   values={k:round(float(v),3) if v is not None else None for k,v in values.items()};assert set(values)==set(d.FIELDS)
   for k,v in values.items():missing_counts[k]+=v is None
   rows.append({'student':sid,'module':module,'presentation':pres,'split':person['split'],'cutoff':t,'values':values,'target_score':y,'target_observed':observed,'target_timely':timely,'target_due':int(target.date),'target_assessment_LOCAL':int(target.id_assessment),'gender_F':int(person['gender']=='F'),'disability_Y':int(person['disability']=='Y'),'source_audit':{'grade_max_due':int(hist.date.max()) if len(hist) else None,'grade_max_submitted':int(hist.date_submitted.max()) if len(hist) else None,'click_max_date':int(used.date.max()) if len(used) else None,'grade_count':len(hist),'lag_days':7}})
 save(O,'snapshots_LOCAL.json',rows);save(O,'availability.json',{'status':'SNAPSHOTS_BUILT','snapshots':len(rows),'unique_students':len({x['student'] for x in rows}),'by_module_stage_split':pd.DataFrame([{k:x[k] for k in ['module','cutoff','split']} for x in rows]).groupby(['module','cutoff','split']).size().reset_index(name='n').to_dict('records'),'target_observed_count':sum(x['target_observed'] for x in rows),'constructed_zero_count':sum(not x['target_observed'] for x in rows),'excluded':dict(excluded),'missing_field_snapshots':dict(missing_counts),'time_violations':violations,'VLE_rows_streamed':read_rows,'VLE_selected_rows':len(activity),'VLE_stream_seconds':time.perf_counter()-start,'attributes_by_split':[{'split':sp,'attribute':a,'n_students':len(z),'positive_students':sum(z[a])} for sp in sorted({x['split'] for x in rows}) for a in ['gender_F','disability_Y'] for z in [pd.DataFrame(rows).query('split==@sp').drop_duplicates('student')]],'assessment_grade_time_limitation':'No grade-release timestamp; lagged submitted/due proxy cannot guarantee true historical grade visibility','target_scope_limitation':'banked/missing-score outcomes excluded; late/no submissions defined as0; evaluate this proxy separately from observed-score subset'})
 print('built',phase,len(rows),flush=True)
if __name__=='__main__':build(sys.argv[1] if len(sys.argv)>1 else 'dev')
