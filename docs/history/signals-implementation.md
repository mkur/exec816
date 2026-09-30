# Signals implementation record

> Historical record: applies to the revisions and profiles described below.
> See the [current documentation](../architecture/overview.md) and [history index](README.md).

This record tracks the executable slices of the
[implementation plan](../plans/signals-wait-implementation-plan.md). `--tasks` now builds
the single current Task/signal implementation; add `--task-capacity 8` for the
required capacity baseline. Old version names in historical qualification
records identify the measured commits, not selectable current kernels.

## Serial adapter — complete

Commit `de8fc6d` implements shared native/emulation serial routing and scoped
ownership. The [adapter contract](serial-irq-adapter.md) and
[qualification](../qualification/serial-irq.json) record the passing minimal path,
normal/abort cleanup, concurrent-source checks and timer-interference limit.
Production bank-zero reservation delta: **0 bytes**.

## Signal ABI and task integration — complete

The [Task ABI](../../abi/tasks.json) reserves selectors 23–27 for
AllocSignal, FreeSignal, SetSignal, Signal and Wait. Core selectors and the prototype heap's 15/16 remain distinct. Future
allocator integration must allocate its new selectors around these ranges.
This is the sole generated Task layout.

The four masks retain all 32 bits. Native packets align LONGCARD to two bytes;
Signal's Task pointer is at offset 0 and its mask at offset 4. The new COP
wrappers pass the outgoing packet's low address in X and bank in Y's low byte,
with selector in A. Y's high byte carries ABI tag 3 for all core Task
and signal calls. Malformed gateway tags fault before Task field access.
Legacy Version/Yield/Poll/Sleep retain their existing wire shapes; the native
Action! signatures are unchanged. Mask
results occupy both complete 16-bit A and X. This differs from a pointer result,
whose high register contains only the bank byte.

The [ABI runner](../../tools/test_signals_abi.py) executes ordinary compiler calls
and redirects the same emitted call entries through the generated COP wrappers
to an explicitly test-only echo responder. These are ABI probes, not successful
signal-service stubs. The probe checks layout, odd/bank-crossing field accesses,
padding/guards, bit 31, complete mask results and context/OS restoration in raw
and optimized emitted code. The [qualification record](../qualification/signals-abi.json)
contains all four passing runs and emitted offsets. The echo responder never enters production builds.

### Private storage chosen for task integration

Generate the metadata base from the highest usable bank in the selected memory
map; the standard 1 MiB profile selects `$0F:0000`. It is an explicit image
reservation, excluded from writable application admission. Packaging must reject
code/data overlap before loading. This placement is independent of the kernel
code's starting bank and moves when the selected usable-bank map changes.

For four public contexts plus private idle, reserve **512 upper-RAM bytes**:

| Range relative to base | Purpose |
| --- | --- |
| `$000–$13F` | Five 64-byte private contexts |
| `$140–$148` | Ready MinList |
| `$149–$151` | Pending-wake MinList |
| `$152–$159` | Live/timer flags and counters |
| `$15A–$189` | Sixteen procedure bindings |
| `$18A–$18E` | Writable-range count and pointer |
| `$18F` | Alignment |
| `$190–$19B` | Stable serial Task/context/mask binding |
| `$19C–$1D9` | Kernel-owned 62-byte root Task |
| `$1DA–$1DD` | Saved serial ownership state |
| `$1DE` | Timed-sleeper count |
| `$1DF–$1FF` | Arena alignment/reserved capacity |

Each private record reuses the old reserved byte at 3 for wait reason and at
13 for queued state. Its separate six-byte MinNode starts at 32. The record
contains 26 bytes of explicit tail reservation, giving a constant-time shift
of six; this is upper-RAM capacity, not a new bank-zero stride. Count the unused
idle node as part of the idle reservation. The fixed non-context arena costs
192 bytes including root, plus 64 per public context and 64 for idle. A public Task grows from
42 to 62 bytes and can still reside anywhere in writable linear RAM.

The ABI-only slice changes **0 production bank-zero reservation bytes**. It
retains all current stack/DP sizes, guards and old arena reservations. The integration uses long indexed-X accesses for private records, including
frame validation (absolute-long indexed-Y is unavailable). DP ownership pointers
retain their bank byte. The checked image loader loads the complete metadata
arena and procedure bindings; writable application admission excludes it.

```sh
python3 tools/test_signals_abi.py --compiler-dir build/actionc \
  --bridge-dir build/altirra-irq-bridge
python3 tools/generate_tasks.py --check
python3 -m unittest discover -s tests -p 'test_signals_package.py'
```

## Mask policy and direct task association

The `--tasks` build moves private contexts,
queues, counters, bindings and the root Task into upper RAM. `Lookup` validates
the opaque context link by range, stride alignment and reciprocal live ownership;
ready-head selection uses that same constant-time association. Admission and
name enumeration may still search. Timer expiry scans run only for a consumed
VBI tick, rather than for every service invocation.

AllocSignal, FreeSignal and SetSignal are implemented in the protected kernel
activation. Allocation is per task and reserves bits 0–15. Success clears the
new bit's received state. FreeSignal `$FF` does nothing; invalid frees fault,
and valid frees retain received bits until reallocation/consumption. SetSignal
returns all 32 old bits. Calls preserve the caller's I flag. Root and new/reused
tasks initialize signals identically. Admission rejects preinitialized signal
state and preserves rejected storage; removal clears association before reuse.
In the slice 3 commit, Signal and Wait still fault; slice 4 below supplies them.

Task builds include signals without a separate API selection.
No public ABI success stub stands in for a missing service.

### Complete bank-zero reservation accounting

The before/after reservation totals are identical. They include guards, unused
capacity, the complete 1 KiB table reservation, 2 KiB near-image arena and the
retained 240-byte legacy context reservation; no space is reclaimed implicitly.

| Phase | Before | After | Delta |
| --- | ---: | ---: | ---: |
| Loading, including OS reservations | 58,560 | 58,560 | 0 |
| Steady runtime, including OS reservations | 57,968 | 57,968 | 0 |
| Loading, excluding OS low/high ranges | 21,696 | 21,696 | 0 |
| Steady runtime, excluding OS low/high ranges | 21,104 | 21,104 | 0 |

Each public task reserves 1,856 bank-zero bytes: 256-byte DP + 1,536-byte stack
+ four 16-byte guards. Private idle costs another 1,856; fixed runtime Exec
reservations cost 11,824. All four public tasks plus idle therefore consume
9,280 of the 21,104 non-OS runtime bytes. The metadata reservation grows in upper
RAM; moving the root descriptor saves active near-image bytes but does not
shrink that image arena. Frame validation temporarily pushes two more stack
bytes while using the existing interrupt reserve; no stack allocation grows.

The reservation map uses the existing loading ranges from the memory profile.
Runtime releases loader/staging storage after adoption, then adds the three
extra DP/stack pools described in the Task contract. Reclaiming unused arenas
and choosing smaller stacks remain the capacity slice's explicit work.

### Slice 3 qualification

[Recorded results](../qualification/signals-masks.json): 25 raw and 25 optimized
emitted cases pass, plus four old/new raw-gateway profile checks. Coverage
includes cold root, admission/rejection, far descriptors, sleep, 260 repeated
admissions/reuses per mode, allocation isolation/exhaustion, full-width masks,
caller-masked nonblocking services, invalid frees, eight NMI transition points
and five interrupted native flag combinations. Stack/DP guards and OS/context
restoration pass. Thirty-four package checks and the generated-definition check
also pass. This is the pinned 1×/1 MiB functional profile, not SIO timing evidence.

The kernel uses ordinary far pointers for upper metadata; the compiler's mapped
globals remain near-only. Small policy helpers keep native frames within the
compiler's 254-byte frame/255-byte displacement limit. Geometry such as the
public-context byte count is generated rather than calculated at runtime.

## Task-context Signal and Wait — complete

`Signal` resolves and updates only its known target. A matching signal waiter
becomes READY; running/ready tasks retain posts, timed Sleep remains separate,
and `Wait(0)` remains parked. `Wait` consumes matching pending bits immediately,
or atomically publishes the mask and suspends its continuation. Completion
consumes matching bits atomically at selection, including earlier posts made
while already READY. Posts after that consume remain pending for the next Wait,
even if native context restoration has not finished. Other pending bits remain.
A blocking wait preserves its task's Forbid nesting
while allowing other tasks to run; an immediate wait keeps exclusion in force.
Caller-masked Wait faults before publishing or consuming signal state.

The [task-signal qualification](../qualification/signals-wait.json) covers emitted
raw/optimized wait/lifecycle fixtures, null/foreign/unaligned/wrong-bank links,
masked Wait with and without preposted bits, and six transition checkpoints per
mode with real VBI interruption. The checkpoint routine exists only in explicit
probe builds. These checkpoints surround complete policy stores; they do not
claim instruction-by-instruction interruption of a 32-bit store. IRQ queue
transactions receive separate assembly-level qualification in the next slice.

This milestone qualifies task-context calls on the pinned 1×/1 MiB profile.
There is no IRQ producer or pending-wake drain in the slice 4 commit.
Production bank-zero reservation delta is **0 bytes**, fixed and per task;
all loading/runtime totals and stack/DP/guard reservations in the preceding
budget remain unchanged. There is no upper metadata reservation increase.

```sh
python3 tools/test_signals.py --compiler-dir build/actionc \
  --bridge-dir build/altirra-irq-bridge --case wait-raw --case wait-opt \
  --case lifecycle-raw --case lifecycle-opt
```

## Pending-wake FIFO and serial posting

The Task adapter now uses the shared serial route with a stable far Task/context/
32-bit mask binding. Its native handler ORs received bits, tests only the bound
context and appends its private MinNode at most once. A known-node cancellation
removes a queued target before direct task-context delivery or removal. Removal
of a still-bound producer target faults; the source must be quiesced and released
first. The cached wake byte tracks the authoritative far MinList, including its
last cancellation/dequeue. No posting, cancellation or ready-head path scans
unrelated tasks.

The IRQ routine uses twelve activation-local scratch bytes on the interrupted
stack and saves/restores D. ROM's emulation serial callback preserves the hidden
B accumulator and complete native registers while posting; it cannot schedule
across the live OS activation. Scoped claim/release uses the shared ownership
adapter. Releasing an inactive producer preserves serial enables. The original
experimental Bind/Release/Drain interface has been replaced by the public
[EXECPRODUCER contract](../reference/resident-drivers.md#public-platform-producer)
in S3. `EXECSIGNALIRQ` now contains only diagnostic pump/context entries.

The [queue qualification](../qualification/signals-irq-queue.json) records ten
passing emitted cases and covers FIFO order, repeated posts, task-context takeover,
head/middle/tail/last cancellation, pending-bit retention and far descriptors
with equal low words in different banks. NMI probe builds wait for real VBIs
after each native IRQ mask/link/flag write, skipping waits inside live emulation
OS activations. This deliberately slow diagnostic profile is not a latency test.
Full-capacity bursts including the root and automatic exit delivery are later
integration gates; they are not established by the three-worker queue fixture.

On the new combined **8×, shadow-ROM, 1 MiB** profile, the measured maximum for
serial routing plus posting was **33.480 µs** across this bounded four-post
fixture. This excludes native entry saves, draining, selection and worker code;
it is not a 125 kbaud end-to-end pass. The adapter and signal assembly live in an
explicit upper image extent at metadata-bank `$1000`; overlapping code/data is
rejected by packaging. Four saved ownership bytes fit the existing 512-byte
metadata reservation. The pending flag uses `$203A` in the existing 256-byte
state reservation. Fixed/per-task bank-zero reservation delta: **0 bytes**;
all earlier full-range totals remain unchanged.

## Safe exits and idle — complete

Commit `cd69e62` supplies the bounded producer and queue. Automatic delivery now
enters policy for pending wakes independently of timer ticks. Outer native IRQ
and NMI return paths retire their OS/IRQ activations before considering policy;
existing task gateway, Permit and native OS-return Poll paths also drain.
Caller-masked I remains masked, and Forbid allows readiness processing while
deferring a task switch.

The original drain implementation ran each target transaction with I=1 and
opened IRQ windows between targets. The current
[critical-section protocol](kernel-critical-sections.md) permits IRQs through
policy, masking only native shared-state operations. SWITCHING stays active,
so nested IRQ/NMI can post or record ticks and return but cannot recursively
dispatch. Selection follows the eligible pass, with a native pending-wake
recheck before return. Private idle masks, checks pending wake/live state,
executes WAI with I=1, then unmasks and polls. A pending IRQ therefore wakes WAI
even if it arrived between the check and sleep; shutdown does not need another
VBI after the final task exits.

[Seventeen emitted cases](../qualification/signals-drain.json) cover raw/optimized
task semantics, real serial wake with VBI disabled, Forbid deferral, all-waiting
idle, a root-inclusive four-target queue burst, and a real IRQ asserted under
I=1 then serviced between drain transactions. The latter verifies no premature
handler entry, no recursive scheduling and retention of an unrelated signal.
The diagnostic burst uses a fixed admitted binding set and snapshots each
actual queued flag before draining. It is explicitly absent from production
builds. The isolated queue tests use `manual_wake=True`, recorded in provenance;
normal builds always drain automatically. Raw/optimized shutdown tests also
complete with VBI disabled. Full guards and domains remain intact.

Fourteen unchanged single/cooperative/preemptive/banked/Lists regression cases
pass after the shared adapter changes. These results qualify functionality;
the separate integrated stream measurement determines baud suitability.
Production bank-zero reservation delta remains **0 bytes**, fixed and per task.
The IRQ-window eligibility byte uses `$203B` in the existing state reservation;
upper metadata, DP/stack/guard reservations and the preceding totals are unchanged.

## Integrated signal qualification — complete, with timing limits

The public calls and real serial IRQ delivery pass functional qualification.
The [integrated record](../qualification/signals-integrated.json) separates that
result from the **failed worker-per-byte 125 kbaud target**. Signals are included in `--tasks`. No allocator,
message ports, production SIO driver or DOS service is included.

The combined [8×/1 MiB profile](../../toolchain/altirra-signals-1m.json) uses the
pinned AltirraOS 3.44 native ROM, PAL, fast ROM, normal VBI, scoped CRITIC and
POKEY divisor 14: 126,674.821 baud and **78.942286 µs per byte**. Measurements
observe hardware-ready through the actual SEROUT write. The passive
[observer patch](../../toolchain/patches/altirra-signals-observer.patch) adds 24-bit
instruction markers and hardware timestamps without adding guest instructions.
Its [build record](../../toolchain/altirra-signals-observer.json) is distinct from
the emulator correctness pin.

| Workload | Bytes | Worst refill | Late refills / gaps | Timing result |
| --- | ---: | ---: | ---: | --- |
| Public Wait per byte, four live tasks, optimized | 256 | 21,458.769 µs | 255 / 255 | Fails |
| Public Wait per byte, idle background, raw | 256 | 3,719.873 µs | 255 / 255 | Fails |
| Diagnostic IRQ byte pump, four live tasks, optimized | 65,535 | 60.334 µs | 0 / 0 | Passes restricted workload |

All streams finish with the correct sequence, no overwrite, final-byte
completion and intact guards. Functional success does not erase the measured
gaps. The general path spends about **602.992 µs in a nonempty masked drain
transaction**, with a measured full drain up to **771.943 µs**. FIFO READY
publication also does not guarantee that the worker runs next; the worst trace
includes a wait for the next VBI. The observer measures executed routine returns,
including the RTL cost; empty drains are not paired with a later IRQ window.
These measurements are workload maxima, not a global worst-case bound.

The diagnostic pump sends bytes in the native or ROM-emulation serial callback
and posts one ordinary signal on block completion. The worker calls public
Wait once. It passes with a busy root and two parked bystanders, **no task kernel
calls during the stream, no timed sleepers and no other ready peer**. The
65,535-byte uninstrumented replay matches its image hash, final memory/context,
65,535 IRQs, 261 VBIs, nine switches and sixteen gateway calls exactly. A 4,096-byte
run also passes. This establishes a measured buffer/phase-completion direction;
it is not a production buffer API, RX path, protocol, or general SIO qualification.

A new upper-RAM sleeper count avoids entering policy on every tick during that
restricted transfer. The native shortcut is reached only after normal context
and transition validation, and only with active serial ownership, no pending
wake, no timed sleeper and an empty ready queue. Ticks remain recorded. Sleep
admission, expiry and removal maintain the count; raw/optimized sleep,
cancellation and target-state regressions pass. Otherwise the existing scheduling
path runs. At this historical measurement boundary, general kernel calls and
nonempty drains still exceeded the byte budget. The later
[critical-section implementation](kernel-critical-sections.md) addresses that
blackout; these earlier measurements remain tied to their recorded inputs.

Additional evidence covers all four interrupted M/X combinations under a real
serial IRQ (A including hidden B, X/Y/P/D/DBR/S/PC/PBR and DP contents), raw and
optimized full queues and protected IRQ windows, core Task admission, and fourteen
historical hosted/cooperative/preemptive/banked/Lists regressions. Instrumented
race fixtures establish correctness; they are excluded from timing claims.

```sh
python3 tools/test_signals.py --compiler-dir build/actionc \
  --bridge-dir build/altirra-irq-bridge
python3 tools/test_signal_stream.py --compiler-dir build/actionc \
  --variant 2 --count 256 --output build/signals-tests/stream-four
python3 tools/test_signal_stream.py --compiler-dir build/actionc \
  --pump --variant 2 --count 65535 --output build/signals-tests/pump-long
python3 tools/test_signal_stream.py --compiler-dir build/actionc \
  --pump --variant 2 --count 65535 --replay \
  --bridge-dir build/altirra-irq-bridge --output build/signals-tests/pump-replay
```

The timing runner reports functional/measurement integrity in `status`, and a
separate `timing.verdict`; scripts accepting a baud profile must require both.

Slice 7 reserves **0 additional bank-zero bytes**, fixed or per task. The
sleeper byte uses existing upper metadata padding. Diagnostic context captures
fit the existing state reservation; IRQ pump counters reuse diagnostic bytes.
The complete four-task loading/runtime totals remain 58,560 / 57,968 bytes
including OS ranges, or 21,696 / 21,104 excluding them. Each public context and
idle still reserves 1,856 bytes; fixed runtime Exec reservations remain 11,824.

## Eight-task capacity — complete for the required baseline

The [capacity record and memory map](../architecture/task-capacity.md) document eight live public
Tasks plus idle, generated stack bounds, upper-RAM bank table and metadata, and
kernel-bank builds at 1 and 3. The [qualification record](../qualification/signals-capacity.json)
covers raw/optimized simultaneous workloads, full wake queues, bank-crossing
Task storage, rejection/reuse, all-context checks and historical regressions.
The runnable [signal example](../../examples/signals.act) uses all eight tasks:
root, six application workers and the native console worker.
Twelve/sixteen contexts remain future qualification targets.

The eight-task IRQ pump passes 65,535 bytes at 125 kbaud's configured hardware
rate, with 59.771 µs maximum refill and an identical uninstrumented replay.
The same restricted interference contract applies. An ordinary eight-target
drain takes up to 4,880.466 µs with a 570.851 µs maximum masked target transaction;
this does not qualify concurrent kernel work for SIO.

Reserved bank-zero runtime grows by **3,568 bytes** from the four-task profile,
while loading shrinks by **1,328 bytes**. Fixed runtime storage saves 1,264 bytes;
root costs 2,080, each of seven workers 1,568, and idle 1,056. The complete
reservation totals and diagnostic-only 128-byte context-capture cost are in the
[budget](../architecture/task-capacity.md#complete-bank-zero-budget). No allocator is needed.

Completed commit boundaries: serial adapter `de8fc6d`, ABI `ea8589c`, direct
association and masks `96a5fee`, task Signal/Wait `dc3cd34`, IRQ queue `cd69e62`,
safe drains/idle `c93cff6`, integrated timing `76e2492`, and the capacity commit
containing this section. Each boundary retains its qualification record.

## Concurrent kernel-work measurement

The [four-task concurrency stress test](signals-concurrency.md) is implemented.
It exercises the existing diagnostic IRQ pump with compute-only, Yield,
Signal/Wait, timed-Sleep and mixed interference. Passive microstate observations
capture complete I-flag transitions, and each measured XEX is replayed on the
uninstrumented emulator. Byte deadlines and functional integrity have separate
verdicts. This slice supplies the baseline for reducing critical sections;
production policy and bank-zero reservations are unchanged.
All twenty observed/replay executions pass functional checks. The optimized
mixed workload misses 1,998 of 4,095 refill deadlines, with a 1,320.028 µs worst
refill and a 1,306.495 µs longest masked interval. Only the compute controls
meet the deadline; the [record](../qualification/signals-concurrency.json) preserves
the complete baseline workload matrix and input hashes. The subsequent
[interruptible-policy slice](kernel-critical-sections.md) replaces whole-call
masking with native atomic mechanisms and repeats the same acceptance matrix.
