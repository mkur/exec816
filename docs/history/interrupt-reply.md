# Native interrupt replies and timer.device

[History](README.md) · [Plan](../plans/interrupt-reply-implementation-plan.md) ·
[Ports](../reference/ports.md#native-interrupt-reply) · [Timer](../reference/timer.md)

This implements shared port transactions, the native ReplyMsg binding,
adapter-owned deferred sources and the first production consumer, timer.device.
Validation uses the development tier plus targeted interrupt, race and transport
checks. It does not qualify every hosted configuration or implement the AES
server. The original Exec source baseline is `7268d114604fca6ee2927b063b6603e156bcbcf2`.
The six [IR0](../development/interrupt-reply-ir0.json),
[IR1](../development/interrupt-reply-ir1.json),
[IR2](../development/interrupt-reply-ir2.json),
[IR3](../development/interrupt-reply-ir3.json),
[IR4](../development/interrupt-reply-ir4.json) and
[IR5](../development/interrupt-reply-ir5.json) records retain exact tested inputs,
machine pins, selected cases, stack observations and measurement limits.

## Shared-state access inventory

| Access | Protection and ownership |
| --- | --- |
| Task PutMsg/ReplyMsg | Policy validates stable arguments; `ports_append` owns IRQ exclusion and PORT_BUSY before the first live tail read. Policy retains only endpoint metadata after publication. |
| GetMsg, including fast gateway | `ports_take`/`ports_take_fast` share one head/sentinel observation and unlink body. No second fast-path list implementation remains. |
| WaitPort and DeleteMsgPort empty checks | `ports_peek` reads a coherent head. Lifetime/quiescence remain caller obligations; an empty observation is not endpoint retention. |
| WaitIO/DoIO exact collection | `ports_collect` checks type, removes that reply and marks it free in one transaction; other replies remain queued. |
| CheckIO | Reads the byte-wide terminal type under Task gateway ownership. Native publication finishes as one transaction before the interrupted Task can resume. |
| Native reply | Activation-local endpoint validation; common append followed by the retained-recipient signal publisher. No request read after the append. A deferred caller can admit an IRQ between validation and publication; IRQ callers preserve exclusion throughout. |
| Signal/Wait/SetSignal/wake claiming | Existing atomic signal protocol remains shared. Received bits precede a single wake-node enqueue. Only Task policy mutates ready lists. |
| Port initialization and registry | NewList requires an inactive port. Registry nodes use Task serialization; IRQ producers never traverse that registry. |
| Private queued I/O/SIO lists | Driver-owned, Task-only queues retain their existing Forbid protocol. Their direct EXECLISTS access is not shared reply-port access. |
| Timer pending/open tables | IOCORE Forbid serializes Task peers. TIMERDRIVER's edit gate blocks its continuation independently; no native callback waits for an editor. |

The public list API remains caller-synchronized. Forbid by itself cannot protect
manual edits to a port accepting native replies. Leases prevent recipient Task
removal; callers separately retain ports, signals and request storage.

## Entry and instruction-level exit inventory

The complete native frame is 13 bytes: DBR, D, Y, X, A, P, PC and PBR. Adapter
entry saves it before changing registers or stacks. On ROM entry a separate
page-one activation retains the native S; NMI records clock/hint state there,
then restores S only after ROM retirement. Pending hints never authorize entry
into compiled policy from an interrupt.

| Phase | S/D/DBR and owner | Legal action |
| --- | --- | --- |
| Native IRQ body | Fully saved interrupted frame; D/DBR initially zero, IRQ_DEPTH owns activation | Bounded native ReplyMsg, with activation-local scratch. No scheduling. |
| Live ROM NMI/IRQ or COP `$00` bridge | Page-one OS stack, ROM D/DBR, OS/IRQ exclusion | Record clock and hints only; retain work until retirement. |
| Post-ROM interrupt exit | Original complete native frame, D/DBR zero, ROM activation retired | Validate stack, Task D and original I. Admit native service or Task policy only after exclusion checks. |
| Task COP/fast service | SWITCHING owns kernel activation; kernel D/stack for policy | Shared queue transactions are legal; native completion waits. Fast GetMsg uses the same transaction. |
| OS bridge retirement | Caller frame restored; OS_BUSY cleared by its owner | Reach ordinary protected return checks; never suspend a live ROM activation. |
| Selected return | S points at the chosen complete frame; kernel D, DBR zero, compiled activation retired | Native work can publish; pending wakes reconsider selection through internal Poll. |
| `native_commit_tail..end` | S unchanged; original frame remains complete | Nested NMI can redirect only that validated outer frame; ordinary native calls leave the classified range and restart the check. |
| `interrupt_quiet_tail..end` | S unchanged after IRQ/ROM retirement, D/DBR zero | Empty-work shortcut remains classifiable through its last branch. A nested event cannot disappear between check and restore. |
| `restore_commit` / `interrupt_restore` | REP changes no frame size; PLB/PLD/PLY/PLX/PLA progressively restore caller ownership | Recognize exactly 0, 1, 3, 5, 7 or 9 popped bytes. Derive full outer S from the nested 13-byte frame and this instruction phase. |
| RTI and pre-COP handoff | Four hardware-frame bytes remain, then the complete original context is restored | A per-Task redirect enters a private COP trampoline. An armed slot prevents interrupt-exit scheduling until decode restores the original PC/PBR, clears the slot and requests Poll. |
| Idle | Private admitted idle frame; no compiled activation | Exhausted budget starts another bounded opportunity if serviceable work remains. Never WAI over eligible retained work. |
| Rejected entry / shutdown | Fault/OS-restoration owner; Task scheduling stopped | No attempt to call deferred policy from an invalid frame. Normal shutdown requires producer quiescence and released leases; fault cleanup restores platform ownership. |

`NI_ACTIVE` protects the complete continuation, including its IRQ-open windows.
`NI_PORT_BUSY` protects queue publication. Neither clears someone else's
SWITCHING. The return interceptor checks both guards, IRQ depth and OS activity;
it accepts only adapter instruction ranges and an original unmasked, owned Task
frame. D comes from the outer frame before PLD, or the nested frame after PLD.
Per-Task original-PC slots prevent double redirects. An armed slot also excludes
switching during the restored-context handoff before COP: another Task cannot
remove this Task or reuse its slot while its saved PC remains live. Foreign PCs
and arbitrary I=1 Tasks remain deferred.

Ten restore/quiet checkpoints exercise actual NMIs, then disable later VBI to
prove exit progress. Separate fixtures cover acknowledgement during a callback,
source disable/reuse, edit gates, blocked callbacks, Forbid and idle backlog.
Root and idle probes additionally inject a real NMI before the private COP,
asserting no premature callback or policy activation and no armed slots left
after collection.
A negative control changing only the guard's armed-return carry result triggers
the regression's premature-work assertion.
Forty-six queue-access checkpoints inject NMI around far reads/writes and retain
IRQ requests until unmasking. These are deliberate diagnostic stalls, not
production timing measurements.

## Bounds, memory and timing

Production source capacity is one; the additional source exists only in probe
builds. Each opportunity admits two callbacks; a timer callback commits at most
four requests. IRQs can run before callbacks, before each timer reply, between
deferred reply validation/publication and after replies. A native IRQ caller's
ReplyMsg itself retains its incoming exclusion. Pending state is acknowledged
before calling its owner, so notification during execution survives. A blocked
source requires its owner to release the edit gate and Poll. Last-close retires
the timer source synchronously; there is no worker or callback-vector mutation.

Native reply reserves 10 saved bytes and 24 local bytes, with a two-byte helper
return and 14 bytes for the signal publisher's D/local storage (plus its return).
The continuation saves 10 register bytes plus P and return addresses; timer
expiry uses 26 local bytes plus D. Nested interrupt frames and the interceptor's
12-byte local frame are additional. The checked native reply admission reserves
32 bytes below its locals for the bounded helper chain. IRQ/NMI nesting uses
the existing 256-byte interrupt allowance; ROM nesting uses the separate OS
stack. Measured root, 1,024-byte worker, 2,560-byte worker, kernel and 512-byte
idle headroom is recorded with boot-fill high-water observations, not asserted
as a mathematical worst case for arbitrary external handlers.

Every slice changes reserved bank zero by **0 fixed bytes and 0 bytes per Task**.
The existing upper Task bank suballocates 256 source bytes, 512 timer bytes,
1,280 alignment bytes and 8,192 native code bytes: **10,240 bytes including all
capacity**. No additional physical bank is reserved. Sixteen pending slots and
eight opens include unused capacity. Avoiding a timer worker leaves an existing
Task slot available; it does not shrink the memory map.

The first measured implementation added unnecessary descriptor scans to every
byte IRQ and shifted masks up to 31 times. The final implementation has a
classified empty-work exit and a fixed mask table. IRQ opportunities separate
immutable reply validation from publication for deferred callers. Matched
fast-service measurements and loaded byte deadlines are retained in IR4/IR5;
queue protection and final return checks add real cost, so this change is not
presented as a general speedup. Clock granularity, expiry publication and Task
scheduling latency are separate quantities. Unbounded OS work, a masked Task
or an application holding an edit gate has no promised completion deadline.

The final sixteen-timer burst at nominal 57.6k transmitted 4,096 correct bytes
with zero late refills; maximum refill was 81.198 µs and maximum observed I=1
interval 110.237 µs. Native reply entry to signal measured 72.951–110.237 µs
(including IRQ interference), signal to recipient restore 786.956–3,840.331 µs,
and maximum callback duration 511.433 µs. The recipient may already be runnable;
these are elapsed pipeline measurements, not exclusive execution costs.

The 125k acceptance gate remains open. The final 4 KiB runs passed, with maximum
refills of 75.559 µs without timers and 78.378 µs with them. Extending to 16 KiB
exposed three missed deadlines without timers (maximum 84.017 µs) and five with
them (maximum 87.400 µs versus 78.942 µs available), among 16,383 refills.
All bytes, requests and ownership checks passed. A 4 KiB baseline with only the
pre-existing routing defect repaired missed none (maximum 77.815 µs); earlier
implementation revisions already missed deadlines at that length. The final
short-run passes therefore do not establish a worst-case bound.
The standard 57.6k build is the tested integration envelope. IR4/IR5 high-speed
acceptance is deliberately not marked complete.

Matched optimized fast-service medians were:

| Call | Baseline | Implemented |
| --- | ---: | ---: |
| Forbid | 47.224 µs | 55.647 µs |
| GetMsg | 77.039 µs | 100.581 µs |
| Permit | 48.458 µs | 55.929 µs |
| Nested claim sequence | 534.799 µs | 636.507 µs |

These measurements include guard/return checks and possible interrupt interference.
They make the cost of the stronger port/exit protocol visible; they do not claim
that the new kernel path is faster overall.

## Timer and compiler integration

Action! and actual Calypsi C calls cover quick completion, asynchronous waits,
abort/collection, reuse, open exhaustion and cleanup. Wide arithmetic checks use
an independent host oracle for PAL/NTSC, all 32-bit GEM durations, carry and
overflow. Real VBI is injected between each snapshot word. Two Task clients
repeat creation/removal with 72 terminal results, including completion during a
CPU-only loop, Forbid, and deferral while I=1. Equal deadlines and a full
sixteen-entry queue retain FIFO order and reject the seventeenth request.

These tests exposed an actionc defect: indexing an array of record pointers
could produce a record value instead of a pointer and fail native emission.
The fix belongs in actionc, with semantic and raw/optimized machine-code
regressions. The [pin](../../toolchain/actionc.json) selects the clean local fix;
its incremental Git bundle and [build instructions](../contributing/building.md)
make the unpublished revision reproducible. Full compiler tests passed (3,699
passed, 29 ignored), all 51 NIR sweep cases passed, and the focused VM regression
passed. These compiler results do not qualify Exec's hosted system.

An existing native input-routing fall-through bug also surfaced: with no active
input timer, the adapter jumped out through input routing before reaching the
serial producer. Routing now tests whether input handled the IRQ and otherwise
continues to serial. The untouched baseline stress run timed out; the matched
fast-service baseline and historical transport records remain identified
separately. Two test issues were corrected: I/O exhaustion storage needed one
slot per possible bank, and the GEM screen oracle must use the actual cursor
blink phase. Neither is a relaxation of queue, disk-data or rendering checks.

AES AS2/TD4 integration, complete release qualification and arbitrary third-party
interrupt handlers remain outside these development results.

## Guarded adapter interrupt returns

PI3's loaded panel run exposed a nested-return case in the existing interceptor.
An NMI during the IRQ restore around `sio_start` could recognize the outer Task
stack, DP and unmasked flags while SIO still held `SWITCHING`. It armed the
private COP trampoline inside that protected adapter entry. COP correctly
rejected the context with `$FF11`; the nonreturning fallback parked the active
graphics system at `$FF93`.

The interceptor now excludes near IRQ/NMI returns while another adapter entry
holds `SWITCHING`. The COP's own classified restore can still finish its
transition, and the far selected-return range keeps its existing protocol.
No deferred callback, scheduling decision or new public API is introduced.

The [development record](../development/interrupt-guarded-return.json) includes
a synthetic private Task entry holding the guard across nested real VBIs.
That probe faults with status 4 before the fix. Afterwards it preserves the
guard, delivers exactly one reply after release, clears the return slots and
restores ownership. Selected PLA/COP handoff and quiet-return probes also pass,
including another NMI before the private COP consumes its original PC. The
quiet handoff probe explicitly interrupts ordinary Task code; interrupting a
live guarded COP may now correctly defer instead of reaching that trampoline.

Reserved bank-zero delta is **0 bytes fixed, 0 per public Task and 0 idle**,
including guards, alignment and unused capacity. There is no state, upper-RAM
reservation or VRAM growth; the extra instructions fit the existing native
code reservation. These are focused optimized development checks, not release
qualification.
