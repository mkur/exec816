# Hybrid AES implementation plan

[GEM plans](README.md) · [Hybrid design](hybrid-aes-vdi-design.md) ·
[Current AES contract](../../reference/aes.md) · [Roadmap](../../roadmap.md)

Status: in progress, 2026-10-06. Started from Exec816
`38d5964f563710c6b66b2438b71c60528d03d9af` and the hybrid design note.
[HY1](../../development/aes-hybrid-hy1.json) and
[HY2](../../development/aes-hybrid-hy2.json) and
[HY3](../../development/aes-hybrid-hy3.json) pass development checks.
[HY4](../../development/aes-hybrid-hy4.json) implements the integrated proof and
demo refresh; its latency acceptance remains open. The subsequent
[diagnostic slice](../../development/aes-hybrid-diagnostics.json) adds timing
breakdown and fixed-offer comparisons without changing acceptance workloads.
Keep the compiler, donor and platform pins recorded in
the repository; record any local overrides with the resulting evidence.

Refactor the existing AES call profile onto caller-owned message and timer
waits. Keep registration, GUI lock policy and physical drawing in the existing
presenter. Priorities remain inactive. This is the first deliverable of the
hybrid design, with direct drawing and additional GEM calls following separate
ownership and coverage gates.

The [AS0–AS4 plan](aes-server-implementation-plan.md) and its
[execution record](../../history/aes-server.md) remain the history of the server
implementation. Preserve their evidence, including the failed AS4 latency gate.
Use the [latency follow-up](../../development/aes-server-latency.json) as the
immediate comparison, retaining the original AS0 acceptance limits.

## Deliverable

The existing two C applications must run unchanged at their GEM call sites,
exchange copied messages, wait for events and timers, acquire GUI locks and
retire independently beside the native desktop. Startup attachment may change
internally. Both named wrappers and `aes_call(AESPB *)` use the same operation
implementation and validation.

| Operation after this refactor | Execution |
| --- | --- |
| `appl_init`, `appl_exit` | Presenter RPC plus caller-side resource setup and retirement. |
| `appl_write` | Caller validates and copies into a destination-owned record, then uses Exec `PutMsg`. |
| `evnt_mesag` | Caller consumes its receiving port or blocks on its signal. |
| `evnt_timer` | Caller owns the timer binding, alarm and completion collection. |
| `evnt_multi`, including `evnt_multi_moblk` | Caller matches the existing `MU_MESAG`/`MU_TIMER` subset. |
| `wind_update` | Existing presenter arbitration and native GUI gates. |

Keep four registrations, sixteen messages per registration, sixteen-byte copied
payloads, nonreused GEM IDs, explicit diagnostics and unsupported-opcode/event
failures. No additional AES version or event capability is advertised. Window,
resource, form, callback and VDI workstation coverage is not silently added.

## Executable slices and commits

| Slice | Result | Dependency |
| --- | --- | --- |
| HY1 | Shared endpoint directory, caller-owned receive resources and safe retirement | Current implementation |
| HY2 | Standalone timer waits run in their callers | HY1 |
| HY3 | Atomic migration of application messaging and all message/combined waits; obsolete presenter event engine removed | HY1, HY2 |
| HY4 | Native GUI, lifetime and latency proof; matching OF816 demo package | HY3 |

Commit each passing executable slice separately. HY1 prepares endpoints while
the existing message path remains authoritative; HY2 moves only standalone
timer calls. HY3 switches every producer and consumer of application messages
together. Do not leave `evnt_multi` observing the old FIFO while `evnt_mesag`
consumes the new port, and do not add a compatibility mode or queue-forwarding
bridge. Every intermediate build has one implementation of each public call.

Rebuild the binding, service and fixtures together for each private ABI change.
Update reference documentation only when its executable behavior lands.

## Code ownership

| Area | Work |
| --- | --- |
| Shared layouts | Extend [aes-server.json](../../../abi/aes-server.json) and [generate_aes_server.py](../../../tools/generate_aes_server.py) for the endpoint directory, message records and registration exchange. Keep GEM opcode/count metadata separate from the remaining RPC allowlist. Generate Action!/C declarations and layout probes. |
| Caller binding | Refactor [aes.c](../../../c/calypsi/aes.c) and [aes.h](../../../c/include/exec816/aes.h). Proposed private `c/calypsi/aes-messages.c` and `aes-events.c` hold copied delivery and wait logic; their names are not public ABI. |
| Registration and shutdown | Change [aescore.act](../../../lib/aes/aescore.act), [aesstate.act](../../../lib/aes/aesstate.act), [aeshost.act](../../../lib/aes/aeshost.act) and [aesboot.act](../../../lib/aes/aesboot.act). Keep service-owned IDs, Task leases and controller lifetime. |
| Obsolete event transport | Retire `aesmessages.act`, `aesevents.act` and `aestimer.act` (removed in HY3) from current builds when HY3 replaces their last users. |
| GUI integration | Preserve [aeslocks.act](../../../lib/aes/aeslocks.act), native paint/input gates and `AESHOST.Settle`. Update presenter event/mask/idle hooks to account for the remaining RPC and retirement work. |
| Build and tests | Update `build_bitmap_console.py`, `build_aes_desktop.py`, `test_aes_server.py`, `test_aes_desktop.py`, their emitted fixtures and the host contract checks. Normalize host text before parsing listings. |
| Measurements | Extend [aes_latency_trace.py](../../../tools/aes_latency_trace.py), `measure_aes_calls.py` and `compare_aes_latency.py`; do not fabricate RPC milestones for direct calls. |

GUI policy stays above Exec. Use public messages, signals, I/O and Task leases.
No scheduler change, new COP selector, timed-wait syscall, additional worker or
driver-private kernel operation belongs in HY1–HY4. Fix compiler defects in
actionc with focused regressions rather than adapting AES around them.

## Existing baseline and measurement updates

The baseline is already established. Reuse the recorded workloads, latency
follow-up and original AS0 acceptance limits; no separate baseline slice or
repeat baseline campaign is a prerequisite for HY1.

Update observers alongside the changed call paths in HY2 and HY3. Preserve
existing RPC measurement boundaries for comparisons. Full public-call timing,
including context lookup and validation, is an additional metric: do not compare
it directly with an older interval that begins at RPC submission. Resolve
emitted markers by checked symbols/instructions, not ambiguous C static function
names. Missing markers must fail the observation, not produce zero cost.

## HY1 Prepare endpoint ownership and retirement

Create one generated, bounded endpoint directory owned by the AES service.
Registration returns access to this directory under the existing retained
service lifetime. It must work across distinct C binding instances; a sender
must not look for another application in its image-local `contexts[]` table.

Each registration supplies a caller-owned receiving port and sixteen message
records. Its published endpoint includes the validated owner, GEM/native
identity, port/pool, lifecycle state, publication holds and pool bookkeeping.
Use detached record state explicitly; stale Exec links are not a free-list test.
All direct readers and the service must follow the same Task-side guard for
directory publication, lookup/hold, withdrawal and recycling. No IRQ reads or
changes this directory.

Refactor binding admission so allocation and port creation occur outside long
`Forbid` regions. Reserve/publish table membership in brief guarded steps and
unwind every failed allocation, signal or registration. Keep one-call occupancy
for both direct and RPC operations, including error exits; nested public calls
must not accidentally enter the guard twice. Keep GEM argument/output arrays
private to the caller even as the service packet changes.

Define endpoint states as unpublished, accepting, closing and retired. On exit,
withdraw lookup admission before waiting for active publishers. If holds remain,
the presenter retains an exit request and continues serving other work; the last
publisher signals its retained service owner. A notification arriving before
the service waits must remain observable. Drain queued records only after
publication has quiesced. The caller frees its receiving port/pool only after
the final exit acknowledgement. Preserve nonreuse of identities on reinit.

Keep the old message FIFO as the sole public message implementation in this
slice. New records remain unused by public sends until HY3; their lower-level
publication/collection lifecycle can be exercised by the emitted fixture.

**Acceptance:** raw/optimized Action!/C layout and pointer probes cover every
shared field, including native versus huge pointers. Optimized tests exercise
four registrations, rejected fifth registration, separate binding tables sharing
one directory, rollback, reinit, slot reuse, counter exhaustion and shutdown.
Pause a publisher after acquiring its hold, begin destination exit, then resume
publication: the service must stay responsive and storage must survive until
the final collection. No new general C loader is needed for the isolated-table
fixture. Confirm no leaked ports, signals, pool records or Task leases.

## HY2 Move standalone timer waits to callers

Implement a private caller timer helper with lazy `OpenDevice(UNIT_VBLANK)`,
one query record, one borrowed absolute alarm and a private reply port. Track
idle, outstanding and retiring ownership before submission, since an immediate
completion can precede `SendIO` return. Reuse the existing checked deadline
formula; a C implementation is ordinary timer-library code and must pass the
same conversion vectors as `TIMER.Deadline`, not introduce different rounding.

Route `evnt_timer` and opcode 24 through this helper and remove their server
dispatch and standalone event-decoder branches. Wait via ordinary Exec signals
and collect the exact I/O
completion. Keep the presenter alarm only for still-server-owned `evnt_multi`;
the two paths implement different public operations during this intermediate
slice. Registration and `wind_update` continue through the existing RPC.

Keep request sequencing in RPC submission: only actual service RPC advances
its sequence, still reserving its last value for exit. Direct calls
retain registration/owner and busy checks but do not manufacture service replies.
Close all caller timer resources during `appl_exit` before freeing the context;
if I/O cannot be retired, retain ownership and fail cleanup rather than freeing
live request storage. A timer setup failure must leave message-only calls usable.

Adapt timer tracing in this slice: attribute deadlines and terminal replies to
the exact request and client instead of assuming a single presenter alarm.
Observe public call entry and return, and separate requested duration and VBI
rounding from completion delay. Retain RPC observations for the operations that
still use the presenter.

**Acceptance:** PAL/NTSC, standalone zero delay, full unsigned 32-bit durations,
64-bit carry/overflow, already-due completion, clock failure, request/open
exhaustion and repeated reopen/exit pass through emitted code. Exercise a CPU
peer without voluntary yields and native interrupt completion near Task/Exec
return boundaries. Four client timer opens plus the temporary presenter open
fit the device's eight-open limit; test competing users instead of assuming
capacity. No standalone timer request reaches AES service dispatch.
The observer accounts for each selected timer call and its completion.

## HY3 Migrate messages and combined waits together

Switch `appl_write`, `evnt_mesag`, every supported `evnt_multi` combination,
`evnt_multi_moblk` and their parameter-block entries in one executable change.
Registration and `wind_update` remain the only ordinary service operations
besides exit; both direct and queued calls share the same validation rules.

For `appl_write`, validate the caller and input, acquire a live destination hold
and reserve a pool record, copy sixteen bytes, then `PutMsg` to its private
receiving port. Return success at publication. Do not wait for the recipient or
presenter. Never touch the record after `PutMsg`; another Task may already have
consumed and recycled it. Release the endpoint hold independently. A full pool
returns `AES_RESOURCE` without sleeping for capacity. FIFO order is publication
order, and a single sender's call order is preserved.

Consume records through public `GetMsg`, copy the payload to caller output,
then recycle the detached record under the pool guard. These one-way records
have no sender reply port. Explicit lifecycle ownership replaces a sender
reply; do not use `NT_FREEMSG` or stale links as reclamation evidence.

Use one local matching routine for message-only, timer-only and combined waits:

1. Validate masks and outputs before consuming anything. Reconstruct the full
   millisecond duration and use HY2's clock/deadline helper when required.
   Compute one absolute deadline per call; spurious wakes never restart it.
2. Inspect selected sources before sleeping. Zero-duration `MU_TIMER` is ready
   immediately without an alarm; a queued message can avoid a future alarm.
   Return all selected ready conditions and consume at most one message.
3. If nothing is ready, publish any needed alarm and recheck before `Wait` on
   selected sources. Unselected queued messages remain intact and must not
   cause a timer-only busy loop. Signals are hints; never clear an arrival
   between checking the queue and waiting.
4. Freeze one readiness result. Cancel and collect any still-owned alarm before
   returning; expiry racing cancellation produces one terminal completion.
   Later arrivals remain for the next call. Establish clock/device success
   before consuming a message so failure preserves queued payloads.

Remove the old FIFO, event masks/deadlines, event-matching scans and shared AES
alarm from the service in this same slice. Delete their dispatch branches and
obsolete modules/build inputs; update host tests that currently require those
modules. Keep GEM opcode definitions for direct bindings while rejecting those
opcodes on the private RPC endpoint. Regenerate its current wire layout and
replace old layout expectations rather than preserving an obsolete protocol.

Update `AESHOST.Mask`, `Wake`, `Runnable`, `Idle`, startup and stop together.
Keep notifications for pending endpoint retirement and retain lock settlement;
removing timer/event scans must not strand an exit or `wind_update` waiter.
Rename the service's shared `waiting` field to describe pending lock/retirement
requests explicitly. Preserve the current native/AES control intake bound and
input boundaries; broad presenter tuning is outside this slice.

Extend tracing for direct message and combined-wait entry/return. Classify each
call by its actual execution path; retain submission, admission and reply
markers only for RPC. Update comparison tools without inventing service
milestones or zero-cost replies for direct calls.

**Acceptance:** named and parameter-block calls pass queue-before-wait,
arrival-before/during-wait, self-send, competing senders, FIFO/full recovery,
sender-buffer reuse, malformed masks/pointers and stale identities. Interleave
message-only, timer-only, combined and immediate waits across clients. Check
simultaneous readiness, all cancellation/expiry orderings and timer failure
without message loss. Repeat send-versus-exit, last-publisher-versus-service-wait,
pool exhaustion and shutdown. A bounded fixture must show direct message/event
progress while the presenter is deliberately parked, with no GUI locks held;
this proves independence from its pump rather than relying on source inspection.
The observer accounts for every selected direct or RPC call.

## HY4 Verify the integrated service and package

Run the existing GUI-lock suite against the refactored transport: nested and
try acquisition, eligible FIFO order, owner exit, native paint exclusion,
deferred gestures and resumption without a fresh input edge. Pending GUI locks
must not prevent other clients from exchanging messages or completing timers.
Keep the retained Control Panel and current drawing owner unchanged.

Run the two-client native desktop proof under idle, scroll and disk load,
including repeated attach/exit/restart, a computing peer and clean shutdown.
Retain guards, DP/register checks, OS restoration and selected IRQ/NMI/SIO
coexistence cases. Use a separate four-client capacity fixture; do not enlarge
the standard eight-Task demo merely to combine every test axis.

Compare with the existing latency follow-up using the original AS0 limits,
visible gestures and workload definitions. Report direct call-entry-to-return,
service RPC delays, native timer deadline-to-reply and reply-to-caller delay, presenter CPU,
idle wakes and background/disk progress. Audit that the presenter now has no
message/event/timer service traffic from the migrated calls. Timing success
requires the actual comparison limits to pass; functional success alone does
not accept HY4 or close the successor AS4/TD4 performance gate.

Record completed calls and offered load as well as elapsed time: faster clients
can generate more traffic, so an identical time window alone does not establish
equal load. Keep saturated throughput separate from latency results; add a
fixed-rate exchange cohort if needed, without replacing the original workloads.
Record compiler, ROM, emulator configuration, SIO profile, stack pools and image
hashes. Use the nominal 57.6 kbit/s loaded envelope; the existing 125k timing
limitation remains separate.

Refresh the desktop demo through `tools/build_demo.py`, including OF816, its
five-second autoboot, the matching system disk, pinned ROM, licenses and
checksums. Check the packaged boot image. Keep intermediates and evidence in
the development directory; distribute only the prescribed `exec816-demo.zip`.
This is development verification, not release or physical-hardware qualification.

## Memory and validation records

Every HY1–HY4 slice targets **0 additional reserved bank-zero bytes**: fixed
adapter/kernel, root, per-public-Task and private idle are each zero. Keep the
existing stack/DP pools, guards, alignment and unused reserved capacity. Measure
caller stack use after moving timer and matching code; exceeding the existing
budget requires a revised reservation decision, not disabling checks.

Account for upper RAM at maximum admitted capacity. Four pools of sixteen
records require at least 2,048 bytes for sixteen-byte Exec headers plus
sixteen-byte payloads, compared with 1,024 bytes of old FIFO payloads. Add actual
generated directory/synchronization metadata, padding, ports and heap rounding.
Four pairs of 38-byte timer records require 304 bytes, plus their ports/state;
HY2 temporarily retains the presenter's existing pair until HY3 removes it.
Record peak transition and final allocations as well as live payload sizes.
Include expanded code/data arenas and their unused reserved capacity.
Do not enlarge per-Task DP storage or introduce a hidden callback stack.

Follow the [testing policy](../../contributing/testing.md): host tests and
changed generators' `--check`, focused optimized emitted behavior, and small
raw/optimized probes for shared layout or language-bridge changes. Reuse and
adapt the existing registration/messages/events/locks suites instead of running
the entire qualification matrix after each commit. Replace obsolete shared-alarm
fixtures with caller-alarm tests, preserving their historical evidence.

Store detailed outputs under `build/aes-hybrid/` and compact per-slice records
under `docs/development/aes-hybrid-hyN.json` when executed. Record scope, pins,
memory, measured latency and unresolved gates. Update the current AES contract,
C application guide, history/indexes and roadmap with each completed slice.

## Follow-on work from the hybrid design

After HY4, add caller-local object/resource functions and private workstation
state in separate coverage slices, each with explicit supported opcodes and
two-client state-isolation tests. Resource I/O stays in the caller's DOS context;
native widget extraction alone does not establish the general GEM interfaces.

Direct VDI drawing then needs an executable ownership prototype before its own
implementation plan is finalized: two callers and native painting must share
stable visible clipping, renderer scratch, cursor handling and the single VBXE
engine. Define display-lease delegation, independent completion routing,
sleeping contention and lock ordering; prove progress without a GUI reply while
holding resources the GUI needs. Test interrupted mapping changes, DMA failure,
retirement, pixel correctness and application stack bounds. Preserve logical
`wind_update` gates. Keep physical drawing in the presenter until that proof
passes. Priority scheduling is not a dependency of either follow-on direction.
