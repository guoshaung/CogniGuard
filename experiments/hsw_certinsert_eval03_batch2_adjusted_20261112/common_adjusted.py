from pathlib import Path
import sys,json,hashlib,subprocess,datetime
E=Path(__file__).resolve().parent;W=E.parents[1];PREV=W/'experiments/hsw_certinsert_eval03_lite_20261112'
sys.path.insert(0,str(PREV));from initialize import read,sha,put,E1,E2
BASE=W/'var/results/hsw-st/certinsert_eval03_lite_20261112/run01';O=BASE/'batch02_adjusted'
def rank(purpose,x):return hashlib.sha256(('2026111205|'+purpose+'|'+x).encode()).hexdigest()
