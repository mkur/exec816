# FujiNet control implementation

[History index](README.md) · [Plan](../plans/fujinet-control-implementation-plan.md) ·
[SIO contract](../reference/device-io.md#siodevice)

## FN0 protocol and serial fixture

The selected control commands and fixed byte extents are generated from
[fujinet.json](../../abi/fujinet.json). Source URLs/hashes are pinned in
[fujinet-control.json](../../toolchain/fujinet-control.json). The execution peer
uses Altirra's existing custom-device serial interface; no emulator changes or
production driver shortcuts are required. It is a scripted protocol fixture,
not executable FujiNet firmware or physical-device qualification.

Development checks pass: 473 host tests, generated definitions and 161 optimized
native assertions covering slot/AUX arithmetic and a complete 128-byte patterned
read over the real serial path. Native stack/domain guards, final heap ownership
and OS restoration pass. The [development record](../development/fujinet-control.json)
retains the exact inputs and scope.

Production bank-zero reservation delta is fixed 0, per public Task 0 and private
idle 0, including guards, alignment and unused capacity. FN0 adds protocol
constants only; its payload storage belongs to the test fixture.

## FN1 raw transfers and unit exclusion

STANDARD19200 admits complete raw frames up to 512 bytes and defaults to a
bounded fifteen-second deadline. Legacy profiles retain their admission and
conversion paths. Sparse unit metadata adds `$70` at offset 240; the exclusive
open bit consumes existing unit-record padding. Neither the 256-byte upper
metadata reservation nor bank-zero reservations grow: fixed 0, per Task 0,
private idle 0, including guards/alignment/capacity.

474 host tests and 2,995 optimized native assertions pass. Real serial reads,
writes and readback cover 140/255/256/304/512-byte payloads across a CPU-bank
boundary; neighboring guards remain intact. Checks cover admission rejection,
deadline rounding/defaults, clock wrap, a three-second completion with another
runnable Task, clean device errors followed by another successful request,
shared/exclusive conflicts on control and disk units, reopen, final ownership
and shutdown restoration. The peer uses Altirra's normal frame/checksum handling;
its receive primitive already supplies the data ACK.

## FN2 caller-context client and native imports

The SIO library owns ordinary caller-context ports/requests and collects exact
replies. Both acquisition failures unwind completely; a submitted frame completes
before a foreground interruption returns. COMMITTED permits the next frame of
a mutation despite a pending BREAK. SIO-disabled builds retain the interface
and reject Open without serial access. The current contract is
[SIO client](../reference/sio-client.md).

Development checks pass: 522 native assertions in each raw/optimized ABI probe,
a loaded command importing all three functions, an SIO-disabled check, and 114
optimized lifetime assertions. The latter exhausts real heap allocations at
both acquisition stages and verifies full restoration, then tests pre-submission
BREAK, a real interruption during a slow frame and committed completion.

The optimized shared client occupies 2,351 upper code bytes. Its caller-owned
session/transaction records are 8/24 bytes; port/request allocations use existing
Exec facilities. The native program ABI advances to 18. Its manifest uses 1,807
of 1,856 reserved upper bytes (+128 capacity); the 160-byte pointer-input state
moves 128 bytes within existing slack. Fixed, per-Task and private-idle bank-zero
reservation changes remain zero, including padding/guards. The larger 4,352-byte
arena in the loaded/lifetime fixtures is test storage; the demo already reserves
6,400 bytes. C program ABI 17 remains current for its unchanged interfaces.

## FN3 reports and directory browsing

C:FUJI implements STATUS (also the default), HOSTS, DISKS with an optional drive,
and DIR with HOST/PATH. It uses inherited output, bounded firmware fields and
one 512-byte scratch buffer. The control binding remains exclusive through
cursor cleanup, including BREAK and output errors. Demo builds install FUJI.

Development checks pass: 474 host tests and 120 optimized emitted assertions
using the actual loaded command and serial frames. Cases cover quoted paths,
full-path reporting, redirected output, invalid host/drive/options, busy control,
malformed adapter text, directory errors, read-only output failure, interruption,
cursor reopen, final heap ownership, guards and OS restoration. The separate
absence case passes eight assertions, returns a bounded timeout and retains the
existing reset-required shutdown policy; it cannot assert ordinary OS restoration.

A control ERROR reply can have no read data, unlike the existing legacy disk
error payload. STANDARD19200 now terminates that reply cleanly. A spare descriptor
byte records the profile rule; legacy error-with-data and raw error-without-data
both execute in the fixture. No unit/opcode special case or retry is added.

The command is 16,189 bytes on disk and has 1,047 bytes of private BSS including
alignment. Sessions request the existing 27-byte port and 52-byte request while
open. Full reserved bank-zero changes are fixed 0, per Task 0 and private idle 0,
including guards, alignment and capacity; the descriptor remains 128 upper bytes.
Stack observations and exact inputs are retained in the development record.

## FN4 guarded image changes

ATTACH/EJECT retain both exclusive control and target-drive bindings. An
occupied configured slot must be ejected before attachment. The host table is
read without changing host names/prefixes; ATTACH defaults to read-only, with
READWRITE setting the same mode in configuration and attachment. A failed second
stage reports the configured slot. After configuration is submitted, collection
and final attachment finish despite BREAK; successful mutation suppresses the
optional report when interrupted instead of returning a false cancellation.

Development checks pass: 201 optimized image-control assertions, 120 report
regression assertions, and 263 MyDOS/128 workflow assertions with an independent
persisted-disk audit. Cases cover raw/filesystem busy bindings before mutation,
repeated attach, selected-host/path/mount failures, configured-state inspection,
late BREAK during configuration/attachment/ejection and pre-mutation BREAK.
Another caller attempts control/drive opens and MOUNT during delayed attachment;
all reject busy before disk traffic. Final heap/ownership and guards pass.

The workflow uses real serial control frames, then a host rendezvous connects
the selected ATR to Altirra's disk peripheral before native filesystem I/O.
It proves the control/admission/cache lifecycle together, not FujiNet firmware's
internal image-backed disk implementation. The first image remains byte-identical;
the replacement is read independently, written, unmounted and remounted.

FUJI is 20,180 bytes on disk with 1,047 private BSS bytes. The existing native
loader additionally reserves 65,535 upper bytes for bank alignment of its text;
this is part of its temporary loaded-image footprint, not resident kernel code.
Each live SIO session requests a 27-byte port and 52-byte request through the
existing allocator. The complete reserved bank-zero delta remains fixed 0,
per Task 0, private idle 0, including guards/alignment/unused capacity. The
workflow fixture's 8,192-byte upper arena is test capacity only; demo capacity
stays at 6,400. Exact command sizes, inputs and stack observations are recorded.

## FN5 workflows and packaged demos

The combined control/mount workflow passes 263 optimized assertions for each
MyDOS/SpartaDOS × 128/256-byte case. Every case verifies unchanged readonly media,
a different replacement payload through a fresh mount, persisted writes after
remount and an independent host audit. A runnable Task progresses throughout;
an unrelated SYS disk remains accessible and control/disk speed profiles switch.
Request/Task ownership, complete heap restoration, stack/domain guards and OS
restoration pass. 474 host checks and generated definitions remain current. The direct-adapter
legacy fixture also initializes the former padding byte to its disk error-data
policy; public requests select that policy through their profile.

Both development demos include C:FUJI, updated STORY/short guides, OF816's
five-second autoboot, matching 720 KiB system/work disks, pinned ROM/licences,
checksums and old/new Atarimax carts. The generated ZIPs contain distribution
files only; serial peers, manifests, launchers and test output stay outside.
An extracted standard/new-cart smoke and extracted VBXE/XEX smoke pass: C:FUJI
lookup, foreground help with redirection, existing command providers/pipeline,
OF816 handoff, guards and EXIT. No GitHub release was published.

The standard upper arena reserves 6,400 bytes (6,399 used). Bitmap composition
uses 6,409 bytes, so its arena grows one page to 6,656 (+256 upper bytes including
247 spare), preserving aligned code placement. Full added reserved bank-zero
bytes are fixed 0, per public Task 0 and private idle 0, including guards,
alignment and unused capacity. Cartridge payloads fit with 680,777/620,116 bytes
of headroom for standard/VBXE. Exact input/output hashes and observed scope are
in the development record.

No real FujiNet firmware executable, SD/TNFS walkthrough or physical device was
executed here. Source snapshots and scripted serial fixtures are the evidence;
they do not qualify firmware image mounting or real-hardware interoperability.
The host media rendezvous used for workflow tests is confined to test code.
