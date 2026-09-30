# SIO driver boundary implementation plan

Status: S1-S4 complete with development validation. Runtime baseline after
the COP refactor: `82010c7`, packaged and measured by G4 below.
Follow the [architecture guidance](../../AGENTS.md#architecture),
[platform contract](../reference/platform.md) and [development testing policy](../contributing/testing.md).
Commit each completed slice with its focused validation record.
See the [selected contract](../reference/resident-drivers.md) and
[implementation record](../history/sio-driver-boundary-implementation.md).

Prerequisite satisfied: the [kernel COP fast-path refactor](kernel-fast-path-refactor-plan.md)
is complete. Use its [measured image](../history/kernel-fast-path-implementation.md#g4-integration-and-play-image)
as the migration baseline. It makes public
`Forbid`/`Permit`/`GetMsg` coordination cheaper without changing their contracts.
The S1-S4 ownership/lifetime work below is a separate sequence.

## Outcome and scope

Make SIO a driver that owns its request and lifecycle policy and uses general
public Exec facilities. Preserve the current application-facing I/O behavior,
one worker per physical bus, cancellation guarantees and OS restoration.
Remove the private `SIODRIVER.Control` protocol as its responsibilities migrate.
A combined receive operation is not a prerequisite or an assumed outcome.

The reference is classic Amiga's driver entry-point model: BeginIO executes in
the submitting task, and AbortIO dispatches to the device's cancellation code.
See [device I/O](https://wiki.amigaos.net/wiki/Exec_Device_I/O) and
[AbortIO](https://developer.amigaos3.net/autodocs/exec.library/AbortIO.html).
QNX and BeOS are references for specific gaps; adopting another kernel's full
IPC or driver framework is outside this plan.

Keep the current serial engine, timing profiles, filesystem implementations,
loader batching and compiler pin. Do not combine this work with sector-copy
optimization, general gateway tuning, dynamically loaded drivers, a complete
Amiga Library/vector ABI, or wholesale DOS/console policy migration. Shared
dispatch and shutdown integration must still be updated where SIO depends on them.

## Starting coupling and target ownership

| Responsibility | Current location | Target |
| --- | --- | --- |
| Open/unit counts, admission, request validation and submission | `task-io.inc`, `task-sio.inc`, `siodriver.act` | Driver entry points on the calling Task's stack/DP; generic I/O dispatch retains public argument/context checks. |
| Pending queue, active request, preparation/cancellation state, reply publication | `SIOTake`, `SIOAbort`, `SIOFinish` under kernel SWITCHING | Driver-owned upper-RAM records, coordinated through public Task, port and List facilities. |
| Worker startup, stop flag, readiness, removal and restart | SIO control operations plus scheduler hooks | Driver lifecycle code using public task/resource lifetime mechanisms. |
| Last-application shutdown and resident counting | `SIORemoved`, `DosRemoved`, `ConsoleRemoved`, `ConsoleCanRemove` | Generic lifetime notification/counting; each service interprets its own stop condition. |
| Signal atomicity, scheduling, Task identity and resource retention | Task kernel | Remain generic kernel responsibilities. |
| POKEY ownership, IRQ state machine, descriptor publication and safe retirement | Native SIO adapter | Remain the platform driver's hardware responsibilities. |

Inspect these paths together, including generated copies:
`lib/io/{siodriver,iocore,blockwire,deviceinspect}.act`,
`lib/io/{task-io,task-sio,io-call-types}.inc`,
`lib/exec/{taskpolicy.act,task-wakes.inc}`, `lib/dos/task-dos.inc`,
`lib/console/task-console.inc`, `platform/altirraos/{io,sio,signal-irq}.s`,
and the I/O, Task and native-program generators. Changing only the worker loop
would leave SIO ownership and shutdown policy in the kernel.

## Required synchronization contract

- **Task-side state:** start with short `Forbid`/`Permit` regions around shared
  driver state. Submission, dequeue/claim and cancellation use the same protocol.
  IRQs remain enabled; IRQ/NMI handlers must never inspect the driver's queue or
  active-request links. Existing scheduling exclusion covers VBI preemption;
  masking IRQ alone does not cover NMI.
- **Claim:** dequeue with `GetMsg` and publish the active pointer/preparing state
  before releasing exclusion. Abort must never see a request removed from the
  queue but not yet owned by the worker. Preserve `NT_MESSAGE` while it is pending.
- **Cancellation:** retain the distinction between public AbortIO and the
  filesystem's conditional cancellation, which declines an already-started
  frame. Move that decision into driver code without changing accepted aborts,
  original error precedence, committed cursors or reset-required outcomes.
- **Hardware state:** retain the native Start/Cancel/Retire publication protocol.
  `Forbid` does not stop serial IRQs. Any changed IRQ-shared update needs a bounded
  native transaction and IRQ/NMI entry tests; do not mask interrupts around an
  Action! queue walk, callback or transfer.
- **Reply:** finalize results and clear active ownership before `ReplyMsg`, under
  task exclusion. Never dereference the request after publishing its reply:
  the recipient can immediately collect, reuse or free it.
- **Wait:** commit all state before waiting. Preserve durable signals between
  checking work and `Wait`; tolerate stale/shared notifications. Do not clear
  notifications in that gap or suspend with a partially updated queue.
- **Execution context:** driver callbacks run on the caller's stack and DP after
  kernel dispatch has returned. Do not call them inside SWITCHING, retain a
  saved kernel activation across them, or introduce recursive kernel-policy entry.

## Slices

| Slice | Deliverable | Suggested commit |
| --- | --- | --- |
| S1 | Fix the driver/lifetime contracts and prove public coordination with ordinary Tasks | `Define the public SIO driver boundary` |
| S2 | Move submission, claim, cancellation and completion into the driver | `Move SIO request ownership into the driver` |
| S3 | Move worker lifetime and replace SIO-specific removal/shutdown hooks | `Move SIO worker lifetime to public Exec facilities` |
| S4 | Profile the complete migration and refresh the play bundle | `Validate and package the SIO driver migration` |

### S1 — Contract and public-coordination proof

1. Document typed resident entry points for Open, Close, BeginIO and AbortIO,
   their execution contexts, ownership and allowed nested public calls. Use an
   immutable built-in dispatch description initially; no dynamic driver loader
   or arbitrary callback execution inside kernel policy. Keep existing console
   and test-device routing working through the one current public I/O interface.
2. Specify the driver record and every reader/writer, including startup, offline
   recovery, diagnostics and teardown. Separate Task-only state from IRQ-shared
   descriptor fields. Put the contract in the device design and implementation
   details in the implementation record.
3. Resolve public Task admission with the existing stack pools. `AddTask` already
   checks availability and Process leases; prefer trying eligible public pool
   bounds under exclusion over another SIO-specific allocator. Replace the
   worker-name exclusion in generated entry admission with a documented entry
   registration rule and a driver-level duplicate-start check.
4. Specify the remaining lifetime mechanism before S3: protection before IRQ
   binding and during teardown, live producer retention, and notification when
   the last application exits. First reuse existing generic mechanisms where
   their contracts suffice. Any missing service must get a minimal **public**
   contract for arbitrary owned Tasks/resources, including failure, notification,
   release and slot-reuse semantics. Do not relocate SIO-name tests into a new
   kernel helper. Audit the existing private signal Bind/Release/Drain interface
   and document its supported public driver contract and platform limits.
5. Add a small emitted-code fixture using ordinary Tasks and public queues to
   exercise dequeue/claim exclusion, a notification arriving before Wait and
   immediate reply reuse. Specify deterministic race checkpoints for S2/S3.
   Test any new public primitive with a non-SIO caller when it is implemented.

Exit: the ownership table, callback contract, lifetime API decisions and memory
budget are concrete. No unspecified lifecycle hook is left for implementation
to improvise. No public combined receive/stop ABI has been presumed necessary.

### S2 — Request ownership and driver dispatch

1. Route the migrated device entry points through the caller-context I/O layer
   (`IOCORE` and native bindings). Keep public signatures, context validation,
   signed errors, SendIO flag clearing, BeginIO flag preservation, quick-I/O
   handling and exact WaitIO collection intact. Exercise a non-SIO resident in
   the dispatch fixture so this is a general device mechanism.
2. Move the request-state functions as one coherent ownership change: enqueue,
   dequeue/claim, preparing-to-active publication, AbortIO/conditional cancel,
   and completion. Use public `PutMsg`, `GetMsg`, `ReplyMsg`, `Signal`, `Wait`,
   List operations and the S1 exclusion protocol. Keep copies and wire waits
   outside critical sections.
3. Remove the converted control operations (currently 2, 3, 4, 9 and conditional
   cancellation) and their kernel implementations in this slice. Remaining
   lifecycle operations may continue until S3, with an explicit state-access
   contract; there is only one owner and implementation for each migrated field.
4. Update `BLOCKWIRE`, error/retirement probes and passive trace markers with the
   new boundary. Keep the existing completion-collection optimization; internal
   helpers implementing generic public I/O are distinct from driver-specific
   kernel services. Do not add further private bypasses for driver coordination.

Exit: the kernel no longer decides which SIO request is active or how it is
cancelled/completed. Hardware behavior and caller-visible I/O semantics pass
the focused regressions. Record a checkpoint profile to expose added crossing
cost early; architectural separation is not itself a speedup claim.

### S3 — Worker lifetime and system integration

1. Start and retire the worker through public Task facilities. Serialize first
   opens, publish readiness only after successful initialization, and roll back
   task/port/signal/hardware acquisition in reverse order on failure. Retain one
   worker across multiple opens and units.
2. Move open counts, stop/readiness state and restart coordination into the
   driver. Stop refuses busy state, prevents new admission, wakes the worker,
   and waits for actual retirement without confusing a reused Task slot with
   the previous worker. Reading the driver's stop flag needs no kernel query.
3. Implement the generic public lifetime services selected in S1, if needed,
   before replacing their current protections. Test an ordinary Task using them.
   Preserve rejection of removal with live producer resources and ensure that
   startup/teardown windows remain protected. Disable/release the producer and
   drain pending wake references before its Task or signal can be reused.
4. Replace SIO-specific accesses in Task, DOS and console shutdown paths with
   generic lifetime information/notifications. Each service retains its own
   stop logic. Cover standalone SIO applications, DOS clients and the full demo,
   including normal return and supported explicit Task-removal paths. Keep fatal
   serial ownership faults on the existing reset-required path.
5. Remove the rest of `SIODRIVER.Control`, its private selector, generated
   bindings/types, SIO-specific scheduler hooks and obsolete tests as they are
   replaced. Change `DEVICEINSPECT` to read a synchronized driver snapshot.
   Update ABI inputs, generators, documentation and import consumers together;
   rebuild affected programs rather than retaining compatibility profiles.

Exit: no SIO policy or worker-identity dispatch remains in Task policy. Generic
resource protections remain enforced. DOS/console use no SIO-private record
layout for lifetime decisions, and the obsolete control interface is absent.

### S4 — Measurement and play image

Rebuild one diagnostic bundle and measure cold HELLO under the same pinned
GENERIC57600 profile, 128-byte SDFS media and command payload, with the prime
worker stopped and running. Compare against the completed fast-path refactor's
recorded baseline to isolate the driver migration. The earlier
[completion-collection baseline](../experiments/sio-completion-collection.md)
remains a historical reference:

| Metric | Prime stopped | Prime running |
| --- | ---: | ---: |
| Mean inter-sector gap | 16.80 ms | 18.57 ms |
| HELLO payload | 2.46 s | 2.42 s |
| HELLO open to prompt | 4.10 s | 4.14 s |

Measure actual gateway counts, exclusion duration and retirement/dequeue/copy
intervals. Reuse the image for traced/untraced replay; keep observer overhead,
scheduling and rotational waits separate from CPU-cost claims. Investigate
material regressions before packaging and report architectural and timing
results separately, including unchanged end-to-end timing.

After focused checks pass, rebuild `build/demo`, run its loading/BREAK smoke,
and record artifact hashes and pins. Retain the previous play bundle according
to the existing workflow; disk cleanup is separate. Full release qualification
and physical-hardware qualification remain separate activities.

## Validation budget

Use host checks and affected generator checks for each code slice. Build raw and
optimized native fixtures once per changed input set, then select scenarios or
reuse saved startup state. Run the following focused selection, not every matrix:

| Slice | Native development selection |
| --- | --- |
| S1 | Small ordinary-Task coordination fixture, raw/optimized; no disk workload. |
| S2 | Generic I/O dispatch/flags/context cases; selected `test_sio_recovery.py` queued, preparing, active, terminal and reuse cases; changed claim/reply race checkpoints in raw/optimized mode. Selected checksum/short error cases reuse the recovery build. One bounded filesystem BREAK regression covers conditional on-wire cancellation and committed data. |
| S3 | Startup-capacity/binding rollback and bound-worker removal cases; add deterministic concurrent-open, stop-versus-open, last-client exit and restart/slot-reuse scenarios. Raw/optimized lifetime fixture plus one DOS/console coexistence shutdown run. |
| S4 | Same-profile HELLO traces and identical-image replay; `test_demo.py --loading-smoke` on the new play bundle. |

Retain guard, register/DP restoration, exact-once reply, buffer ownership and
bounded-completion assertions. Add a targeted high-speed IRQ/NMI coexistence
case when a changed critical section or producer binding affects serial service;
broader baud, density, placement and eight-Task matrices belong to release
qualification. Adapt observation hooks instead of dropping assertions when
kernel-owned SIO routines disappear. Documentation-only changes run content/link
checks, with no compiler build or emulator execution.

## Memory, ABI and completion criteria

Target **0 additional fixed bank-zero bytes and 0 per Task** in every slice.
Reuse existing upper-RAM SIO records and the existing worker slot where possible.
Budget any new generic lifetime/dispatch metadata in upper RAM, including unused
capacity; report actual reservation and stack-peak deltas with guards/alignment.
Do not infer free memory from a smaller active record or enlarge all Task DPs.

Keep the compiler revision in `toolchain/actionc.json`. No compiler qualification
or pin update is part of this work. Any genuine compiler defect belongs in
actionc with a focused regression; do not introduce routine-specific workarounds.

The migration is complete when ordinary clients retain their I/O behavior,
SIO owns its policy, all required kernel coordination has a documented reusable
public contract, old SIO-control paths are removed, and the measured play image
passes the focused checks. If repeated public calls still dominate, propose a
separate measured public-ABI optimization with ordinary-Task tests and precise
message/signal/ownership semantics. Do not automatically add it to these slices.
