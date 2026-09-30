# Initial AltirraOS platform contract

> Historical record: applies to the revisions and profiles described below.
> See the [current documentation](../reference/platform.md) and [history index](README.md).

Status: design baseline with an executable [OS-boundary probe](os-boundary-probe.md)
on the [pinned platform](../../toolchain/altirra.json). The
[single-program launcher and console adapter](native-launch.md) and
[two-task cooperative gateway/scheduler](cooperative-tasks.md) and
[VBI preemption](vbi-preemption.md) are implemented for the pinned machine.
Unresolved details below must be settled before dependent code is qualified.
The current emulator pins include the [native interrupt masking correction](emulator-native-irq-fix.md)
required by Task integration qualification; the ROM and machine profiles are unchanged.

## Repository and platform boundary

Exec816's first platform is the dedicated AltirraOS 65816 build under Altirra.
Exec owns native task contexts, scheduling policy, resource lifetimes and its
allocated memory. AltirraOS supplies initial console, keyboard and I/O services
through an explicit adapter.

The kernel must keep platform dependencies behind interfaces so a later
bare-metal implementation can replace the adapter. Compiler-specific changes
belong in actionc, with minimal compiler regressions there and system tests here.

## Compiler and memory contract

The compiler pin is [toolchain/actionc.json](../../toolchain/actionc.json).
Use `wdc-65816-native`, ABI `action65816.native.v2`, and version-3 native images (version 4 when runtime division/remainder requires
the arithmetic-fault adapter).
Import generated ABI constants from that same revision. The
[earlier compiler migration record](compiler-ae1f555-qualification.md) describes
native-v1 frame maps; it does not qualify the current DP layout.
The [DP partition plan](../plans/direct-page-partition-implementation-plan.md) tracks
native-v2 development checks and the required program rebuild.
The [stack-check build setting](../contributing/stack-checks.md) extends that pin with an
explicit opt-out; ordinary builds retain compiler and assembly checks.

Runtime DIV/MOD uses the pinned compiler's raw `__a816_arithmetic_fault_v2`
contract: JML, A16=1 for division by zero, X16=S, native 16-bit widths, DBR=0,
D/I preserved. The distinct launcher entry terminates through the existing
fault/OS-restoration path with status `$FF97`; the existing fault report cells
hold the reason and S. It adds no reserved bank-zero bytes. Version-4 packaging
requires this exact assembled address and retains version-3 frame checks.
This kernel binding does not add an arithmetic provider to the external-command
ABI; command import support remains independently constrained.

Each task owns its stack, aligned direct-page domain and invocation storage.
Saving the D register does not copy the domain it points to. The platform must
reserve nonoverlapping bank-zero regions for OS state, bootstrap, task and
interrupt stacks/domains, bridge code and relevant vectors. Banked code/data
must fit the selected machine's actual memory map.

D remains the base of an aligned 256-byte domain:

| D-relative bytes | Ownership |
| --- | --- |
| `$00–$7F` | Caller/runtime workspace, preserved by Action! and Exec helpers. |
| `$80–$BF` | Compiler call-clobbered scratch. |
| `$C0–$C2` | Owner pointer. |
| `$C3` | Domain kind. |
| `$C4–$C7` | Stack floor and ceiling. |
| `$C8–$FF` | Reserved zero. |

Initialization/reuse may clear the whole page before a new owner runs. During
its lifetime the lower half may hold arbitrary data; it is never copied on
calls or switches. Kernel/interrupt domains keep separate pages. Temporary D
values addressing an activation's stack keep their local layouts; ROM DP is
outside this ABI. Constants in `lib/exec/a816abi.act` and `abi/native-dp.json`
are generated from the pinned compiler manifest by `tools/generate_native_abi.py`.
Fixed and per-task bank-zero reservation deltas are both **0 bytes**, including
guards, alignment, pool stride and unused capacity.

Only native-v2 programs and compact o65 v3 commands (`A8C3`) are current.
Compact descriptors remain eight bytes plus four bytes per import. Rebuild all
programs after changing the native ABI; old artifacts are rejected before entry.

The memory layer is a [bank manager](bank-manager.md), initialized from
an explicitly qualified platform map before banked payload writes. It owns
whole-bank availability, system/image reservations and client claims; future
heap allocation consumes banks through that interface. Bank zero remains
outside whole-bank acquisition and keeps explicit range reservations. The
[banked launcher](banked-loading.md) uses a separate pinned upper-RAM profile;
the original PAL/64K profile retains its bank-zero loading path.
Byte-level allocation follows the [classic Exec design](../reference/memory.md),
including explicit bank-zero selection and IRQ-permitting serialization for SIO.
The four-task layout keeps the ownership table in bank zero, with four
active bytes per `MAX_BANKS` entry inside a 1 KiB reservation. The
[eight-task layout](../architecture/task-capacity.md) moves it to the configured kernel
bank and releases that bank-zero arena. This build limit includes bank zero
and is independent of physical RAM; the default 16 entries occupy 64 bytes.

The initial compiler frame limit is 254 bytes including spills. Stack-relative
accesses have additional displacement limits. Image maps give local costs, not
whole-task stack bounds; Exec must budget call depth and platform interrupt
headroom. The hosted bridge must establish its own headroom requirement rather
than assuming the standalone bridge's figures cover OS handlers.

### Boot service settings

The banked loader publishes the eight-byte little-endian record defined in
[abi/boot-v1.json](../../abi/boot-v1.json). Its address is generated in
`memory.json` under `boot_config`; consumers must use that metadata rather than
hard-code the current `$2C80` placement. The record occupies eight previously
unused bytes inside the existing 256-byte boot-state reservation.

| Offset | Width | Field |
| --- | --- | --- |
| 0 | 2 | Magic `$4245` |
| 2 | 1 | Version, currently 1 |
| 3 | 1 | Record size, currently 8 |
| 4 | 2 | Cache capacity in 128-byte blocks |
| 6 | 1 | System drive: 1..8 with a selected mount, otherwise 0 |
| 7 | 1 | Reserved zero |

The loader initializes this record after clearing boot state during its first
INITAD. A monitor may change it after loading, before `loader_start`. Native
Task initialization copies validated settings into resident upper RAM before
admission; later changes to the input record have no effect. Defaults apply to
direct XEX startup as well as monitor startup. An invalid header, reserved byte
or invalid system-drive value selects build defaults with status 1; an invalid
cache capacity selects defaults with status 2. Success has status 0.

`cache_blocks` in the kernel build configuration defaults to 512 (64 KiB).
Valid values are zero or powers of two from 16 through 2048. Zero retains only
the existing scratch-sector cache. The system-drive default comes from the
explicitly selected mount, or is zero when none is selected. Zero is invalid
when a system mount exists; nonzero is invalid when none exists. A valid drive
that conflicts with another configured unit/name fails mount validation with
`ERROR_OBJECT_IN_USE`; it does not fall back. See [SYS:](../reference/sys-volume.md).
Boot parameters add **0 fixed and 0 per-Task reserved bank-zero bytes**,
including padding, guards and unused capacity. Resident captured values occupy
four upper-RAM bytes.

### Kernel bank build parameter

The banked kernel's starting bank is selected at compile/link time through
`kernel_bank` in [config/kernel.json](../../config/kernel.json), default `$01`,
with a per-build `--kernel-bank` override. The platform map defines usable
banks; its historical `code_origin` no longer independently selects the bank.
Generated Action!/assembly definitions and build provenance record the resolved
`KERNEL_BANK`.

Require `1 <= KERNEL_BANK <= 255`, `KERNEL_BANK < MAX_BANKS`, and usable RAM at
the selected bank. Validate all image extents and reservations, including
additional banks occupied by growing code. This is the starting bank of the
shared kernel/application image, not a one-bank size limit. Bank-zero launch
profiles retain their separate layout.

The eight-task profile reserves the ownership table at `KERNEL_BANK << 16`.
Current Task builds then reserve the heap list, claim ledger and MemHeaders
before emitted code. At `MAX_BANKS=16`, that heap reservation is 512 bytes:
a separate 16-byte message-port registry follows it (11 active bytes).
A 256-byte device arena follows the port registry. A DOS association/error table then reserves 16 bytes per public task slot
(14 active), followed by a 96-byte filesystem service arena (96 active) and a
64-byte DOS stream registry (four 16-byte entries). The resident
[Process table](../reference/process.md) adds 128 bytes per public slot and a four-byte
identity counter, initialized by Task policy before admission.
These reservations are in upper RAM even when DOS mounts are disabled.
Four bytes for captured boot settings follow the resident reservations.
Eight-task code without console storage starts at
`(KERNEL_BANK << 16) + $878`, including the 64-byte bank table; four-task code
starts at `(KERNEL_BANK << 16) + $5F8`, retaining its bank-zero bank table. Minimal non-Task banked probes retain their original
origin. This prefix prevents metadata/code collisions without an internal
hole in the compiler's contiguous image. Packaging rejects overlaps with
all upper reservations. The resolved `memory.json` is authoritative.
Bootstrap and native manager use the generated address and preserve claims
through adoption. Changing the parameter requires a complete image rebuild;
runtime relocation remains outside the contract.

The [capacity qualification](../architecture/task-capacity.md) covers kernel banks 1 and 3,
raw and optimized emitted code, loading/adoption, switching, full saved
contexts and OS restoration. Invalid banks and overlapping extents are rejected.

### Native console publication

Task builds may enable `console` in [config/kernel.json](../../config/kernel.json)
or pass `--console` to the packager; `--no-console` overrides that configuration.
The default remains disabled. Root startup admits one console worker after
memory and Task initialization and enters user code only after the worker is
ready. Failure rolls back ownership and finishes with `$FF95` before user entry.
The public `console.device` uses the unchanged Exec I/O API; OpenDevice does not
create a worker. See the [console contract](../reference/console.md).

Enabled builds reserve another 672 bytes of metadata before upper-RAM code,
including retained foreground routes and the four-entry instance registry,
after 12 bytes of alignment following the Process table;
eight-task code therefore starts at `(KERNEL_BANK << 16) + $B20`. Capture,
boot bindings and tables fit existing upper Task storage. The worker uses an
existing slot and 2,048 heap payload bytes, with **no added bank-zero reservation**.
Console-disabled builds omit that console metadata and admit no console worker.
Additional [console instances](../reference/console-windows.md) allocate upper-RAM
cells, input and presentation state and share the existing worker. Their
creation/retirement protocol retains the owner and any worker borrow; no new
bank-zero reservation accompanies them. Release qualification of the window
changes remains pending under the [testing policy](../contributing/testing.md). Native route
mailbox/clear helpers expand the code subregion inside the existing upper Task
arena from 8,192 to 8,704 bytes; the full arena reservation is unchanged.
The [COP fast paths](kernel-fast-path-implementation.md) extend that native code
subregion to 9,216 bytes within the same upper Task arena. This changes neither
the full arena nor any bank-zero reservation.

While native console ownership is active, ROM console/foreign COP entry is
rejected just as for owned native SIO. Closing an instance retains its worker
and ownership; safe resident shutdown restores the exact borrowed screen and
changed keyboard/display state. Last-application removal accounts for console,
filesystem and SIO workers and initiates their coordinated retirement. Clients
must collect requests and close their instance before leaving; live borrowed
requests are not reclaimed implicitly. Unsafe SIO still parks at `$FF93`
before console cleanup or memory release. This publication qualification is
separate from the eight-task concurrent workload in console slice 8.

### Bank-zero memory budget

**Conserving bank-zero memory is a general Exec816 design requirement.** Native
65816 stacks and direct-page storage share bank zero with platform reservations.
Their capacity limits how many task contexts can be resident and how much stack
each can use. Additional upper RAM does not increase this budget. This principle
applies to every 65816 platform; the platform map determines which bank-zero
addresses are usable.

Prefer upper RAM for bulk kernel/application code, public Task records, ordinary
data and metadata that do not require bank-zero placement. Every new or enlarged
bank-zero reservation must identify the CPU, compiler ABI or platform requirement
that needs it. Other placement choices need an explicit tradeoff supported by
measurements, rather than convenience or an assumed preference for near memory.

For each implementation slice, report the change in reserved bank-zero bytes,
including zero change. When storage changes, record the before/after footprint,
separating fixed and per-task costs and distinguishing loading from steady
runtime. Count the complete reserved ranges, including alignment, guards and
unused capacity. Reducing an object's active size saves no allocatable space
until the corresponding reservation is reduced or made reusable.

- Size tables and pools for the configured capacity. Reserve additional capacity
  only when its purpose and cost are documented.
- Choose stack sizes from the needs of the workload, compiler calls and interrupt
  paths. Idle and worker tasks need not have identical allocations. Preserve
  required headroom and guards; smaller stacks require execution qualification.
- Reclaim boot-only storage after its last use. Document the handoff and ensure
  that callbacks, interrupts and retained pointers cannot still reference it.
- Keep the upper-RAM heap and bank-zero storage allocation as separate concerns.
  Increasing heap capacity must not be presented as increasing native stack or
  direct-page capacity.

The [current memory map](banked-loading.md#placement-and-lifetime) records the
implemented reservations and reuse. These rules guide future changes; they do
not release existing reservations or qualify smaller stacks. Placement changes
must update the machine-readable map/ABI inputs and pass the relevant overlap,
stack/domain, interrupt and OS-coexistence checks.

### Task capacity requirement

The asynchronous SIO driver and DOS/filesystem system must support **at least
eight simultaneously live tasks**, with a growth target of **12–16**. This count
includes the root/shell, device and filesystem workers, and applications; the
private idle context is additional. Kernel and interrupt storage must also be
budgeted separately. Ready, running and waiting tasks all count: each retains
its native stack and direct page until removal.

Make task capacity a build parameter with generated, configuration-sized context
and storage definitions. Eight is the required baseline for the future SIO/DOS
system; smaller layouts may be used for focused tests. Preserve the public
Task-pointer API as capacity grows. A 12- or 16-task configuration requires a
complete checked memory layout and workload/interrupt stack qualification before
it is advertised as supported.

The [eight-task layout](../architecture/task-capacity.md) meets this
simultaneous-capacity requirement with static pools. The default four-task
profile remains available; neither configuration qualifies twelve/sixteen tasks
or general SIO timing. Additional descriptors and sequential reuse do not
count as simultaneous capacity.

## COP gateway

Exec reserves **`COP #$50`** within its supported platform configuration.
A's low byte selects a service. The [Task kernel](../guides/tasks.md), currently reporting
`$0700`, provides AddTask, RemTask, FindTask, SetTaskPri, Forbid/Permit and the
five [signal calls](../reference/signals.md), plus the six system
[memory services](../reference/memory.md). The private-pool Allocate and
Deallocate pair uses native calls. Yield, Poll and timed Sleep remain
extensions. [tasks.json](../../abi/tasks.json) generates public/private layouts,
selectors, register arguments and results; [heap-v1.json](../../abi/heap-v1.json)
defines current memory call layouts. Core, signal and memory calls require M=X=0;
interrupted tasks retain complete native context in every M/X combination.
Priority is stored but ignored.

The Task policy permits IRQs under the SWITCHING guard; IRQ/NMI cannot reenter
the scheduler or borrow its compiler scratch. Only shared signal-mask,
wait-publication and wake-link transactions exclude maskable IRQs. Native
entry saves the full frame and asserts the guard before enabling IRQs for
ownership validation; native return masks and
rechecks pending wakes before restoring a task. The
[critical-section protocol](kernel-critical-sections.md) defines these
boundaries and scratch ownership. The pending-wake queue retains known targets
without a waiter scan. Blocking Wait preserves the caller's Forbid nesting. Disable/Enable
integration remains deferred. The gateway tag and width checks validate current
call shapes before field access.

Forbid, Permit and GetMsg have [native fast paths](kernel-fast-path-implementation.md)
after common frame validation, through the same `COP #$50` gateway. They retain
the complete saved context and SWITCHING guard, use activation-local scratch,
and avoid the Action! stack/workspace when no deferred work needs processing.
Completed operations that need wake/timer or scheduler work enter general Poll
with their saved result; they never execute the operation twice. Other services
retain general dispatch. There is one implementation and no caller-selected
fast-call ABI.

The [resident driver boundary](../reference/resident-drivers.md) returns a checked
static route through the existing I/O operations. SIO callbacks then execute on
the caller's stack/DP outside SWITCHING, with Forbid covering Task-side ownership
updates and IRQs enabled. Public port calls can enter COP from those callbacks;
no kernel activation remains across the driver call. Native descriptor
publication/retirement retains its separate IRQ/NMI protocol.

Public Task retention and resident notification use ten previously unused bytes
of each existing 64-byte upper-RAM TaskControl. The per-slot incarnation does
not wrap; an exhausted slot rejects admission. Address-bound Task leases occupy
12 caller-owned bytes. Public EXECPRODUCER binding requires a retained recipient
and keeps removal/signal reuse blocked through release and wake draining. See the
[resident contract](../reference/resident-drivers.md#public-platform-producer).
SIO startup, stop and last-application retirement use these public facilities;
no SIO-specific Task removal or admission hook remains. The native packet tag
stays `$0600` because call packet layouts are unchanged; it is distinct from the
available-feature version. Fixed/per-Task bank-zero and full upper reservations
are unchanged, including guards, alignment and unused capacity.

Maintain one Task implementation. ABI changes update callers and tests together;
rebuild programs instead of preserving compatibility profiles. The small
single-program/two-task launch probes exercise platform entry and coexistence;
they are not alternative application Task APIs.

- Preserve AltirraOS's `COP #$00` native-to-emulation service bridge.
- Leave `$80-$FF` untouched: WDC reserves them for future processor instructions.
- Intercept Exec's signature explicitly and preserve other signatures' existing
  behavior by chaining to the previous OS dispatcher.
- Inspect and test the selected ROM's real dispatch path; do not infer working
  dispatch solely from the presence of the `VCOPU` vector definition.
- Save the complete native context before using registers or shared workspace.
- Define allowed calling contexts and behavior under preemption locks.
- Unknown Exec service selectors must produce a defined error or fault.

The pinned compiler's standalone bridge uses `COP #$00` for yielding. Exec's
hosted bridge must adapt that convention; replacing the OS COP vector with the
standalone implementation unchanged is invalid.

The pinned AltirraOS 3.44 ROM routes tested signatures `$00`, `$50`, and `$7F`
to `VCOP0`. Exec must intercept `$50` through `VCOPN`; installing a `VCOPU`
handler alone does not work on this ROM. Preserve the saved dispatcher's
behavior for other signatures.

Ordinary kernel helpers can use normal calls. COP is the controlled service
entry for operations that need it, not a requirement for every public function.

## VBI preemption

The first scheduling tick is ANTIC's vertical-blank NMI. Display-list NMIs are
not scheduling ticks and DLI remains disabled. The
[preemption contract](vbi-preemption.md) defines the implemented adapter and
dedicated execution qualification.

The bridge must preserve the interrupted context, run required OS VBI work
through a controlled stack/mode adapter, and switch only when the interrupted
execution was an eligible native Exec task. It must not suspend a live OS or
interrupt-handler activation as if it were an ordinary task.

Defer task switching when the interrupted status has I set, while an OS call
or preemption lock is active, and during scheduler/context transitions. Keep a
pending reschedule request and service it at a defined safe boundary, including
outermost unlock and OS-return paths. Update the relevant flags atomically with
a protocol valid even when NMI arrives between instructions.

SEI does not mask NMI. The interrupt and lock design must therefore explicitly
cover NMI entry, nesting, partial saves/restores, and stack/domain changes.
Define a bounded NMI/DLI nesting policy before enabling these paths.

The AltirraOS native VBI path in the inspected source enters emulation mode.
The adapter must accommodate the effect on stack and register widths; it must
not blindly chain that path on an arbitrary native task stack.

The boundary probe confirms that VBI restores the tested native register/DP/DBR
contexts on a page-one stack. On a private stack it enters page one while the
native return frame remains on the private stack. A stack adapter is required
before using this ROM's VBI with private task stacks.

The initial launcher supplies non-switching native NMI/IRQ wrappers that save
the interrupted frame, select or retain a page-one OS stack, and chain to the
saved ROM handler. This permits the single native program to use a private
stack. The cooperative gateway now handles task switching, locks and pending
yield requests. In preemptive mode, a common immediate VBI hook records ticks
in native and emulation-mode OS paths. Native interrupt return dispatches only
after retiring the OS activation and validating the interrupted task context;
protected returns retain a pending request. Cooperative mode remains passive.

## OS calls

Start with serialized OS calls and deferred task switching while an OS call is
active. Hardware interrupts required by OS I/O must remain functional; holding
IRQ disabled across all I/O is not the serialization strategy.

The adapter establishes and restores the required CPU mode, widths, direct
page, bank registers and stack. It also owns conversion between native pointers
and each service's buffer/address requirements. Never silently truncate a
banked pointer to a 16-bit OS address. Define buffer staging where needed.

The probe successfully calls CIOV through `COP #$00` on a page-one stack with
native D=`$2200` and DBR=`$12`, verifying console output and restoration of the
caller domain. The ROM's COP0 emulation transition does not preserve an
arbitrary native stack location; the adapter must move to its OS stack first.

Initially, a blocking OS call may delay all Exec tasks. Improving this behavior
requires a separate service/driver design and new qualification.

The [serial latency experiment](sio-latency-poc.md) identifies additional
requirements for the 125 kbaud target: direct native serial IRQ delivery,
explicitly fast ROM access and scoped CRITIC ownership during a transfer. Its
passing 8× PAL profile is separate from the existing 1× pins. Full ROM VBI and
generic ROM serial dispatch miss the measured worker-refill deadline. CRITIC
retains stage-one VBI while postponing stage two; arbitrary OS calls and timer
callbacks remain outside this experiment's latency guarantee. Carry these
constraints into the next adapter slice and repeat the measurement there.

## Startup and qualification

Before the first launchable image, pin the emulator version, dedicated 65816
ROM version/hash, CPU configuration, memory expansion/map and PAL/NTSC mode.
Specify image loading, initialization/zero-fill, OS memory reservations, native
entry, fault handling and shutdown behavior.

Acceptance must exercise actual emitted bytes with raw and optimized NIR:

- Native startup, OS console I/O and return/fault behavior.
- Independent stacks/domains and full register restoration for two tasks.
- COP `$50` services and preserved COP `$00` behavior.
- VBI preemption of a task that never voluntarily yields.
- Deferred switching during OS calls, locks and transitions, including nested
  locks and pending reschedule delivery.
- Continued keyboard, display and selected I/O operation while tasks run.
- Stack/domain guards, bounded completion and reproducible configuration.

Compiler-only acceptance does not establish this hosted platform's correctness.

## References

- [W65C816S datasheet, section 7.15](https://www.westerndesigncenter.com/wdc/documentation/w65c816s.pdf#page=52): COP signature reservation.
- [Altirra 4.40 source archive](https://www.virtualdub.org/downloads/Altirra-4.40-src.7z): inspected `src/Kernel/source/Shared/interrupt816.s`, `syscall816.s`, `kerneldb.inc` and `vbi816.s`. This inspection is not a runtime ROM pin.
- [Altirra hardware reference, section 4.8](https://www.virtualdub.org/downloads/Altirra%20Hardware%20Reference%20Manual.pdf): ANTIC NMI sources.
- [Pinned compiler context interface](https://github.com/mkur/actionc/blob/ae1f555e77d0ae6caffbfc7453cbf06e3d098bee/docs/MIR65816_CONTEXT_INTERFACE.md): existing standalone bridge and its qualification boundary.

## Native SIO ownership

The [Task SIO adapter](device-io-sio-implementation.md#slice-5-native-task-adapter)
uses an exclusive, silent POKEY profile. It establishes its audio configuration
explicitly because the ROM does not shadow every write-only register; arbitrary
pre-existing audio/cassette state is unsupported. Active timer ownership cannot
be borrowed. Private descriptor/code storage is upper RAM. The adapter saves
owned vectors and available shadows, merges unrelated IRQ/PIA bits on release,
and restores CRITIC to its original value. ROM calls are rejected while POKEY
is owned, while immediate VBI, Exec scheduling and unowned IRQ handling
continue. Clean completion restores CRITIC without a mandatory OS-service
sleep; stage-two VBI may run in inactive intervals, but is not guaranteed
between consecutive queued requests in the dedicated Exec workload. OS state
is restored at shutdown. Public queued-device availability and timing are
separate gates; the private adapter alone does not qualify them.
