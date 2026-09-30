"""Build/use the pinned independent Altirra SDFS producer and reader."""
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT/'build/altirra-irq-fix'
FILES = {
    'src/ATIO/source/diskfssdx2.cpp': '6f2cc1d700c3c1bc674b954f32f7ecfcf381b4d667b6fc4d84b3367070e59fe8',
    'src/ATIO/source/diskfssdx2util.cpp': '3e1d7e63edbf01cb26dcfad403741ffb31fa479d25292c289068982b2a5a7f81',
}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def reference(output=ROOT/'build/sdfs-reference'):
    output.mkdir(parents=True, exist_ok=True)
    for name, expected in FILES.items():
        if digest(SOURCE/name) != expected:
            raise ValueError('Changed independent SDFS source: '+name)
    libraries = [SOURCE/f'build/latency/src/{name}/lib{name}.a'
                 for name in ('ATIO', 'ATCore', 'system')]
    source = ROOT/'tools/sdfs_reference.cpp'
    inputs = {str(p.relative_to(ROOT)): digest(p) for p in [source, *libraries]}
    binary, stamp = output/'sdfs-reference', output/'inputs.json'
    if not binary.exists() or not stamp.exists() or json.loads(stamp.read_text()) != inputs:
        subprocess.run(['c++', '-std=c++23', '-O2', '-DAT_SDL3_PORTABLE=1', '-DVD_OS_MACOS=1',
                        '-I'+str(SOURCE/'src/compat'), '-I'+str(SOURCE/'src/h'), str(source),
                        *map(str, libraries), '-lz', '-framework', 'CoreFoundation', '-o', str(binary)], check=True)
        stamp.write_text(json.dumps(inputs, indent=2)+'\n')
    return binary


def make(image, directory, sectors=720, sector_bytes=128):
    subprocess.run([str(reference()), 'make', str(image), str(directory), str(sectors), str(sector_bytes)], check=True)


def extract(image, directory):
    subprocess.run([str(reference()), 'extract', str(image), str(directory)], check=True)


def verify(image, expected, output):
    """Read back each packaged byte independently of the target implementation."""
    extract(image, output)
    actual = {p.relative_to(output).as_posix(): p.read_bytes()
              for p in output.rglob('*') if p.is_file()}
    if actual != expected:
        raise ValueError('Independent SDFS read-back differs from source files')
    return {name: hashlib.sha256(data).hexdigest() for name, data in actual.items()}
