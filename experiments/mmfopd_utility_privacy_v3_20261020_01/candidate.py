"""One teacher-protected orthogonal family with explicit feasibility, rank0 allowed."""
import core as c
import numpy as np
from sklearn.svm import LinearSVC
import warnings

def teacher_weight(model):
    names=model.named_steps['dictvectorizer'].get_feature_names_out()
    scale=model.named_steps['standardscaler'].scale_
    coef=model.named_steps['ridge'].coef_
    return np.array([coef[np.where(names==f'h{i}')[0][0]]/scale[np.where(names==f'h{i}')[0][0]] for i in range(3)])

def family(rows,enc,protect=True):
    v,m=enc.transform(rows);views,_,_,_,_=c.emit(rows,enc,c.identity())
    model=c.predictor().fit(views,[r['target_score'] for r in rows]);w=teacher_weight(model)
    t=w[:,None]/np.linalg.norm(w) if protect and np.linalg.norm(w)>1e-10 else np.zeros((3,0))
    s=np.array([[r[a] for a in c.ATTRS] for r in rows]);cov=c.crosscov(v,s)
    residual=(np.eye(3)-t@t.T)@cov
    u=c.basis(residual)
    out={0:c.identity()};records={}
    for rank in [1,2]:
        ur=u[:,:rank];p=np.eye(3)-ur@ur.T
        if protect:assert np.linalg.norm(p@w-w)<1e-8
        assert np.linalg.norm(p-p.T)<1e-9 and np.linalg.norm(p@p-p)<1e-9
        out[rank]={'P':p,'bias':v.mean(0)}
    records={'teacher_value_weight':w.tolist(),'sensitive_crosscov':cov.tolist(),
             'task_shared_sensitive_crosscov_frobenius':float(np.linalg.norm(t@t.T@cov)),
             'total_sensitive_crosscov_frobenius':float(np.linalg.norm(cov)),
             'task_complement_sensitive_crosscov_frobenius':float(np.linalg.norm(residual)),
             'available_directions':u.shape[1],'teacher_protected':protect,
             'teacher_weight_residual_by_rank':{str(r):float(np.linalg.norm(z['P']@w-w)) for r,z in out.items()}}
    return out,records

def select_rank(innerfit,innerval,indices,bg,protect=True,loss_gate=True):
    enc=c.Encoder(indices).fit(innerfit);transforms,meta=family(innerfit,enc,protect)
    evaluations=[]
    for rank,t in transforms.items():
        xt,wt,vt,vpt,mt=c.emit(innerfit,enc,t);xv,wv,vv,vpv,mv=c.emit(innerval,enc,t)
        pred=np.clip(c.predictor().fit(xt,[r['target_score'] for r in innerfit]).predict(xv),0,100)
        mae=float(np.mean(abs(pred-np.array([r['target_score'] for r in innerval]))))
        dist=float(np.sum((vpv-vv)**2)/max(1e-30,np.sum(vv**2)))
        nt=c.token_counts(wt+wv)
        privacy=[]
        for attr in c.ATTRS:
            met,_,_=c.attack_fit(xt,xv,np.array([r[attr] for r in innerfit]),np.array([r[attr] for r in innerval]),'RF')
            background=next(x for x in bg if x['attribute']==attr and x['attacker']=='RF')
            privacy.append({'attribute':attr,'RF_AUC':met['AUC'],'RF_BA':met['BA'],
                            'nonnegative_excess':max(0.,met['AUC']-background['AUC'])})
        evaluations.append({'rank_requested':rank,'rank_removed':3-int(np.linalg.matrix_rank(t['P'],tol=1e-8)),
                            'MAE':mae,'distortion':dist,'actual_tokens_max':int(nt.max()),
                            'risk_max_RF_excess':max(x['nonnegative_excess'] for x in privacy),'privacy':privacy})
    baseline=evaluations[0]['MAE'];eligible=[]
    for x in evaluations:
        x['MAE_bound']=baseline+1.;x['MAE_gate_enabled']=loss_gate
        x['eligible']=bool((not loss_gate or x['MAE']<=baseline+1.) and x['distortion']<=.20 and x['actual_tokens_max']<=64)
        if x['eligible']:eligible.append(x)
    assert eligible # Identity is always admissible.
    # Quantization at1e-12 only defines numerical tie handling, not risk smoothing.
    selected=min(eligible,key=lambda x:(round(x['risk_max_RF_excess'],12),x['distortion'],x['rank_requested']))
    return selected['rank_requested'],{'candidates':evaluations,'selected_rank':selected['rank_requested'],
                                      'protect_teacher':protect,'explicit_loss_gate':loss_gate,
                                      'fit_students':len({r['student'] for r in innerfit}),
                                      'validation_students':len({r['student'] for r in innerval}),
                                      'fit_snapshots':len(innerfit),'validation_snapshots':len(innerval),'geometry':meta}

def references(v,s):
    import torch
    from concept_erasure import LeaceEraser
    torch.set_num_threads(1)
    eraser=LeaceEraser.fit(torch.tensor(v,dtype=torch.float64),torch.tensor(s,dtype=torch.float64),
                         affine=True,shrinkage=False,constrain_cov_trace=False,svd_tol=1e-10)
    refs={'LEACE':{'P':eraser.P.numpy(),'bias':eraser.bias.numpy()}}
    p=np.eye(3);rows=[];records=[];joint=(2*s[:,0]+s[:,1]).astype(int)
    for it in range(3):
        if np.linalg.matrix_rank(p,tol=1e-8)==0:break
        with warnings.catch_warnings(record=True) as found:
            warnings.simplefilter('always')
            model=LinearSVC(C=1,class_weight='balanced',max_iter=20000,random_state=20261020).fit(v@p.T,joint)
        u=c.basis(model.coef_.T);rows.append(u@u.T);union=c.basis(sum(rows));p=np.eye(3)-union@union.T
        records.append({'iteration':it+1,'remaining_rank':int(np.linalg.matrix_rank(p,tol=1e-8)),
                        'warnings':[str(w.message) for w in found]})
    refs['INLP3']={'P':p,'bias':np.zeros(3)}
    return refs,records
