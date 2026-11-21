"""After blind evaluation, wrap the transient AES key with Windows user DPAPI."""
import ctypes
import sys
from ctypes import wintypes
from pathlib import Path

class Blob(ctypes.Structure):
    _fields_ = [('size', wintypes.DWORD), ('data', ctypes.POINTER(ctypes.c_ubyte))]

def blob(data):
    buf = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
    return Blob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_ubyte))), buf

key = bytes.fromhex(sys.stdin.readline().strip())
assert len(key) == 32
value, keep = blob(key)
wrapped = Blob()
crypt = ctypes.windll.crypt32
kernel = ctypes.windll.kernel32
kernel.LocalFree.argtypes = [ctypes.c_void_p]
kernel.LocalFree.restype = ctypes.c_void_p
assert crypt.CryptProtectData(ctypes.byref(value), None, None, None, None, 1, ctypes.byref(wrapped))
data = ctypes.string_at(wrapped.data, wrapped.size)
kernel.LocalFree(wrapped.data)
out = Path(__file__).with_name('r48b_blind_key.dpapi')
with out.open('xb') as f:
    f.write(data)
print('DPAPI_WRAPPED_KEY_SAVED')
