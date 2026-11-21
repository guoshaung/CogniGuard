"""Wrap the unused grouped-test AES key for this Windows account."""
import ctypes
import sys
from ctypes import wintypes
from pathlib import Path

class Blob(ctypes.Structure):
    _fields_ = [('size', wintypes.DWORD), ('data', ctypes.POINTER(ctypes.c_ubyte))]

key = bytes.fromhex(sys.stdin.readline().strip())
assert len(key) == 32
buf = (ctypes.c_ubyte * len(key)).from_buffer_copy(key)
source = Blob(len(key), ctypes.cast(buf, ctypes.POINTER(ctypes.c_ubyte)))
wrapped = Blob()
kernel = ctypes.windll.kernel32
kernel.LocalFree.argtypes = [ctypes.c_void_p]
kernel.LocalFree.restype = ctypes.c_void_p
assert ctypes.windll.crypt32.CryptProtectData(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(wrapped))
data = ctypes.string_at(wrapped.data, wrapped.size)
kernel.LocalFree(wrapped.data)
with Path(__file__).with_name('r48b_quality_key.dpapi').open('xb') as f:
    f.write(data)
print('DPAPI_WRAPPED_KEY_SAVED')
