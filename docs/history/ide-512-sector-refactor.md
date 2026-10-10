# IDE 512-byte sector refactor development record

[Implementation plan](../plans/ide-512-sector-refactor-plan.md)

## I512-0 — Independent media

The pinned Altirra SDFS producer now creates uniform 512-byte ATR staging
volumes with a one-sector boot region. Identity normalization preserves the
complete first sector. A shared ATR sector view supports the existing floppy
layout and uniform sectors; MyDOS still rejects 512-byte media.

Development checks: two IDE image-builder cases and five existing allocation
audit cases pass. The new case independently extracts a file extending beyond
one 254-entry map page, checks header geometry and audits allocation. The
pinned real IDE Plus BIOS lists distinct SYS and WORK contents on the new
512-byte APT. No XEX launch was attempted in this slice.

Evidence: `build/development/ide-512/i512-0/`, including producer hashes,
raw image/mapping and `bios/results.json` with the BIOS/ROM/emulator pin and
directory screenshots. These are development artifacts, not distribution files.
Runtime bank-zero reservation change: **0 fixed, 0 per-Task and 0 idle bytes**,
including guards, alignment and unused capacity; this slice changes host tools.

## I512-1 — Shared sector storage

BLOCKIO's scratch sector and the SDFS map are now 512 bytes. The shared mutation
workspace has four 512-byte sector arrays; its emitted size is 2,214 bytes,
an increase of 1,024. Total shared buffer payload growth is **1,536 upper-RAM
bytes**, without per-file buffers or a larger cache allocation. Cache tags use
zero-based pieces; a hit requires all one, two or four 128-byte pieces before
copying into the destination. Short sectors continue using every cache set.

Development checks pass: raw/optimized emitted record access and far copy,
optimized block adapter fixture (including the existing full 64 KiB working
set, disabled cache and errors), all four independently missing pieces of a
512-byte sector, crossing destination guards, invalidation and cache-metadata
allocation rollback. Evidence is under `build/development/ide-512/i512-1/`.
The pinned compiler revision is unchanged; the cache runner uses its release
host binary. Runtime bank-zero reservation change remains **0 fixed,
0 per-Task and 0 idle bytes**, including guards/alignment/unused capacity.
