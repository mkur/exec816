# Larger demo system disk

[History](README.md) · [Demo guide](../guides/demo.md)

The OF816 demo's read-only system disk now defaults to 720 KiB. Its default
SDFS image has 5,760 sectors of 128 bytes instead of 720; `--system-kib 360`
selects 2,880 sectors. The 256-byte option uses 2,880 or 1,440 sectors for
the same respective capacities. The disposable writable WORK: disk remains
720 sectors at the selected sector size. The generated mount descriptor and
demo manifest record the actual system geometry.

The MyDOS image builder now writes the extended VTOC needed for these larger
volumes and uses full 16-bit file links when sectors can exceed 1,023. Its
720-sector DOS 2-compatible image remains available for WORK: and existing
fixtures. The SDFS producer continues to use the independent Altirra
reference formatter and reader.

Development checks covered 340 host tests, complete byte-for-byte SDFS
extraction and allocation audits for both capacities at 128 and 256 bytes per
sector, and MyDOS byte-for-byte extraction and allocation audits for the same
geometries. A MyDOS host test read back a 153,600-byte file whose chain crosses
sector 1,023. The packaged 720 KiB SDFS and MyDOS demos each completed the
physical OF816 shell/prime and file-command walkthrough with the pinned
AltirraOS ROM and emulator. The 360 KiB and 256-byte sector variants have
host checks but no packaged physical walkthrough in this slice. This is
development-tier evidence, not release qualification.

The executable source and memory profile are unchanged. Compared with the
preceding shell-editing demo, both packaged builds reserve **0 additional
fixed bank-zero bytes and 0 additional bytes per Task**, including guards,
alignment and unused capacity. The idle reservation is unchanged.
