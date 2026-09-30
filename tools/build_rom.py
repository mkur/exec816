#!/usr/bin/env python3
"""Build the hash-pinned AltirraOS 65816 ROM from unmodified upstream source."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
PIN = json.loads((ROOT / "toolchain/altirra.json").read_text())["rom"]


def verify(path, digest):
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != digest:
        raise RuntimeError(f"SHA-256 mismatch for {path}: {actual}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, help="Existing Altirra-4.40-src.7z; otherwise download it")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "build/firmware")
    args = parser.parse_args()
    archiver = shutil.which("7zz") or shutil.which("7z")
    mads = shutil.which("mads")
    if not archiver or not mads:
        raise RuntimeError("Building the ROM requires MADS and 7zz (or 7z) on PATH")
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="exec816-rom-") as temporary:
        temp = Path(temporary)
        archive = args.archive.resolve() if args.archive else temp / "source.7z"
        if not args.archive:
            with urllib.request.urlopen(PIN["source_url"], timeout=30) as response, archive.open("wb") as dest:
                shutil.copyfileobj(response, dest)
        verify(archive, PIN["source_archive_sha256"])
        subprocess.run([archiver, "x", str(archive), "src/Kernel/source/*", "-r", "-y", f"-o{temp}"],
                       check=True, stdout=subprocess.DEVNULL, timeout=30)
        source = temp / "src/Kernel/source"
        rom = temp / "altirraos-816.rom"
        subprocess.run([mads, str(source / "main.xasm"), "-d:_KERNEL_XLXE=1", "-d:_KERNEL_816=1",
                        "-s", "-p", f"-i:{source / 'Shared'}", "-b:$c000", f"-o:{rom}",
                        f"-l:{output / 'altirraos-816.lst'}", f"-t:{output / 'altirraos-816.lab'}"],
                       check=True, cwd=source.parent, timeout=30)
        verify(rom, PIN["sha256"])
        if rom.stat().st_size != PIN["bytes"]:
            raise RuntimeError("Unexpected ROM size")
        shutil.copyfile(rom, output / rom.name)
        # Preserve upstream's copyright/permission notice with the generated ROM.
        header = (source / "main.xasm").read_text().splitlines()[:12]
        (output / "ALTIRRAOS-LICENSE.txt").write_text("\n".join(header) + "\n")
        provenance = {**PIN, "source_modified": False,
                      "defines": {"_KERNEL_XLXE": 1, "_KERNEL_816": 1},
                      "mads_options": ["-s", "-p", "-b:$c000"]}
        (output / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
    print(f"Verified ROM: {output / 'altirraos-816.rom'}")


if __name__ == "__main__":
    main()
