"""Audit worker receives public JSON only; deny post-import filesystem reads."""
import builtins
import ctypes
import io
import json
import os
import sys
import time
from pathlib import Path
from reference_replay import audit as replay
from temporal_reference import audit as temporal

def memory():
    class Counters(ctypes.Structure):
        _fields_=[('cb',ctypes.c_ulong),('PageFaultCount',ctypes.c_ulong),
                  ('PeakWorkingSetSize',ctypes.c_size_t),('WorkingSetSize',ctypes.c_size_t),
                  ('QuotaPeakPagedPoolUsage',ctypes.c_size_t),('QuotaPagedPoolUsage',ctypes.c_size_t),
                  ('QuotaPeakNonPagedPoolUsage',ctypes.c_size_t),('QuotaNonPagedPoolUsage',ctypes.c_size_t),
                  ('PagefileUsage',ctypes.c_size_t),('PeakPagefileUsage',ctypes.c_size_t)]
    c=Counters(); c.cb=ctypes.sizeof(c)
    ctypes.windll.psapi.GetProcessMemoryInfo(ctypes.windll.kernel32.GetCurrentProcess(),ctypes.byref(c),c.cb)
    return c.PeakWorkingSetSize

def deny(*args,**kwargs):
    raise PermissionError('audit worker may not open files, including oracle')

def main():
    request=json.loads(sys.stdin.buffer.read().decode('utf8'))
    builtins.open=deny; io.open=deny; os.open=deny; Path.open=deny
    before=time.perf_counter(); cpu=time.process_time()
    result=(replay if request['method']=='B1' else temporal)(request['public'])
    result.update(elapsed_seconds=time.perf_counter()-before,cpu_seconds=time.process_time()-cpu,
                  peak_rss_bytes=memory(),file_reads_disabled=True)
    sys.stdout.buffer.write(json.dumps(result,ensure_ascii=False).encode('utf8'))

if __name__=='__main__': main()
