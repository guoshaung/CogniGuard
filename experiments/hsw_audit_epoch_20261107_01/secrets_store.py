"""Windows current-user DPAPI for local experimental keys. No secrets printed."""
import ctypes as C
from ctypes import wintypes as W
import json
from pathlib import Path
class Blob(C.Structure):_fields_=[('size',W.DWORD),('data',C.POINTER(C.c_ubyte))]
def _blob(b):
 a=(C.c_ubyte*len(b)).from_buffer_copy(b);return Blob(len(b),a),a
def _transform(data,protect):
 inp,keep=_blob(data);out=Blob();lib=C.WinDLL('crypt32',use_last_error=True)
 fn=lib.CryptProtectData if protect else lib.CryptUnprotectData
 fn.argtypes=[C.POINTER(Blob),C.c_void_p,C.c_void_p,C.c_void_p,C.c_void_p,W.DWORD,C.POINTER(Blob)];fn.restype=W.BOOL
 if not fn(C.byref(inp),None,None,None,None,1,C.byref(out)):raise C.WinError(C.get_last_error())
 try:return C.string_at(out.data,out.size)
 finally:
  kernel=C.WinDLL('kernel32');kernel.LocalFree.argtypes=[C.c_void_p];kernel.LocalFree(C.cast(out.data,C.c_void_p))
def store(path:Path,obj):
 with path.open('xb') as f:f.write(_transform(json.dumps(obj,separators=(',',':')).encode(),True))
def read(path:Path):return json.loads(_transform(path.read_bytes(),False))
