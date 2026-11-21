"""Calibration-split learned CGC safety stage.

Trains only on a stratified JailbreakBench calibration split, then evaluates
on held-out JBB and full XSTest. This is an offline benchmark of a second-stage
classifier; it does not change the deterministic production adapter.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

import requests
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import FeatureUnion

from experiments.evaluation.run_cg_jailbreakbench import fetch_split
from experiments.evaluation.run_cg_xstest import URL as XSTEST_URL

ROOT = Path(__file__).resolve().parents[2]
JBB_CATEGORIES = [
    "Disinformation", "Economic harm", "Expert advice", "Fraud/Deception",
    "Government decision-making", "Harassment/Discrimination", "Malware/Hacking",
    "Physical harm", "Privacy", "Sexual/Adult content",
]


def stratified(rows, per_category):
    out=[]
    for cat in JBB_CATEGORIES:
        out.extend([r for r in rows if r.get('Category')==cat][:per_category])
    return out


def metrics(rows):
    tp=sum(r['label'] and r['pred'] for r in rows); fn=sum(r['label'] and not r['pred'] for r in rows)
    fp=sum(not r['label'] and r['pred'] for r in rows); tn=sum(not r['label'] and not r['pred'] for r in rows)
    rec=tp/(tp+fn) if tp+fn else 0; fpr=fp/(fp+tn) if fp+tn else 0
    return {'n':len(rows),'tp':tp,'fn':fn,'fp':fp,'tn':tn,'recall':rec,'false_block_rate':fpr,'precision':tp/(tp+fp) if tp+fp else 0,'f1':2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 0,'balanced_accuracy':(rec+1-fpr)/2}


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--output',type=Path,required=True); ap.add_argument('--calibration-per-category',type=int,default=7); ap.add_argument('--threshold',type=float,default=.5); args=ap.parse_args()
    harmful=fetch_split('harmful'); benign=fetch_split('benign')
    # Calibration uses the first 7/category; held-out JBB uses the remainder.
    cal=stratified(harmful,args.calibration_per_category)+stratified(benign,args.calibration_per_category)
    cal_ids={(r.get('Category'),r.get('Goal')) for r in cal}
    held=[r for r in harmful+benign if (r.get('Category'),r.get('Goal')) not in cal_ids]
    train_text=[r['Goal'] for r in cal]; train_y=[r in harmful for r in cal]
    vectorizer=FeatureUnion([
        ('word',TfidfVectorizer(ngram_range=(1,2),min_df=1,sublinear_tf=True)),
        ('char',TfidfVectorizer(analyzer='char',ngram_range=(3,5),min_df=1,sublinear_tf=True,max_features=30000)),
    ])
    X=vectorizer.fit_transform(train_text); clf=LogisticRegression(max_iter=1000,class_weight='balanced',C=2.0,random_state=20261008).fit(X,train_y)
    def score(rows,label_name):
        texts=[r['Goal'] if label_name=='jbb' else r['prompt'] for r in rows]
        probs=clf.predict_proba(vectorizer.transform(texts))[:,1]
        out=[]
        for r,p in zip(rows,probs): out.append({'label':(r.get('split')=='harmful') if label_name=='jbb' else r.get('label')=='unsafe','pred':bool(p>=args.threshold),'probability':float(p),'id':r.get('Index',r.get('id'))})
        return out
    held_rows=[]
    for split in ('harmful','benign'):
        for r in held:
            if (r in harmful and split=='harmful') or (r in benign and split=='benign'): held_rows.append(r | {'split':split})
    xresp=requests.get(XSTEST_URL,timeout=45); xresp.raise_for_status(); xrows=list(csv.DictReader(xresp.text.splitlines()))
    result={'calibration':{'harmful':args.calibration_per_category*10,'benign':args.calibration_per_category*10},'threshold':args.threshold,'jbb_heldout':metrics(score(held_rows,'jbb')),'xstest_full':metrics(score(xrows,'xstest'))}
    args.output.mkdir(parents=True,exist_ok=True); (args.output/'summary.json').write_text(json.dumps(result,indent=2)+"\n",encoding='utf8')
    print(json.dumps(result,indent=2))

if __name__=='__main__': main()
