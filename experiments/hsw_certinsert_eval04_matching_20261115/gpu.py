"""Use the existing EVAL-03 CUDA scorer in an isolated process."""
import json
import math
import os
import subprocess
import sys
import time


class Scorer:
    def __init__(self, root, primary, out, cuda_visible):
        self.log = (out/"scorer.stderr.log").open("a",encoding="utf-8")
        worker = root/"experiments/hsw_certinsert_eval04_b2_20261114/score_worker.py"
        runtime = root/"var/results/hsw-st/insertion_feasibility_20261109_01/run05/v3_gpu/runtime"
        model = primary/"assets/models/qwen2.5-3b-instruct-q4_k_m.gguf"
        env = os.environ.copy()
        if cuda_visible is None:
            env.pop("CUDA_VISIBLE_DEVICES",None)
        else:
            env["CUDA_VISIBLE_DEVICES"]=cuda_visible
        self.worker = subprocess.Popen(
            [sys.executable,"-S","-B","-u",str(worker),str(root),str(runtime),str(model)],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=self.log,encoding="utf-8",
            creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0),env=env,
        )
        ready = self.worker.stdout.readline()
        if not ready or not json.loads(ready).get("ready"):
            self.close()
            raise RuntimeError("SCORER_START_FAILURE")
        self.prefix = json.loads(ready)["prefix_tokens"]
        self.cache = {}
        self.seconds = 0.
        self.tokens = self.calls = 0

    def command(self, operation, texts):
        self.worker.stdin.write(json.dumps({"operation":operation,"texts":texts})+"\n")
        self.worker.stdin.flush()
        line = self.worker.stdout.readline()
        if not line:
            raise RuntimeError("SCORER_PROCESS_EXIT")
        result = json.loads(line)
        if "error" in result:
            raise RuntimeError("SCORER_"+result["error"])
        return result["result"]

    def get(self, texts, limit=None):
        start=time.perf_counter()
        missing = list(dict.fromkeys(t for t in texts if t not in self.cache))
        try:
            for i in range(0,len(missing),4):
                batch = missing[i:i+4]
                lens = self.command("tokenize",batch)
                good=[]
                for t,n in zip(batch,lens,strict=True):
                    if n+self.prefix>1024:
                        self.cache[t]=None
                    else:
                        good.append((t,n+self.prefix))
                if limit is not None:
                    deadline,token_cap=limit
                    if time.perf_counter()>deadline or self.tokens+sum(n for _,n in good)>token_cap:
                        raise TimeoutError("DYNAMIC_SCORE_LIMIT")
                if not good:
                    continue
                returned = self.command("score",[t for t,_ in good])
                for (t,_),r in zip(good,returned,strict=True):
                    assert math.isfinite(r["log_probability"])
                    self.cache[t]=r["log_probability"]
                    self.tokens+=r["input_tokens"]
                    self.calls+=1
            return [self.cache[t] for t in texts]
        finally:
            self.seconds+=time.perf_counter()-start

    def close(self):
        try:
            if self.worker.poll() is None:
                try:
                    self.worker.stdin.write('{"operation":"stop","texts":[]}\n')
                    self.worker.stdin.close()
                except OSError:
                    pass
                try:
                    self.worker.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    self.worker.terminate()
                    self.worker.wait(timeout=10)
        finally:
            self.log.close()
