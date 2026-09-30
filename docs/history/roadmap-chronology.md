# Exec816 implementation roadmap

> Historical record: applies to the revisions and profiles described below.
> See the [current documentation](../roadmap.md) and [history index](README.md).

The design baseline, [OS-boundary probe](os-boundary-probe.md), and
[single-program native launcher](native-launch.md),
[two cooperative tasks](cooperative-tasks.md), and
[VBI preemption](vbi-preemption.md), and
[banked loading and ownership](banked-loading.md) are implemented. The probe
pins the machine and establishes VBI/COP stack requirements and COP routing.
Subsequent milestones need their own executable results and focused regressions.

## 1. Native program under AltirraOS

Status: complete for the pinned single-program console configuration. The
[qualification record](../qualification/native-launch.json) covers 28 hosted cases
in raw and optimized modes, plus package-boundary checks. The documented launch
restrictions still apply; this does not qualify scheduling or arbitrary DOS/OS
extensions.

- Pin the actual emulator, 65816 ROM and machine configuration.
- Implement a reproducible loader/package path for compiler version-2 images.
- Reserve memory and establish the native ABI from the OS launch environment.
- Add one OS console adapter and defined exit/fault behavior.

Acceptance: a compiled native Action! program launches under AltirraOS, prints
through the OS, and reaches a controlled end with intact stack/memory guards.

## 2. Exec gateway and two cooperative tasks

Status: implemented for the pinned hosted configuration, with Action! scheduling
policy, generated gateway/record constants, full native context switching and
serialized console calls. See the [contract and tests](cooperative-tasks.md) and
[qualification record](../qualification/cooperative-tasks.json). VBI remains passive.

- Define the versioned COP `$50` service ABI and generated shared constants.
- Implement full-context entry and compatible forwarding of other COP services.
- Construct two independent task stacks/domains and implement yield/task exit.
- Define preemption locks, OS-call ownership and pending reschedule state.

Acceptance: two tasks enter the same routines with independent local state,
yield repeatedly, use the serialized OS adapter and terminate correctly.
AltirraOS's COP `$00` behavior remains intact.

## 3. VBI preemption

Status: implemented for the pinned PAL/64K hosted configuration. The
[contract](vbi-preemption.md) defines tick recording in both CPU modes,
interrupt-return eligibility and atomic pending delivery. The
[qualification record](../qualification/vbi-preemption.json) includes no-yield
progress, protected transitions, register restoration and OS coexistence.

- Implement native NMI entry and controlled OS VBI chaining.
- Switch eligible tasks at a defined VBI exit boundary.
- Defer switching during locks, OS calls and interrupt/context transitions.
- Qualify register widths, bank/direct-page state, stack headroom and nesting.

Acceptance: two tasks that do not voluntarily yield both progress while
keyboard/display operation continues. Adversarial interruption tests cover
protected transitions and pending reschedule delivery.

## 4. Bank manager and banked loading

Status: implemented. The [banked launcher](banked-loading.md) boots through
INITAD/RUNAD and adopts the bootstrap table before task dispatch. See its
[qualification record](../qualification/banked-loading.json). The [bank-manager contract](bank-manager.md) separates physical
availability, system/image reservations and client ownership. The
[loader and bank/region manager implementation plan](../plans/loader-bank-manager-plan.md)
defines the implementation sequence, affected files and acceptance matrix.

- Qualify an explicit upper-bank RAM map and emulator profile.
- Initialize a bank-zero table without depending on a heap allocator, sized by
  the kernel's `MAX_BANKS` build parameter (default 16; four bytes per entry).
- Implement query, exact reservation, acquisition and checked release.
- Keep bank zero outside whole-bank allocation, with explicit range reservations.
- Adapt the established XEX staging/`INITAD` copy-up pattern documented in the
  bank-manager contract, validating and reserving image banks before writes.
- Boot the kernel from that same XEX: seed reservations in the standalone
  bank-zero bootstrap, then enter the fully loaded native kernel at `RUNAD`.
- Qualify banked execution and full-context preemption, including nonzero PBR.

Acceptance: the loader and native manager agree on ownership, conflicts and
exhaustion fail without changing state, and a banked preemptive program runs
with intact guards and OS services.

## 5. General task management

Status: the [general-task profile](../guides/tasks.md) implements the
[classic Exec Task core](../reference/tasks.md), currently reporting `$0700`. Public Task pointers
replace handles and creator-owned completions. AddTask accepts prepared storage;
RemTask supports self and external removal, including cancellation of sleep.
FindTask searches running, ready and sleeping tasks. SetTaskPri stores priority;
the scheduler deliberately remains FIFO. Forbid/Permit nest scheduling exclusion.
The same implementation includes signals and Wait below.

Four private execution contexts include the root, with a separate idle context.
Public Task storage is independent of those slots. Released contexts can be
reused beyond 255 lifetimes and after root removal; shared image banks remain
reserved. The [Lists library](../reference/lists.md) supplies the classic sentinel ready queue.
The [migration record](tasks-exec-update.md) describes the implementation slices,
ABI qualification and integration tests. Historical handle/lifecycle records
remain evidence only for the previous profile. The earlier two-task launch
profiles retain their existing interfaces.

The [original core qualification](../qualification/tasks-exec.json) passes 64 raw/optimized
Task cases; [compatibility and Lists regressions](../qualification/tasks-exec-regressions.json)
pass 14 cases on the corrected pinned emulator. The initial revised Task subset
is complete; priority scheduling and dynamic storage remain later work.

Acceptance: prepared Tasks run through the six core calls in raw and optimized
emitted code, with admission rollback, far pointers, finalization, external and
self removal, reuse, sleep, nesting, native context restoration and OS coexistence.

## 6. Allocation and synchronization

The [serial latency proof](sio-latency-poc.md) runs before committing to the full
stack. Its minimal worker-per-byte path passes the 125 kbaud target with direct
native IRQ delivery, fast ROM access and CRITIC during transfers; generic ROM
dispatch/full VBI configurations fail. First carry those requirements into a
bounded device IRQ adapter and SIO/OS ownership contract, retaining the latency
probe as the acceptance check. No new signal ABI, ports or capacity were needed
for this experiment, and its passing result does not qualify those services.

Status: slices 1–7 of the [signal implementation plan](../plans/signals-wait-implementation-plan.md)
are complete in the current Task kernel. The
[implementation record](signals-implementation.md) covers ABI/mask bookkeeping,
task-to-task waits, real IRQ posting, safe drains and context/compatibility checks.
Direct association and an intrusive wake FIFO remove scans from target delivery;
priorities remain ignored. Static Task storage needs no allocator.

The original general worker-per-byte measurement **failed 125 kbaud**. The
diagnostic IRQ byte pump passed a 65,535-byte restricted stream with
block-completion Signal/Wait, while whole-target masked drains took about
603 µs. Keep IRQ buffering as the driver direction. Historical qualification
records remain tied to their measured commits.

The first latency follow-up slice adds a
[four-task concurrency stress test](signals-concurrency.md): compute control,
Yield, Signal/Wait, timed Sleep and a mixed workload, with raw/optimized emitted
code, hardware byte deadlines, passive I-transition tracing and uninstrumented
replays. In that baseline, all twenty executions pass functional checks while
every active-kernel workload misses byte deadlines.

The second follow-up [shortens the critical sections](kernel-critical-sections.md).
Policy permits IRQs under the scheduler guard; small native transactions
protect masks, wait publication and wake links. All ten 4,096-byte raw/optimized
workloads and their identical replays now pass the 125 kbaud deadline. Six
65,535-byte Yield/Signal/mixed runs and their replays also pass, with a worst
refill of 73.304 µs across both matrices. Reserved bank-zero delta is zero.
That slice did not qualify eight-task timing. The later
[queued SIO](device-io-sio-implementation.md) and
[DOS integration](block-io-dos-implementation.md#slice-10-concurrent-filesystem-qualification)
records cover their respective eight-task workloads.
Per-byte worker delivery is not requalified here. A static-buffer TX/RX probe
may proceed separately; full driver integration follows the allocator and
message-port services below.

Status: the upper-RAM allocation milestone is complete. The
[classic Exec allocation design](../reference/memory.md)
supersedes the earlier Alloc/Free proposal. The [current ABI qualification](../qualification/memory-exec-abi.json)
passes raw/optimized layout and full-width call probes. The [private free-list engine](../qualification/memory-exec-core.json)
passes model-based traces and corruption cases. [Heap registration](../qualification/memory-exec-registration.json)
qualifies ownership, rollback and shutdown. [System policy](../qualification/memory-exec-policy.json)
passes shared ordinary/LINEAR placement and query traces. [Public services](../qualification/memory-exec-api.json)
qualify all eight imports, vectors and caller-side CLEAR. The implementation uses the IRQ-permitting kernel
guard for heap metadata and task-context wrappers for preemptible clearing.
The [implementation plan](../plans/memory-allocation-implementation-plan.md) replaces the
prototype plan with six completed executable slices: ABI, private free-list engine,
registration, system policy/queries, public services and concurrent qualification.
The [implementation record](memory-allocation-implementation.md) reports shared
lifetime, forced interrupt races, eight-task functional allocation, 66 selected
integration regressions and four-task serial timing under allocator load.
All 458,724 measured refills meet the deadline; no bank-zero reservation was
added. Eight-task serial timing stays deferred.

The new design retains AllocMem/FreeMem, AllocVec/FreeVec, 32-bit sizes/flags,
MemHeader/MemChunk free lists and shared explicit lifetime. Ordinary and linear
requests share upper-RAM free extents. Bank-zero allocation is explicit and
must respect the separate task-capacity reservations. Implement its range and
Task-storage integration alongside milestone 7; an empty tc_MemEntry still
does not introduce automatic reclamation.

The new call shapes and native structures are qualified in the single current
Task kernel, reporting `$0600`; rebuild callers. The prototype's `$0201`
metadata and `$0F/$10` register layouts are historical. The current timing
qualification covers the generated-byte TX pump; RX/turnaround and worker buffer
budgets still need driver-specific requirements and measurements.

Message ports and their planned integration qualification are complete. The
[design note](../reference/ports.md) specifies
the nine classic calls, native Message/MsgPort layouts, FIFO queues, signal
arrival actions, named discovery and explicit lifetime. Public IRQ port calls
and PA_SOFTINT remain deferred; a future SIO worker replies after receiving
the existing IRQ completion signal. PutMsg, GetMsg, ReplyMsg, WaitPort and
CreateMsgPort/DeleteMsgPort and AddPort/RemPort/FindPort are now
implemented; see the [implementation record](messages-ports-implementation.md).
The [implementation plan](../plans/messages-ports-implementation-plan.md) has six
completed slices: native contract, queues/replies, WaitPort, creation/deletion,
named discovery and integrated qualification. Each ends with executable evidence
and a commit. The integration record covers eight tasks, 17 ports and four-task
125 kbaud TX with message/registry/allocator interference. At that milestone,
eight-task serial timing was deferred.
The implemented [queued device I/O and SIO design](../reference/device-io.md)
defines classic IORequest calls, one SIO worker and a prearmed
native transaction engine. The [focused hardware probe](device-io-sio-implementation.md)
now passes buffered RX/TX and phase-alarm timing at the 125 kbaud target with two
contexts. Production integration and full Task timing now have separate
queued-driver evidence.
DOS follows queued I/O;
the [implementation plan](../plans/device-io-sio-implementation-plan.md) defines eight
completed slices. [Concurrent qualification](../qualification/sio-concurrency.json)
covers four/eight tasks and target/stock speed in raw/optimized kernel-bank-1
builds, with functional bank-3 coverage. The native I/O layouts
and call shapes pass raw/optimized probes. All ten generic calls execute with
test-only immediate/queued devices and the resident sio.device, including
specific waits, cancellation and explicit offline recovery.
Each slice has executable
acceptance and a separate commit.
Introduce semaphores in a separately specified slice when shared-resource users
need them. The queue/registry timing
runs pass with zero refill misses; worker wake and client collection remain
substantially slower than IRQ byte service. The queued-driver record also
covers RX, turnaround and buffer budgets.

## 7. Bank-zero task capacity

Status: the [eight-task configuration](../architecture/task-capacity.md) is implemented and
qualified for the recorded workloads. It provides eight simultaneously live
public Tasks plus idle, a compile-time kernel bank, an upper-RAM ownership table
and generated stack/DP pools. Raw/optimized qualification covers kernel banks
1 and 3, all-target IRQ wakes, overflow admission, timed sleep, removal/reuse,
full-context restoration and guards. Four- and eight-task storage layouts use the same implementation. Twelve/sixteen tasks remain unqualified growth targets.

The implementation sequence is:

1. Implement the [kernel-bank build parameter](platform-contract.md#kernel-bank-build-parameter)
   and [upper-RAM bank table](bank-manager.md#planned-upper-ram-table-placement).
   Reclaim the old table reservation and report the actual before/after bank-zero
   footprint, including loading and steady runtime.
2. Generate task capacity, idle identity, context storage and per-context stack
   bounds from build configuration. Remove fixed four-task/five-pool and 1536-byte
   stack assumptions from policy, generators, adapters and tests. Keep public
   Task pointer identity and core calls unchanged.
   Entry bindings and validation tables must accommodate the configured workload
   without reserving maximum-size tables for every build.
3. Establish a checked eight-task layout. Account for all kernel, idle, OS,
   adapter and driver storage as well as task stacks/DPs and guards. Move metadata
   with no bank-zero requirement to upper RAM and reclaim boot-only ranges only
   after their last use. Qualify any smaller stacks before adopting them.
4. Qualify eight live tasks together in raw and optimized emitted code. Cover
   full-capacity admission and unchanged state on the next rejected admission,
   waiting tasks retaining capacity, removal/reuse, guard integrity, complete
   register restoration, bounded progress and OS coexistence. Record the complete
   memory budget and provenance. This is a simultaneous-capacity test, not a loop
   that creates and removes one task at a time.
5. Remaining: develop and qualify 12- and 16-task layouts using measured workload stack
   needs and further reservation savings. Reject configurations that cannot fit.
   The [current-size budget](tasks.md#capacity-target-and-memory-budget) shows
   why copying today's uniform allocations cannot deliver sixteen tasks.

The eight-task implementation uses generated static pools. General bank-zero
allocation can follow; it must not be confused with the upper-RAM heap milestone.
Capacity qualification alone does not qualify SIO: driver integration must also
establish interrupt latency, request completion/cancellation and task progress
through transfers, timeouts and retained OS activity.

## Later platforms and services

The first complete storage-system target is an asynchronous SIO driver with DOS
and filesystem services above it, using the eight-task minimum. Signal/wait,
message ports and qualified interrupt entry are prerequisites. With queued SIO
implemented, the [block I/O and DOS design](../reference/dos.md) adds
one filesystem worker, a sector adapter and read-only MyDOS support with
subdirectories, 128/256-byte sectors and ten-/sixteen-bit links. The
[256-byte transport gate](../qualification/sio-sectors.json) is separately qualified;
initial DOS API and parser work alone does not establish transport support.
Filesystem writes follow the complete read-only path. The
[implementation plan](../plans/block-io-dos-implementation-plan.md)
defines ten executable slices, each with evidence and its own commit, from the
256-byte transport gate through native DOS, MyDOS parsing, service lifetime and
eight-task qualification. All ten slices are complete on the pinned emulator.
The [integration results](block-io-dos-implementation.md#slice-10-concurrent-filesystem-qualification)
document 125-kbaud wire timing and the queue/throughput limits of serializing
whole filesystem operations. Expand other device services after this read-only path.

The completed [SpartaDOS filesystem plan](../plans/spartados-implementation-plan.md) adds
SDFS alongside MyDOS in six separately committed slices: independent fixtures,
a shared backend boundary, file/map access, directories, public DOS integration
and an SDFS play image with measured loading costs. The first milestone is
read-only SDFS 2.0/2.1 on 128/256-byte media, with unchanged public DOS calls and
no added worker or bank-zero reservation. MyDOS remains available; writes and
512-byte sectors are separate follow-ups. See the
[implementation evidence](spartados-implementation.md) for development checks
and loading measurements; full release qualification remains separate.

The [MyDOS simplification](../plans/mydos-simplification-plan.md) removes its
record-translation adapter, uses the common filesystem records directly and
reclaims duplicated upper-RAM state in four slices. Read-only behavior and the
public DOS API remain unchanged. All four slices are complete; see the [measured results](mydos-simplification.md).

The [filesystem object split](../plans/filesystem-objects-implementation-plan.md) is
complete: file wrappers retain shared backing for inheritance, and locks keep
only metadata, ancestry and their canonical names. It saves 112 heap bytes per
file wrapper and 32–40 per lock. Public DOS interfaces and bank-zero reservations
remain unchanged; see the [measured results](filesystem-objects.md) for the
938-byte resident-code tradeoff and development checks.

The [FSINIT simplification plan](../plans/fsinit-simplification-implementation-plan.md)
is complete: the worker callback count falls from eight to four, descriptor
handling is smaller and partial block teardown is shared. It saves 1,531 resident
bytes with unchanged memory reservations; FSINIT falls from 11,059 to 9,494 bytes.
See the [results and development checks](fsinit-simplification.md).

The [sector-cache plan](../plans/sector-cache-implementation-plan.md) is implemented:
a shared 64 KiB upper-RAM read cache, a boot capacity parameter and OF816
configuration words. The [development measurements](../architecture/sector-cache.md) show an
8 KiB retained read falling from 7.64 s to 0.66 s, with zero warm wire reads.
MyDOS/SDFS and SIO interfaces and bank-zero reservations are unchanged.

The [SYS: plan](../plans/sys-volume-implementation-plan.md) is implemented in three
slices: an explicit system-volume alias, boot-time drive selection/OF816 words,
and shell integration. It shares the cache boot record and adds no bank-zero
reservation. [SYS paths](../reference/sys-volume.md) remain stable when the system disk moves
to another SIO drive; physical names remain canonical.

The initial [native console](../reference/console.md) milestone is complete in
[eight committed slices](console-io-implementation.md). `--console` enables
keyboard input and a retained 40×24 text screen through ordinary device requests.
One worker occupies an existing slot, with state in upper RAM and zero added
bank-zero reservation. The [resident DOS example](../guides/console-example.md) needs no
application binary format. [Eight-task qualification](../qualification/console-concurrency.json)
passes typing, wrapping/scrolling, memory/message/signal work and a single large
MyDOS read alongside 125 kbaud SIO. Raw/optimized code and kernel banks 1/3 are
covered, with timing/replay on bank 1. That workload measured visible echo
delays of about one second. The subsequent [idle-scrolling optimization](console-scrolling.md)
reduces optimized scrolling from about 319 to 98 ms per line without I/O;
shared FIFO output can still delay interactive echo.
The [plan](../plans/console-io-implementation-plan.md#required-multiwindow-follow-up)
keeps multiple independent text windows, focus and instance fairness as required
future stages, sharing one worker and keeping presentation separate from cells.
The resident shell is implemented below; the application loader remains separate.

The [DOS console stream layer](../reference/streams.md) supplies
RAW:/NIL: handles, DOS Write and task-local Input/Output selection. It preserves
the read-only MyDOS backend and uses caller-side adapters over the existing
console worker, so a waiting keyboard Read never holds the filesystem worker.
All seven [implementation slices](dos-console-streams-implementation.md) are
complete, including deterministic ownership/failure tests, the
[resident example](../guides/streams-example.md) and
[eight-task timing qualification](../qualification/dos-streams-concurrency.json).
Raw/optimized FASTEST125 runs verify full 70,003-byte reads on 256-byte media;
128-byte media, STOCK810, alternate kernel bank, TX and observer-free replay
retain their documented scopes. Stack/domain guards and interrupt reserves pass.
Fixed and per-Task bank-zero reservation deltas are zero; the endpoint registry
uses 16 explicitly reserved upper-RAM bytes. Streams add no worker Task.
FIFO scrolling still delays echo, reaching 1.7 seconds when a completion message
scrolls ahead of it. [Cooked CON:](../reference/cooked-console.md) now implements bounded
editing, partial line reads and EOF, with physical raw/optimized tests recorded in
[console interaction C2](console-interaction-implementation.md#c2-physical-con-backend).
[Foreground break scopes](../reference/foreground-break.md) deliver durable
Ctrl-C/BREAK independently of Read. Console and filesystem waits retire canceled
operations safely, and shell commands restore a usable prompt. The
[B5 qualification](console-interaction-implementation.md#b5-shell-cancellation-and-prompt-recovery)
passes the 100/250/500 ms delivery, queued-reply and healthy-prompt gates with
eight live Tasks, raw/optimized code and observation/replay. Processes now inherit
handles and can execute loaded o65 commands. [Windows W1–W3](../reference/console-windows.md) now
implement lifetime, tiled presentation, captured focus and worker rotation.
Raw/optimized development checks include eight-Task fairness/SIO; complete
window release qualification remains pending.

The [resident-shell milestone](shell-design.md) is complete in
[eight separately committed slices](../plans/shell-implementation-plan.md). CurrentDir,
NameFromLock and relative/parent/root Open/Lock resolution support CD navigation.
The root Task runs HELP/ECHO/CD/DIR/TYPE/MEM/EXIT, bounded CON: editing and temporary
Input/Output redirection. Deterministic lifetime tests and eight-task SIO timing
pass in raw/optimized code with unchanged stack and bank-zero reservations.
Integrated testing found and fixed a pending watchdog delayed by keyboard IRQ
delivery; byte and timer deadlines remain unchanged. The
[shell guide](../guides/shell.md) and [implementation record](shell-implementation.md)
cover usage, full-file throughput, synchronous filesystem queue waits and scrolling
latency. Follow-up work has three implementation plans:

- [Console interaction](../plans/console-interaction-implementation-plan.md): historical
  qualification maintenance, cooked CON:, foreground cancellation and windows.
- [Process lifetime](../plans/process-lifetime-implementation-plan.md): resident child
  execution, inherited resources, cleanup and Task retirement. P1–P3 are implemented
  and development-tested; full release qualification remains pending.
- [o65 loading and external commands](../plans/o65-loading-implementation-plan.md): L1–L4
  implement native validation, relocation/providers, retained Process execution,
  MyDOS loading and shell dispatch. The scoped integrated lifetime, failure and
  transport matrix passed in raw/optimized code, including observation/replay.

The [plan index](../plans/interactive-programs-implementation-plan.md) records their
dependencies and shared rules. The 19 slices retain their failure cleanup,
native acceptance checks and memory accounting.

The development showcase follows the
[demo implementation plan](../plans/demo-implementation-plan.md): a shell and prime search
in two text regions, external CAT/WC commands, a two-stage foreground pipeline,
and a packaged XEX/ATR walkthrough. D1–D6 separate presentation, commands, pipe
streams, grouped Process lifetime, shell syntax and final packaging. The target
uses seven of eight public Task slots and adds no reserved bank-zero memory;
see the [implementation record](demo-implementation.md) for slice status and
focused validation, and the [demo guide](../guides/demo.md) for build and boot instructions.

GEM integration, a bare-metal platform, and broader compiler capabilities are
separate milestones driven by concrete requirements.

The first [filesystem/SIO hot-path optimization](../experiments/sio-hot-path-optimization.md)
passes retained worker context into sector transfers, skips kernel entry for
empty cancellation queues, and batches loader reads at 4 KiB. Focused
development checks cover cancellation, request ownership and loading recovery;
same-profile measurements reduce HELLO open-to-prompt time from 5.20 to 4.14 s
with the demo prime task running. Reserved bank-zero change is zero. Broader
Exec gateway changes remain separate from this measured-path slice. The
[refreshed play image and follow-up profile](../experiments/sio-hot-path-profile.md)
confirm that request handoff and sector consumption are the next measured
targets; empty cancellation checks now average about 10 microseconds.

The next [completion-collection slice](../experiments/sio-completion-collection.md)
uses one operation to test and collect the sector reply. The retirement interval
falls about 22%; mean inter-sector gaps fall 5.1% with the prime task stopped
and 11.1% with it running. End-to-end HELLO timing is unchanged in these runs.
Focused raw/optimized cancellation and error-retirement checks pass, with zero
reserved bank-zero growth.

The completed [kernel COP fast-path refactor](../plans/kernel-fast-path-refactor-plan.md)
retains the public `COP #$50` calling convention while giving `Forbid`, `Permit`
and `GetMsg` bounded native paths before the general Action! dispatcher. The
[implementation record](kernel-fast-path-implementation.md#g4-integration-and-play-image)
reports optimized medians of about 48, 48 and 77 microseconds, versus 684, 686
and 793 before the refactor. Pending work enters Poll after the operation has
completed. Focused raw/optimized interruption and serial checks pass, with zero
additional fixed/per-Task bank-zero reservation. The refreshed play image passes
loading/BREAK recovery. Same-profile HELLO open-to-prompt falls from 4.10 to 3.90
seconds with the prime worker stopped and remains 4.14 seconds with it active;
active sector gaps increase. This is the measured baseline for the SIO migration,
not a claim that all SIO intervals improved.

The [SIO driver boundary plan](../plans/sio-driver-boundary-implementation-plan.md)
follows the [architecture guidance](../../AGENTS.md#architecture):
use the Amiga driver model, with QNX and BeOS as references for specific
improvements. S1 fixes the [resident contract](../reference/resident-drivers.md), and
S2 moves submission, active ownership, cancellation and reply publication into
caller/worker driver code coordinated with public primitives. Request controls
2/3/4/9/12 are removed. The [implementation record](sio-driver-boundary-implementation.md)
records focused checks and checkpoint HELLO profiles. S3 moves worker lifetime
to public Task leases, resident notifications and platform producer binding,
and removes the remaining private SIO controls and scheduler hooks. S4 completes
the profile and play-image refresh. A combined kernel operation
must have a reusable, documented public ABI and tests with ordinary Tasks; its
need is not assumed. This supersedes the proposed private stop/dequeue fusion.

Preserve exact request retirement and durable wakeups. Raw/optimized lifetime,
startup rollback and stop/restart checks pass. The complete migration measures
3.88/4.16 seconds for HELLO open-to-prompt with the prime worker stopped/active,
versus the G4 baseline's 3.90/4.14 seconds. Identical-image replay confirms the
recorded intervals; this is not a material loading-speed improvement. The new
play bundle passes loading/BREAK recovery. Fixed and per-Task bank-zero
reservations remain unchanged; release and physical-hardware qualification are
separate.
The [isolated sector-copy measurement](../experiments/sector-copy-cost.md) identifies
about 3.2 ms in the actual 128-byte SDFS byte loop and about 0.14 ms in setup and
bookkeeping. Raw/optimized fixtures and same-image HELLO replays agree; no
production code or compiler pin changes. This is roughly 58 ms of copy work for
HELLO, not an explanation for most of its loading latency. Sector-copy
optimization remains a separate follow-up.

The [payload and loader breakdown](../experiments/loading-breakdown.md) attributes
1.62/1.53 seconds of payload reading to modeled disk/device waits, 0.475 seconds
to serial transmission and 0.352/0.417 seconds to Exec work/scheduling outside
transactions. Import resolution then takes 0.239/0.268 seconds: five imports
cause 70 provider-entry parses across a 14-entry manifest. That measurement
selected one manifest pass per load as the next bounded optimization, preserving
all provider validation and matching checks. Same-image stopped/active replays
reproduce the S4 phase and hardware timings; no production change or new
compilation was needed.

The [one-pass resolver](../experiments/provider-resolver.md) implements that slice
using the existing import-address fields as attempt-local match state. HELLO
now parses 14 provider entries, while retaining all 70 name comparisons and
five contract checks. Resolver time falls from 239/268 to 68/76 ms with the
prime worker stopped/active; open-to-prompt falls from 3.88/4.16 to 3.72/3.94
seconds. Raw/optimized provider, relocation and lifetime checks plus identical
image timing replays cover the change. Reserved bank-zero delta remains zero;
play-image packaging uses the existing compiler pin.

## Native direct-page partition

The [cross-repository migration](direct-page-partition.md) moves compiler
scratch to `$80–$BF`, metadata to `$C0–$C7`, and preserves `$00–$7F` for a caller
runtime. Native ABI v2 and compact o65 v3 reject older artifacts. The 256-byte
reservation, guards, alignment and pool stride are unchanged: zero additional
fixed or per-task bank-zero bytes. Development checks cover calls, waits,
preemption, slot reuse and loaded COMMAND/CSTRING calls. Rebuilt programs and
play-image evidence are recorded with the migration; full release qualification
remains pending. C compiler selection, headers and wrappers remain later work.

## Native compiler pointer loops

The [pointer-loop plan](../plans/compiler-pointer-loops-plan.md) is implemented. Its
frameless follow-up moves byte temporaries into spare resident DP space and
refreshes the compiler pin. [Measured results](compiler-pointer-loops-results.md#frameless-follow-up)
show FindName at 189 bytes with no local frame, versus 381/26 before the plan,
and 889 versus 2,092 VM cycles on the first-match workload. The existing OF816
demo predates the frameless follow-up. Source and ABI are unchanged;
reserved bank-zero delta is zero fixed and per Task. Existing full-backend
failures reproduced on the old pin remain a separate release gate.

## Native compiler word addresses

The [word-address compiler fix](compiler-word-addresses-results.md) selects
zero-extended CARD addresses through X before allocating pointer temporaries.
The Result helper becomes 14 bytes with no frame, versus 65 bytes and an
8-byte frame. Reserved bank-zero delta is zero fixed and per Task.

## Backlog

### Native console scrolling

The [console refactor plan](../plans/console-refactor-plan.md) now covers this work,
followed by console driver-policy consolidation. Implementation is pending.
Optimize both parts of scrolling against the
[existing benchmark](console-scrolling.md#measurement):

- Replace the retained-cell `OP_SCROLL` loop with native 65816 overlap-safe
  forward copy and fill: move 920 bytes and blank 40 bytes for a 40×24 console.
  Evaluate completing the bounded scroll without yielding between every row,
  keeping IRQs enabled and preserving native context and bank-boundary correctness.
- Add a physical-screen scroll path that moves already translated screen bytes
  and blanks the bottom row. Remove/restore the cursor overlay and use this path
  only when the displayed contents are synchronized with retained cells; preserve
  ordinary redraw for pending dirty content, hidden or clipped presentations.

Reusable native copy/fill primitives belong in actionc; console policy and
presentation remain in Exec816. Measure retained scrolling, physical updates
and visible completion separately in raw/optimized emitted code. Preserve exact
cells/cursor, cancellation, IRQ/NMI context, OS restoration, eight-Task SIO
deadlines and stack guards. Target zero added fixed/per-Task bank-zero reservation.
Cycle estimates are motivation, not a measured performance claim. This follow-up
does not change the W1–W3 window scope.

### Narrow DOS API scalar types

Deferred and unscheduled. Review scalar widths in the
[command API](../reference/program-loading.md#checked-providers) and DOS for the 65816:

- Change `Open` mode from `LONGINT` to `CARD`, preserving mode values
  1004/1005/1006. A mode enum remains an option, but current actionc enums are
  byte-sized; retaining these values would require wider-enum support in actionc.
- Change `Close` and other Boolean DOS results from `LONGINT` to `INT`, preserving
  `DOSFALSE=0`, `DOSTRUE=-1` and the separate `IoErr()` error code.
- Retain 32-bit file positions, offsets and transfer counts where their range
  is needed. Apply narrowing consistently through COMMAND, providers and DOS,
  updating machine-readable contracts, generated declarations, callers and tests.

Treat signature changes as one ABI migration and rebuild affected commands and
the kernel together. Measure emitted size and argument/result handling in raw
and optimized builds; run focused success/error checks under the
[development testing tier](../contributing/testing.md#development-checks). Expected savings are
small; no disk-speed improvement is assumed. Target zero additional fixed or
per-Task bank-zero reservation.

### Command Main returns a status

Implemented with raw/optimized development checks and a refreshed, smoke-tested
play image. See the cross-repository [implementation plan](../plans/command-main-implementation-plan.md)
and [development record](../development/command-main.json).

Commands and resident Process callbacks return a signed `LONGINT` primary status.
The Process wrapper captures `IoErr()` before cleanup; public `SetIoErr` handles
command-defined errors. Ordinary Task entries remain procedures. Compact o65 v2
keeps the metadata layout size unchanged and rejects old procedure-entry files.
Reserved bank-zero delta is zero fixed bytes and zero bytes per Task.

### C-string literals and text APIs

Implemented in the [C-string plan](../plans/cstring-implementation-plan.md): `c"Hello\n"`
literals, the read-only CSTRING pointer view and seven allocation-free routines.
The pinned compiler owns language semantics, the implementation and its checked
provider contract. Exec includes one resident implementation alongside the
kernel. Commands import only used routines and call them directly in the Task's
context, without COP or per-call lookup. HELLO uses one counted write, including
its newline. Bank-zero reservations remain unchanged.

Follow-up: migrate selected public text APIs and their checked signatures
together, using zero-terminated text for names and paths while retaining counted
binary I/O; Process argument access now uses `GetArgStr()` and rejects embedded NUL. Near/far pointers,
allocating strings and dynamic library discovery/unloading remain deferred.

### Shared command arguments

Implemented the [small ReadArgs plan](../plans/command-arguments-implementation-plan.md):
`COMMAND.ReadArgs()` accepts positional strings and `/A`, with caller-owned
three-byte result slots and decoding storage. CAT and WC use it; shell token
separators include spaces and tabs. No allocation or new COP operation, and no
additional fixed or per-Task bank-zero reservation. Broader Amiga template
modifiers remain deferred.

### Near/far data pointers

Future compiler/ABI work: introduce explicit 16-bit near and 24-bit far pointer
forms, with a defined bank context, checked conversions and corresponding
signature identities. Apply the same facility to CSTRING; see the
[pointer considerations](cstrings-design.md#future-nearfar-pointers).
Begin with internal objects in known banks and retain far public interfaces
initially. Account for the current DBR=0 call boundary and preserve interrupt
context without enlarging bank-zero reservations for convenience. Measure code,
data and execution costs before migration; near callable pointers need a
separate call-convention design.
