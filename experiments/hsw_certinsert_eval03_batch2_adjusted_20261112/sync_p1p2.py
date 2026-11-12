from common_adjusted import *
import shutil
s=W/'var/tmp/eval02_sync_20261112';branch='codex/hsw-eval03-adjusted-batch02-20261112';base='ad46db1b138e960a182ab681909ee19fbb12a642';rel='CG/experiments/2026-11-12-hsw-certinsert-eval03-lite/batch02-adjusted/P1-N10-P2';src=O/'publication_P1N10_P2';dst=s/rel
assert not subprocess.check_output(['git','-C',str(s),'diff','--cached','--name-only']).strip()
assert not dst.exists();shutil.copytree(src,dst)
def git(*args,input=None):return subprocess.check_output(['git','-C',str(s),*args],input=input).decode().strip()
git('update-ref','refs/heads/'+branch,base);git('symbolic-ref','HEAD','refs/heads/'+branch);git('read-tree',base);git('add','--',rel)
paths=git('diff','--cached','--name-only').splitlines();assert paths and all(p.startswith(rel+'/') for p in paths)
tree=git('write-tree','--missing-ok');commit=git('commit-tree',tree,'-p',base,'-m','Archive adjusted Batch02 N10 spoof/scrub and structural region audit');git('update-ref','HEAD',commit,base);git('push','origin',branch)
put(O/'P1P2_PUSH_PENDING_VERIFY.json',dict(commit=commit,branch=branch,path=rel,files=len(paths),repository='guoshaung/research-sync'));print(commit)
