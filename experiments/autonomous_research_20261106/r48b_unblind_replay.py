"""Replay deblinding on the same Windows user without printing the key."""
import ctypes
import subprocess
import sys
from ctypes import wintypes
from pathlib import Path

class Blob(ctypes.Structure):
    _fields_ = [('size', wintypes.DWORD), ('data', ctypes.POINTER(ctypes.c_ubyte))]

root = Path(__file__).parent
payload = (root / 'r48b_blind_key.dpapi').read_bytes()
buf = (ctypes.c_ubyte * len(payload)).from_buffer_copy(payload)
encrypted = Blob(len(payload), ctypes.cast(buf, ctypes.POINTER(ctypes.c_ubyte)))
decrypted = Blob()
kernel = ctypes.windll.kernel32
kernel.LocalFree.argtypes = [ctypes.c_void_p]
kernel.LocalFree.restype = ctypes.c_void_p
ok = ctypes.windll.crypt32.CryptUnprotectData(ctypes.byref(encrypted), None, None, None, None, 1, ctypes.byref(decrypted))
if not ok:
    raise RuntimeError('Windows user DPAPI could not unwrap the key')
key = ctypes.string_at(decrypted.data, decrypted.size)
kernel.LocalFree(decrypted.data)
assert len(key) == 32
result = subprocess.run([sys.executable, '-B', str(root / 'r48b_blind_deblind.py')],
                        input=key.hex() + '\n', text=True, capture_output=True, check=True)
print(result.stdout, end='')
