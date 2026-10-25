# AltirraOS platform contract

[Reference index](README.md)

The initial platform is the dedicated AltirraOS 65816 ROM under pinned AltirraSDL
configurations. Exec owns native Tasks, scheduling and resource lifetime; its
adapter controls OS entry, hardware ownership and context transitions. Compiler
semantics and ABI primitives belong to actionc; emulator correctness belongs to
actionc-vm. Platform tests must qualify the hosted combination.

Other ROMs remain outside this platform contract. The
[firmware diagnostics](../contributing/building.md#firmware-diagnostics) record
bounded XLOS boot checks and their setup without extending platform qualification.

The [SDX Process development profile](../development/sdx-loader.md), selected
by default for standalone SIO distributions,
adds **544 fixed reserved bank-zero bytes** after bootstrap retirement: two
aligned guest direct pages and two 16-byte outer guards, with no extra padding.
It adds **0 bytes per native Task, root, kernel or idle**. The loading map and
existing bridge reservations stay unchanged. The source-audited synthetic
catalog, [MD5 subset](../development/sdx-md5.md) and
[ARC listing/extraction subset](../development/sdx-arc.md) are admitted for development;
these checks do not qualify a release profile.

The [resident guest contract](sdx-runtime.md) distinguishes the two retained
Image/private-DP slots from one active page-one lease. Guest frames remain in
physical page one across native waits; ordinary native Task switches copy no
page-one image. Runtime ROM entry borrows below a complete frame with a
128-byte budget and minimum anchor `$0190`. Idle BASIC parks without losing
its Process or data. This refactor adds zero reserved bank-zero bytes, including
fixed, root/kernel, each public Task and idle guards/alignment/spare capacity.

The [RAWCON cell/vector delivery](../history/rawcon-latency.md) also adds zero
reserved bank-zero bytes. Its 96-byte binding fits inside the existing bridge
bank; four lower native Task DP bytes are borrowed and restored. The console's
896-byte upper reservation stays fixed, and per-Instance allocations still
round to 208 bytes. Session and screen-packet growth uses upper heap storage.

## Compiler and memory contract

Use the revision and generated ABI selected by [actionc.json](../../toolchain/actionc.json):
`wdc-65816-native`, `action65816.native.v2`. Native image v3 is the baseline;
v4 adds the runtime arithmetic-fault binding. Current disk commands use compact
o65 v3 (`A8C3`); see [program loading](program-loading.md). Rebuild programs with
ABI changes; obsolete artifacts are rejected rather than supported in parallel.

Each Task owns a native stack and aligned 256-byte direct page. Saving D preserves
the pointer, not a copy of the memory it addresses. Kernel and interrupt contexts
have separate storage. The current D-relative partition is defined in
[native-dp.json](../../abi/native-dp.json):

| Bytes | Ownership |
| --- | --- |
| `$00–$7F` | Caller/runtime workspace, preserved by Action! and Exec helpers. |
| `$80–$BF` | Compiler call-clobbered scratch. |
| `$C0–$C2` | Owner pointer. |
| `$C3` | Domain kind. |
| `$C4–$C7` | Stack floor and ceiling. |
| `$C8–$FF` | Reserved zero. |

Native frame maps admit aligned, complete two- and three-byte temporary homes
within `$A0–$BF`, including mixed widths and reused extents. These homes may
appear in routines containing calls; actionc proves liveness and call-clobber
safety. Packaging checks the final extents, not those compiler-owned proofs.
The separate three-byte selector slots at `$80`, `$83` and `$86` remain
leaf-only and cannot mix with residence homes in one routine. Byte and
four-byte direct-page temporary homes are rejected by the current contract.
This validation uses existing scratch: **0 fixed and 0 per-Task reserved
bank-zero bytes added**, including guards, alignment and unused capacity.

Each DP reservation is exactly 256 bytes, with no external canaries or stride
padding. Initialization clears that page and publishes metadata before a new
owner runs. Stack canaries and checked stack bounds remain enabled. During its lifetime,
the lower half may contain arbitrary caller state. Temporary stack-based D values
and the ROM's DP have their separately defined layouts. Native register, bank,
mode and stack restoration must preserve the complete interrupted context.

The current target has 4 MiB of CPU address space: 64 KiB base RAM plus 63
linear 64 KiB high banks (4,032 KiB). Select 63 high banks in Altirra; this is
separate from Atari extended-memory modes and VBXE's private VRAM. Current
builds use `max_banks=64` and the [4 MiB map](../../platform/altirraos/memory-4m.json).
Exec leaves the entire first linear bank, **`$010000–$01FFFF`**, untouched for
platform firmware and possible hardware aliases. The bank table marks bank
`$01` RESERVED with SYSTEM ownership; neither payload loading nor heap
registration uses it. The default kernel and upper bank table start in bank
`$02`. This reserves 64 KiB of upper RAM and adds **0 fixed and 0 per-Task
reserved bank-zero bytes**, including guards, alignment and unused capacity.
The [development check](../development/memory-4m.json) covers every upper bank
and raw shell/pipeline cleanup. Historical 1 MiB pins and evidence retain their
original configuration.

The bank manager validates usable banks and image reservations before payload
writes. The [heap](memory.md) allocates byte ranges from registered memory.
`kernel_bank` in [kernel.json](../../config/kernel.json) selects the resident
image's starting bank: require 2..255, below MAX_BANKS, and usable mapped RAM.
Check every emitted extent, including additional banks. This is not a one-bank
image size limit or runtime relocation feature.

Runtime division/remainder uses the pinned `__a816_arithmetic_fault_v2` binding:
JML with A16=1 for division by zero, X16=S, native 16-bit widths, DBR=0 and D/I
preserved. The launcher records the reason and stack, then exits through its
fault/OS-restoration path with status `$FF97`. Version-4 packaging requires the
assembled adapter address. This does not add an arithmetic provider to the
external-command ABI.

### Bank-zero memory budget

Bank zero contains OS reservations, native stack/DP pools, bridge state, vectors
and loading storage. Conserve it explicitly. Report reservation changes for
implementation slices, including zero, separating fixed and per-Task costs.
Count guards, alignment and unused capacity, not only live payload bytes.

The build's `memory.json` is authoritative for `runtime_reservations`,
`task_pools` and `bank_zero_budget`. Loading and runtime lifetimes differ:
loader/staging storage may be reused only after adoption retires every live
bootstrap frame and callback. The manifest at `$6700–$6EFF` remains protected
through memory adoption, Task initialization and boot-setting capture. The
adapter publishes `M_RETIRED=1` at `startup_complete`, before Task dispatch;
only then is that entire range reusable. Failed startup does not publish it.
Repeated memory adoption/initialization uses the live adoption state and never
revalidates retired manifest bytes. The boot-state page at `$0B00–$0BFF` stays
reserved, including shutdown information. Restarting retired bootstrap code is
unsupported; a cold boot reloads the manifest.

The launch profile reserves `$0000–$09FF` for the OS or a small binary loader
and places the 256-byte adapter state at `$0A00–$0AFF`. Both loader and hosted
entry require the original `MEMLO <= $0A00`; hosted entry checks before writing
that page. `MEMTOP` must be at least `$BC00`; the loader and hosted entry publish
`MEMLO=$BC00` until shutdown restores its original value. BASIC must be disabled
and no cartridge may be mapped at native entry. Boot transport disables BASIC;
the Atarimax loader switches its cartridge off for INITAD callbacks and RUNAD.
When the pinned ROM has the BASIC/cart mode-0 allocation at `$9C40`, boot
preparation reopens E: through CIO with `RAMTOP=$C0`, yielding the real
`MEMTOP=$BC1F` and screen at `$BC40`. Other inadequate bounds remain errors.
State fields are generated from
the profile base and ABI offsets. Larger resident Atari DOS layouts remain
unsupported; Exec's own DOS/file services are independent of that restriction.
This boundary does not itself qualify a particular third-party loader.

The ordinary bitmap call adapter preserves all native registers and 24 bytes of
lower direct-page workspace on the calling Task's stack. Its synthesized RTL
target keeps the original program bank even for an entry at offset `$0000`;
RTL wraps PC without a carry into PBR. The bank-boundary correction and four
additional transient save bytes fit the existing console code/Task stack
reservations: **0 added fixed, root/kernel, per-Task or idle reserved bank-zero
bytes**. See the [workbench development record](../history/fastbasic-workbench.md)
for the raw/optimized register and boundary probes.

Ordinary compiled globals default to a 2 KiB `image_data` arena in the selected
upper kernel bank, after resident metadata and 256-byte alignment. Emitted code
starts after the full arena. The image owns its bank even when some capacity is
unused; packaging rejects code/metadata overlap, arena overflow and resident
image payload in bank zero.

For a linked foreign image, native code starts above the foreign image's full
banks. The bitmap/desktop C image uses code bank `$0C`, data bank `$0D`, and
code banks `$0E` and `$10` as needed for composed AES applications. GEM renderer
lookup tables occupy read-only bank `$0F`, reserving its full 64 KiB including
unused capacity. The composed standard-dialog desktop uses `$10` and starts
native code at `$110000`; smaller images start above their highest populated
foreign bank. Runtime renderer bindings check generated executable extents,
including additional code banks only when populated. The existing native data
arena and all stack/DP reservations stay in place. The effective origin is
recorded in `memory.json` and `layout.json`;
normal extent and bank-ownership checks still apply to the combined image.

The text demo reserves an 8 KiB upper static arena for its composed application
state, controller, session registry and resident literals. The SS8 standard and
shell-only builds each use 8,144 of 8,192 bytes (48 spare). The standalone bitmap
profile adds one 256-byte page, for 8,448 bytes. Desktop profiles reserve 9 KiB;
the SS8 GEM desktop uses 8,578 of 9,216 bytes (638 spare). These capacities are
selected by `tools/build_demo.py`; code placement remains page-aligned.

The opt-in text and bitmap/desktop SDX demos select a 12 KiB upper static arena
for the composed shell controller and guest service globals. They use the
existing 544-byte guarded SDX direct-page pool described above, with no
additional fixed or per-Task bank-zero growth beyond that enabled profile.

Session contexts, cooked editors, histories and console models use ordinary
upper heap allocations. Desktop event/content requests additionally allocate
208 bytes only while attached. The sole console backing remains 40,960 bytes
in VRAM. SS1–SS8 add **0 fixed, 0 per-public-Task and 0 idle reserved bank-zero
bytes**, including guards, alignment and unused capacity; no Task pools grow.
Per-build emitted spans and heap/stack observations are recorded in
[session evidence](../history/shell-sessions.md).

The desktop's shared C runtime and renderer lookup tables are included in the
compressed boot image. The loader expands all initialized extents before native
startup publishes C bindings. They remain resident for the session. The panel,
counter, Files, calculator, dialog example and text viewer remain separate
disk-loaded APPs with Process-owned lifetimes. There is no shared GUI component
file or native component-loader arena.
Optional bitmap payloads inherit the matching demo’s arena size. Task pools and
all bank-zero reservations are unchanged. Build reports record the selected
capacity and actual image extents; standalone fixtures keep their separately
recorded profiles.

The profile reserves **`$8000–$8FFF` (4 KiB) for the VBXE CPU aperture** during
loading and runtime. The standard twelve-Task map uses the
[audited high RAM](../history/high-bank-zero-audit.md) while preserving the
ROM display list at `$BC20–$BC3F` and screen at `$BC40–$BFFF`:

| Twelve-Task range | Ownership |
| --- | --- |
| `$0A00–$0AFF` | Adapter state |
| `$0B00–$0BFF` | Boot state |
| `$0C00–$0CFF` | Kernel DP |
| `$0D00–$14FF` | Public Task DPs 0–7 |
| `$1500–$15FF` | Idle DP, logical slot 12 |
| `$1600–$25FF` | Resident platform adapter, including padding |
| `$2600–$62DF` | Existing root, kernel, worker and idle stacks with guards |
| `$62E0–$7FFF` | 7,456 bytes available after startup, before optional SDX pages |
| `$8000–$8FFF` | VBXE CPU aperture |
| `$9000–$93FF` | Public Task DPs 8–11 |
| `$9400–$ADDF` | New worker stacks with guards |
| `$ADE0–$BBFF` | 3,616 unreserved bytes |
| `$BC00–$FFFF` | OS display, boundary slack, ROM and hardware |

The [platform profile](../../platform/altirraos/memory-4m.json) publishes explicit
per-capacity `direct_pages`, stack bases and sizes. Generated arrays are
authoritative; do not derive later DPs from the root's address. Four-Task
fixtures keep the full near bank-table reservation; eight- and twelve-Task
builds keep that table in upper RAM. Unsupported maps and overlaps fail packaging.

Root and kernel stacks remain at `$2610` and `$2C30`, each with 1,536 bytes and
two 16-byte guards. Public slots 1–5 and 8–10 have 1,312 stack bytes; slots 6,
7 and 11 have 2,560 bytes. New bases are `$9410`, `$9950`, `$9E90` and `$A3D0`.
Idle retains `$60D0` with 512 bytes. Every stack includes a 256-byte interrupt
reserve; every DP is exactly 256 bytes without outer guards or padding.

Relative to the previous eight-Task SDX map, new public pools reserve 7,648
bytes (three at 1,600 and one at 2,848, including DP and stack guards). Existing
slots, root, kernel, idle and fixed Exec reservations each add zero bytes.
Reducing the OS reservation by 11,264 bytes gives a net 3,616-byte reduction
in total reserved bank zero. The SDX-enabled standard demo leaves 10,528 bytes
unreserved. See [Task capacity](../architecture/task-capacity.md) for the full
budget and [development evidence](../history/twelve-task-layout.md).

Temporary staging occupies `$62F0–$66FF`, the manifest `$6700–$6EFF`, and the
loader `$6F00–$7BFF`. They form one boot arena clear of every persistent pool.
`phase_reservations` records loading, initialization and runtime ownership;
`runtime_free_ranges` records the complement after startup. Initialization
retains the manifest after retiring loader/staging. The full free range becomes
reusable only at `startup_complete`; it is not registered with the general heap.

[Compressed boot loading](boot-loading.md) streams independent LZ4 blocks
through the same staging area after OF816 returns. Decoder code/state fit the
existing loader capacity, with **0 fixed and 0 per-Task reserved bank-zero
bytes added**, including guards, alignment and unused capacity. Expanded kernel
storage and startup ownership phases are unchanged.

Moving the start from `$0800` to `$0A00` protects 512 additional low bytes.
The OS/loader reservation grows by **512**; fixed Exec runtime and per-Task
reservations do not change from that relocation. The
[low-memory relocation checks](../development/memory-low-a00.json) retain the
original relocated profile before the subsequent stack growth.

The [larger-stack record](../development/larger-task-stacks.json) accounts for
slots 6 and 7 growing by 1,536 bytes each. The subsequent
[application headroom change](../history/gem-application-stack-headroom.md) and
[file-selector change](../history/file-selector.md#fsel4-loadable-consumer-and-of816-package)
add 256 and 32 bytes respectively to each ordinary pool. Integrating these
changes into the current `$0A00` map adds **288 bytes per slot 1–5**, or
**1,440 reserved bank-zero bytes** total. Fixed runtime, root, kernel, slots
6–7 and idle add **0**. Guards, alignment and interrupt reserves are unchanged.

The boot arena moves to `$62F0–$7BFF`; temporary loader capacity shrinks from
4,608 to **3,328 bytes**, retaining its `$7C00` end and diagnostic scratch space.
The linker bounds the emitted compressed loader. The manifest permits 96
extents within its existing 2,048-byte reservation (1,056 bytes at 64 banks),
with byte-sized extent indexes. Eight-Task runtime reserves **58,080 bytes**
including OS ranges, initialization **60,128**, and loading **51,600**.
The guarded idle stack ends at `$62E0` exclusive, leaving 16 bytes before
staging. Four-Task runtime remains **51,904 bytes**; its loading reservation
is **52,848**. All totals include unused reserved capacity. Pools may not
overlap any part of the boot arena, even when phase lifetimes differ.

[Bank-zero compaction](../development/bank-zero-compaction.json) combines nine
holes into one for eight Tasks, with zero change in total reservations or
per-Task cost. Removing an obsolete near context reservation also saves 240
fixed bytes for four Tasks. The current relocated map leaves `$4AC0–$7FFF`
(13,632 bytes) contiguous.
Both budgets include guards and full reserved capacity. The earlier
[DP compaction record](../development/dp-compaction.json) preserves its separate
192/2,336-byte savings and historical addresses.

OF816 borrows the root DP and guarded root/kernel stacks before handoff:
3,392 bytes for that temporary lifetime. Test-only scratch is declared separately
in `diagnostic_scratch` and checked against every live phase. It does not reserve
production bytes; instrumented runs must report their borrowing and restore
scratch when the observation ends.

The monitor runs inside an INITAD activation before the main image records.
Its eight-byte saved caller context remains on the live page-one loader stack;
ROM calls and native interrupt wrappers use an anchor below that frame. The
monitor restores the context and returns with RTS before payload loading
resumes. It retires its keyboard, vectors and borrowed native storage at that
return. The manifest, staging and loader remain live until their existing
startup boundaries; returning from the monitor does not retire them early.

The [boot-only SIO reader](boot-loading.md#boot-only-sio-reader) reserves the
complete `$4000–$5FFF` arena during split-XEX and ATR loading. It borrows idle
Task stacks, including intersecting guards and spare capacity, and retires
before those stacks are initialized. This adds 8,192 loading-phase bytes to
the split profile and zero beyond the ATR's existing reader reservation;
fixed/root/kernel/per-public-Task/idle runtime growth is zero. Generated media
reports include the full union and per-pool intersections. ROM VBI remains
active while its serial-vector transitions exclude serial IRQs and deferred
OS I/O; no boot handler survives native handoff.

The reserved aperture supports the optional [display adapter](display.md). The
[aperture development record](../development/vbxe-aperture.json) covers the
unmapped RAM reservation, loading, Task execution and OF816 handoff; mapped
VBXE hardware requires a separate configuration pin and integration checks.

The optional [GEM development pin](../../toolchain/altirra-gem-vdi.json) selects
FX 1.26 at `$D600` with private 512 KiB VRAM. Its
[G0 probe](../../ports/gem4xe/README.md) reads identity without enabling mapping
or presentation, and rejects absent/unsupported hardware. The G3 adapter adds
shared console/graphics ownership, bounded completion, mapped VRAM readback and
reset-required recovery. The [G4 backend](../../ports/gem4xe/adapter/README.md)
connects selected GEM rendering to that service with pixel and scanout checks.
Standard pins still require add-ons off; the combined drawing/peer/SDFS workload
remains G5.

Heap and resident metadata stay in upper RAM
where the profile permits. See [Task capacity](../architecture/task-capacity.md)
for supported layouts; do not copy old code origins or memory totals into new
build assumptions.

Compiler frame reports do not prove whole-Task stack bounds. Budget call depth,
interrupt headroom and adapter nesting. Keep [stack checks](../contributing/stack-checks.md)
enabled for ordinary builds; guards are diagnostic protection, not address-space
isolation.

### Boot service settings

The loader publishes the eight-byte record in [boot-v1.json](../../abi/boot-v1.json).
Use `memory.json`'s `boot_config` address, not a hard-coded historical location.
The fields are magic `$4245`, version 1, record size 8, cache-block count,
system-drive byte and a flags byte. Bit 0 enables technical kernel boot output;
other flag bits must be zero. Verbose output defaults on. OF816's
`BOOT-VERBOSE@` and `BOOT-VERBOSE!` inspect/change this flag before handoff.

Kernel diagnostics use CIO on the existing OS screen before console ownership.
They report memory bounds, kernel/table banks, skipped firmware bank, DP/stack
placement, memory adoption, Task/heap initialization and detected VBXE hardware.
Memory adoption and Task/heap initialization each print a single `OK` or `FAILED`
result. `VBI/IRQ       =OK` follows vector/state installation and interrupt enable;
`CONSOLE WORKER=OK` follows worker signal/endpoint setup, before display claim.
Console admission already blocks ROM entry, so this one line appends directly
to the OS text screen with cursor updates under IRQ/NMI exclusion.
Both automatic text startup and deferred bitmap startup activate the startup
phase and OS-screen snapshot before Task initialization.
These messages report completed initialization, not interrupt qualification.
After its console stream opens, the resident shell prints `CONSOLE       =OK` and
`SHELL         =LAUNCHED` through retained console output. Session/streams/initial aliases
are then established; mounting and startup scripts follow, with the prompt
marking interactive readiness. Quiet mode suppresses routine milestones.
All technical diagnostic lines begin at column zero, with `=` in column 14
(zero based), including the handoff from ROM output to the retained console.
ROM reporting temporarily selects full-width margins and restores them afterward.

Terminal kernel failures during this startup phase print `System halted: $hhhh`
even in quiet mode. Console admission failure is `$FF95`; heap/Task initialization
and later startup faults retain their original native code. The adapter records
the first cause before a subsequent reset-required status can replace `STATUS`.
Terminal reporting abandons the faulting stack, uses kernel DP/stack, disables
IRQ/NMI and writes the final OS text row directly after console restoration.
It does not allocate, call ROM or wait for the worker. A reset-required path
exposes the saved OS text display, disabling an owned FX overlay, but retains
DMA/bus ownership and storage; this is reporting, not device recovery.
Loader/unclaimed-state rejection retains its separate pre-kernel path. Ordinary
command errors after shell launch do not produce this fatal-startup message.

OS success reports retain the existing private stack buffer and OS_BUSY protocol,
preserving native context and IOCB0. Startup phase, first cause and OS display
snapshot occupy spare bytes in the existing adapter state page. Two further
spare bytes retain the text console's incoming character/priority shadows for
normal and terminal restoration. Native routines
fit existing upper code reservations: **0 fixed, 0 per-public-Task and 0 idle
reserved bank-zero byte growth**, including guards, alignment and unused capacity.

The first setup callback initializes defaults once, before OF816. A monitor may
change settings before `loader_start`; resumed copy/zero-fill callbacks preserve
the entire boot record and skip initialization. Task initialization validates
and captures cache/drive requests before admission; later writes do not change
those services. The trace flag is read during boot. Invalid headers or drive values select
build defaults with status 1; invalid cache capacity selects defaults with status
2; valid input has status 0.

Cache blocks count 128-byte units: default 512, or zero/powers of two 16..2048.
The system drive is 1..8 when a system mount is selected, otherwise zero. Zero
is invalid with a selected system mount; nonzero is invalid without one. A valid
drive conflicting with another configured mount fails validation rather than
silently selecting a fallback. See [SYS:](sys-volume.md) and the
[boot monitor guide](../guides/boot-monitor.md).

## COP gateway

Exec uses **COP #$50**. The low byte of A selects the service; generated
[tasks.json](../../abi/tasks.json) and related ABI files define call layouts.
Native core calls require 16-bit accumulator and index widths. Simple services
may take a short path through the same gateway; public helper routines may use
ordinary calls where no kernel operation is needed.

Preserve AltirraOS's COP #$00 bridge and leave WDC-reserved `$80–$FF` signatures
unused. Chain other signatures to the saved dispatcher. On the pinned ROM the
adapter must intercept through VCOPN; installing only VCOPU does not provide the
required route. The compiler's standalone COP #$00 yield bridge cannot be
installed unchanged into this environment.

Save context before using shared workspace. Unknown service selectors have a
defined error/fault path. No kernel activation remains across a resident-driver
callback: those execute on the caller's stack/DP through the
[resident driver contract](resident-drivers.md).

## VBI preemption

ANTIC vertical blank supplies the scheduling tick; DLI remains disabled. A switch
may occur only after required OS VBI work has retired and the interrupted context
is an eligible native Task. Do not suspend a live OS/interrupt activation as a
normal Task.

Defer switching while the interrupted I flag, an OS call, Forbid or a context
transition prevents it. Retain a pending reschedule request for a safe boundary.
**SEI does not mask NMI.** The SWITCHING protocol covers asynchronous entry,
partial saves/restores and stack/DP changes; IRQ masking alone is insufficient.
The ROM's emulation-mode transition needs the adapter's controlled page-one
stack, not an arbitrary native Task stack.

The [runtime model](../architecture/runtime.md) describes caller and worker
contexts. The [preemption implementation record](../history/vbi-preemption.md)
retains the entry protocol and original executable evidence.

## Deferred native completion

The fixed native source table has one production source, timer, and one
diagnostic-only source. [native-interrupts.json](../../abi/native-interrupts.json)
defines byte-wide enabled/pending/running/blocked flags, an activation guard and
a budget of two callbacks per opportunity. These descriptors are adapter-owned
and immutable; they are distinct from public EXECPRODUCER signal bindings.
There is no application callback registration interface.

Raw VBI updates the versioned timer clock and retains a hint. It never touches
reply links or calls compiled code. After ROM retirement, a fully saved native
Task frame can admit bounded assembly work if its original I bit is clear,
stack/DP ownership is valid, and no OS, IRQ, queue transaction or native service
activation is live. Forbid prevents Task scheduling but permits this service.
Driver edit gates mark only their own source blocked. Timer release publishes
a hint for an armed queue before unblocking it; the enclosing I/O wrapper's
Permit provides the native service opportunity, even under an outer Forbid.
No second VBI is required for a deadline reached during first insertion.
Acknowledgement precedes the callback, preserving a new hint
arriving while the callback runs. IRQ opportunities between replies/callbacks
retain activation ownership against recursive NMI dispatch.

COP/fast-service and eligible interrupt exits share a final work/wake check after
retiring compiled policy and selecting a complete frame. A nested NMI in the
adapter's restore-only ranges, including the empty IRQ-return check, may patch
that frame's PC to an internal COP trampoline. The original PC/PBR is retained
per Task; the trampoline restores it and requests a fresh scheduling decision.
An armed redirect also prevents interrupt-exit scheduling until that COP consumes
the saved PC, including an interrupt immediately after RTI. This prevents Task
removal or slot reuse while return state is still live.
Only recognized instruction ranges and an original unmasked Task frame qualify.
An IRQ/NMI restore around a private adapter entry which still holds SWITCHING
does not qualify, even with a valid Task stack/DP and I=0. COP's own classified
restore may finish its guarded transition. Foreign/ROM frames are never redirected. No extra VBI is needed for a reply
arriving after the last wake check. Idle revisits bounded service opportunities
while eligible work remains; runnable Tasks can retain excess backlog until the
next safe opportunity. See the instruction/exit inventory and measured limits
in the [implementation record](../history/interrupt-reply.md).

Storage occupies the already reserved upper Task bank: `$5A00–$5AFF`
source state, `$5B00–$5CFF` timer state, `$5D00–$5FFF` alignment capacity and
`$6000–$7FFF` native code, including pointer capture routines. The complete
suballocation is 9,728 bytes including 768 alignment bytes and unused code
capacity. MA1 moved state within this bank to accommodate the larger pointer
ring; source and timer state sizes are unchanged. Fixed and per-Task bank-zero
reservation deltas are both **0 bytes**. Linker limits retain the existing near
adapter reservation; no private interrupt stack or timer Task is allocated.

## OS calls

Serialize OS calls while keeping required hardware interrupts functional. The
adapter establishes mode, widths, DP, bank registers and the OS stack, then
restores the caller. Never truncate a far pointer into an OS near address;
stage buffers where necessary. No reentrant ROM service is assumed.

The small `EXECOS.Write` adapter accepts 0–255 bytes from the resident compiled
data arena. Banked builds stage the bytes on the caller's checked stack while
`OS_BUSY` excludes switching, before entering ROM on the separate OS stack.
Its local stack peak is 266 bytes, including 256 temporary buffer bytes; it adds
no permanent bank-zero reservation. It is not a general far-buffer console API.

Native console ownership excludes conflicting ROM console use until shutdown.
Native SIO ownership likewise excludes ROM serial/POKEY use. Shutdown must retire
workers and live hardware/OS activations before restoring saved vectors, state
and MEMLO. Controlled launcher completion is not an arbitrary DOS return.

## Native SIO ownership

The SIO worker owns physical transactions. Native IRQ code owns time-sensitive
byte progress; Task callbacks own bounded queue/state updates. Descriptor
publication, cancellation and retirement follow the IRQ/NMI protocol, retaining
Task and signal lifetime until all posts and wakes retire. See
[resident drivers](resident-drivers.md) and [device I/O](device-io.md).

POKEY timer 1 configuration, its emulation vector and IRQ enable composition
belong to the fixed platform timing component. It has independent SIO-alarm,
pointer-sampling and blitter-watchdog demands. A display owner retains its timer
participation while open, but requests timer edges only while an asynchronous
list is ARMED. Its bounded check reads the VBI deadline, not blitter BUSY.
Each acknowledged edge advances an armed alarm at
most once; serial RX/TX receive bounded service opportunities around sampling.
SIO retains timer 2 and its watchdog, transfer and recovery policy. Timer 1 uses
divisor 15 normally (3,958.6 Hz on PAL). SIO requests divisor 7 for COMMAND
setup/transmission/hold and write turnaround, retaining its fine-alarm units.
Pointer capture uses every normal edge and every second fine edge. Changing
AUDF1 does not reset the timer; the first interval can retain the old reload.
The capture divider resets at rate changes and pointer acquisition/release.
SIO transaction setup still resets STIMER before serial transmission; joining
an existing timing owner does not reset it. A new owned timer
edge arriving during keyboard capture remains latched for the next native IRQ;
it is never delegated to the ROM handler while the timing owner remains live.

The first compatible owner establishes a silent baseline for its audio/timing
registers using write shadows, never POKEY's unrelated read aliases. Existing
timer ownership outside this protocol is incompatible. SIO release restores its
serial resources while preserving surviving sampling/watchdog demand; last timer release
restores its vector and silent baseline. Task-side transitions use SWITCHING and
local IRQ masking, covering asynchronous NMI entry as well as IRQ. The fixed
ST/port 2 pointer backend uses this clock for public INPUT capture; diagnostic
sampling counters and test entry points are excluded from production. See
[mouse development](../history/gem-mouse.md) and the
[4 kHz development record](../history/mouse-performance.md).

Timed relative pointer capture measures short intervals with a saturating
`VCOUNT` age under the same sampling-gap contract. It does not derive time from
the number of normal/fine POKEY IRQs or from Task scheduling. See the
[INPUT representation and limits](input.md#st-mouse-capture). The guarded
64-sample ring reserves `$4800–$51FF` in the upper Task bank. Its 2,304 live bytes,
two 16-byte guards and 224 spare bytes use no bank-zero storage. The pointer
routines share the existing native-code reservation at `$6000–$7FFF`, with
same-bank near calls and unchanged public interrupt entry protocols.

The VBXE backend participates in both native and emulation IRQ routing, including
when SIO owns the serial route. It acknowledges only its owned source and chains
unowned work. The emulation shim has an inactive fast path; its active path
preserves the page-one frame and full native context. Neither it nor the timer
watchdog switches a live OS activation. Launch publishes ID/deadline and ARMED
under IRQ masking before enabling and starting hardware; NMI may record ticks
but cannot consume this state or switch across the protected entry protocol.

The generated [blitter layout](../../abi/blitter.json) reserves 64 bytes after
the serial binding in upper Task metadata. Its 2 KiB code reservation starts at
offset `$5200` in the existing upper Task bank, outside the guarded pointer capture
reservation. Packaging checks segment bounds and overlap. The bank-zero shim
fits the existing resident adapter segment; fixed, root/kernel, per-Task and
idle bank-zero reservation deltas are all zero, including guards and padding.
No extra Task, DP, stack or CPU bank is allocated. See the
[implementation record](../history/blitter-completion-irqs.md) for measured costs.

Peripheral speed, RX/TX timing, recovery and coexistence are profile-dependent.
Pinned emulator evidence does not qualify other profiles or real hardware.

## Startup and qualification

The [build guide](../contributing/building.md) identifies current toolchain and
platform pins. The [demo guide](../guides/demo.md) gives its exact user-facing
configuration. Boot validates image extents, reservations and ABI before entry;
native console startup must succeed before entering an application that requires
it. OF816 settings use the same boot record as direct XEX startup.

Use the [testing policy](../contributing/testing.md) for focused checks versus
release qualification. Compiler tests alone do not qualify the hosted system.
The [original platform document](../history/platform-contract.md) preserves
historical addresses, measurements and migration details.
