# Boot-only fast SIO reader implementation plan

Status: implemented, 23 October 2026. BF0–BF8 are delivered. SIO demo builds
now default to auto negotiation; standard bulk policy remains available.
[Implementation and measurements](../history/boot-only-fast-sio.md) and the
[development record](../development/boot-only-fast-sio.json) identify the exact
artifacts and executed scope. Physical UART qualification remains separate.

[Plans](README.md) · [Roadmap](../roadmap.md) ·
[Boot contract](../reference/boot-loading.md) ·
[Platform and memory budget](../reference/platform.md#bank-zero-memory-budget) ·
[Testing policy](../contributing/testing.md) ·
[Split boot evidence](../history/fujinet-xex-boot.md) ·
[ATR plan](bootable-system-atr-implementation-plan.md)

## Delivery and scope

Load the small initial reader at standard speed, negotiate nominal 57,600 baud
with FujiNet, then stream the existing OF816/kernel XEX at that speed. Preserve
the five-second OF816 countdown, interactive Forth, boot settings, streaming
LZ4 decoding, native memory admission and orderly native SIO ownership.

The primary delivery retains these slots:

| Drive | Media | Role |
| --- | --- | --- |
| D1 | `Exec-of816.xex`, read-only | FujiNet virtual XEX boot disk |
| D2 | Matching `system.atr`, read-only | Native SYS |
| D8 | Existing `work.atr`, writable | Native WORK |

The combined ATR retains its existing single writable D1 SYS/WORK layout.
Both transports use one XEX execution core and one boot SIO engine. Boot source
selection is independent of the monitor's native SYS drive setting.

Pin the dedicated AltirraOS 65816 ROM, 8× 65C816 with shadow ROMs, PAL, 64K base
RAM and 63 linear high banks. Retain the selected graphical build's VBXE and
mouse requirements. BASIC must remain disabled through CONFIG's ROM restart;
keep the documented hold-OPTION procedure and existing memory rejection.

The first delivery supports divisor 8, the existing nominal 57,600 profile,
and standard divisor 40. Roughly 125 kbaud, other turbo protocols, clock-in
acceleration, other ROMs, cartridges, arbitrary DOS environments and writes
from the boot reader are outside this plan. It adds no Task, public kernel
operation, runtime baud negotiation or compiler ABI.

## Current bottleneck and measurement basis

PicoBoot repeatedly calls ROM SIO at `$E459`. The pinned ROM programs standard
speed for those calls; setting POKEY's divisor once in an INIT callback cannot
accelerate subsequent reads. Native `sio.device` starts after loading and uses
its independently configured profile.

The examined split XEX is 663,395 bytes. At ten serial bits per byte, its
nominal payload-only times are 345.5 seconds at 19,200 and 115.2 seconds at
57,600. These are estimates, excluding framing, sector links, turnaround,
decoding and the countdown. BF0 freezes the actual comparison inputs; BF8
measures the resulting boot rather than treating the estimates as a result.

## Reader and takeover decisions

### An ordinary XEX prefix, without PicoBoot code patches

Generate a small prefix before the canonical combined OF816/kernel XEX. Its
first segment retains a safe default RUNAD: use a self-contained parking
trampoline in the existing loader arena before loading the reader into
`$4000–$5FFF`. An explicit early INITAD enters the reader. Appending the
canonical XEX, including its repeated `$FFFF` marker, remains an ordinary XEX
stream for external loaders.

The prefix carries generated, versioned metadata: boot unit D1, logical payload
offset, exact 24-bit payload length, canonical image identity, reader extent,
callback bindings and requested speed policy. Define this build/reader format
in `abi/boot-sio.json` and generate its assembly/Python constants. It is not a
native Task or public boot-settings ABI extension. Compute identity from the
canonical payload before wrapping it; avoid a checksum dependency cycle.

The early INIT does a bounded standard-speed source probe. For the supported
FujiNet virtual disk, find `AUTORUN` in its DOS directory and follow its
double-density, 16-bit sector links. Compare the on-disk prefix metadata with
the running prefix before taking ownership. Use the generated logical offset
to find the canonical payload, preserving a partially consumed sector. Do not
read PicoBoot's private zero-page variables, stack frames, call sites or cursor.
The generated offset is authoritative; there is no scan for an apparent XEX
marker in payload bytes.

When a matching source is absent, as during direct emulator XEX loading with
SYS on D2, restore the caller state and return from INIT so the external loader
continues the appended canonical stream. Do this before a speed-changing query.
Keep this probe bounded and measure its direct-launch cost.

After selecting a matching source, the Exec reader owns the remaining load.
It parses and executes the canonical XEX once, then jumps to its guarded RUNAD.
It never returns to PicoBoot to load the same payload a second time. Later
transport or image failures stop in a ROM-screen diagnostic and require reset.
The canonical payload must not contain another takeover prefix.

### One streaming XEX core

Extract the existing ATR reader's XEX machinery into shared assembly includes
or modules. Give it two small byte-stream backends: the FujiNet DOS-linked
virtual file and the existing SDFS root file/maps. Replace the converted ATR
implementation rather than retaining a second parser.

Keep exact file completion, repeated markers, headers crossing sectors,
24-bit positions, segment admission, guard checks, cleared-before-call INITAD,
balanced callback frames and a final guarded RUNAD. The existing native loader
remains responsible for manifest, extent, compression and incomplete-image
validation. Do not add another decompressor or buffer the complete kernel.

### Boot SIO ownership

Implement a synchronous caller interface backed by bounded emulation-mode
serial IRQ routines. Use the pinned ROM's IRQ dispatcher and serial-vector
contract; keep ROM VBI/NMI entry working. Native Exec, its scheduler and its
driver lifetime protocol do not exist yet and cannot service this reader.

Limit operations to STATUS, HSIO-index query and sector READ, with four-byte,
one-byte, 128-byte and 256-byte replies as appropriate. Validate the complete
checksum-bearing frame before exposing its bytes to the stream parser. Record
the chosen command, ACK/completion handling, turnaround delays and finite
deadlines in generated constants, based on BF0's pinned protocol audit.
Distinguish terminal ERROR replies from disk errors carrying a data frame;
define bounded draining before any recovery transaction.

Publish IRQ-visible state and switch serial vectors with short IRQ-masked
transactions while no frame is active. Specify what ROM NMI can observe at
each transition; SEI alone is not an NMI protocol. Preserve the caller's mode,
full register context, direct page, live page-one stack, DCB and affected OS
state. Save the OS masks/vectors and documented shadows, and establish/restore
the cold-launch silent audio baseline. Do not read write-only POKEY aliases
as saved audio state or mask interrupts for an entire sector transfer.

All buffers, vectors and pending serial work must be settled before a callback
uses the ROM or native Exec takes ownership. No boot handler may remain in a
vector when its storage is reused as Task stacks.

### Negotiation, fallback and monitor suspension

Model both host and peripheral speed explicitly. A successful `$3F` query can
switch FujiNet's speed after its reply; it is not a passive capability read.
Freeze this behaviour against the actual firmware binary/source in BF0.

| Observation | Required action |
| --- | --- |
| Explicit standard policy | Read bulk data at divisor 40 without an opportunistic speed query |
| Valid index 8 | Change host to divisor 8 and confirm a complete read before committing to fast loading |
| Valid index 40 or clean unsupported-command reply | Continue standard loading only after standard-rate communication is confirmed |
| Other index, corrupt/lost reply or failed fast confirmation | Attempt only the pinned, bounded standard resynchronization; continue only after a verified standard reply, otherwise stop with a reset-required diagnostic |

Do not label a host-only divisor reset as fallback: the peripheral may still
be fast. Do not implement an unbounded rate scan or retry a partially consumed
stream. A failed frame remains private until a complete replacement validates.

Keep the bus fast across known local callbacks that only load OF816 pages,
decode native records or print progress. Generate their bindings from the
canonical build. This avoids two negotiations around every small INITAD.
The interactive OF816 entry is a distinct boundary: finish the frame, return
the peripheral to confirmed standard speed, restore the OS serial environment
and then call the monitor. On return, reacquire the bus, check the selected
source, restore the saved stream position and negotiate again. Conservatively
suspend around any other admitted callback whose I/O behaviour is not proven.

Before native entry, settle the bus at the configured native profile's expected
speed and retire the boot engine. For this delivery the three slots belong to
one FujiNet and native storage uses the existing divisor-8 profile. Standard
boot fallback does not silently change native mount profiles or imply support
for a peripheral that cannot satisfy that native configuration. Record and
test boot speed and native handoff speed separately.

## Memory gate

Target the existing ATR reader's **8,192-byte `$4000–$5FFF` arena**, including
all code, state, sector/map buffers, guards, alignment and spare capacity. The
current split build has a 3,328-byte main loader reservation; do not assume
that a larger standalone fixture's loader allowance is available there.

The examined split build has a 40,336-byte loading union, including OF816's
borrowed ranges. Adding this arena gives 48,528 bytes: **+8,192 temporary
loading bytes**. Runtime remains 55,008 bytes. These are placement estimates
from the current generated map, not a measurement of the future reader binary.
The ATR already reserves this arena, so sharing it adds zero further loading
bytes if the completed implementation fits.

The proposed split reader borrows the following currently idle stack ranges:

| Public Task slot | Bytes borrowed, including intersecting guards |
| --- | ---: |
| 3 | 512 |
| 4 | 1,344 |
| 5 | 1,344 |
| 6 | 2,592 |
| 7 | 2,400 |
| Total | 8,192 |

Runtime reserved bank-zero targets are **0 added fixed, root, kernel, per-public-
Task and idle bytes**, including guards, alignment and unused capacity. The
reader retires before Task initialization; the pools are not enlarged. The
prefix trampoline uses the already reserved loader arena. Use no bank-$01
scratch and preserve `$8000–$8FFF`, MEMLO admission and MEMTOP >= `$BC00`.

Every slice reports actual used bytes and complete reservation unions for
loading, initialization and runtime, with per-pool borrowing. Reject overlap
with the resident adapter, staging, manifest, OF816 and every streamed XEX
write. If 8 KiB is insufficient, revise the placement and budget before further
implementation rather than silently borrowing another range.

## Executable slices

### BF0 — Freeze baseline, protocol and honest transport observation

- Record the compiler pin, optimized native image, canonical XEX, ROM/emulator,
  actual FujiNet binary and source/configuration hashes. Capture CONFIG →
  held-OPTION → first INIT → OF816 → native entry at standard boot speed.
- Audit `$3F`, frame deadlines, error replies, baud transitions and the ROM
  IRQ/NMI contract. Define the standard resynchronization bound; uncertain
  recovery must have a finite stop outcome.
- Audit `tools/fujinet_pc_peer.py`: it currently sets the firmware baud from
  the target command and transmits replies at that same observed period.
  Separate host and peripheral rate observations so this cannot hide a bad
  negotiation. Add a cycle-paced raw-SIO fixture in which a deliberate rate
  mismatch fails. Keep real NetSIO firmware/media evidence distinct from
  physical UART timing.
- Freeze the generated memory map and baseline byte/time counters.

Acceptance: a deliberate baud mismatch is detected, normal standard transfer
still passes, and baseline boot byte counts, phases and context are recorded.
No production reader change is required for this slice.

### BF1 — Extract the common streaming XEX core

- Refactor `disk-boot-reader.s` into one XEX core plus the SDFS byte backend,
  initially retaining ROM SIO. Generate the shared reader layout definitions.
- Preserve current ATR format, EOF/INITAD/RUNAD handling and all rejection
  behaviour; independently reconstruct and compare the streamed payload.
- Exercise fragmented files, map transitions, sector-boundary headers,
  >64 KiB input, malformed lengths/entries and intact guards/context.

Acceptance: the existing ATR reaches OF816 and native entry through the shared
core with exact native bytes; focused emitted reader failures still terminate.

### BF2 — Take over the split XEX at standard speed

- Define and generate the prefix descriptor and safe initial RUNAD, add the
  DOS-linked source backend and build the wrapper around the canonical XEX.
- Take over by directory/chain metadata and generated logical offset, without
  consulting or modifying PicoBoot's implementation. Keep callback and stream
  state entirely reader-owned.
- Implement the pre-takeover return for direct XEX loading. After takeover,
  failure parks and final entry never resumes the outer loader.
- Update layout admission and host XEX inspection for the wrapper and repeated
  markers. Keep the unwrapped canonical image as the shared build input; the
  ATR stores that image, not a recursively wrapped executable.

Acceptance: real FujiNet-PC CONFIG boots the split layout at standard speed,
each canonical callback runs once, and all native initialized/zero-fill bytes
match. Direct loading with D1 absent or unrelated still works within the probe
bound. Malformed running-prefix metadata, truncation after takeover,
cyclic/invalid selected-source links and reader-overwriting segments stop
safely. Low MEMTOP is still rejected before OF816.

### BF3 — Implement the boot serial engine at standard speed

- Add the boot-only engine, initially divisor 40, and route owned-reader I/O
  through it. Keep IRQ handlers, ownership state and buffers within the arena.
- Implement bounded command/ACK/completion/data handling, checksum admission,
  cancellation at defined safe boundaries and complete idle-state retirement.
- Exercise exact 128/256-byte counts, checksum carries and buffer boundaries;
  an eight-bit counter wrap must not complete a 256-byte frame early.
- Inject missing/late ACK, NAK/ERROR, partial data, checksum errors and missing
  devices. Check IRQ/NMI entry during descriptor/vector transitions and serial
  traffic during real ROM VBI. Prove no caller context or stack corruption.

Acceptance: cycle-paced standard reads and a real-firmware standard boot pass;
all injected failures finish within recorded deadlines, leave COMMAND inactive
and have no live serial handler pointing into retired storage.

### BF4 — Negotiate and stream at divisor 8

- Implement the explicit speed state machine, verified fast confirmation and
  bounded recovery described above. Parameterize the isolated firmware peer's
  HSIO setting so unsupported/disabled cases are real test inputs.
- Add one build policy, `--boot-sio auto|standard`, to the normal demo builder.
  `standard` supplies a recovery/comparison image; it selects transport policy
  in the same reader, not a second implementation. Keep the new default opt-in
  until BF5–BF8 pass.
- Exercise supported index 8, index 40/disabled, unsupported index, lost query
  reply after a device speed change, bad fast data and failed resynchronization.

Acceptance: the same native payload loads through confirmed fast frames, while
safe standard fallback and reset-required ambiguity remain distinguishable.
Every test records both endpoint rates; a rate-forcing relay is insufficient.

### BF5 — Preserve OF816 and the native ownership boundary

- Implement callback classification, monitor suspension, standard-rate OS
  restoration, stream resumption and native-profile handoff.
- Check automatic five-second startup and physical-key interruption into
  interactive Forth. Exercise a ROM-backed disk operation there, change native
  boot settings, and enter `EXEC816` after an extended pause.
- Inject a transfer failure after monitor return and an NMI at each ownership
  transition. Preserve the partially consumed sector and exact callback order.
- Verify the final native image, native D2/D8 SIO, guards, contexts and normal
  EXIT. Inspect vectors and reuse the borrowed Task pools after retirement.

Acceptance: the countdown remains 249–251 PAL frames, Forth disk I/O works,
settings reach native Exec, resumed loading is byte-exact, and no pending boot
IRQ or stale vector survives native startup. Standard bulk mode also establishes
the required native handoff rate explicitly.

### BF6 — Use the same fast engine for the bootable ATR

- Route its SDFS backend through the shared engine; negotiate after the small
  ROM-loaded first stage/reader. Retain ordinary protected BOOT.LDR and
  EXEC816.XEX, allocation/locator checks and the writable single-volume model.
- Keep one parser and one speed/callback/retirement state machine for both
  backends. Include the compiled reader and actual full arena in media reports.

Acceptance: a real-firmware ATR boot and fragmented/map-crossing fixture reach
OF816/native entry through fast reads, with the same native bytes and zero
additional reservation beyond the ATR's existing reader arena.

### BF7 — Exercise final-package recovery and persistence

- Extract the candidate split ZIP and cold-boot through real CONFIG/OPTION.
  Load HELLO and FastBasic, save source/text/preferences on D8, reset, reload
  the saved data and exit normally. Preserve the existing writable work disk.
- Run the corresponding focused ATR save/reboot path. Independently audit saved
  bytes and unchanged protected boot content.
- Cover mode selection, invalid source identity, disconnect/truncation before
  and after OF816, clean standard fallback and ambiguous-speed stop. Use small
  emitted fixtures for most failures rather than repeating the desktop each time.

Acceptance: both transport profiles complete their development walkthroughs;
failures neither enter an incomplete kernel nor resume PicoBoot after takeover.
Read-only boot media remain byte-exact and saved workspace data survives reboot.

### BF8 — Measure, document and freeze the delivery

- Compare standard and auto using the same canonical payload and pinned
  configuration. Record initial prefix loading, negotiation/recovery, OF816,
  bulk transfer, decoding, native handoff and total startup separately.
- Run repeated short matched bulk-read cohorts and one complete standard/fast
  boot pair. Target at least a twofold bulk-transfer improvement at nominal
  57,600; report the measured full-boot improvement and fixed overheads. Diagnose
  a missed target before making auto the default.
- Publish host and focused emitted results, actual memory unions, source/tool
  hashes, endpoint rates, frame/error counts and timing limitations in a new
  development record. Preserve earlier evidence unchanged.
- Update the current boot contract, split/ATR guides, builder/launcher help,
  source packaging and indices. Make auto the default for the supported FujiNet
  SIO boot builds only after the preceding gates pass; retain explicit standard
  policy and direct emulator launching.
- Build/refresh through `tools/build_demo.py`, including OF816, pinned ROM and
  notices. Freeze executable artifacts before testing the final extracted ZIP;
  do not regenerate a different monitor image after the check. Distribute only
  boot files, short guide, notices and checksums in `exec816-demo.zip`, with
  build/test output and corresponding-source delivery kept separately.

Acceptance: exact packaged bytes pass, timing gains are measured rather than
inferred, source/build inputs are reproducible, and scope is reported as
development-tier evidence. Physical FujiNet/accelerator UART qualification is
separate; record it explicitly if performed, otherwise leave it unclaimed.

## Validation policy and completion

Run host checks and the affected generated-definition checks after coherent
code slices. Use focused emitted assembly cases with the optimized native
kernel. No compiler-facing ABI change is planned; add raw/optimized probes only
if implementation actually changes a language bridge or compiler-facing layout.
Select deeper interrupt/transport cases at BF3–BF5, without automatically running
the entire release matrix after every slice.

The plan is complete when split and ATR loading share the reader, fast boot is
measured on frozen artifacts, safe fallback/stop outcomes are executable, OF816
and native SIO retain their contracts, and the final package and corresponding
source are validated. BF2 is the first split takeover milestone; BF4 establishes
fast transport; BF5 establishes usable OF816/native integration. None alone is
the final delivery or a physical-hardware qualification claim.

## Delivery record

| Slice | Delivered result |
| --- | --- |
| BF0 | Frozen baseline/pins; independent endpoint rate observations; deliberate mismatch and real firmware recovery |
| BF1 | Shared parser; fragmented >64 KiB/map-crossing fixture and nine bounded rejection cases |
| BF2 | Ordinary split prefix/DOS backend; exact native bytes; direct absent/unrelated-D1 launch; metadata, bounds and chain failures |
| BF3 | IRQ-driven serial engine; real VBI, 128/256-byte frames, finite timeout, BREAK and error retirement |
| BF4 | Index-8 negotiation, disabled/unsupported devices, lost/corrupt query recovery, auto/standard builder policy |
| BF5 | Local callback retention, standard ROM/Forth boundary, source identity recheck, resumed exact image and native profile retirement |
| BF6 | ATR SDFS backend shares the same parser/engine; real firmware save/reboot and intact protected boot content |
| BF7 | Exact extracted split package, D8 saves/reboot, ATR persistence, bounded failures and normal native EXIT |
| BF8 | Matched short cohorts/full boot pairs, phase counters, frozen packages, source rebuild and published development scope |

Runtime bank-zero reservation change for **every slice is zero fixed/root/
kernel/per-public-Task/idle bytes**, including guards/alignment/spare capacity.
BF1/BF3–BF8 fit existing reservations. BF2 adds the complete 8,192-byte temporary
reader arena to split loading, borrowing the five stack intersections tabulated
above; BF6 adds zero beyond the ATR arena already reserved. Actual assembled
usage and phase unions are in the generated record.

BF0 corrected the initial relay diagnosis: NetSIO `$80` reports peer baud rather
than forcing firmware baud. Sending responses at the observed command period
and the firmware's zero low-byte XOR at 19,200/57,600 could hide disagreement.
The delivered relay keeps endpoint rates distinct and rejects mismatched frames.
The full-boot timers include transfer and decode together; individual decoder
CPU time is not isolated by the phase observation. This is an explicit
measurement limit, not a physical timing or release qualification claim.
