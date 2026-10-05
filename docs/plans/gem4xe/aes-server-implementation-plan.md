# AES server implementation plan

[GEM plans](README.md) · [Design note](aes-server-design.md) ·
[Desktop contract](../../reference/desktop.md) · [Roadmap](../../roadmap.md)

Status: in progress, 2026-10-06. AS0a has passed development checks; AS0b–AS4
remain pending. Implementation starts from Exec816
`ab6eb2dec33412fd383b4970cbd23c05e9011e20`, using the
GEM4XE source revision and provenance recorded in the design and
[port inputs](../../../ports/gem4xe/inputs.json).
Current reference contracts remain authoritative until their executable slices
pass. Keep donor analysis, extracted source and adaptations outside GEM4XE.

The [AS0a record](../../development/aes-server-as0a.json) covers the generated
132-byte request, private C contexts, raw/optimized probes with an active native
presenter, and matched baseline observations. The
[binding inventory](../../../ports/gem4xe/aes-binding-inputs.json) pins donor
signatures and parameter counts. No AES endpoint or GEM calls are published yet.
Fixed and per-Task bank-zero reservation deltas are zero. Baseline widget latency
targets remain open; an unchanged heavy-scroll pointer observation also timed
out, while the dedicated widget scroll/disk cohorts passed. These observations
are retained as comparison limits, not new qualification claims.

## Deliverable and dependency boundary

Deliver a GEM-compatible C binding backed by an AES service inside the existing
console/desktop presenter. Two ordinary C Tasks must register, exchange messages,
wait for messages/timers, acquire GUI locks and exit independently while native
desktop work continues. Preserve application call names, argument widths,
parameter-block conventions and event-loop structure. Runtime attachment and
termination belong in the Exec816 startup wrapper.

The first profile is `appl_init`, `appl_exit`, standard 16-byte `appl_write`,
`evnt_mesag`, `evnt_timer`, `evnt_multi` with `MU_MESAG`/`MU_TIMER`, and
`wind_update` update/mouse-control ownership. Publish explicit failure mappings
and supported `global[]` fields. Other event bits and unsupported calls fail;
linking the binding must not advertise a complete AES implementation.

Use the existing [timer.device](../../reference/timer.md),
[C device I/O](../../guides/calypsi-c.md), ordinary messages and `Wait`.
Timer TD0–TD3 and native interrupt replies already have
[development evidence](../../history/interrupt-reply.md). AS2 integrates them;
AS4 supplies the timer TD4 GUI measurements. Do not add a timed-wait kernel
operation, COP signature, timer worker, AES worker or per-client worker.

The nominal 57.6 kbit/s configuration is the initial loaded development envelope.
The 125 kbit/s transport gate remains open, including port-only timing misses.
It does not prevent AS0/AS1 development, and an AES pass does not close it.
Release qualification and hardware compatibility claims remain separate.

Windows, `WM_REDRAW`, visible-rectangle enumeration, independent VDI workstations,
menus, resources, forms, application callbacks, general discovery, C/G4A loading
and forced client recovery follow this foundation. The native Control Panel
remains a retained-widget application; it is not an AES compatibility oracle.

## Sequence and commit boundaries

| Slice | Executable result | Dependency |
| --- | --- | --- |
| AS0a — passed | Generated protocol and emitted C/Action! layout/context probes; matched presenter baseline | Existing desktop and C bridges |
| AS0b | Presenter service admission, shared intake budget, retained discovery handle and rollback | AS0a |
| AS0c | Real C `appl_init`/`appl_exit`, private binding state, re-registration and source-level call profile | AS0b |
| AS1 | Two C clients exchange messages and block independently in message waits | AS0c |
| AS2a | One real timer open, shared alarm lifecycle and presenter wake integration | AS1, implemented timer.device |
| AS2b | GEM timer and combined-event semantics, including failure and race cases | AS2a |
| AS3a | Nested owner-aware lock arbitration and pending acquisitions | AS2b |
| AS3b | Native painting/interaction gates and complete registration/service retirement | AS3a |
| AS4 | Two-client proof under native GUI/SIO load, latency and lifetime evidence | AS3b |

Commit each passing executable slice separately. Keep one current protocol and
update callers/tests together when it changes; do not retain intermediate ABI
profiles. Intermediate builds advertise only their implemented call subset.

## Code ownership and placement

New paths below are proposed names, not existing interfaces. Keep protocol,
client binding, service policy and presenter integration separate.

| Area | Implementation work |
| --- | --- |
| Wire ABI | New `abi/aes-server.json` and `tools/generate_aes_server.py`; generated Action! types under `lib/aes/` and C transport declarations under `c/include/`. Generate sizes, offsets, capacities, operations and statuses. |
| C binding | New `c/calypsi/aes.c` and compatibility headers matching the selected donor include/call surface. Marshal through existing public Exec C calls; no new kernel gateway. Keep Task-local parameter arrays, registration and request ownership explicit. |
| Service policy | New `lib/aes/aescore.act`, `aesmessages.act`, `aestimer.act` and `aeslocks.act`, with generated types and upper-RAM state. Registration, event matching and locks remain service policy. |
| Service lifecycle | New `lib/aes/aeshost.act` / `aesboot.act` for presenter-owned setup, masks, runnable/idle checks, retained launch handle, shutdown and rollback. Follow the ownership pattern in [deskboot.act](../../../lib/desktop/deskboot.act). |
| Presenter pump | [consoledriver.act](../../../lib/console/consoledriver.act), [deskhost.act](../../../lib/desktop/deskhost.act) and [deskcore.act](../../../lib/desktop/deskcore.act): share intake budget, service timer replies, include AES work in sleep/stop decisions. |
| Native GUI gates | [deskpaint.act](../../../lib/desktop/deskpaint.act), [deskinput.act](../../../lib/desktop/deskinput.act), [deskwidgetinput.act](../../../lib/desktop/deskwidgetinput.act), move/cache and console drawing paths: enforce application lock ownership at bounded completion boundaries. |
| Build and provenance | Extend [library_paths.py](../../../tools/library_paths.py), [native_program.py](../../../tools/native_program.py), [calypsi_build.py](../../../tools/calypsi_build.py) and [build_bitmap_console.py](../../../tools/build_bitmap_console.py) for the new modules, C sources and explicitly admitted client entries. Reuse checked foreign-image packaging. |
| Tests and evidence | New `tools/test_aes_server.py`, C/Action! fixtures under `tests/programs/`, and small host ABI/contract checks. Detailed outputs under `build/aes-server/`; compact records under `docs/development/aes-server-asN.json`. |

The existing `ports/gem4xe/aes/` owns the extracted widget implementation. Do not
silently replace or repurpose its extraction manifest. If binding declarations
or code are copied from GEM4XE, record exact source hashes and adaptations in
a separate selection/patch record, preserving upstream notices. Follow
[LICENSING.md](../../../LICENSING.md) for new native interfaces; an MIT interface
directory does not relicense donor code. No FreeMiNT/XaAES implementation is
imported by this plan.

## AS0 — Binding, registration and presenter integration

### AS0a: Freeze the wire and measure the starting point

1. Inventory the selected donor prototypes, AES parameter counts, word
   signedness and `global[]` fields. Record which conventions are preserved and
   which calls fail. Reconstruct GEM's timer words as an unsigned 32-bit value.
2. Define a bounded packet with the native Exec Message header, version/size,
   operation, client identity, sequence, scalar inputs, inline outputs/status
   and space for one standard message. Registration identifies the owner,
   original binding storage and reply port. Generate all wire constants.
3. Separate 16-bit GEM IDs from native internal identities. Reserve zero for
   the service, return `-1` for failed init, reject exhaustion before wrap and
   never recycle a GEM ID during one service lifetime. Define malformed-call,
   unsupported-call, resource and timer diagnostics separately from GEM results.
4. Give each caller private parameter arrays, output state, request and reply
   port. For the resident two-Task fixture, use a bounded runtime binding table
   keyed by the live owning Task, with separately allocated per-Task contexts.
   Protect table admission/removal with ordinary Task coordination; never hold
   that protection while waiting for a reply. Do not use a shared donor global
   parameter block or assume compiler TLS. Runtime attachment supplies the
   retained service handle before application entry; public GEM calls resolve
   their own Task's context.
5. Extend the existing C image builder to admit both named client entries and
   compose their binding with the desktop drawing image. Preserve the existing
   layout/overlap checks and C DP partition. A separate standalone message
   example is not proof that this composition works.
6. Record native desktop input/feedback, idle wakeups, pump costs and stack
   high-water marks before enabling AES. Pin compiler, donor, ROM, emulator,
   memory map, CPU configuration and SIO profile. Freeze comparison scenarios
   and tolerances from baseline variability before evaluating AS4 results.

**Acceptance:** generated-output checks and small raw/optimized emitted probes
agree on every shared size/offset, 16-bit word and native/C pointer conversion.
Reject out-of-range pointers without truncation. Exercise bank-crossing packet
access, complete native register restoration and interleaved C Tasks with
different parameter sentinels. Record the actual Task/stack assignment and
upper-RAM layout before service publication. Source fixtures use ordinary GEM
function signatures; startup hooks are separate from their application loops.

### AS0b: Admit a service without changing display ownership

Allocate AES state and its request-port signal in the existing presenter.
Publish readiness only after initialization succeeds; root retains the service
allocation through all client detachments. A failed AES setup unwinds AES
resources while leaving native desktop service available. Plain console builds
do not create an AES endpoint or timer open.

`DESKCORE.Pump` currently admits up to four native requests on every call.
Refactor the internal pump boundary to accept a remaining intake budget, and
use **four admissions total per presenter turn** across native/AES ports,
rotating the starting port. Update all internal callers/tests together. Do not
add an independent four-request AES loop. Count requests moved to pending or
deferred lists against the admission budget; revisit pending state separately
within the four-client bound.

Extend request masks, queued-work checks, local-runnable checks and shutdown
eligibility together. Pending event waits or lock acquisitions alone do not
keep the presenter runnable. Exhausted budgets with immediately serviceable
work do. Drain owned queues before `Wait`, retain coalesced signals, and never
clear a signal between the final empty check and sleeping. The presenter calls
its service routines directly, never its synchronous public binding.

**Acceptance:** emitted presenter tests cover startup failure at each acquired
resource, request arrival around the final wait check, both ports continuously
busy, budget exhaustion, rotation and idle with no clients. Native drawing,
input and stop continue to work. The service refuses shutdown while clients or
unsettled requests retain it; no new Task, display lease or periodic wake appears.

### AS0c: Complete the registration round trip

Implement real C `appl_init` and `appl_exit` through the presenter. On admission,
validate storage/owner/port relationships, retain the owning Task and create the
registration only after all required resources exist. A repeated init on a
live binding returns its existing ID. Check subsequent request identity,
sequence and one-call occupancy before changing state.

The binding drains its private reply queue, waits through ordinary Exec calls,
collects exactly once, checks the reply and then copies outputs. Publish replies
only after detaching service references. For the final exit reply, use the
design's short `Forbid` publication/release/record-retirement protocol so the
caller cannot remove itself before the service lease is released. The runtime
exit wrapper performs `appl_exit` before ordinary C Task/image retirement.

**Acceptance:** actual C init/exit/reinit, distinct interleaved callers, fifth
registration rejection, stale IDs/sequences, wrong owner/port, unsupported calls,
admission failure rollback and reply-before-submit-return pass. Verify four
registrations with a bounded capacity fixture, separately from the full GUI
load. Force identity exhaustion through diagnostic setup rather than billions
of calls. Collect the exit reply before freeing the private port/context; repeat
Task-slot reuse and prove no leaked signals, leases or allocations.

## AS1 — Messages and independent message waits

Implement sixteen-entry FIFO queues of eight GEM words per registration.
`appl_write` copies exactly 16 bytes after length/destination validation; success
means accepted into the destination queue. Reject a full queue without replacing
an older message or parking the sender. Pointer-sized or borrowed application
payloads are not supported.

`evnt_mesag` consumes an existing message or retains the client's one ordinary
request as a pending wait. Incoming messages reevaluate it without blocking the
presenter. Remove the wait, copy output words and detach the descriptor before
reply. An accepted message for a destination that subsequently exits may be
discarded during that destination's retirement.

**Acceptance:** two C event loops pass queue-before-wait, wait-before-send,
self-send, FIFO, full-queue failure/recovery, invalid lengths/IDs, immediate reply
and independent progress while the other client waits. Modify the sender's
buffer after its send reply to prove the receiver sees the accepted copy.
Native request/input service remains responsive during sustained messaging.
Keep test peer-ID exchange in the startup fixture; do not invent `appl_find`.

## AS2 — Consume timer.device in GEM event waits

### AS2a: One open and one reusable alarm

Add the design's presenter-owned timer resources before advertising timer calls:
one dedicated `PA_SIGNAL` reply port, an original 38-byte clock-query open on
`UNIT_VBLANK`, and one 38-byte alarm record borrowing its binding and port.
`TD_READCLOCK` uses the immediate QUICK `DoIO` path. Future alarms use
`SendIO(TD_WAITUNTIL)`, never a blocking future `DoIO`.

Track idle, outstanding and retiring alarm ownership plus the submitted target.
Mark ownership before SendIO; due targets and immediate errors still reply.
Drain the timer port as a completion queue, with pointer/status checks. On a
changed earliest target, abort once if necessary, collect, recompute live
deadlines and only then reuse the record. An unchanged target does not rearm.
Normal expiry can beat AbortIO; both success and the expected aborted result
retire that submission exactly once. CheckIO alone never returns ownership.

Include the timer signal and retiring-alarm state in both wait and stop paths.
Do not spin, blindly WaitIO or suppress native input while retiring an alarm.
Sample the clock when evaluating timed waits and complete already-due clients
without waiting for another tick. Before sleeping, future deadlines must have
an outstanding alarm or a retiring alarm with a guaranteed collection wake.

**Acceptance:** use the real device, not a synthetic timer source. Cover earlier,
later and equal target changes; four clients sharing one alarm; last-deadline
removal; expiry before submission returns; expiry during abort; a stale/coalesced
signal; and native input during retirement. Inject clock/open/queue failures and
check every rollback path. No failed submission may leave a waiter without a
wake source. An unrelated message must not be collected as the alarm.

### AS2b: GEM event semantics and failures

Convert each unsigned 32-bit duration once with `TIMER.Deadline`, retaining the
absolute high/low deadline per client. Use reported PAL/NTSC rate and checked
64-bit arithmetic. Replacing the shared alarm preserves all client deadlines.
`evnt_timer(0)` records `now+1`; zero-duration `MU_TIMER` is immediately ready
without an alarm. Reject unsupported `evnt_multi` bits as a whole.

At an event-completion decision, use the queued messages and a coherent current
clock sample to return every selected ready condition, with at most one message
and exactly one AES reply. An old alarm completion after a message won only
retires device ownership. It cannot generate a second AES reply or turn
`IOERR_ABORTED` into a timer event.

On timer failure, return the design's zero GEM result plus a binding diagnostic,
without consuming a message or fabricating `MU_TIMER`. A clock failure affects
all pending timed calls; an alarm failure affects all waits depending on that
wake source. Continue message-only/native service and retire device ownership.
No busy retries or conversion of old deadlines into fresh relative waits.

**Acceptance:** real C timer-only, message-only and combined waits pass with no
input traffic. Cover both zero forms, simultaneous readiness, multiple equal
deadlines, long descheduling, the full 32-bit millisecond range, low-word carry,
overflow and device/clock errors. Use controlled test clock boundaries for long
intervals, plus real VBI for progress; never wait days to test large durations.
Prove a CPU-only peer does not prevent expiry or client resumption, and a
pending timer introduces no frame delay into unrelated AES/native replies.

## AS3 — GUI locks, painting and retirement

### AS3a: Owner-aware locks without blocking the pump

Represent update ownership, update-associated mouse holds and explicit mouse
holds separately. `BEG_UPDATE` must obtain its update and mouse ownership
atomically; `BEG_MCTRL` obtains an explicit mouse hold. Implement recursive
ownership, checked nesting, exact matching release and `0x100` check-and-set.
Require registration before lock calls.

A normal contended acquire retains the caller's ordinary request in an
arrival-ordered pending set. It consumes no presenter stack continuation.
Grant eligible callers fairly; allow an existing owner to recurse without
waiting behind a dependent peer. A failed try-acquire creates no partial hold.
Do not use kernel Forbid as the application GUI lock or revoke ownership after
an arbitrary timeout.

**Acceptance:** contention, recursion, mixed explicit/implicit mouse nesting,
overflow, wrong-owner release, underflow, all-or-nothing try acquisition and
pending-order cases pass. The owner's release remains admissible while another
client waits. Message/timer replies and disk progress continue under either lock.

### AS3b: Enforce ownership across the native GUI

Audit every conflicting painting/focus/geometry path: desktop controls and move
continuations, console presentation/scroll, widget press/focus/feedback,
background repair and cache capture/restore. Route admission through one
presenter-owned lock decision. Retain deferred damage and controls until eligible;
do not discard them or leave the worker spinning over blocked paint.

Before granting an acquisition, finish previously admitted conflicting drawing
and retire its hardware/scene token. Keep later conflicting work behind the
pending grant so a stream of native paint cannot starve it. Once granted, do not
hold a Layers token while waiting for application code. Continue bounded input
capture, device completion and the existing serialized cursor path; mouse locks
defer conflicting desktop/widget gestures rather than bypassing ownership.
On unlock or owner exit, resume retained work without needing another input edge.

Complete `appl_exit` cleanup: mark closing, reject new sends, remove queue/wait
state, update the shared alarm, release every owned lock and make waiters
eligible before final registration retirement. The ordinary synchronous caller
has already collected its previous call; no new cancellation lane is required.
Normal service shutdown remains BUSY with registrations. With none left, retire
and collect the alarm, close the original open, detach borrowed handles and free
the empty timer/AES ports before allowing the presenter to stop. Never withdraw
the only notification path while a request remains outstanding.

**Acceptance:** locks defer actual native pixels and focus/geometry changes,
including Control Panel feedback and console scrolling, while input capture,
messages, timers and disk I/O progress. Observe no live Layers token across an
application wait. Exercise exit with nested locks and blocked peers, both client
retirement orders, shutdown during alarm retirement and failure after every
acquired resource. Repeat init/exit and Task-slot reuse; compare allocator,
signal, lease, queue and driver ownership against the initial baseline.

## AS4 — Integrated proof and latency gate

Build two bounded resident C applications whose bodies use the ordinary GEM
calls and event loops from the supported profile. Startup supplies service/peer
handles and owns termination wrappers. Run them beside the native desktop and
Control Panel, with console output and selected real 57.6k disk traffic. Add a
CPU-only phase, an update-lock phase and repeated client restart. Explicitly
record which Task performs disk work; a raw C Task does not acquire a DOS Process
context merely by calling CreateTask.

Measure matching optimized configurations with AES disabled, enabled but idle,
and under load. Record submit-to-service, service-to-reply, reply-to-client,
clock deadline-to-device reply, device reply-to-AES reply and input-to-first-pixel /
complete-feedback. Distinguish VBI rounding from queue/scheduling/rendering delay.
Record distributions, maxima, stack peaks, work per turn and idle wake counts.
Use passive observation where available and replay the identical image without
observation for functional checks. Diagnostic stalls prove races, not latency.

**Acceptance:** no lost/double reply, stale ownership, starvation, port/lease leak,
guard damage or new 57.6k transport failure. No deliberate extra-frame wait or
periodic presenter polling. Unexpected latency growth beyond the AS0 comparison
tolerances blocks the affected slice until explained and resolved; throughput
or VRAM savings cannot substitute for responsiveness. A GUI lock may delay
conflicting paint, but must not stop independent messages/timers or disk service.
Existing open widget latency targets and the 125k gate remain explicitly open
unless separate evidence closes them.

This passes the AES foundation and timer TD4 integration only. A conventional
two-window GEM application performing its own `WM_REDRAW`/VDI painting is the
next compatibility milestone, not an implied result of these fixtures.

## Task, signal and memory budgets

Use the existing eight-Task map and generated stack bounds. The loaded proof
targets this live set; AS0 verifies actual placement, including prepared Process
reservations, before AS4 relies on it:

| Role | Existing pool use |
| --- | --- |
| Root/controller | One root pool; owns the scene launch handle and selected DOS work. |
| Console/desktop/AES presenter | One 2,560-byte worker pool; one shared rendering owner. |
| SIO and filesystem workers | Two ordinary worker pools. |
| Native Control Panel | One ordinary worker pool. |
| Two C AES clients | Two ordinary 1,024-byte worker pools, subject to emitted stack checks. |
| Foreground command, when tested | The remaining larger worker pool; at most one additional live Task. |

That target uses seven persistent public Tasks and at most eight with the
selected command. It does not promise capacity for an extra prime Task, pipeline
or four simultaneous AES applications under the same load. Prove both C clients
fit ordinary pools before AS1; if they do not, revise the fixture and report
the limitation rather than silently consuming the command pool or adding stacks.
Test four-client registration capacity in a separate bounded configuration.

All new state, bindings, parameter arrays, queues and packets belong in upper
RAM. Reuse the presenter's existing stack and C DP workspace. Target **0 additional
fixed bank-zero bytes and 0 additional bytes per Task** for every slice, counting
guards, alignment and unused reserved capacity. The existing timer foundation's
10,240-byte upper Task-bank suballocation is already reserved and is not charged
again as new AES storage.

| New AES payload subtotal | Bytes |
| --- | ---: |
| Four queues × sixteen messages × sixteen bytes | 1,024 |
| Four absolute 64-bit deadlines | 32 |
| Two timer clock/alarm records × 38 bytes | 76 |
| Known payload subtotal | 1,132 |

This is not a total service budget. AS0 records complete generated service and
binding sizes, private C arrays, request/port headers, alarm/lock metadata,
allocation overhead, code placement, alignment and reserved spare capacity.
The presenter adds two allocated signals when timers are enabled: AES intake
and timer replies. Each live AES binding adds its own reply-port signal on its
Task. No per-client timer signal or new scene/window capacity is reserved.
Measure presenter, C client, kernel and IRQ/NMI stack use together; earlier
standalone timer high-water marks do not establish the combined stack bound.

## Validation, evidence and completion

Follow the [two-tier testing policy](../../contributing/testing.md). Run host
checks and affected generators for code slices. Use small raw/optimized probes
for new layouts, C/Action! boundaries and compiler defects; use optimized builds
for functional, concurrency, pixel and latency scenarios. Reuse unchanged timer
evidence and rerun affected foundation tests only when integration changes their
inputs or exposes an unresolved concern. Compiler defects belong in actionc.

The proposed `tools/test_aes_server.py` should select `registration`, `messages`,
`timers`, `locks`, `lifecycle` and `integrated` suites and individual cases. Save
build hashes and runtime observations separately from compact reviewed records.
Use existing runners where they test the changed boundary:

| Existing runner | Focused reuse |
| --- | --- |
| [test_calypsi.py](../../../tools/test_calypsi.py) | Public Exec C context and Task entry conventions. |
| [test_timer_device.py](../../../tools/test_timer_device.py), [test_interrupt_reply.py](../../../tools/test_interrupt_reply.py) | Only affected device/return-path regressions if those implementations change. |
| [test_desktop.py](../../../tools/test_desktop.py), [test_desktop_apps.py](../../../tools/test_desktop_apps.py) | Native protocol, independent clients and retirement after shared pump changes. |
| [test_desktop_startup.py](../../../tools/test_desktop_startup.py), [test_desktop_fault.py](../../../tools/test_desktop_fault.py) | Admission/rollback, completion and shutdown integration. |
| [test_desktop_presentation.py](../../../tools/test_desktop_presentation.py), [test_widgets.py](../../../tools/test_widgets.py) | Existing pixel and widget behavior across new lock gates. |
| [measure_desktop.py](../../../tools/measure_desktop.py), [measure_desktop_echo.py](../../../tools/measure_desktop_echo.py) | Matched native latency baselines and input/console regression measurements. |

Each AS record includes exact sources, generated ABI, compiler/ROM/emulator pins,
Task placement, complete memory deltas, actual case scope, measured timings and
remaining gates. Keep large images/traces in ignored development directories;
retain compact evidence in the repository. Do not overwrite older qualification
records or mark an intermediate fixture as full GUI compatibility.

After AS4, add a current `docs/reference/aes-server.md` call/ownership contract,
a C usage guide and a history page with evidence; update their indexes, this
plan, the design status and roadmap. Publish only behavior actually tested.
Any demo refresh uses [build_demo.py](../../../tools/build_demo.py), includes
OF816 and the matching disk/ROM/notices, preserves the five-second standard
shell/prime autoboot, and smoke-tests the exact package. Keep the AES proof as
an explicit optional fixture until deliberately integrated into the demo.

For this plan-only change, reserved bank-zero delta is **0 fixed bytes and
0 bytes per Task**. Validation is content and link checking; no new executable,
performance or qualification result is claimed.
