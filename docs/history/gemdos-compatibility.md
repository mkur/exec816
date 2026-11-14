# GEMDOS source compatibility delivery

[History index](README.md) · [Source contract](../reference/gemdos-compatibility.md) ·
[Design](../plans/gemdos-compatibility-design.md) ·
[Implementation plan](../plans/gemdos-compatibility-implementation-plan.md)

The shared source library now supplies QED's generic file/allocation calls,
runtime-aware termination and the narrow Fcntl(FSTAT) profile. Native DOS owns
ExamineFH; the common C runtime retains the sole descriptor table and allocation
chain. DOS revision 16 / APP ABI 40 are current. Loaded native COMMAND and SDX
FILELENG consumer migrations remain separate.

The [GC1 evidence](../development/gemdos-compatibility-gc1.json) covers wrapper
extraction, raw C layout/returns, LONG bank-crossing transfers, exhausted
descriptors, consumed Close and two independent Images with repeated execution.
[GC2](../development/gemdos-compatibility-gc2.json) covers native exact metadata
on RAM/SDFS/MyDOS, inherited positions, and cancellation during measurement and
before publication. [GC3](../development/gemdos-compatibility-gc3.json) covers
FSTAT output, scratch failure, unsupported metadata and pending transfer errors.

## Consumer acceptance

[GC4 evidence](../development/gemdos-compatibility-gc4.json) records an independently
written MGVIEW-style loader/model, not a port of its GUI. It executes the same
Open/FSTAT/Malloc/exact-Read/index-allocation structure. A 65,519-byte document
and 16,380-pointer line index succeed; the next larger sizes are rejected.
CR/LF handling, empty input, short reads, scratch/text/index allocation failure,
terminal Close failure, two Images and repeated execution preserve ownership.
An independent closed-ATR audit verifies the saved document bytes.

Routine graphical acceptance uses the small Counter: two private instances tick,
physical close works, both restart, and stop before the first C instruction
retires correctly. Five executions collect with guards and ownership intact.
The tested Counter APP matches the rebuilt distribution byte for byte. QED's
file regression and 41 transactional-save cases ran once for this migration,
including independent saved-file/backup bytes. Follow-up testing should stay
with small probes and Counter unless changed behavior requires QED coverage.

The demo was rebuilt with build_demo.py, OF816, the standard five-second autoboot,
SYS/WORK, MD5/ARC/EDX and separate QED media. Its ZIP/SYS audit passes for 74
files; all thirteen disk C APPs and the resident provider use ABI 40. The ATR
boot reached native handoff with the 249-frame countdown and intact reader
guards. A broader About-menu walkthrough did not complete on either the previous
ABI 39 demo or this package. It is not part of the Counter acceptance or a
hosted-system qualification claim; GUI menu code is unchanged in this slice.

Host checks pass: 715 tests with four historical skips; final focused C image and
runtime contract checks add eleven tests. Native behavioral builds are optimized;
small raw C probes cover the interface boundaries. The records pin actual
compiler, firmware and emulator inputs. This is development-tier evidence.

## Memory

Reserved bank-zero change is **0 fixed, 0 root/kernel, 0 idle and 0 per public
Task bytes**, including guards, alignment and unused capacity. The production
regions, Task pools, runtime reservations and bank-zero budget match the prior
mapped-raster demo exactly. No VRAM or CPU aperture reservation changes.

The native C binding adds 25 emitted code bytes and two BSS bytes inside the
existing provider reservation. FSTAT adds 323 selected C code bytes, a 52-byte
local result and 280 temporary upper heap bytes including the runtime prefix
and rounding. Descriptor and allocation bookkeeping are reused. Selected loader
stack observations leave at least 355 bytes above the existing application
floor; these samples are not a worst-case bound.
