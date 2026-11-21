"""Posthoc timing sensitivity, preserving every primary case and fitted model."""
from pathlib import Path
import json,collections
import pandas as pd
import numpy as np
P=Path(__file__).parent;ROOT=P.parents[1]
def load(n):return json.loads((P/n).read_text(encoding='utf8'))
def save(n,z):(P/n).write_text(json.dumps(z,ensure_ascii=False,indent=2),encoding='utf8')
if (P/'target_timing_audit.json').exists():raise RuntimeError('no overwrite')
sub=pd.read_csv(ROOT/'.cache/oulad-author-v1/studentAssessment.csv',usecols=['id_student','id_assessment','date_submitted']);by={(int(x.id_student),int(x.id_assessment)):float(x.date_submitted) for x in sub.itertuples()};out=[];sensitivity=[]
for phase,rows in [('train',[x for x in load('dev_data/snapshots_LOCAL.json') if x['split']=='train']),('dev',[x for x in load('dev_data/snapshots_LOCAL.json') if x['split']=='dev']),('test',load('test_data/snapshots_LOCAL.json'))]:
 known={(x['student'],x['cutoff']) for x in rows if by.get((x['student'],x['target_assessment_LOCAL']),float('inf'))<=x['cutoff']};out.append({'phase':phase,'n_snapshots':len(rows),'next_scheduled_TMA_already_submitted_by_cutoff':len(known),'already_submitted_fraction':len(known)/len(rows),'interpretation':'scheduled-future deadline does not ensure an unobserved submission/grade; grade publication timestamp unknown'})
 if phase=='train':continue
 cases=load(phase+'_results/cases_LOCAL.json');cells=collections.defaultdict(list)
 for x in cases:
  if (x['student'],x['cutoff']) not in known:cells[x['intent'],x['wording'],x['method']].append(x)
 for (intent,wording,method),z in cells.items():sensitivity.append({'phase':phase,'intent':intent,'wording':wording,'method':method,'not_yet_submitted_eval_n':len(z),'MAE_existing_fit':float(np.mean([abs(x['prediction']-x['target']) for x in z])),'scope':'POSTHOC subset sensitivity only; primary test unchanged, no refit or new sample selection'})
save('target_timing_audit.json',{'status':'COMPLETED_POSTHOC_TEMPORAL_LIMITATION_CHECK','primary_data_or_predictions_changed':False,'new_model_fits':0,'cohorts':out,'sensitivity':sensitivity,'scope':'Primary task is next scheduled TMA score from restricted historical view, not always genuinely future/unobserved performance. Publish limitation; do not replace test to improve ranking.'});print(json.dumps(out,indent=2))
