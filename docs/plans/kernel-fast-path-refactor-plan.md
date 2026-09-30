# Kernel COP fast-path refactor plan

Status: G1-G4 complete. Runtime baseline: `d0d1d7c`.
See the [implementation record](../history/kernel-fast-path-implementation.md).
Implement this before the [SIO driver boundary migration](sio-driver-boundary-implementation-plan.md).
Follow the [platform contract](../reference/platform.md),
[critical-section protocol](../history/kernel-critical-sections.md) and
[development testing policy](../contributing/testing.md). Commit each completed slice with its
focused validation record.

## Outcome and scope

Make frequent public coordination calls cheaper while retaining `COP #$50`,
the existing service selectors, native calling conventions and public behavior.
Initially cover only `Forbid`, `Permit` and `GetMsg`. Ordinary Tasks and all
drivers use the same implementation; callers do not select a fast/slow variant.

Keep the complete saved context, signature decoding and caller validation in
the first version. Route eligible calls before installing the kernel stack and
entering the general Action! dispatcher. Native handlers use checked local
scratch, without borrowing the shared compiler workspace. Existing temporary
DP changes during signature decoding are not themselves removed by this plan.

`Wait`, `Yield`, `Sleep`, Task lifetime, signal posting, message submission/reply
and other services retain their general paths. Additional COP signatures,
direct-call replacements, reduced context saves, priority scheduling and SIO
policy migration are separate work. Keep the compiler pin unchanged.

## Design constraints

The current gateway also processes timer work and pending IRQ wakes. Bypassing
Action! dispatch must preserve those responsibilities, not just the immediate
operation's result. Use the existing state as the authority; do not add a second
set of scheduling flags or duplicate ready/wake queues.

| Operation | Native work | When general processing is still needed |
| --- | --- | --- |
| `Forbid` | Check the depth limit; increment private depth and update `tc_TDNestCnt`. | Pending wake/timer bookkeeping may require dispatch even though switching is excluded. Apply exclusion before allowing another Task to run. |
| `Permit` | Reject underflow; decrement depth and update `tc_TDNestCnt`. | Process pending work; outermost release must honor pending rescheduling. Nested release alone does not prove that bookkeeping can be skipped. |
| `GetMsg` | Validate the argument packet and port; remove one head or return null through the existing pointer-result ABI. | Process pending work and any scheduling required before returning. A dequeue is completed exactly once. |

Define three internal outcomes: decline before mutation, completed, and fault.
A declined call retains its original frame and arguments for normal dispatch.
After completion, any required dispatch is **post-operation processing**, never
a retry of the service. Preserve the completed result while processing ticks,
wakes and scheduling. An internal continuation or the existing Poll machinery
may implement this; no new public service is needed.

Keep one implementation of each migrated operation. Share its native body with
the general route where needed, removing superseded Action! bodies as each
service migrates. Do not retain a selectable legacy implementation for timing
comparisons; use the recorded baseline revision.

### Entry, synchronization and return

- Retain full frame ownership, stack/DP bounds, service-width/tag checks,
  current-task bookkeeping (`savedS`, `tc_SPReg`), and existing fault behavior.
  Preserve each service's currently supported caller-masked behavior. IRQ, OS,
  idle and rejected activations must not acquire a shortcut around their rules.
- Hold `SWITCHING` while native code changes exclusion state or queue links.
  IRQs may continue once entry is stable; IRQ/NMI cannot run a second policy
  activation or inspect partial Task-only queue changes. `SEI` alone is not
  sufficient protection against NMI.
- Keep scratch activation-local and budget its peak stack use. Do not leave a
  native scratch frame active when transferring to the general dispatcher or
  restoring another Task. Preserve the saved D, DBR, register widths and flags.
- Audit all sources of deferred work: `E816_TICK_PENDING`, `T_TIMER_PENDING`,
  `T_WAKE_PENDING`, the caller's pending bit and the scheduler's protection and
  ready-state rules. Start conservatively: uncertainty takes the general path.
  Do not clear a tick or wake hint merely to qualify for fast return.
- Define the final decision under the existing IRQ/NMI return protocol. A wake
  or tick arriving after the initial check must be handled or remain durably
  pending at a documented safe boundary. Retain the native final wake recheck;
  an Action!-only check would leave an epilogue race. Test arrivals during that
  decision and during partial restoration, including NMI while I is set.

`GetMsg` must retain the [port contract](../reference/ports.md): FIFO, null
when empty, unchanged message type/body/reply port, stale removed links, and no
signal clearing. Preserve PA_SIGNAL/PA_IGNORE validation and existing ownership
preconditions; do not add a consumer-owner restriction. Support full 24-bit
pointers and records crossing bank boundaries. Its internal guard ends at the
call boundary: a driver still needs an outer `Forbid`/`Permit` region around
dequeue plus publication of its active request.

## Four executable slices

### G1 — Record the baseline and fix the entry/return contract

1. Map entry, validation, dispatch and restore in
   `platform/altirraos/{cooperative,preemptive,signal-irq}.s`, `tasks.s`, `ports.s`
   and `lib/exec/{taskpolicy.act,task-ports.inc,task-wakes.inc}`. Record the exact
   fast-return predicates and post-operation handoff, including masked callers.
2. Add a small ordinary-Task fixture for nested exclusion, empty/nonempty
   dequeue and their combined driver-style sequence. Include ready peers,
   timed sleepers, pending signals and Wait inside Forbid. Measure complete
   public calls, including native import wrappers, on the existing runtime.
3. Use passive entry/exit markers to distinguish full dispatch, fast completion
   and post-operation dispatch in later slices. Keep `E816_GATE_COUNT` counting
   every accepted COP entry. Diagnostic counters, if necessary, belong in upper
   RAM and must be separated from production timing measurements.

Exit: a reproducible raw/optimized baseline and a reviewed state-transition
table. No runtime optimization yet. Suggested commit:
`Define and measure the COP fast-path contract`.

### G2 — Add the native route and migrate Forbid/Permit

1. Add early service routing after safe common entry, before the general
   dispatcher. Keep unhandled services and foreign COP forwarding intact.
2. Implement exclusion updates once in bounded native code. Preserve maximum
   depth 128, underflow/overflow faults and the public nesting mirror. Remove
   the old Action! mutation path; retain general scheduler processing.
3. Implement same-Task fast return and the operation-completed continuation.
   A late IRQ/NMI or outermost Permit must never cause a second decrement or
   increment. Do not run a ready peer before a successful Forbid takes effect.
4. Exercise the changed entry, update, handoff and return boundaries with
   deterministic interrupt checkpoints; update observations that previously
   assumed every COP reaches Action! dispatch.

Exit: exclusion semantics and deferred-work delivery pass focused tests;
quiescent calls measurably avoid the full dispatcher. Report the change in
complete-call cost. Suggested commit: `Add fast COP paths for Forbid and Permit`.

### G3 — Migrate GetMsg without changing queue semantics

1. Add checked packet/port decoding and a bounded native dequeue under the same
   guard. Keep ABI constants generated from `abi/tasks.json` and `abi/ports.json`.
   Remove the superseded GetMsg service body from `task-ports.inc`; keep general
   Lists operations available to their existing callers.
2. Preserve full pointer results across both fast return and post-operation
   scheduling. Test empty, single-message and multi-message queues, bank
   crossings, invalid calls, and an IRQ arriving after dequeue but before return.
3. Move the dequeue race observation hook to the new implementation. Existing
   Action! List hooks alone will no longer prove interruption of native link
   writes. Cover a subsequent ordinary PutMsg/ReplyMsg exchange and immediate
   reply reuse, including the outer exclusion used for a driver claim.

Exit: exactly one dequeue per call, coherent queues at every scheduling point,
unchanged ownership/signals and a measured reduction in complete-call and
combined-sequence cost. Suggested commit: `Add the GetMsg COP fast path`.

### G4 — Validate integration, profile and refresh the play image

1. Measure the three calls and `Forbid/GetMsg/claim/Permit` against G1, with and
   without ready peers and interrupt activity. Report fast/general-path counts,
   entry-to-return cycles, elapsed latency when descheduled, stack peaks and
   longest IRQ-masked intervals separately. COP count alone cannot show success.
2. Run one bounded high-speed serial coexistence workload that repeatedly uses
   the changed calls, with a deadline observer and identical-image untraced
   replay. Check IRQ service, pending-wake latency and Task progress, not merely
   successful bytes. Forced race-checkpoint waits are excluded from timing.
3. Repeat cold HELLO on the existing PAL 8x, GENERIC57600, 128-byte SDFS profile,
   with the prime worker stopped and running. Preserve ROM/emulator/compiler,
   media, command payload and disk-timing settings from the
   [completion-collection baseline](../experiments/sio-completion-collection.md).
   Record all hashes and both CPU intervals and end-to-end times; disk rotation
   may hide CPU savings. This still measures the current SIO implementation.
4. After the focused checks pass, rebuild `build/demo`, run its loading/BREAK
   smoke and retain the previous bundle using the existing workflow. Publish
   the measured gateway result as the new baseline for the SIO migration.

Exit: measured primitive savings, no unresolved scheduling or serial regression,
and a usable play bundle. Report unchanged timings honestly. Suggested commit:
`Validate and package the COP fast paths`.

## Focused validation budget

Run the host suite for code slices and affected generator `--check` commands.
Reuse each raw/optimized build across runtime-selectable scenarios; extend
existing runners when they currently rebuild identical inputs. Do not rerun a
passing case unless its inputs or the affected boundary changed.

| Slice | Development selection |
| --- | --- |
| G1 | Small coordination/timing fixture in raw and optimized mode; establish guards, restoration and bounded completion. |
| G2 | Fixture plus relevant Task core/far, exclusion-fault and signal Wait/IRQ-under-Forbid cases; new transition checkpoints and representative native register/context rejection cases. Use filtered `test_tasks.py`/`test_signals.py` cases. |
| G3 | Focused `test_ports.py` queues, queue-context, queue-crossing, queue-races and queue-handoff cases in raw/optimized mode; extend the shared fixture for late-work handoff and GetMsg-specific invalid arguments. One signal-before-Wait case preserves the dequeue/wait protocol. |
| G4 | One targeted high-speed coexistence workload with raw/optimized correctness and observed/replay timing; stopped/running HELLO profile; new demo loading/BREAK smoke. |

Retain stack/domain guards, full register restoration, OS restoration, exact
message ownership and bounded completion. Include far Task nesting fields and
multi-byte queue links in the native-operation tests. Broader baud, capacity,
placement and failure matrices remain release qualification; expand earlier
only when a specific failure or changed assumption warrants it.

## Memory, ABI and completion

Target **0 additional fixed bank-zero bytes and 0 per Task**, including guards,
alignment and unused reservations. Keep public layouts and Task pools unchanged.
Account for native code placement inside the actual reserved regions, not just
its active byte count; use existing upper-RAM code capacity where practical.
Report any scratch/headroom change and actual reservation delta per slice.

No public fast-call variant, additional COP signature or ABI version change is
expected. Update generators/import bindings when implementation addresses move
and rebuild packaged programs consistently. No compiler qualification, disk
cleanup or release qualification is included.

Completion requires cheaper measured calls, preserved entry/return and queue
semantics, one implementation per migrated operation, focused interrupt and
integration evidence, and a refreshed play image. The measured image is the
baseline for S1-S4 of the separate SIO driver boundary plan; any additional
combined public API remains a separate
decision based on measurements.
