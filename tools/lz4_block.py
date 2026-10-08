"""Raw LZ4 host blocks; high-compression encoding uses the same decoder."""
import ctypes
import ctypes.util
import os
from pathlib import Path
import shutil


class LZ4:
    def __init__(self, path=None):
        path = path or os.environ.get('EXEC816_LZ4_LIBRARY') or ctypes.util.find_library('lz4')
        if path is None:
            executable = shutil.which('lz4')
            if executable:
                directory = Path(executable).resolve().parent.parent / 'lib'
                path = next((str(p) for name in ('liblz4.dylib', 'liblz4.so')
                             if (p := directory / name).exists()), None)
        if path is None:
            raise ValueError('Install liblz4 or set EXEC816_LZ4_LIBRARY')
        self.lib = ctypes.CDLL(str(path))
        self.path = str(Path(self.lib._name).resolve()) if Path(self.lib._name).exists() else self.lib._name
        self.lib.LZ4_versionString.restype = ctypes.c_char_p
        self.version = self.lib.LZ4_versionString().decode()
        self.lib.LZ4_compressBound.argtypes = [ctypes.c_int]
        self.lib.LZ4_compress_default.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
                                                ctypes.c_int, ctypes.c_int]
        self.lib.LZ4_compress_HC.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
                                           ctypes.c_int, ctypes.c_int, ctypes.c_int]
        self.lib.LZ4_decompress_safe.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
                                               ctypes.c_int, ctypes.c_int]

    def compress(self, data, high=True):
        output = ctypes.create_string_buffer(self.lib.LZ4_compressBound(len(data)))
        if high:
            count = self.lib.LZ4_compress_HC(data, output, len(data), len(output), 12)
        else:
            count = self.lib.LZ4_compress_default(data, output, len(data), len(output))
        if count <= 0:
            raise ValueError('LZ4 compression failed')
        return output.raw[:count]

    def decompress(self, data, size):
        output = ctypes.create_string_buffer(size)
        count = self.lib.LZ4_decompress_safe(data, output, len(data), size)
        if count != size:
            raise ValueError('LZ4 decompressed length mismatch')
        return output.raw
