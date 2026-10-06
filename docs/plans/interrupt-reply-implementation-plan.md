# Interrupt-context ReplyMsg implementation plan

[Implementation plans](README.md) · [Design note](interrupt-reply-design.md) ·
[Current port contract](../reference/ports.md) · [timer.device design](timer-device-design.md)

Status: implementation delivered at the development tier, 2026-10-06, with a remaining
high-speed timing gate. See the [execution record](../history/interrupt-reply.md)
and current [port](../reference/ports.md) / [timer](../reference/timer.md) contracts.
IR0–IR3 correctness checks pass; IR4/IR5 pass the standard nominal 57.6 kbit/s
loaded envelope. The final 16 KiB port-only workload misses three of 16,383 refill
deadlines at 125 kbit/s; adding sixteen timers misses five, despite correct data
and replies. Both shorter 4 KiB runs pass, so they cannot establish a bound. That profile is
not accepted or qualified; retain the stricter performance gate below as open.
The original design baseline is Exec816
`7268d114604fca6ee2927b063b6603e156bcbcf2`. The sections below retain the planned
gates so implementation evidence and remaining acceptance work stay distinct.

## Deliverable and sequence

Deliver one public native interrupt binding for ReplyMsg, backed by the same
protected port transactions as Task calls. Add generic deferred native sources
so the controlled NMI path can record work and complete it at safe boundaries.
Keep queue publication synchronous once ReplyMsg is called, and Task scheduling
outside the reply primitive. The [design note](interrupt-reply-design.md) remains
the authority for semantics; this plan assigns code changes and acceptance gates.

| Slice | Deliverable | Dependency | Status |
| --- | --- | --- | --- |
| IR0 | Access inventory, native ABI, return/stack proof and executable probe scaffolding | Current implementation | Development checks pass |
| IR1 | Shared protected queue transactions for existing Task operations | IR0 | Development checks pass |
| IR2 | Native IRQ ReplyMsg and generic retained-recipient signal publication | IR1 | Development checks pass |
| IR3 | Controlled NMI continuations, safe exits and guaranteed pending-work handoff | IR2 | Development checks pass |
| IR4 | Cancellation/lifetime races, coexistence and latency evidence | IR3 | Implemented; 125k timing gate open |
| IR5 | Real timer.device adoption and foundation handoff to AES | IR4 and timer TD0–TD3 | TD0–TD3 implemented; 57.6k envelope tested |

IR0–IR4 are the generic foundation. IR5 verifies its first production consumer
and shares the timer work with TD0–TD3; it is not a second timer implementation.
AES server work follows that gate. Existing SIO, console and display drivers
keep their current completion protocols unless a slice explicitly changes a
shared primitive they use. Do not migrate those drivers as incidental cleanup.

Use the slices as reviewable commit boundaries when implementation is requested.
IR3 is deliberately split into smaller changes below. Keep one current Task API,
with no compatibility profile, new COP signature or timer-private kernel call.
No timer worker, public WaitTimed or arbitrary application callback dispatcher
is part of this sequence.

## Code ownership and placement

| Area | Existing files and intended changes |
| --- | --- |
| Public port ABI | [abi/ports.json](../../abi/ports.json), [generate_ports.py](../../tools/generate_ports.py): describe/generate the native ReplyMsg binding while preserving Task selectors, packets and public record layouts. |
| Task port policy | [task-ports.inc](../../lib/exec/task-ports.inc), [portcore.act](../../lib/exec/portcore.act), [ports.s](../../platform/altirraos/ports.s): retain validation and Task-facing wrappers; route queue access through shared bounded native transactions. |
| Fast dequeue | [fast-getmsg.inc](../../platform/altirraos/fast-getmsg.inc), [fast-services.s](../../platform/altirraos/fast-services.s): protect head observation and removal, and integrate the common exit protocol. |
| Device reply collection | [task-io.inc](../../lib/io/task-io.inc), [iocore.act](../../lib/io/iocore.act), [io.s](../../platform/altirraos/io.s): coordinate exact-request collection and completion observations with interrupt publication. |
| Signals and wake queue | [signal-irq.s](../../platform/altirraos/signal-irq.s), [signal-atomic.s](../../platform/altirraos/signal-atomic.s), [task-signals.inc](../../lib/exec/task-signals.inc), [task-wakes.inc](../../lib/exec/task-wakes.inc): reuse one atomic publisher and preserve Wait/SetSignal/wake-claim ordering. |
| Entry, exits and scheduling | [hosted.s](../../platform/altirraos/hosted.s), [cooperative.s](../../platform/altirraos/cooperative.s), [preemptive.s](../../platform/altirraos/preemptive.s): distinguish queue exclusion, native service eligibility and Task scheduling eligibility. |
| Generation and packaging | [generate_tasks.py](../../tools/generate_tasks.py), [generate_memory.py](../../tools/generate_memory.py), [native_program.py](../../tools/native_program.py): reserve upper state/code, emit definitions and record all inputs/extents. |

Proposed new implementation files are `platform/altirraos/ports-atomic.s` for
queue transactions and `platform/altirraos/interrupt-work.s` for generic native
sources. Describe the latter in `abi/native-interrupts.json`, generated by
`tools/generate_native_interrupts.py`. Final symbols and storage offsets are
fixed in IR0, not copied into handwritten callers. These are now implemented paths; the current reference describes their supported interfaces.

Keep public binding declarations/generated interface outputs under the current
[interface licensing policy](../../LICENSING.md); update the licence map if a new
public output falls outside its existing coverage. Runtime code follows the OS
licence. Compiler/ABI defects belong in actionc, and emulator defects in
actionc-vm, with focused upstream regressions.

## IR0 — Freeze contracts and prove the entry/return model

1. Record source hashes, [compiler pin](../../toolchain/actionc.json), ROM hash,
   emulator revision/configuration, CPU rate, kernel placement and memory profile.
   Capture existing Task PutMsg/ReplyMsg/GetMsg/WaitIO costs and interrupt stack
   peaks using small optimized fixtures, before changing their implementation.
2. Inventory every read/write of active port links and message completion state.
   Include ordinary policy, fast GetMsg, IOCollect, CheckIO, WaitPort and deletion
   checks. Separate inactive initialization and driver-private lists from shared
   reply ports. Identify direct EXECLISTS access that needs migration; Forbid is
   not sufficient protection once native replies are enabled.
3. Specify the generated native binding: E=0, M=X=0, I=1, fully saved and admitted
   outer frame; A contains the low address word and X the zero-extended bank;
   preserve A/X/Y/P/D/DBR and S. Define activation-local scratch, stack admission
   and the bounded misuse/fault path. Keep ordinary Action!/C entry rules intact.
4. Specify immutable native source descriptors, enabled/pending/running state,
   notification and quiescence rules. Size the compiled source table explicitly;
   include a test-only non-timer source without reserving production test slots.
   Distinguish these descriptors from existing EXECPRODUCER signal bindings.
5. Write an instruction-level exit inventory: direct IRQ, post-ROM NMI, normal
   COP, fast service, OS bridge, rejected entry, idle and shutdown. For every
   phase record S/D/DBR ownership, frame shape, exclusion owner, legal completion
   and legal scheduling. Include NMI between individual restore instructions.
6. Build small assembly/Action! probes and a focused runner, proposed
   `tools/test_interrupt_reply.py` with fixtures under
   `tests/programs/interrupt_reply*`. Reuse the existing interrupt injection and
   guard machinery; prove the injection actually occurred in emitted code.

The highest-risk proof is the final return window: a byte indicating a safe
phase alone does not guarantee progress. Demonstrate how a completion arriving
after the last wake check reaches another scheduling decision before returning
to idle when scheduling is allowed. Select and document an adapter-owned return
trampoline or another instruction-proven handoff if the current restore tail
cannot provide this. Preserve the interrupted continuation and registers; never
redirect arbitrary foreign/ROM frames or reenter an active kernel frame.

**Acceptance:** checked ABI/layout outputs, complete access/exit inventories,
executed raw/optimized binding and context probes, and an explicit stack/cycle
budget for the proposed call chain. The admission/return feasibility probe must
cover the last-check race before production continuation dispatch is enabled.
IR0 probes exercise the proposed frame protocol; they do not yet make public
interrupt replies available.

## IR1 — Replace Task queue access with shared transactions

Implement the bounded native helpers first, and connect all existing consumers
before admitting an interrupt producer. Prepare immutable arguments and validate
record extents outside the masked region. Begin exclusion before the first
shared-state read that determines a mutation, and restore the incoming I flag
on every normal/fault exit.

| Transaction | Required work under common protection |
| --- | --- |
| Append | Commit message kind and every far link, then publish notification from retained local endpoint metadata. |
| Remove head | Observe the head/sentinel, unlink the selected node and return a coherent far pointer. |
| Collect exact reply | Inspect node type, unlink that request if replied, and mark it free; keep unrelated replies queued. |
| Observe | Read the queue/completion state consistently for WaitPort and CheckIO. |

Use short IRQ exclusion plus an NMI-visible publication guard or established
activation ownership. Task gateway SWITCHING remains kernel ownership, not a
general-purpose flag for interrupt code to clear. No list-length-dependent scan,
allocation, wait or compiled callback may occur inside these transactions.
Do not globally change EXECLISTS synchronization.

Keep Task validation, null reply-port behavior, PA_SIGNAL/PA_IGNORE and fault
semantics. Preserve the ordinary ReplyMsg/SendIO ownership handoff: after
publication use only locally retained wake/return data, never the message again.
Keep queue-to-signal ordering explicit while factoring the native publisher for
IR2; no second implementation of link updates may remain in fast GetMsg.

**Acceptance:** existing Task queue/wait/I/O behavior passes with empty, singleton,
multiple-node, exact middle-node and cross-bank records. Inject NMI around each
link access and request IRQs during masked transactions, checking delivery after
unmasking and intact queue state. Re-run focused raw/optimized access probes for
new bridges, and optimized behavioral cases. Record masked cycles and stack
peaks against IR0. Interrupt ReplyMsg is still unsupported in this slice.

## IR2 — Add the native IRQ ReplyMsg entry

1. Extract a retained-recipient native signal publisher from the current binding
   path. Existing hardware bindings and the new reply entry call the same core.
   Preserve atomic signal-mask updates, single wake-node enqueue, Wait publication
   and SetSignal behavior. IRQ code records a wake; Task policy owns ready lists.
2. Export the native ReplyMsg binding with bounded endpoint/context checks and
   the IR1 transaction. Resolve the retained Task from existing metadata without
   allocating or entering compiled policy. No recursive COP, shared kernel
   scratch, lease acquisition or Task scheduling belongs in the entry.
3. Add a synthetic non-timer resident with a retained request and reply endpoint.
   Its real native IRQ commits one result and replies. Test it independently of
   timer, SIO and GUI policy. Keep its source and instrumentation out of production
   builds.
4. Update existing context regressions precisely: the ordinary COP port gateway
   still rejects IRQ callers. Only the new admitted native binding is legal;
   early emulation/ROM entries remain unsupported.

**Acceptance:** by native ReplyMsg return, the queue and notification are
published. Test PA_SIGNAL, PA_IGNORE, null reply port, multiple senders, bank
crossings, and immediate collection/free/reuse. Preserve the full native context,
including nondefault D/DBR and caller flags, within the checked stack budget.
Use deliberate IRQ/NMI overlap with Wait, signal changes and wake claiming.
Invalid-context tests must fail without queue mutation; ownership violations
do not imply that every bad address/duplicate can be diagnosed at runtime.

Publish the supported IRQ contract in current reference documentation only after
this gate passes. Deferred NMI completion remains a separate pending capability.

## IR3 — Add controlled NMI work and close every exit race

Implement this in four reviewable steps. Intermediate probe builds may exercise
new paths, but production NMI dispatch is enabled only after the full IR3 gate.

### IR3a: Generic source storage and notification

Generate immutable source IDs/handlers and upper-RAM state. Notifications are
coalescing hints, with authoritative work retained by the source. Claim the hint
before inspecting work; new work must either enter that inspection or leave a
pending hint. Rearm on a bounded unfinished batch. Use independent flags with
defined access widths, not a shared NMI-unsafe read/modify/write bitmap.

Exercise notification, acknowledge, disable, quiescence and source reuse with
the non-timer fixture. Freeze callback and total service budgets in generated
configuration using the IR0/IR2 measured costs. Reject configurations whose
worst masked interval exceeds the pinned transport/input allowance.

### IR3b: Native continuation admission

Dispatch only with a fully saved native frame, retired ROM activation, stable
stack/DP ownership, no queue transaction and no recursively running native
continuation. Use an explicit service-active guard. The raw VBI path merely
retains a source notification; the wider timer clock belongs to the timer slice.

The existing saved-I exclusion stays in force for arbitrary masked Task/OS
frames. Forbid suppresses scheduling but permits native completion when other
admission conditions hold. Task-side driver edit gates defer their own source;
release with pending work uses the ordinary Poll gateway to reach a valid exit.
Neither an ISR nor NMI waits for interrupted code to drop a gate.

### IR3c: Return-phase handoff and scheduling

Apply the IR0 phase protocol to every inventoried exit, including the fast path
and OS bridge. Publish completion-safe state only after frame/stack selection
is consistent and before the final pending check. Keep its meaning valid across
the restore-only tail. NMI during that narrowly admitted phase may service work
from its own saved frame even if the saved I bit reflects adapter restoration.

When a reply wakes a Task after policy selection, reconsider that selection
only after the old kernel activation has retired. Cover a wake during the final
restore tail with the proved handoff, not only the earlier pending check. Never
return to idle with serviceable retained work and rely on an unrelated next VBI.
Do not clear another activation's SWITCHING or borrow its compiler workspace.

### IR3d: Bounded progress and production enablement

Service each source fairly with a finite per-source and per-opportunity budget.
Give hardware IRQs service opportunities between safe batches. Keep backlog
pending and specify its next service opportunity, including the path when all
Tasks would otherwise sleep. Avoid both an unbounded interrupt drain loop and a
fixed one-VBI penalty on every protected handoff. Separately report delay caused
by budget exhaustion or deliberately ineligible contexts.

**Acceptance:** inject one NMI before/after each flag publication, final work
check, kernel/OS retirement, stack transition and restore instruction. Cover
notifications during acknowledgement and running/disabled source transitions.
After a deferred event, suppress later unrelated ticks in the fixture and prove
completion at the protected exit; separately prove CPU-bound Tasks making no
Exec calls still receive service from normal hardware interrupts. Check a sole
sleeping client and idle selection. Repeat with nested IRQ/NMI and nondefault
register state. Demonstrate bounded backlog progress and no recursive dispatch,
stale phase ownership, lost work or premature stack reuse.

Only after these checks pass, enable production dispatch and update the platform
reference with the exact phase/admission rules and measured supported envelope.

## IR4 — Prove driver lifetime and loaded behavior

Extend the synthetic resident with caller-context submission/cancellation and a
native completion continuation. Serialize Task peers separately from its native
edit gate and short terminal commit. Release a gate with retained work through
the IR3 handoff. Have completion and AbortIO compete for the same terminal
transition; whichever commits first replies exactly once.

Cover pending, active, replied and already-collected requests, shared reply
ports, unrelated messages, immediate reuse, and cancellation at each commit
boundary. Stop the source before retiring state; drain pending/running work and
wakes, collect replies, then release recipient leases and endpoint storage.
Test failed admission rollback and repeated source/Task-slot reuse. A Task lease
does not authorize port deletion or FreeSignal while a producer still owns the
endpoint; verify that ownership rule explicitly without adding hidden kernel
port reference counts.

Run selected optimized SIO traffic with pointer capture and VBXE completion
active, plus OS calls and controlled shutdown/fault cleanup. Existing hardware
drivers still use their own public binding paths. Changes to their shared signal
publisher must preserve those paths' timing and lifetime behavior.

**Acceptance:** no double reply, lost signal, torn link, stale source/recipient,
post-retirement access or stack/DP damage. Record completion-to-signal and
signal-to-Task latency separately, and upper bounds on masked intervals, service
bursts and stack peaks. Compare matched input/configuration against IR0. A new
transport failure, broken existing timing bound, or unexplained latency increase
blocks adoption; a passing functional test alone is insufficient.

## IR5 — Adopt the foundation in timer.device

After IR4, execute timer TD0–TD3 from the [timer design](timer-device-design.md):
resident admission and rollback, wide coherent VBI clock, bounded native expiry,
and cancellation/close ownership. Use the generic source facility and native
ReplyMsg; driver code owns deadlines, queue ordering and terminal decisions.
Keep the proposed maximum four completions per timer continuation, subject to
the generic service budget validated above. No timer Task is admitted.

Verify actual timer requests from Action!/C, a sole sleeping client, multiple
simultaneous deadlines, abort versus expiry, last-close quiescence and repeated
reopen. Read the clock without modifying an active request. Compare empty-source,
long-wait and burst costs; distinguish timer resolution/rounding from native
completion delay and Task scheduling delay. The synthetic resident cannot serve
as evidence that the real timer driver has passed.

**Acceptance:** passing timer TD0–TD3 evidence plus the unchanged IR4 ownership
and interrupt invariants on the integrated build. This unlocks AES AS2 timer
wait integration and timer TD4 GUI measurements. Until those consumer checks run,
report IR0–IR4 foundation completion separately and leave IR5 pending.

## Verification and evidence

Use the [development tier](../contributing/testing.md) for each coherent slice.
Run the host suite and affected generators with `--check`; use small raw/optimized
probes for new layouts, ABI bridges and context preservation. Run functional,
race, lifetime and performance scenarios optimized. Add focused deeper interrupt
cases because these slices alter asynchronous entry, without launching the full
qualification matrix at every step.

| Existing runner | Reuse in this plan |
| --- | --- |
| [test_ports.py](../../tools/test_ports.py) | ABI, queues, cross-bank access, handoff, Wait publication/gap and supported/rejected contexts. For example, `--suite queues --case queues-opt` selects one optimized behavioral case. |
| [test_io_services.py](../../tools/test_io_services.py) | Queues, lifetime, handoff and exact-request wait/collection, using `--case opt` for behavior. |
| [test_signals_irq.py](../../tools/test_signals_irq.py), [test_signal_concurrency.py](../../tools/test_signal_concurrency.py) | Existing native publisher, signal/wake races and real IRQ/NMI delivery. |
| Proposed `test_interrupt_reply.py` | Select IR slice, optimized behavior or raw/optimized ABI probe, and individual injection/return boundary; report which machine-code checkpoints actually fired. |

Store detailed results under `build/interrupt-reply/irN/`, with compact reviewed
records under `docs/development/interrupt-reply-irN.json`. Record fixture and
production input hashes, actual machine pins, executed cases, timing/stack data,
memory deltas and remaining limits. Do not replace earlier qualification records
or describe diagnostic instrumentation as a production timing measurement.

At foundation completion, record final behavior in a new history page and update
its index, ports/signals/platform/device reference contracts, this plan and the
roadmap. When refreshing the demo, use `tools/build_demo.py`, include OF816 and
the matching disk/ROM/notices, retain five-second standard autoboot, and smoke-test
the exact package. Full release qualification remains separately requested work.

## Memory and completion gates

Target **0 additional fixed bank-zero bytes and 0 additional bytes per Task**
throughout. Reserve native source metadata, guards and code in upper memory;
count complete capacities and alignment. New near entry/exit stubs must fit the
existing adapter reservation, checked by linker extents. Do not assume unused
Task metadata space or resident padding is available without the generated map.

Measure the whole nested call chain: interrupted native frame, ROM/IRQ frame,
continuation, queue/signal helpers and nested NMI. Check root, ordinary, larger
worker, kernel and idle stack paths that the admission rules permit. Include
disabled-source fast-path overhead. No private interrupt stack or extra Task is
presumed. If the measured chain does not fit, revise the implementation/budget
before enabling that entry path; report guards, alignment and spare capacity in
any reservation change.

Avoiding a timer worker preserves one slot with 1,312 already reserved bytes
(1,024 stack + 32 guards + 256 DP). It does not shrink the bank-zero map.
Each implementation slice must report actual fixed and per-Task reservation
deltas, upper-RAM reservations and observed stack headroom. This documentation
change itself reserves **0 fixed bytes and 0 bytes per Task**.

The foundation is complete only after IR0–IR4 pass their selected executable
gates and current contracts describe the tested scope. Timer adoption is complete
only after IR5. Any unclosed exit race, dependence on an unrelated extra tick,
unsupported stack transition or unbounded masked operation leaves the affected
slice pending; do not substitute a quiet-machine demonstration for those gates.
