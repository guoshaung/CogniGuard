"""Score exact contexts with the frozen Qwen 3B weights and CPU bridge."""
import json
import subprocess
import sys
from functools import lru_cache

from shared import HERE


class CPUScore:
    def __init__(self, log_path):
        self.stderr = log_path.open("x",encoding="utf-8")
        self.worker = subprocess.Popen(
            [sys.executable,"-S","-B","-u",str(HERE/"score_cpu_worker.py")],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=self.stderr,encoding="utf-8",
            creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0),
        )
        ready = self.worker.stdout.readline()
        if not ready or not json.loads(ready).get("ready"):
            self.close()
            raise RuntimeError("CPU scorer initialization failed")
        self.tokens = 0
        self.calls = 0
        self.get = lru_cache(maxsize=30_000)(self._get)

    def _get(self, text):
        self.worker.stdin.write(json.dumps({"text":text})+"\n")
        self.worker.stdin.flush()
        line = self.worker.stdout.readline()
        if not line:
            raise RuntimeError("CPU scorer exited")
        data = json.loads(line)
        if "overlength" in data:
            return None
        self.tokens += data["input_tokens"]
        self.calls += 1
        return data["log_probability"]

    def close(self):
        try:
            if self.worker.poll() is None:
                try:
                    self.worker.stdin.write('{"stop":true}\n')
                    self.worker.stdin.close()
                except OSError:
                    pass
                self.worker.wait(timeout=30)
        finally:
            self.stderr.close()
