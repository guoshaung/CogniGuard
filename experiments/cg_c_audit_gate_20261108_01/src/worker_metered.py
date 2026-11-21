"""Telemetry-only correction. Frozen worker/algorithms remain unchanged."""
import builtins
import ctypes
from ctypes import wintypes
import worker

def memory():
    class Counters(ctypes.Structure):
        _fields_=[('cb',wintypes.DWORD),('PageFaultCount',wintypes.DWORD),
                  ('PeakWorkingSetSize',ctypes.c_size_t),('WorkingSetSize',ctypes.c_size_t),
                  ('QuotaPeakPagedPoolUsage',ctypes.c_size_t),('QuotaPagedPoolUsage',ctypes.c_size_t),
                  ('QuotaPeakNonPagedPoolUsage',ctypes.c_size_t),('QuotaNonPagedPoolUsage',ctypes.c_size_t),
                  ('PagefileUsage',ctypes.c_size_t),('PeakPagefileUsage',ctypes.c_size_t)]
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.GetCurrentProcess.restype=wintypes.HANDLE
    psapi=ctypes.WinDLL('psapi',use_last_error=True)
    psapi.GetProcessMemoryInfo.argtypes=[wintypes.HANDLE,ctypes.POINTER(Counters),wintypes.DWORD]
    psapi.GetProcessMemoryInfo.restype=wintypes.BOOL
    c=Counters(); c.cb=ctypes.sizeof(c)
    if not psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(),ctypes.byref(c),c.cb):
        raise ctypes.WinError(ctypes.get_last_error())
    return c.PeakWorkingSetSize

def wrap(fn):
    def run(x):
        denied=False
        try: builtins.open('../oracle/forbidden_probe.json','r')
        except PermissionError: denied=True
        if not denied: raise AssertionError('ORACLE_FILE_ACCESS_NOT_BLOCKED')
        r=fn(x); r['oracle_access_probe_denied']=denied
        return r
    return run

worker.memory=memory
worker.replay=wrap(worker.replay)
worker.temporal=wrap(worker.temporal)
if __name__=='__main__': worker.main()
