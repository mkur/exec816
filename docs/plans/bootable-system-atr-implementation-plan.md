# Bootable system ATR implementation plan

Status: implemented, 22 October 2026, at the development tier. Implements the
[design](bootable-system-atr-design.md) in five executable slices. See the
[execution record](../history/bootable-system-atr.md) and
[frozen evidence](../development/bootable-system-atr.json). Changes remain
uncommitted until requested. Use the
[platform contract](../reference/platform.md) and development tier of the
[testing policy](../contributing/testing.md).

## BA0 — Describe and construct boot media

Define generated boot layout/locator constants and a first-stage ROM loader.
Build an independently validated SDFS/256 ATR with an ordinary contiguous
BOOT.LDR file and a byte-exact EXEC816.XEX. Patch only defined boot fields/code,
protect boot files and verify allocation and capacity. Prove live-reader/XEX/
OF816 disjointness and report temporary and runtime bank-zero reservations.

Acceptance: host image read-back, locator/allocation and overlap rejection;
emitted first-stage loading from ROM with no external executable hook.

## BA1 — Stream XEX through OF816 to native entry

Implement bounded root-directory/sector-map reads, 24-bit file positions and
ordinary XEX segment/INITAD/RUNAD handling in the boot-only arena. Preserve
partially consumed sectors and OS context through callbacks. Keep firmware I/O
quiescent at each callback and retire the reader before native entry. Bound
failure/cancellation and report ROM-screen errors.

Acceptance: emitted cold disk boot, five-second and manual OF816 paths, native
payload bytes, guards and settings; fragmented/map-crossing files, large input,
truncated/cyclic/invalid records and transport failure before native entry.

## BA2 — Integrate one writable volume

Add --bootable-atr to build_demo.py. Select 8,192 SDFS/256 sectors and one writable
D1 system mount; install WORK: -> SYS:WORK before desktop/workspace use. Build
OF816 before inserting its final XEX, then finalize media hashes without an
executable/disk hash cycle. Package one ATR, matching recovery XEX, pinned ROM,
guide, notices and checksums. Launch a persistent writable copy as a disk image.

Acceptance: a matching native shell/desktop reaches SYS with no D8, one physical
disk mount and three ordinary assigns; launcher and ZIP contents/checksums agree.
Existing external-XEX build selections remain usable.

## BA3 — Exercise persistence and actual FujiNet transport

Cold-boot the exact extracted package. Load commands/apps, save BASIC source and
settings, exercise copy/rename/delete and cold-boot the modified disk. Check
read-only/disk-full behavior, intact boot files and normal final EXIT. Repeat
the core boot/save/reboot path through the local FujiNet-PC ATR/SIO transport,
recording actual firmware and machine configuration. Keep hardware qualification
separate; explicitly record any unavailable transport instead of claiming it.

Acceptance: persisted bytes read independently, repeatable boot and native SIO
handoff, bounded failures, intact context/guards and settled ownership. Use
focused deeper interrupt/transport cases where this new boundary requires them.

## BA4 — Freeze delivery and documentation

Update current boot/volume contracts, guide, design status and indices. Record
source/toolchain/ROM/emulator/firmware/artifact hashes, executed development
scope, memory accounting and remaining limits. Refresh the demo through the
normal builder and corresponding-source archive, checking the final packaged
bytes rather than substituting an earlier test image.

Acceptance: host checks, affected emitted tests, documentation links, clean diff
formatting, extracted package audit and available source rebuild checks. No
release or physical-hardware qualification claim follows from this delivery.

## Resource gate for every slice

Target zero new fixed/root/kernel/per-public-Task/idle runtime bank-zero bytes,
including guards, alignment and unused capacity. Initial boot-only claims are
$3000–$317F (384 bytes) and $4000–$5FFF (8,192 bytes), both over existing Task
storage before it becomes live. Record their phase union, including OF816's
actual borrowed ranges, and reject any live overlap. Never weaken the MEMLO
guard or use firmware bank $01 to make the loader fit. Add no resident Task,
private kernel operation or duplicate runtime filesystem implementation.

## Delivered slices

| Slice | Result | Reserved bank-zero change |
| --- | --- | --- |
| BA0 | Generated locator, first stage, protected allocated files and independent media/layout audit | +8,192 loading-phase union bytes; 0 runtime bytes |
| BA1 | Streaming reader, repeated INITAD/OF816, native bytes/context and visible bounded failures | 0 additional bytes beyond BA0 |
| BA2 | One writable D1, ordinary WORK assign, builder/refresh/launcher and one-ATR ZIP | 0 |
| BA3 | Final FujiNet-PC cold boot/save/manual reboot, persisted source/preferences, full/read-only failures and EXIT | 0 |
| BA4 | Current contracts, guides, hashes, delivery audit and corresponding-source rebuild | 0 |

Every runtime row means zero fixed/root/kernel, zero for each of the twelve
public Tasks, and zero idle bytes, including guards, alignment and unused
capacity. The full arena and per-pool borrowing are counted in the execution
record; the 384-byte first-stage claim adds zero loading-union bytes.

The delivered graphical FastBasic image retains OF816 and five-second autoboot.
The default build selection retains the standard shell/prime startup. Actual
development coverage is 560 host tests, ten focused emitted reader cases,
direct ROM boot and final-package FujiNet-PC boot/persistence, plus two focused
native storage failures. No compiler ABI changed; the native kernel is optimized
and the reader is assembly. Physical hardware, UART timing, arbitrary DOS,
cartridges and IDE power-on boot remain unqualified or unsupported as recorded.
