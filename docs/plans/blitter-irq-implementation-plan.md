# Blitter completion IRQ implementation plan

[Implementation plans](README.md) · [Console contract](../reference/console.md) ·
[Display contract](../reference/display.md) · [Signals](../reference/signals.md)

Status: BI0 and BI1 complete with [baseline](../development/blitter-irq-bi0.json) and
[IRQ delivery evidence](../development/blitter-irq-bi1.json); BI2–BI5 pending,
3 October 2026. Replace the bitmap console's repeated scroll
polling with a VBXE completion interrupt that signals its existing worker.
Keep one copy/fill list in flight, continue input and READ service, and sleep
when all remaining work depends on that list. Implement and commit each
executable slice with its focused development evidence before proceeding.

The goal is less CPU work and earlier completion observation. IRQ delivery does
not accelerate the VRAM copy or guarantee immediate scheduling. Keep the
character model, scroll geometry, synchronous text renderer, Task priorities and
request completion semantics unchanged. Circular character rows and a queue of
hardware lists are separate work.

## Starting point and hardware support

The [current measurements](../history/console-responsiveness.md) report isolated
scrolls of 30.77 and 33.19 ms. Their launch-to-confirmed-idle spans are upper
bounds that include observation and scheduling. Exact BUSY edges are unmeasured.
The earlier [synchronous rectangle benchmark](../history/whole-rectangle-scroll-benchmark.md)
also observed about 13.9 ms from launch to idle. Do not attribute the entire
interval to polling or set a one-millisecond full-screen copy target.

The current path is `CONSOLEDISPLAY.Advance` through `CONSOLEBITMAP.Scroll`,
`GemDrawingScrollStart` and `VbxeOwnerScrollStart`. The worker then calls Poll
once per pending turn and yields. Further model writes and all hardware drawing
remain gated, including caret and presentation controls. `BitmapComplete`
adopts only matching unit/view/model generations and retains completion while
the registry entry is PRESENTING.

VBXE provides a completion IRQ for the whole blit list. On the pinned `$D600`
configuration, `$D654` reads IRQ status; bit 0 indicates completion. Writes
control enable bit 0 and acknowledge any pending interrupt, including a write
of zero. `$D653 & 3` distinguishes idle from execution or command loading.
See the [Altirra hardware reference](https://www.virtualdub.org/downloads/Altirra%20Hardware%20Reference%20Manual.pdf),
VBXE register descriptions. The driver currently writes zero to IRQ_CONTROL.
Keep that inactive cold-boot requirement; enable the source only after binding
and launch preparation, and restore it on release.

## Ownership and interfaces

Use the classic Exec pattern: the driver owns the operation and its durable
result; an interrupt posts a signal indicating work. A signal can coalesce and
is not the completion record. The worker owns final adoption and recovery.

Extend the existing public `EXECPRODUCER.Bind/Release/Drain` framework with a
fixed `VBXE_BLITTER` source, proposed value 4. Generate the constant from
`abi/tasks.json` for all bindings. Update source dispatch, controller/recipient
retention and signal-free protection together; current loops end at
`POINTER_INPUT`. Use the existing `signal_post_binding` implementation. Do not
introduce a VBXE-specific kernel selector, kernel drawing policy, callback
registry or second worker. Fixed source activation remains driver/platform
code, as with keyboard and pointer producers.

The source can be bound only for the current retained VBXE display owner.
Binding does not grant display access. A live binding protects its controller,
recipient and allocated bit until Release and Drain complete. Place the fixed
binding and driver mailbox in generated upper-RAM storage. The IRQ must never
follow a caller's C stack packet, mutable console instance or VRAM aperture.

At display initialization allocate one owner signal, then establish the producer
and timeout resource. Roll back cleanly if any step fails. The console must
reserve its existing request/input/stop bits 31/30/29 before the display obtains
an arbitrary free bit, so initialization cannot collide with resident stop
registration. Standalone drawing owners use the same allocation contract.

Add an owner-checked ordinary driver query, provisionally
`VbxeCompletionMask(display)`, and its GEM drawing equivalent. A live successful
open supplies a nonzero mask owned by the driver; clients include it in their
Wait mask and never free it. Return the mask to the native console through the
checked bitmap packet at open, rather than querying it on each turn. Define
failure behavior and check emitted C/native layouts. Update the packet version,
size validation and every caller together if its layout changes. Private native
bridge helpers may arm/snapshot the driver's mailbox through ordinary calls;
they are not new kernel services or authorization cached across yields.

Keep `ScrollStart`, `ScrollPoll` and Fence semantics: Start accepts one operation
or rejects BUSY without changing the list or ID; Poll is a nonblocking status
query; Fence finishes pending work before dependent access. Synchronous drawing
keeps IRQ generation disabled and its existing bounded fences. Poll remains
useful to ordinary callers, but the console stops invoking it on every turn.
Give the native backend sole responsibility for IRQ_CONTROL and its software
shadow, including writes from the interrupt handler. Route C launch/close and
fault cleanup through that backend so a stale C shadow cannot re-enable a
retired source. Keep IRQ-disabled synchronous launches from producing worker
notifications; acknowledge their latched status before arming a later scroll.

## Launch and completion protocol

Use a driver state machine with IDLE, ARMED, DONE and EXPIRED states. Retain the
nonreused scroll ID and display/binding generation. DONE/EXPIRED remain durable
until consumed by the owner; IRQ completion does not release the command arena
or clear the console's pending flag.

1. In Task context validate ownership and the complete operation, construct and
   upload the list, and restore MEMAC. Reject unexpected hardware activity
   through the existing recovery path. No list upload occurs while another
   operation owns the arena.
2. Retire old notification state only while the old producer is quiescent.
   With a short IRQ-masked publication sequence, disable/acknowledge stale VBXE
   status, publish ID/generation/deadline, arm the independent watchdog, and
   publish ARMED last. Enable completion IRQ and start the list before restoring
   the incoming interrupt state. No upload, allocation, COP or wait belongs in
   this masked sequence. NMI may record ticks but cannot consume half-published
   driver state or switch a protected transition.
3. A recognized IRQ checks the owned source and hardware idle condition,
   acknowledges/disables the completion IRQ, commits DONE for the armed ID,
   cancels its timeout demand, then posts the bound signal. It performs no C
   call, drawing, registry traversal, allocation or ordinary Task gateway call.
   A stale/duplicate IRQ cannot complete a later operation. A premature status
   must not authorize reuse while BUSY/BCB_LOAD is nonzero; keep the watchdog and
   resolve it through the documented fault path.
4. After a notification, the owner takes a coherent snapshot, verifies the ID
   and final idle state, and retires the operation. The existing
   `BitmapComplete` generation checks and PRESENTING deferral then run in Task
   context. A final fence can also retire an already completed operation; a
   later stale signal must be harmless.

Document the exact masking and publish/consume order in the new native helper.
Multi-byte IDs and masks need coherent publication, not ordinary unsynchronized
reads. Preserve D, DBR, full native registers, stack guards and the existing
SWITCHING/IRQ-depth/OS_BUSY protocol. `Forbid` alone is insufficient.

## Shared IRQ routing

Add the owned VBXE source to both native and emulation-mode IRQ routes. The
native `signal_route` currently delegates to `sio_route` when serial ownership
is active; adding a check only on its fallback path would miss completion during
disk activity. Preserve bounded service of simultaneous serial, timer, keyboard
and VBXE sources, and chain genuinely unowned sources to the original handler.
Recheck time-critical serial work around signal publication where needed, using
measured limits rather than an unbounded drain loop.

A VBXE-only interrupt does not invoke a POKEY callback. Install a bounded,
chainable emulation IRQ entry for the pinned ROM and restore it at final
release. Preserve the page-one frame and existing ROM/SIO callback conventions;
never suspend a live OS or interrupt activation. Post through the existing
deferred-wake machinery and switch only at an eligible native boundary. IRQ
support during both CPU modes is required before the console may sleep on it.

## Independent timeout wake

`Wait` has no timeout. Hardware completion alone therefore cannot preserve the
existing sixteen-VBI-tick fault bound. Provide an independent driver watchdog
before replacing the pending Yield loop.

Use the existing shared POKEY timer 1 service as a third fixed user. Keep its
divisor, SIO alarms and ST sampling unchanged. The VBXE owner retains timer
ownership while open; its timer demand exists only while a scroll is ARMED.
At each existing timer service, perform only a bounded armed/deadline check
against the original wrapping VBI start tick. Do not poll blitter BUSY on every
timer edge. Once sixteen ticks expire, commit EXPIRED once, disable/acknowledge
the blitter IRQ, retire timeout demand and post the same completion signal.
Ensure simultaneous timeout and completion produce one terminal mailbox result.

Task-context recovery then checks BUSY. If the engine is already idle, retire
the valid operation and record the missing notification in diagnostic evidence.
Otherwise use the existing STOP and bounded idle recovery. Failure to prove
quiescence retains ownership/storage and enters reset-required park. IRQ and
timer handlers never run that recovery loop.

The watchdog must work with no disk activity, no pointer owner and no keyboard
events, including tick wrap and emulation-mode OS work. Measure its total cost:
moving expensive polling into frequent timer interrupts would defeat this plan.
Measure both a timer already running for ST input and a timer activated solely
for this watchdog, including coherent VBI-counter reads across NMI rollover.
Keep the current timer/audio ownership baseline and restore it when the final
timer user releases. If its cost fails existing SIO/input bounds, revise this
slice before enabling sleeping; never substitute an unbounded hardware-only wait.

## Worker scheduling

Merge the display notification into Collect and the worker Wait mask alongside
input, requests and stop. Preserve bits already consumed by Wait. Clear only
the worker-owned notification bits at the start of the turn, before checking
their durable state; never clear a completion wake after the final empty check.
Query scroll completion on a display notification or an explicit lifecycle
drain, not once per input or output turn. Keep `bitmapReady` adoption runnable
until a matching presentation transaction permits it.

While pending, continue bounded input processing, request admission and READ
replies. Keep model writes, echo, caret and all screen mutations deferred.
Distinguish actionable work from queued work blocked by the blit: a queued
WRITE or deferred focus operation must not keep the worker yielding forever.
When no actionable work remains, Wait on input/request/stop/display signals.
A newly queued request may cause one admission turn and then sleep again.

Completion before Start returns, before Wait, or during Wait is retained by the
mailbox and the ordinary signal protocol. No instance pointer survives a
worker borrow across Wait/Yield. Stop still drains an in-flight list even after
the last WRITE has been replied. Cancellation retains accepted bytes and the
existing exactly-once request replies.

## Teardown and storage

On normal close, complete or recover the active operation first. Disable and
acknowledge VBXE IRQs, cancel timeout demand, Release the producer, Drain queued
wakes, then free its signal and release retained identities/storage. Restore
owned vectors and timer participation before display ownership returns to the
OS. Apply the same ordering to initialization rollback and forced launcher
cleanup. Generic producer Release stops notifications; it must not implicitly
free graphics storage or declare DMA complete. Driver quiescence remains a
separate precondition for display release.

Keep one mailbox and binding in upper RAM with generated offsets and checks.
Reuse existing Task pools and the 4 KiB command arena. Target **zero additional
reserved bank-zero bytes**, including any emulation-vector shim fitted into an
existing segment. Verify actual segment headroom rather than assuming it.
Each slice reports fixed, root/kernel, per-Task and idle reservation deltas,
including guards, alignment and unused capacity, plus upper-RAM payload and
interrupt stack peaks. If a reservation must grow, justify and record it before
adopting the layout. No extra Task, DP or Task stack is planned.

## Executable slices

All slices use the pinned compiler from `toolchain/actionc.json` and the recorded
PAL 65C816 x8, 4 MiB, AltirraOS/VBXE FX 1.26 configuration. Record exact ROM,
emulator, configuration and image hashes and any observer-only changes.

| Slice | Executable result and main files | Development exit check |
| --- | --- | --- |
| BI0 Measure the current path | Extend `tools/bitmap_console_performance.py`, `tools/console_turn_profile.py` and focused scroll tooling to separate launch, hardware completion, IRQ entry, signal publication, Task resumption and adoption. First record the unchanged polling baseline. | Independent final-pixel oracle; idle and loaded baseline. Observe actual emulator BUSY transitions when supported; otherwise label IRQ-entry timestamps as upper bounds. Validate any observer-only emulator extension with unchanged timing and unobserved replay. |
| BI1 Route the completion producer | Add the generated producer source, lifetime coverage and upper-RAM binding/mailbox; add bounded native/emulation VBXE routing and an ordinary driver bridge. Relevant paths include `abi/tasks.json`, `lib/exec/task-wakes.inc`, `platform/altirraos/signal-irq.s`, `hosted.s` and `sio.s`. Keep production scroll scheduling unchanged. | Small emitted real copy/fill fixture receives exactly one completion; native and emulation contexts, source-only and simultaneous POKEY IRQs, foreign bind/release and signal/Task retention. Restore the OS and unrelated vectors. |
| BI2 Arm operations and bounded timeout | Integrate ID/generation publication, completion consumption and the shared-timer watchdog into `platform/altirraos/vbxe.c` and native helpers. Extend generated timer state/demand and update the C/native interface together. Add the completion-mask query. | Completion before return, stale status, tick wrap, missing IRQ, stuck BUSY and STOP failure. Prove a silent system receives a watchdog wake. Existing synchronous callers and second-start BUSY behavior remain correct. |
| BI3 Make the console wait | Update `lib/console/consoledriver.act`, `consolebitmap.act`, `console-bitmap-display.inc`, shared drawing bridge and packet generator. Reserve signals in a safe order and distinguish runnable input/read work from blocked output/control work. | Sleep while blitter is active, wake on input and completion, deliver READ during BUSY, preserve echo ordering and PRESENTING completion. Queued WRITEs/control requests do not cause a poll/yield loop. |
| BI4 Cover races and lifetime | Extend signal, display, bitmap fault/focus and shutdown fixtures at publication, Wait and close boundaries. Include standalone GEM owners as well as the console. | Raw/optimized emitted race and fault cases, simultaneous completion/timeout/stop, cancellation, failed initialization, close/reopen and recipient reuse. No stale completion, lost wake, premature arena reuse or leaked timer/binding/vector. |
| BI5 Measure and document | Repeat isolated and loaded input phases with `tools/measure_async_scroll.py`, the scroll fixture and turn profiler; record portable results and update current display/console/signals/platform contracts and history index. | Same-image unobserved replays, exact pixels, input ordering, guards, physical SIO and ST deadlines. Report IRQ/watchdog cost, completion latency and remaining targets without treating development checks as release qualification. |

BI1 can use test-only launch helpers; BI2 replaces them with the production
operation protocol. BI3 depends on both IRQ routing modes and the watchdog.
Keep one final API and implementation; remove temporary fixture substitutions
when their production equivalent exists. Commit each slice after its selected
checks pass. This plan itself changes no executable code or memory reservation.

## Acceptance and required races

| Boundary | Required result |
| --- | --- |
| Completion during launch or before the caller receives its ID | Published identity and durable result survive; Start still returns the accepted ID. |
| Completion around Collect, final empty observation or Wait | Signal is consumed now or remains pending; no rescue key/request is required. |
| Input, completion and stop arrive together | Preserve every reason, service bounded input and retire DMA before shutdown. |
| Repeated/coalesced/spurious notifications | Recheck durable state; no duplicate retirement or completion of a new ID. |
| Hardware completes while the owner is off CPU, in Forbid or inside OS work | Acknowledge the source, retain its result and defer Task switching safely. |
| Binding release and later reuse, including failed startup | Old IRQ/timer/wake state cannot target a new owner or recycled bit. |
| Focus publication, hide, destruction, cancellation and final WRITE reply | Preserve retained completion and generation rules; never release live DMA storage. |
| Lost completion IRQ, expired deadline and late IRQ | Independent wake reaches recovery; one terminal result; STOP cannot masquerade as normal completion. |
| Simultaneous VBXE, SIO, timer, keyboard and NMI | Correct source ownership, bounded service, complete register/DP/stack restoration and unchanged SIO/ST limits. |
| Bitmap backend absent or text-only launch | No VBXE register access, producer, timer demand or vector hook from this feature. |

For an uninterrupted successful scroll, expect one hardware launch, one accepted
completion notification and one Task-context completion query, with no periodic
worker Poll/Yield loop. Explicit synchronous fences and diagnostic callers are
separate observations. When there is no actionable work, demonstrate a blocked
worker rather than inferring sleep from a low poll count.

Measure hardware occupancy, completion-to-IRQ service, IRQ-to-signal,
signal-to-worker execution and final adoption separately. Include IRQ/watchdog
CPU cost as well as worker charge; do not sum nested elapsed spans. Compare
idle and eight-Task disk/input load with the baseline at the same input phases.
Acceptance for this mechanism requires reduced completion-checking CPU cost
without relaxing existing correctness or peripheral timing limits. Keep the
broader 4 ms worker-turn, 20 ms scroll and 40 ms visible-input goals open until
measured; meeting this plan does not establish those targets automatically.

Use the [two-tier testing policy](../contributing/testing.md): host checks,
generator checks and focused emitted raw/optimized coverage as each slice needs.
IRQ, scheduling and ownership changes require the targeted coexistence and
failure cases above. Run full qualification only for a release, explicit
qualification claim or request. A demo refresh is separate; when requested, use
`tools/build_demo.py` with OF816, matching disk/ROM, notices and five-second boot.
