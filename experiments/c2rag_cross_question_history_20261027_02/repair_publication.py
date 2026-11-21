"""Retain packaging failure and create a new packaging attempt, never replay."""
import json
from experiments.c2rag_cross_question_history_20261027_02.common import RESULTS_DIR,SOURCE

root=RESULTS_DIR/'c2rag_cross_question_history_20261027_github_sync_01'
failure={'stage':'publication packaging only','error':'LookupError unknown encoding utf8-sig; correct codec utf-8-sig',
         'repair_attempt':'PowerShell quoting failed before Python execution; use saved Python source instead',
         'experiment_rerun':False,'new_publication_attempt':'c2rag_cross_question_history_20261027_github_sync_02'}
with (root/'FAILURE.json').open('x',encoding='utf8') as f:json.dump(failure,f,ensure_ascii=False,indent=2)
text=(SOURCE/'prepare_publication.py').read_text(encoding='utf8')
text=text.replace('c2rag_cross_question_history_20261027_github_sync_01','c2rag_cross_question_history_20261027_github_sync_02')
text=text.replace("'utf8-sig'","'utf-8-sig'")
text=text.replace("files['LICENSE_SOURCES.md']=", "files['failed_publication01/FAILURE.json']=(RESULTS_DIR/'c2rag_cross_question_history_20261027_github_sync_01/FAILURE.json').read_bytes()\n    files['LICENSE_SOURCES.md']=")
with (SOURCE/'prepare_publication_02.py').open('x',encoding='utf8') as f:f.write(text)
print('Failed attempt preserved; publication02 ready, experiment data unchanged.')
