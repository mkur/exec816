# IDE-only demo development record

[Implementation plan](../plans/ide-only-demo-implementation-plan.md)

The [native 512-byte refactor record](ide-512-sector-refactor.md) supersedes this
record's packed IDE geometry and documents the successful real BIOS XEX load
through OF816 to the IDE shell. The original measurements and outcomes below
retain their historical scope.

## ID0 — IDE system volume

System selection now admits a configured IDE mount, preserving its unit and
physical alias. SYS shares that slot's identity and cache. The existing SIO
drive override remains limited to SIO-selected SYS; IDE uses a zero override
and its generated immutable unit. The eight-byte boot record and four-byte
upper captured settings retain their layouts.

All 425 host checks pass. A focused optimized emitted check opens both SYS:
and SYSTEM: on the same SpartaDOS partition, checks the canonical root name,
rejects creation on read-only SYS and retires filesystem ownership. A nonzero
SIO override falls back to the fixed IDE default with BAD_RECORD status.
Read-only media stays byte-exact. Evidence:
`build/development/ide-only/id0/results.json`.

Reserved bank-zero change: **0 fixed / 0 per Task / 0 idle bytes**, including
guards, alignment and unused capacity. No pools or public layouts change.
This is development coverage, not hosted-system or physical qualification.

## ID1 — Driver selection

The generated admission/transport modules and native assembly can exclude SIO.
Keyboard, pointer, timer and interrupt services remain shared; timer callbacks
have a standalone bridge when the serial engine is absent. Reserved metadata
and Task pools are unchanged. OpenDevice on sio.device returns the ordinary
open failure, with no SIO worker, Action driver or native serial engine linked.

All 425 host checks and the optimized ordinary SIO public example pass. The
IDE-only SYS fixture passes both boot-setting cases, guarded cleanup and exact
read-only media comparison. Its IDE worker ordinary call bound is 458 bytes;
including the 256-byte interrupt reserve and 16-byte dispatch margin gives
730 of the existing 1,024 bytes (294 bytes headroom). Evidence:
`build/development/ide-only/id1/results.json` and `id1-sio/results.json`.
Reserved bank-zero change: **0 fixed / 0 per Task / 0 idle bytes**.

## ID3 — Production disk layout

The new host builder creates a 4 MiB APT with fifteen mapping slots, two real
partition entries, SYSTEM/WORK metadata leaders and boot unit 1. Both partitions
have 2,880 256-byte logical sectors packed as adjacent halves of 512-byte
physical sectors. SYSTEM is protected; WORK is writable. Each source filesystem
is reconstructed byte-for-byte and audited independently after packing. Layout
follows [APT revision T](https://drac030.krap.pl/APT_spec.pdf); partition IDs
count actual partitions from one, excluding headers and mapping slots.

All 426 host checks pass. The optimized native case discovers units 1 and 2,
checks exact geometry/protection, rejects SYSTEM writes and verifies a WORK
write/read. Whole-image comparison permits only the requested 256 bytes to
change, preserving metadata, SYSTEM and the neighbouring packed sector. Evidence:
`build/development/ide-only/id3/results.json`. This media slice was completed
before ID2 to let shell checks use the production layout.
Reserved bank-zero change: **0 fixed / 0 per Task / 0 idle bytes**.

## ID2 — Shell startup

Filesystem attachment now opens the selected transport; shell startup no longer
warms up SIO. Generated diagnostics identify IDE SYS and WORK and report IDE
controller failures without floppy advice. C:/S: and command lookup retain the
ordinary DOS paths. The optimized shell fixture has both IDE mounts, no floppy
attachments, executes STARTUP/USER markers, loads HELLO through C:, and verifies
exact accepted console output, Task counts, guards and ownership cleanup.
Explicit IDE Stop follows filesystem stop for this fixture's heap oracle; the
controller service normally persists until kernel EXIT. Evidence:
`build/development/ide-only/id2/results.json`. The standard console preserves
loader text, so this check compares accepted output rather than an empty-screen
pixel baseline. All 426 host checks pass.
Reserved bank-zero change: **0 fixed / 0 per Task / 0 idle bytes**.

## ID4 — Distribution

`--ide-only --text-shell-only` packages the final OF816 executable inside SYS
and as the external XEX. Companion hashes are finalized after packing without
changing executable bytes, avoiding a disk digest cycle. The ZIP includes the
raw image and both Atarimax carts, no ATRs, BIOS or development manifests.
Refresh paths also repack SYS around the refreshed executable.

All 426 host checks pass. An extracted new-cart package boots with no floppy
attachments, keeps the five-second OF816 countdown, mounts IDE SYS/WORK, loads
C:HELLO, lists devices/mounts/assigns, and passes pixel, stack, ownership and
OS restoration checks on EXIT. SYS's EXEC816.XEX equals the external file.
Evidence: `build/development/ide-only/cart-smoke/results.json`; package and
capacity reports in `build/development/ide-only/demo/`. The combined executable
is 329,163 bytes, with 703,028 bytes cartridge headroom. Its measured IDE worker
call bound remains 730 bytes in the existing 1,024-byte stack.
Reserved bank-zero change: **0 fixed / 0 per Task / 0 idle bytes**.

## ID5 — Firmware-menu admission remains open

The real pinned BIOS 2.1 menu was entered through cold reset with START held,
SDX and UltraSpeed SIO disabled, no floppy attachments, and boot unit D1.
Pressing L reaches the PBI handler at $D805 with DCB device/unit/command
`31 01 53` (D1 STATUS). It returns to the pinned OS at $C352 with carry clear:
the request is unclaimed, so the OS falls back to serial SIO. The menu then
reports `Hit [1]-[9] or [A]-[O] to change disk`; a separate trace sees STATUS
timeout $8A. Native IDE reads of both partitions succeed independently.

`tools/test_ide_only_firmware.py` reproduces this admission failure and stops
before serial fallback. Evidence is `build/development/ide-only/id5-firmware/`;
it is an **incompatible diagnostic outcome**, not a passing boot test. Header
global flags cleared, a protective MBR, a normal cold reset before the menu,
and shadow ROM disabled did not resolve the failure in disposable experiments.
The source of the BIOS's missing unit mapping is not established. Do not infer
firmware compatibility from the native APT reader or bypass the loader guard.

MEMLO at this failure is $0700. No executable reader, INITAD callback, OF816
countdown, kernel RUNAD or native IDE worker is reached, so the actual loader
workspace/MEMLO and page-one handoff remain **unmeasured**. ID5 remains open.
Cartridge and external-XEX paths are the usable preview paths. No firmware or
emulator patch was made, and physical hardware remains unqualified.
Reserved bank-zero change: **0 fixed / 0 per Task / 0 idle bytes**.

## ID6 — Persistent WORK and failure coverage

The complete IDE-only profile includes RAM as well as SYSTEM/WORK. Rebuilding
removes the previously generated embedded EXEC816.XEX before text staging, then
installs the newly composed bytes at finalization. A repeat build and monitor
refresh both pass the disk, source-hash and cartridge-capacity gates.

The extracted new-cart walkthrough passes DEVICES/MOUNT, C:/S:/PATH, HELLO,
COPY of the 23,872-byte LONG.TXT, CMP, append, MAKEDIR, same-parent RENAME,
copy into a subdirectory, DELETE, RAM write/read, and EXIT. Independent WORK
audit finds only README.TXT and the exact COPY.TXT; its directory count is one.
The separate cancellation walkthrough starts PRIMES, waits for its pane, sends
physical BREAK during a committed Write and receives error 304. Its persisted
BREAK.TXT is an exact 1,024-byte source prefix. PRIMES progress advances from
202 to 12,902; timer.device and VBI each advance 803 ticks/frames. HELLO still
runs; BREAK of the background job, collection and EXIT retire ownership.

Both cartridge variants boot with no floppy attachments. A physical SEROUT
write breakpoint remains installed from cartridge RUN entry through EXIT,
including across harness breakpoint resets; all three extracted sessions
record zero writes. A deliberately emitted STA to SEROUT triggers the guard
in a separate positive control. Linked code has no SIODRIVER/SIOADAPTER or
native serial engine. The observer's private PROGRAMIMAGE offsets were updated
for its existing kind byte; no production program-image ABI changed here.

The optimized failure fixture passes normal remount/readback, absent IDE,
protected WORK, rejected ATA write and verification mismatch. Rejected writes
leave the complete medium exact. An accepted uncertain outcome rejects cached
SYS and WORK lookup/read admission together while RAM/console remain usable.
The verification stimulus corrupts only the readback buffer, not the source
buffer or device image. Every case checks guards, OS context, ownership and
heap restoration after filesystem/controller stop. SYS, APT, leaders and all
bytes outside WORK remain exact in both successful and failed sessions.

Evidence under `build/development/ide-only/`: `full-cart/results.json`,
`copy-break-cart/results.json` and `persistence.json`,
`old-cart-smoke/results.json`, and `id6-failure/*/results.json`. All 426 host
checks pass. These are development checks; no full release matrix or physical
qualification was run. ID5 remains the explicitly open firmware-loader slice.

The final native image has 971,130 executable bytes, 10,302 initialized data
bytes and 991 zero-fill bytes. The compressed native XEX is 304,107 bytes;
combined OF816 XEX is 329,189 bytes, with 703,002 bytes cartridge headroom.
SYS allocates 1,849 logical sectors and leaves 1,031 free; pristine WORK uses
nine and leaves 2,871 free. One IDE worker uses its existing 512-byte buffer
and shared filesystem cache; no new cache, Task or stack pool was introduced.
The IDE call bound remains 730/1,024 bytes. The largest observed worker stack
touch is 584 bytes with 184 untouched bytes above its 256-byte IRQ reserve;
kernel touch is 279/1,536 bytes with no interrupt-reserve touch. All stack/domain
guards pass. Watermarks are observations, not a complete worst-case bound.

Reserved bank-zero change: **0 fixed / 0 per Task / 0 idle bytes**, including
guards, alignment and capacity. Existing runtime reservations excluding OS
remain 25,408 bytes (10,528 fixed plus unchanged Task/idle pools). Bank $01
remains reserved and untouched. New mount objects are ordinary upper-heap
allocations, retired by the checked lifetime paths.
