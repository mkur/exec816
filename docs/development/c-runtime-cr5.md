# CR5 — GemARC and matching delivery

[Implementation plan](../plans/c-runtime-implementation-plan.md) ·
[Current C runtime](../reference/c-runtime.md) · [GemARC guide](../guides/gemarc.md)

CR5 passes the development gate. The [reconciled record](c-runtime-cr5.json)
binds emitted-code checks, artifact hashes, source materials and selected
package acceptance. No full hosted-system qualification is claimed.

GemARC uses the same allocation, arguments, descriptors, FILE implementation and
phased entry as QED. Its pinned donor is
`0692b5519112dcde1f29f061ebcebe7a095aaf60`; preparation verifies 24 originals,
applies ordered patches outside the donor checkout and generates the resource.
APP ABI 32 adds the generic C `SetFileDate` binding over the existing native DOS
operation. Runtime contract 1 is unchanged. The provider and all APPs are rebuilt.

The archive gate independently checks methods 1–4, 8 and 9, LZW growth/clear,
empty files, CRC, truncation, 512-member and 64-source limits, native filenames,
and unsupported methods 5–7. The original donor's read-error publication and
replacement-rename data loss are reproduced against its unmodified engine.
The port distinguishes EOF from read failure, checks terminal Close, uses
exclusive same-parent temporary names and preserves recovery copies if
publication fails. It promises neither atomic replacement nor crash durability.

Optimized emitted-code checks cover actual native files and full descriptor
identities, short writes, consumed Close failures, rename failure, cancellation,
all nine startup allocation failures, directory errors, read-only media and
real disk exhaustion. The accepted full-disk case starts from an independently
audited 360 KiB SDFS volume with three free sectors, consumes the remainder
through native writes and checks that the original archive survives. Filling
larger volumes from empty exceeded the development runner's time bound; those
runs are not counted as passes. Timestamp probes execute both C optimization
modes and raw native NIR, with independent on-disk metadata checks.

The 27-member GUI probe covers physical cursor input and Select All, repeated
launches, two concurrent instances, cooperative Stop and exact heap restoration.
A separate controller runs production QED, GemARC and Counter together while
checking computing/timer progress and heap restoration. The production desktop
uses another large Task pool and therefore admits one GemARC or QED instance at
a time. Its admission limit is retained. Atari cursor chords carry Ctrl, so the
port decodes navigation before its letter shortcuts.

QED is rebuilt on the same runtime. Its frame ledger resolves the fixed phase
callbacks through their actual object sections, including the two different
private functions called `finish`, and verifies that QED registers no atexit
handlers. The conditional emitted-source bound is 599 bytes, with an 809-byte
margin under its declared 2,560-byte admission after the existing continuation,
interrupt and safety allowances. This is not a general whole-system stack proof.
Unchanged supplied objects reproduce the production APP byte for byte; replacing
a retained CF-Lib object produces a distinct APP, with all 61 admitted banks
independently relinked in both cases.

Additional reserved bank-zero bytes are **0 fixed, 0 root/kernel, 0 per public
Task and 0 idle**, including guards, alignment and spare capacity. Task pools,
direct pages and interrupt reservations are unchanged. GemARC's upper-memory
figures are 41,785 code bytes, 141 initialized bytes, 3,970 BSS bytes, a
69,647-byte relocation span and 135,184 bytes of rounded loader backing.
The APP is 49,694 bytes and declares a 2,560-byte stack. Its nine persistent
buffers request 84,610 bytes, or 84,760 with prefixes/rounding. The resource is
2,674 bytes. These are separate charges; GUI resources, FILEs and argv add their
actual owned allocations. QED is 137,266 serialized bytes with a 184,610-byte
span and 250,152 bytes of rounded backing, keeping its existing stack admission.

The demo is built by `tools/build_demo.py --basic-workbench --qed
--release-compiler`, including OF816 and five-second autoboot, a combined
writable SYS/WORK ATR, matching XEX/cartridges/ROM, MD5/ARC/EDX and notices.
QED's ATR and both corresponding-source packages remain separate from the
small boot ZIP. The source identity is clean revision
`ab5b88f3585b1a4895f63be6d8fc0e20576ed043`; the record binds later observer fixes
separately. Native code and APPs have not been changed by those observer fixes.

The exact extracted ZIP cold-boots through the ROM reader and OF816 in 249
countdown frames. Its native-entry checkpoint is verified against the emitted
image and used for subsequent physical walks. Production QED and the changed
CF-Lib diagnostic each pass saves, backups, reopen, collection and clean EXIT.
The GemARC session passes selection, extraction, create/add/replace, relaunch,
Escape cancellation and close during I/O beside the desktop. It then passes
BASIC open/run/input/cancel/save/build, the standalone output program, MD5,
legacy ARC, native HELLO and EXIT.

The post-execution GemARC audit initially expected LF in the sample member;
the current utility fixture contains ATASCII `$9B`. The completed execution log
and exact observer are preserved. A separate reconciliation corrects that host
oracle, independently extracts both ARC files with The Unarchiver and audits
the SDFS bytes, including the saved BASIC program and cancelled Add's unchanged
archive. The transient return dictionary from the completed walk was not saved
before that host assertion; the record identifies this evidence limit instead
of inventing runtime counters. Future runs save an execution receipt first.
