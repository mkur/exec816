# Input registration and lifetime design

[Implementation plans](README.md) · [Refactor plan](input-registration-lifetime-implementation-plan.md) ·
[Current input contract](../reference/input.md) ·
[Console contract](../reference/console.md) · [Open roadmap](../roadmap.md)

Status: implemented through IR5, 4 October 2026. This note preserves the design
and its original baseline. The [refactor plan](input-registration-lifetime-implementation-plan.md)
and [implementation record](../history/input-registration-lifetime.md) describe
execution and remaining performance limits; the input reference defines the
current caller obligations.

Adopt classic Amiga's registration and lifetime discipline for native input:
establish the consumer, storage and producer relationship at acquisition, trust
that relationship during ordinary use, and retire all activity before releasing
it. Keep the existing IRQ capture, bounded rings, signals and Task consumers.
Move repeated memory-range and full lease audits out of ordinary event delivery.

The first migration covers keyboard and pointer input, the Action! and C entry
paths, console integration and hosted GEM. The same principle should guide later
display and DOS work, but each public contract needs its own explicit migration.
This note does not change core Exec ownership rules, scheduling, mouse sampling,
drawing or filesystem behavior.

## Reason for the change

Before this refactor, the console's quiet-input optimization already avoided
entering INPUT when no work was indicated. Active input still paid full validation on each
[INPUT.Take](../../lib/input/input.act), including the final call returning
EMPTY. Each call validates both the lease and event-buffer extent, audits the
lease and invokes `FindTask(NULL)` to check the consumer.

The [archived active-input baseline](../development/input-registration-baseline.json)
records passive profiling of the unchanged optimized circular-console image.
For three single-key drains in the loaded phase-zero workload:

| Work | Charged CPU per drain |
| --- | ---: |
| Complete console input service | 8.59–8.89 ms |
| Two Take calls, including final EMPTY | 6.75–7.61 ms |
| Four writable-table searches inside those calls | 4.40–5.26 ms |
| Two full lease checks, including FindTask | 1.56–1.66 ms |
| Character translation | 0.060–0.067 ms |

These are nested spans, not additive categories. CPU charge includes kernel
and scheduling tails and bus stalls; native IRQ bodies and off-worker time are
excluded. Both resident buffers match writable-range record 22, so four scans
visit 88 range records per key. This is a shared image-range table, not memory
protection or per-Task allocation ownership.

The pre-refactor [C bridge](../../c/calypsi/input-bridge.inc) added another full `INPUT.Extent`
check before calling the native operation. That duplication is a source finding;
the timing table measures the Action! console path and does not quantify C cost.

Reuse these saved measurements and the [existing loaded-console evidence](../development/console-circular-buffer-cb4.json).
No new baseline workload is needed merely to begin implementation. Compare new
code against the existing artifacts under matching inputs; identify any changed
workload or compiler separately. These development records do not qualify the
hosted system or establish an achieved speedup for this proposal.

## Amiga precedent and the retained queue architecture

Classic Amiga's [IND_ADDHANDLER contract](https://d0.se/autodocs/input.device/IND_ADDHANDLER)
registers a handler and data pointer and retains the registration structure
until removal completes. Our chosen interpretation is to establish authority
and storage lifetime at registration and make correct use during that lifetime
a caller obligation. This does not claim that all Amiga device operations omit
checks or that its input API is identical to ours.

Preserve our existing execution flow:

```text
hardware IRQ -> fixed capture ring and durable notices -> consumer signal
             -> bounded Task drain -> route and translate -> client input
```

IRQ code remains bounded, allocation-free and confined to resident capture
storage. No application callbacks run in IRQ context. There is no new input
Task, callback chain or per-event message allocation. The consumer can process
input while a graphics operation is in flight, subject to the existing model
and drawing gates.

A future desktop can own the hardware sources and route input to windows. This
refactor prepares that use without implementing window distribution or changing
the current exclusive-source rule.

## Registration contract

Keep `Acquire`, `Take`, `Pending`, route operations and `Release` as the one
public input API. A live lease identifies a registration; it is not a memory
protection capability. Retain the existing 32-byte lease, 32-byte configuration,
24-byte event and eight-entry C bridge unless implementation reveals a concrete
need for a separately documented layout change.

### Acquisition

Acquire remains a checked, infrequent boundary. Before enabling capture it must:

1. Validate complete lease/configuration extents, alignment and bank placement,
   configuration version, supported source/protocol, bounds, filters and flags.
2. Require free, zero-initialized lease storage, an available source and an
   allocated nonzero wake mask belonging to the acquiring Task.
3. Retain the Task, copy configuration, allocate a nonwrapping acquisition
   identity and establish the producer binding.
4. Initialize capture and route state before publishing the active registration.
   Unwind all partial ownership if admission fails.

The lease remains address-stable and unmodified by callers until successful
Release. The retained Task reference prevents removal/recycling of its Task
record; it does not keep an arbitrary heap buffer or a returned stack frame
alive. The caller must separately preserve the lease's storage and wake signal.
Configuration storage may be reused after Acquire returns because it is copied.

### Ordinary use

The proposed caller obligations are:

- Pass the original live lease. Do not copy, move, mutate, free or reuse it.
- Only the acquiring Task consumes events through Take or releases the source.
- Other cooperating Tasks may continue to use Pending and route operations
  through an explicitly shared live registration. Its owner must coordinate
  their lifetime and stop further calls before release.
- Output records must be writable, correctly aligned, within the supported
  upper-RAM bank extent, and live for the whole call. They must not overlap the
  lease, configuration snapshot or input subsystem state.
- Do not invoke Task-only operations from IRQ/NMI context or race storage
  retirement with a call.

Output storage is borrowed for one synchronous call, never retained. Keep the
existing `Take(lease, event)` signature: a valid buffer may change between calls.
Do not register an extra output buffer, pin it or add a buffer registry solely
to avoid repeated checks. Valid writable storage becomes a caller precondition.

Violating these obligations is API misuse; production builds do not promise
safe rejection of arbitrary, freed, copied, corrupted or wrong-Task arguments
during ordinary use. Detected errors may still return INVALID_OWNER, but callers
must not use that as a lifetime probe. In particular, an old pointer to reused
lease storage carries no independent generation that can prove its old identity.

Legal calls retain their current results and output rules: EMPTY does not alter
the output, Pending is observational, and records preserve their acquisition,
captured route, ordering and field initialization.

### Release and reuse

Release remains a checked lifecycle boundary, including owner and registration
identity checks before mutation. The owner first prevents new calls from Tasks
sharing the registration and joins their outstanding use through the existing
service lifecycle. It must not wait for such a join while holding Forbid.

Then preserve the existing serialized retirement transaction: mark RELEASING,
stop addressed capture and the hardware producer, drain retained producer
notifications, purge raw records/notices and pending pointer-button output,
retire route state, release the Task retention, and clear the registration.
The source must not become available to a new acquisition before retirement is
complete. A failed lifecycle check leaves the live registration intact.

Only successful Release permits freeing/reusing the lease or wake signal.
Stopping capture must prevent a late IRQ or producer post from referring to the
old consumer. Reacquisition starts with a new acquisition identity and no old
queued input. Merely publishing route zero is not release.

## Checks that remain during use

Distinguish stable registration facts from state that can change after Acquire.

| Check or operation | Proposed placement |
| --- | --- |
| Full writable-table/heap-region validation of lease storage | Acquire and Release; diagnostic audits during use |
| Configuration, allocated signal, owner Task, Task incarnation and immutable lease fields | Lifecycle boundaries; diagnostic audits during use |
| Full memory audit of output event/tag/mask storage | Diagnostic builds; valid memory is a production caller obligation |
| C huge-pointer representability and fixed record shape | C boundary before narrowing; constant-cost checks remain |
| Resolving the fixed keyboard/pointer source | Once per public operation under the existing exclusion |
| Queue availability, ring capacity and publication order | Runtime |
| Route existence, retirement references and generation exhaustion | Runtime |
| Captured acquisition/route/notice epoch when data can outlive a change | Runtime |
| Pointer arithmetic overflow, clipping, button ordering and loss recovery | Runtime |
| Cancellation, producer shutdown and notification retirement | Runtime |

Use the existing two resident source descriptors to resolve the original lease
address once. Pass the resolved state/capture to internal helpers, instead of
repeating `Shared`, `SourceOf`, and `Capture` lookups. A missing registration can
still be rejected cheaply. Do not add a variable-length registry or expose
native descriptors to public callers. This lookup chooses the source; it does
not replace the caller's lifetime and correct-consumer obligations.

For a valid ordinary Take, the remaining work is source resolution, protected
notice/ring consumption, event construction and return. There must be no
`TASKMEMORY.Writable`, `TypeOfMem`, or `FindTask(NULL)` call attributable to
INPUT's registration validation in that path, including EMPTY. Apply the same
stable-check removal to Pending and route operations; retain checks on the
route values and changing state they manipulate.

## Synchronization and notification

Preserve the current division of responsibility. Forbid serializes Task-side
registration and consumption. Short native transactions save/set the interrupt
mask for ring copies, acknowledgements and hardware publication. NMI remains
possible and must preserve the existing IRQ-depth, stack, DP and switching
protocol. Removing validation does not justify replacing these guards with an
unprotected head/tail copy.

Resolve state only after entering the Task exclusion and do not retain borrowed
descriptor pointers across Permit, a yield or a wait. Callbacks and blocking
operations remain excluded from this transaction. Initially keep the console's
outer Pump exclusion, which also covers routing and delivery; removing nested
Forbid/Permit pairs requires a separate concurrency argument.

Signals remain hints that work may exist. Keep the console's cached pending
flag and the GEM loop's pending-before-wait discipline. A bounded drain that
stops at its budget keeps the consumer runnable; it does not claim EMPTY. A new
arrival after an empty observation must leave its notification pending. An
invariant failure must never be converted into EMPTY or a cleared wake.

Retain durable cancellation/loss outside ordinary ring capacity, capture-time
route tags across focus changes, and pointer coalescing barriers at button
edges. Generations carried by deferred data serve a different purpose from
rechecking the unchanged lease on every call and must remain.

## Diagnostics and public contract migration

Provide an explicit build-time input diagnostic setting, recorded in the build
manifest, off by default. It adds memory and lease audits around the same
implementation; it does not select a second API or queue algorithm. Production
input consumption must compile without those audits, rather than visiting a
runtime diagnostic branch on every event. Diagnostic support may reuse the
existing validators.

Diagnostic failures should report the operation and failed invariant before
mutation where possible. Tests with readable copied/corrupted records or a
wrong consuming Task can retain deterministic rejection checks there. Diagnostic
validation remains best-effort in shared memory and is not a sandbox.

The C bridge must preserve full huge pointer values until range, alignment and
fixed-bank-shape checks have passed. Split representation checks from memory
membership audits: ordinary C calls use the former, while Acquire/Release
perform INPUT's full lifecycle validation once in native code. Required checks
inside Exec's retention primitives remain. Moving the old full audit into a
differently named bridge helper would leave the problem intact.

This changes the behavioral contract even if the binary layouts and config
version stay unchanged. Update the [input reference](../reference/input.md),
generated public-header comments through [the generator](../../tools/generate_input.py),
Action!/C callers and test expectations together. Rebuild all consumers. Preserve
current numeric status values and configuration version 2 when their meanings
and layout do not need changing; diagnostics are a build setting, not an ABI
compatibility mode. Historical qualification retains its original assertions.

Production regressions must still test invalid admission, malformed C values,
bad route tags, exhausted identities, full queues and lifecycle failures. Move
per-use wrong-Task/corrupt-storage assertions to diagnostic coverage instead of
silently deleting them or running deliberate undefined misuse as production
acceptance. Exec TaskLease checks and general `TASKMEMORY.Writable` behavior
remain unchanged for other APIs.

## Integration boundaries

| Area | Required refactoring or later application |
| --- | --- |
| INPUT Action! implementation | Separate admission/audits from ordinary use; resolve source once and share trusted internal helpers for both sources. |
| C input bridge | Remove duplicate full audits while preserving checks before narrowing huge values. |
| Console capture and foreground routing | Audit registration sharing, stop order and output-buffer lifetime; retain loss/BREAK and routing exclusion. |
| Hosted GEM input | Migrate keyboard and mouse together; preserve partial-acquisition rollback, bounded drains and session/route checks on deferred events. |
| Display and drawing | Later review of repeated worker/lease-owner checks after establishing drawing lifetime; busy/fault and in-flight resource rules remain necessary. |
| DOS and filesystem | Later review of repeated handle-list and packet-identity audits; retain cancellation, mount/media state, transfer bounds and on-disk validation. |
| Core Exec | No new private input gateway, Task service or global unchecked mode. Any later change needs its own public contract and evidence. |

The wider principle is to retain resources through their use, trust the
documented caller relationship, and enforce changing state at the operation
that changes it. A live file or display object has different sharing and
retirement rules from an input registration; removing all checks globally is
not a migration strategy.

## Memory and performance expectations

No new Task, stack, DP, capture queue, registered-buffer table or retained
per-event allocation is proposed. Expected reserved bank-zero delta is **zero**
for fixed/root/kernel storage, **zero for each public Task**, and **zero for
private idle**, counting guards, alignment and unused capacity. This document
itself changes no reservation. Implementation must verify emitted placement,
upper-code/data size and stack high-water marks for each slice and diagnostic
setting; existing upper capture reservations should remain unchanged.

The immediate structural target is zero repeated memory-table/heap scans and
zero current-Task lookups for input authority during ordinary use. A proposed
performance target is at most **2 ms charged CPU** for the complete
`CONSOLEINPUT.Service` call for each recorded single-key drain, including its
final EMPTY, on the matched optimized workload.
This is a target to measure, not a subtraction-based speedup claim. Measure empty,
single-event, burst, loss and cancellation paths separately, including the C
bridge and pointer consumer.

Keep the wider 4 ms worker-turn, 20 ms scroll and 40 ms visible-input goals.
Record complete turns, maximum Forbid duration and capture-to-visible latency;
cheaper consumption alone does not establish those goals. If full-ring drains
remain too long, size a separate per-turn event budget from measurements and
preserve the pending-work rule; queue capacity need not be the drain budget.

Mouse sampling remains approximately 7.9 kHz in the recorded workload. Timer
frequency, common IRQ overhead, scheduler policy and drawing budgets are
separate variables. Keep them fixed during the input-contract comparison.

## Validation and completion criteria

Use the [development tier](../contributing/testing.md): host checks, generated
interface checks and focused emitted raw/optimized coverage. Select existing
input, pointer, console and GEM fixtures rather than starting with a full
release matrix. The [refactor plan](input-registration-lifetime-implementation-plan.md)
splits these executable changes and measurements into reviewable slices.

Acceptance requires:

- Valid Action! and C consumers produce unchanged keyboard, motion/button,
  cancellation and loss results; EMPTY preserves every output byte.
- Acquire failure leaves no producer, Task hold or partial active source;
  release/reacquire purges old input and prevents late posts into retired state.
- Shared route calls, focus changes and retirement preserve captured tags,
  including queued cancellation and pending pointer-button output.
- Arrivals before/after empty observation, during bounded drains and around
  release have no lost wake, torn record, duplicate acknowledgement or use of
  retired storage. Preserve IRQ/NMI context, guards and OS restoration.
- Both sources operate with physical SIO and blitter completion active on the
  pinned machine. Preserve existing sample-gap and serial timing assertions.
- Diagnostic fixtures still detect supported misuse. Production emitted code
  and passive traces show the removed audit calls are absent from ordinary
  input paths; matched functional results agree across diagnostic settings.
- Reuse the saved baseline, measure the changed build, and replay selected
  integration workloads without passive tracing. Publish measured costs and
  remaining misses without claiming full qualification.

Completion means one documented registration contract used by both languages
and both consumers, lifecycle and queue behavior preserved, diagnostic coverage
retained, and the active-input cost measured. Desktop routing, sampling-rate
changes and other subsystem migrations remain subsequent work.
