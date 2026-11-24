import json,re,subprocess,time,os
from pathlib import Path
def read(p): return Path(p).read_text()
def snapshot():
 g=subprocess.check_output(["nvidia-smi","--query-gpu=utilization.gpu,memory.used,memory.total","--format=csv,noheader,nounits"],text=True).strip().split(",")
 cpu=list(map(int,read("/proc/stat").splitlines()[0].split()[1:9]))
 mem=int(re.search(r"MemAvailable:\s+(\d+)",read("/proc/meminfo"))[1])
 io={f[2]:[int(f[5])*512,int(f[9])*512] for f in map(str.split,read("/proc/diskstats").splitlines()) if len(f)>10}
 path="/root/autodl-tmp"
 stat=os.statvfs(path)
 net={l.split(":")[0].strip():[int(l.split(":")[1].split()[i]) for i in (0,8)] for l in read("/proc/net/dev").splitlines()[2:] if not l.lstrip().startswith("lo:")}
 return dict(epoch=time.time(),gpu_util=int(g[0]),vram_mib=int(g[1]),vram_total_mib=int(g[2]),cpu_total=sum(cpu),cpu_idle=sum(cpu[3:5]),available_ram_kib=mem,disk=io,network=net,data_free_bytes=stat.f_bavail*stat.f_frsize)
t=time.monotonic()
for i in range(61):
 time.sleep(max(0,t+i-time.monotonic()))
 print(json.dumps(snapshot()),flush=True)
