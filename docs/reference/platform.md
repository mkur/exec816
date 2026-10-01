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

Initialization may clear the page before a new owner runs. During its lifetime,
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
revalidates retired manifest bytes. The boot-state page at `$2C00–$2CFF` stays
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
loading and runtime. Boot staging is at `$0900–$0D0F`. In the eight-Task layout,
slot 7's stack moves to `$0D20–$111F` and idle to `$7CB0–$7EAF`, each with
16-byte guards on both ends. Other pools retain their locations and sizes;
the four-Task layout already fits below the aperture. Staging and the retired
manifest remain unavailable to a general heap until explicitly registered.

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
