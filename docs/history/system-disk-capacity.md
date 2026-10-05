# Larger demo system disk

[History](README.md) · [Demo guide](../guides/demo.md)

The OF816 demo's read-only system disk now defaults to 720 KiB: 2,880 sectors
of 256 bytes, equivalent to 80 tracks, two sides and 18 sectors per track.
`--system-kib 360` selects 1,440 sectors. `--sector-bytes 128` instead uses
5,760 or 2,880 sectors for the same respective capacities. The disposable
writable WORK: disk remains 720 sectors of 128 bytes (90 KiB). The
generated mount descriptor and demo manifest record the actual system geometry.

The MyDOS image builder now writes the extended VTOC needed for these larger
volumes and uses full 16-bit file links when sectors can exceed 1,023. Its
720-sector DOS 2-compatible image remains available for WORK: and existing
fixtures. The SDFS producer continues to use the independent Altirra
reference formatter and reader.

Development checks covered 340 host tests, complete byte-for-byte SDFS
extraction and allocation audits for both capacities at 128 and 256 bytes per
sector, and MyDOS byte-for-byte extraction and allocation audits for the same
geometries. A MyDOS host test read back a 153,600-byte file whose chain crosses
sector 1,023. Both final packages completed the physical OF816 shell/prime
and file-command walkthrough with a 2,880 × 256-byte SYS: disk and a
720 × 128-byte WORK: disk on the pinned AltirraOS ROM and emulator. The earlier
5,760 × 128-byte SYS: packages passed the same walkthrough. The 360 KiB
variants have host checks but no packaged physical walkthrough in this slice.
Both final WORK: images passed a post-walkthrough allocation audit.

An all-256-byte MyDOS trial timed out during `HELLO | TEE WORK:LOG.TXT` after
reserving a sector on WORK:. The final build retains the previously exercised
128-byte WORK: geometry. This is development-tier evidence, not release
qualification or a claim about physical drive compatibility.

The executable source and memory profile are unchanged. Compared with the
preceding shell-editing demo, both packaged builds reserve **0 additional
fixed bank-zero bytes and 0 additional bytes per Task**, including guards,
alignment and unused capacity. The idle reservation is unchanged.
