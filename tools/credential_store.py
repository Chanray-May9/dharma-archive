import argparse
import ctypes
from ctypes import wintypes
import json
from pathlib import Path
import sys


class DataBlob(ctypes.Structure):
    _fields_ = [('size', wintypes.DWORD), ('data', ctypes.POINTER(ctypes.c_ubyte))]


def transform(content, decrypt=False):
    if sys.platform != 'win32':
        raise RuntimeError('This credential helper uses Windows user-bound DPAPI')
    buffer = ctypes.create_string_buffer(content)
    source = DataBlob(len(content), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    target = DataBlob()
    crypt = ctypes.WinDLL('crypt32', use_last_error=True)
    crypt.CryptProtectData.argtypes = [ctypes.POINTER(DataBlob), wintypes.LPCWSTR, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(DataBlob)]
    crypt.CryptProtectData.restype = wintypes.BOOL
    crypt.CryptUnprotectData.argtypes = [ctypes.POINTER(DataBlob), ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(DataBlob)]
    crypt.CryptUnprotectData.restype = wintypes.BOOL
    if decrypt:
        success = crypt.CryptUnprotectData(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target))
    else:
        success = crypt.CryptProtectData(ctypes.byref(source), 'Dharma archive credential', None, None, None, 1, ctypes.byref(target))
    if not success:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return ctypes.string_at(target.data, target.size)
    finally:
        free = ctypes.windll.kernel32.LocalFree
        free.argtypes = [ctypes.c_void_p]
        free.restype = ctypes.c_void_p
        free(target.data)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--file', required=True, type=Path)
    parser.add_argument('action', choices=['save', 'store', 'get', 'erase'])
    args = parser.parse_args()
    if args.action == 'save':
        content = json.load(sys.stdin)
        args.file.parent.mkdir(parents=True, exist_ok=True)
        args.file.write_bytes(transform(json.dumps(content).encode('utf-8')))
        print('Credential encrypted with current Windows user DPAPI')
    elif args.action == 'get':
        query = dict(line.rstrip('\n').split('=', 1) for line in sys.stdin if '=' in line)
        credential = json.loads(transform(args.file.read_bytes(), decrypt=True))
        if query.get('host') == credential['host']:
            sys.stdout.write(f'username={credential["username"]}\npassword={credential["token"]}\n\n')
