# AltirraOS platform contract

[Reference index](README.md)

The initial platform is the dedicated AltirraOS 65816 ROM under pinned AltirraSDL
configurations. Exec owns native Tasks, scheduling and resource lifetime; its
adapter controls OS entry, hardware ownership and context transitions. Compiler
semantics and ABI primitives belong to actionc; emulator correctness belongs to
actionc-vm. Platform tests must qualify the hosted combination.

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

Each DP reservation is exactly 256 bytes, with no external canaries or stride
padding. Initialization clears that page and publishes metadata before a new
owner runs. Stack canaries and checked stack bounds remain enabled. During its lifetime,
the lower half may contain arbitrary caller state. Temporary stack-based D values
and the ROM's DP have their separately defined layouts. Native register, bank,
mode and stack restoration must preserve the complete interrupted context.

The bank manager validates usable banks and image reservations before payload
writes. The [heap](memory.md) allocates byte ranges from registered memory.
`kernel_bank` in [kernel.json](../../config/kernel.json) selects the resident
image's starting bank: require 1..255, below MAX_BANKS, and usable mapped RAM.
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
bootstrap frame and callback. The manifest at `$6000–$67FF` remains protected
through memory adoption, Task initialization and boot-setting capture. The
adapter publishes `M_RETIRED=1` at `startup_complete`, before Task dispatch;
only then is that entire range reusable. Failed startup does not publish it.
Repeated memory adoption/initialization uses the live adoption state and never
revalidates retired manifest bytes. The boot-state page at `$0900–$09FF` stays
reserved, including shutdown information. Restarting retired bootstrap code is
unsupported; a cold boot reloads the manifest.

The no-resident-Atari-DOS profile reserves `$0000–$07FF` for the OS and places
the 256-byte adapter state at `$0800–$08FF`. Both loader and hosted entry require
the original `MEMLO <= $0800`; hosted entry checks before writing that page.
`MEMTOP` must still cover `$9000`. State fields are generated from the profile
base and ABI offsets. Exec's own DOS/file services are independent of this
resident Atari DOS restriction.

Ordinary compiled globals occupy a 2 KiB `image_data` arena in the selected
upper kernel bank, after resident metadata and 256-byte alignment. Emitted code
starts after the full arena. The image owns its bank even when some capacity is
unused; packaging rejects code/metadata overlap, arena overflow and resident
image payload in bank zero.

The profile reserves **`$8000–$8FFF` (4 KiB) for the VBXE CPU aperture** during
loading and runtime. Persistent Exec reservations are packed below it:

| Eight-Task range | Ownership |
| --- | --- |
| `$0800–$08FF` | Adapter state |
| `$0900–$09FF` | Boot state |
| `$0A00–$0AFF` | Kernel DP |
| `$0B00–$12FF` | Public Task DPs |
| `$1300–$13FF` | Idle DP |
| `$1400–$23FF` | Resident platform adapter, including segment padding |
| `$2400–$5B3F` | Root, kernel, worker and idle stacks, including guards |
| `$5B40–$7FFF` | 9,408 unreserved bytes after startup |

The [platform profile](../../platform/altirraos/memory-1m.json) defines physical
placement. Kernel DP is `$0A00`; public slot `i` owns `$0B00+i*$100`, and idle
owns slot `capacity`. Four-Task DPs end at `$0FFF`, followed by the full near
bank-table reservation at `$1000–$13FF`. The eight-Task table is in upper RAM.
Generated assembly/Action! constants and the resident linker configuration use
this profile. Unsupported capacities and overlaps are rejected.

The root stack starts at `$2410`, the kernel stack at `$2A30`; each reserves
1,536 stack bytes with 16-byte guards at both ends. Other stack bases and sizes
are published in `task_pools`; see [Task capacity](../architecture/task-capacity.md).
All DPs remain exactly 256 bytes without guards. In the eight-Task profile,
slots 1–5 have 1,024-byte stacks, slots 6–7 have 2,560 bytes and private idle
has 512 bytes. Every stack retains checked bounds and an internal 256-byte
interrupt reserve. Four-Task pools remain 1,536 bytes each.

Temporary staging occupies `$5BF0–$5FFF`, the manifest `$6000–$67FF`, and the
loader `$6800–$7BFF`. They form one boot arena clear of every persistent pool.
`phase_reservations` records loading, initialization and runtime ownership;
`runtime_free_ranges` records the complement after startup. Initialization
retains the manifest after retiring loader/staging. The full free range becomes
reusable only at `startup_complete`; it is not registered with the general heap.

The [larger-stack development record](../development/larger-task-stacks.json)
accounts for the 3,072-byte increase over the compact eight-Task map: fixed
delta 0, slots 6 and 7 +1,536 bytes each, all other pools unchanged. Runtime
reserves 56,128 bytes including OS ranges; initialization reserves 58,176
while the manifest is live, and loading remains 52,592. The guarded idle stack
ends at `$5B40` exclusive, leaving 176 bytes before staging. Pools may not
overlap any part of the boot arena, even when phase lifetimes differ.

[Bank-zero compaction](../development/bank-zero-compaction.json) combines nine
holes into one for eight Tasks, with zero change in total reservations or
per-Task cost. Removing an obsolete near context reservation also saves 240
fixed bytes for four Tasks, leaving `$48C0–$7FFF` (14,144 bytes) contiguous.
Both budgets include guards and full reserved capacity. The earlier
[DP compaction record](../development/dp-compaction.json) preserves its separate
192/2,336-byte savings and historical addresses.

OF816 borrows the root DP and guarded root/kernel stacks before handoff:
3,392 bytes for that temporary lifetime. Test-only scratch is declared separately
in `diagnostic_scratch` and checked against every live phase. It does not reserve
production bytes; instrumented runs must report their borrowing and restore
scratch when the observation ends.

This reserves address space only. The current adapter does not enable VBXE,
manage its window registers or hand display ownership to GEM. The
[aperture development record](../development/vbxe-aperture.json) covers the
unmapped RAM reservation, loading, Task execution and OF816 handoff; mapped
VBXE hardware requires a separate configuration pin and integration checks.

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
system-drive byte and a reserved zero byte.

The loader initializes defaults during startup. A monitor may change settings
before `loader_start`; Task initialization validates and captures them before
admission. Later writes have no effect. Invalid headers or drive values select
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
