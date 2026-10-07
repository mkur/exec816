# AES application input implementation plan

[GEM integration](README.md) · [Design note](aes-application-input-design.md) ·
[Current AES contract](../../reference/aes.md) · [Current INPUT contract](../../reference/input.md)

Status: in progress, 2026-10-07. AI1–AI3 pass development checks; AI4–AI7 remain
pending. See the [execution record](../../history/aes-application-input.md).

Implement the design in seven executable slices, committing after each passing
slice. The result is an ordinary GEM application receiving keyboard and
left-button input through caller-local event waits, followed by a two-instance
demo beside the native shell. The existing presenter owns routing; existing
Exec signals and `timer.device` provide wakeups and deadlines.

Use the completed WA1–WA6 work, integration merge `78ba5ff` and input design
`cb3564d` as the starting evidence. Record the actual source revision when work
starts. There is no baseline-only slice or prerequisite to close PI4/HY4;
broader latency tuning and the observed flicker remain separate work.

## Scope and sequence

The [design](aes-application-input-design.md) is authoritative for event,
ownership and failure semantics. This plan adds `evnt_keybd`, `evnt_button`
and all nonempty combinations of `MU_KEYBD`, `MU_BUTTON`, `MU_MESAG` and
`MU_TIMER`. Support one left-button click, down/up and the specified inverse
predicate. Reject unsupported requests as a whole. Keep the current timer
semantics, message capacity and windowless message/timer waits.

No new server Task, input signal allocation, kernel operation, polling timer,
priority policy or per-wait presenter RPC is planned. Public forms/objects, resources, menus,
rectangle events, multiple clicks and modal keyboard policy remain outside
this milestone. Donor GEM4XE sources remain read-only.

| Slice | Deliverable | Depends on | Completion gate |
| --- | --- | --- | --- |
| AI1 | Generic capture route options and button qualifiers | Existing INPUT | Console cancellation and native capture remain correct under interrupts. |
| AI2 | Bounded AES input inbox and lifetime protocol | AI1 | Publication, wakeup, loss and retirement pass emitted-code tests. |
| AI3 | GEM keyboard translation and focus routing | AI2 | Captured keys reach the correct open lifetime with correct GEM encoding. |
| AI4 | Content gestures and GUI-lock integration | AI3 | Release, lock acquisition and native replay cannot strand each other. |
| AI5 | Public caller-local input waits | AI4 | Combined readiness, alarm retirement and payload consumption are atomic at the defined decision. |
| AI6 | Interactive GEM application | AI5 | Press/release feedback and keyboard input work through ordinary GEM calls. |
| AI7 | Coexistence, cost evidence and OF816 demo | AI6 | Two instances, shell/disk load, cleanup and the extracted bundle pass. |

Keep each slice buildable and preserve the current counter/demo profile.
AI2–AI4 use focused private fixtures to exercise new routing and storage;
public input event bits remain unsupported until AI5. Do not retain temporary
public interfaces or compatibility profiles after integration.

## Rules for every slice

- Follow the [platform contract](../../reference/platform.md),
  [code style](../../contributing/style.md) and
  [two-tier testing policy](../../contributing/testing.md). Use the revision in
  [the compiler pin](../../../toolchain/actionc.json); record C compiler, ROM,
  emulator configuration and any local overrides in evidence.
- Generate changed Action!/C/assembly layouts and constants from their ABI
  inputs. Rebuild affected callers together. Update current reference pages
  only for behavior actually delivered by that slice.
- Validate supported arguments once at admission. Establish pointers and
  ownership during registration. Retain required lifetime/state checks without
  adding repeated pointer, list or geometry validation to event delivery.
- Keep IRQ code on fixed resident adapter state. Use short Task-side guards
  for publication and snapshots; never wait, call VDI or perform timer I/O
  inside an inbox guard. Keep translation and FIFO scans outside long guards.
- Report reserved bank-zero delta: target **0 fixed + 0 per public Task +
  0 private idle bytes**, counting guards, alignment and unused capacity.
  Preserve eight public Task slots, four AES registrations, four layers and
  fixed VRAM. Report upper live/reserved data, heap rounding, code growth and
  requested/measured stacks separately.
- Freeze layouts against the design's planning ceilings: 640 upper bytes per
  registration, plus 1 KiB shared upper data. At four registrations these are
  2,560 + 1,024 bytes, not measured allocations. Count spare capacity and
  alignment. Fit resident capture additions within existing reservations;
  redesign or document a revised budget before silently enlarging them.
  Keep substantial caller scratch off the 1,024-byte application stack and
  measure peaks with interrupt headroom.
- Run focused host and optimized emitted-code tests. Add small raw/optimized
  ABI and C/native bridge probes where those boundaries change; do not repeat
  the entire GUI workload in raw mode. Interrupt, ownership and transport
  changes require targeted asynchronous/failure cases, not an automatic full
  qualification matrix.
- Add compact evidence as `docs/development/aes-application-input-aiN.json`
  and an execution record at `docs/history/aes-application-input.md` as slices
  complete, updating their indexes. Keep traces and images under `build/`.
  Label the actual development-test scope; do not claim hosted qualification.

## AI1 — Preserve route policy and captured qualifiers

Implemented. [Evidence](../../development/aes-application-input-ai1.json) covers
physical key/button capture, raw/optimized ABI probes, interrupted publication,
relative BUTTON qualifiers and 57.6k disk coexistence. Reserved bank-zero growth
is zero; existing upper reservations are unchanged.

Make the generic capture layer capable of carrying GEM input without changing
the native shell's cancellation policy.

1. Extend [INPUT ABI inputs](../../../abi/input.json),
   [native capture inputs](../../../abi/input-native.json), generators and
   `lib/input` for a generic keyboard route option bypassing configured key
   filters. Publish the route identity and option atomically. Existing routes
   retain filtering; physical BREAK remains durable for both policies.
2. Implement the constant-cost resident check in
   [keyboard capture](../../../platform/altirraos/input.s). Do not inspect
   application/window storage in IRQ context or remove the global Ctrl-C
   filter. Record the added instructions and resident-state/code size.
3. Carry native modifiers with button edges and released baselines in
   [pointer capture](../../../platform/altirraos/pointer.s), preferably through
   unused sample flags. Preserve them through relative normalization and a
   retained BUTTON record. Preserve motion interval encoding and sample
   modifiers only for edges/baselines, without extra idle 4 kHz work.
4. Preserve the platform's modifier limits: live Shift, Control observable
   through a held ordinary key, and an unmodified baseline clearing stale
   qualifiers. Do not advertise standalone Control-click support.

Validation: extend `tools/test_input_registration.py`,
`tools/test_input_capture.py`, `tools/test_pointer_capture.py` and relevant
relative-pointer fixtures. Probe generated layouts in raw/optimized modes.
Exercise route/option publication during IRQ/NMI, complete register/DP/stack
restoration, captured Shift-click and Ctrl-key qualifiers, baseline clearing,
durable BREAK and filtered shell Ctrl-C under queue pressure. Run focused SIO
coexistence at the pinned supported 57.6k profile and check bounded completion.

Exit: both route policies work without changing the existing sampling schedule or
cancellation semantics. Suggested commit: `input: capture route policy and button qualifiers`.

## AI2 — Add bounded inboxes and safe wakeups

Implemented. [Evidence](../../development/aes-application-input-ai2.json) covers
252 transport assertions, registration/GUI/event regressions and both-mode
layout probes. The inbox adds 592 heap-reserved bytes per registration and
sixteen shared directory bytes; fixed bank and bank-zero reservations are unchanged.

Establish transport and loss/retirement semantics before production routing.

1. Extend [the AES ABI](../../../abi/aes-server.json),
   [its generator](../../../tools/generate_aes_server.py), registration/context
   state and private C records. Allocate two sixteen-entry FIFOs, a coherent
   pointer/eligibility snapshot, interest/loss state and selection scratch with
   registration. Generate `AES_INPUT_LOST`. Preserve sixteen ordinary message
   records and the separate durable GUI record.
2. Define immutable record contents, nonrepeating input/open epochs and
   producer/consumer indices within the budget. The presenter is the sole
   producer and caller binding the sole consumer. Publish each record and
   signal decision in short guards; keep the endpoint publication hold through
   the final signal to prevent port/signal reuse during exit.
3. Reuse the existing receiving-port signal. Publish selected input interest
   before the final readiness check, clear it on every return/error, and wake
   for relevant records, loss or newly eligible button levels. Motion alone
   produces no input-event wake. A signal with no message is valid.
4. Latch source-specific overflow/loss outside full FIFOs; stop admission
   without overwriting a selected record. Define consumer acknowledgement,
   source purge and pointer release rearming. Preserve unrelated messages and
   input. Message/timer-only calls leave pending input loss untouched.
5. Integrate partial-registration unwind, close/reopen epoch withdrawal and
   exit ordering: withdraw, finish publisher wakes/native route references,
   retire queues and alarms, then free. Reject identity exhaustion before wrap.

Validation: extend the existing [AES runner](../../../tools/test_aes_server.py)
with private input transport cases. Cover full queues independently, wrapped
indices, unselected records, publication immediately before sleeping, stale
wake hints, loss while a record is selected, retirement during the last wake,
allocation rollback and reuse after close/reopen. Check ordinary message
capacity and registration cleanup. Use small raw/optimized layout probes.

Exit: an emitted producer/consumer fixture proves bounded storage, no missed
wakeup and no publication into retired storage. Suggested commit:
`aes: add bounded application input inboxes`.

## AI3 — Route and translate GEM keyboard input

Implemented. [Evidence](../../development/aes-application-input-ai3.json) covers
translation, original-recipient routing, physical Ctrl-C/BREAK and console/window
regressions. Public input waits remain pending in AI5.

1. Add a machine-readable Atari-to-GEM mapping and generated translation data,
   checking the pinned donor reference and recording provenance for reused
   material. Translate in Task context before inbox publication: printable
   ASCII, Return, Tab/Shift-Tab, Space, Escape, Backspace, Delete, cursor chords,
   Ctrl-letter shortcuts and captured repeat events. Keep shared Caps state
   across GEM focus changes; preserve native console translation.
2. Integrate `DESKCORE`, `DESKINPUT` and `CONSOLEINPUT` with AES open-lifetime
   routes. Use committed focus and the captured route, not current focus at
   consumption. Keep old route references alive until capture is drained;
   close/reopen must never redirect an old key into the new window lifetime.
3. Select filter bypass for AES routes. Deliver Ctrl-C as a GEM key and a
   durable physical BREAK notice as one Escape. Native title gestures consume
   Escape/BREAK themselves, without duplicate application delivery.
4. Publish each key with captured GEM modifiers and a coherent pointer
   snapshot. Keep translation outside the existing bounded capture-drain guard
   where necessary; do not extend that guard around lookup/translation work.

Validation: table-driven host mapping checks plus optimized emitted routing
tests with two AES recipients and the shell. Include Return `$1C0D`, Escape
`$011B`, left cursor `$4B00`, shifted/control cases, Caps across focus changes,
capture-before-focus-change, close/reopen, BREAK coalescing, raw overflow and
shell Ctrl-C. Verify no new repeat timer and no raw POKEY scan codes exposed as
GEM keys. Check key-only loss does not discard unrelated button/message data.

Exit: private consumers receive correctly encoded keys for the original open
lifetime; native keyboard behavior remains intact. Suggested commit:
`aes: route captured keyboard input to GEM applications`.

## AI4 — Route content gestures through GUI locks

This is a prerequisite for exposing button waits: a mouse-control owner must
be able to receive the release needed to finish its operation.

1. Extend `DESKINPUT`/`DESKDRAG` classification for focused AES work-area presses.
   Capture the content recipient through physical release, including outside
   the work area and across programmatic focus changes. Publish accelerated
   screen coordinates without clipping them to the recipient.
2. Preserve inactive-window topping as a manager-owned sequence: send
   `WM_TOPPED`, consume the entire activation click and prevent click-through
   even if the app accepts topping before release. Titles/closers and native
   controls retain their existing ownership.
3. Split `AESLOCKS.MouseBlocked` and the deferred `AESINPUT` path into explicit
   routing/lock decisions. `BEG_UPDATE` freezes native gestures but permits
   eligible application input using committed geometry. `BEG_MCTRL` directs
   content input to its open-window owner without taking keyboard focus.
4. Make lock eligibility account for physical gesture ownership. A competitor
   waits for release while capture continues draining; the gesture owner may
   acquire/recurse. A released deferred native sequence must not deadlock an
   update owner's upgrade/unlock. Classify each sequence once and prevent
   duplicate application delivery/native replay or conflicting overtaking.
5. Publish level eligibility and wake on focus/ownership changes, manager
   handback and unlock/exit even without a new edge. Close/loss cancels content
   capture and requires an observed release before rearming; never fabricate
   an application release. Routing must not acquire DISPLAY or wait for a BLT.

Validation: optimized emitted routing/lock fixtures cover quick down/up during
painting, outside release, repeated focus changes, accepted/declined topping,
title/closer exclusion, owner waiting for release, competing and recursive
locks, background repaint, windowless exclusion, deferred native press/release,
update-to-mouse upgrade and unlock without fresh input. Inject normalized/raw
loss and lost release; verify recovery and no stuck ownership. Retain native
widget/drag and message/timer progress checks.

Exit: each sequence has one recipient, release makes progress under locks and
no event path depends on physical display ownership. Suggested commit:
`aes: route application mouse gestures through GUI locks`.

## AI5 — Expose caller-local GEM input waits

1. Extend the [binding inputs](../../../ports/gem4xe/aes-binding-inputs.json),
   generated constants, `gem.h` and dispatch for `evnt_keybd` (20, counts
   0/1/0/0), `evnt_button` (21, 3/5/0/0), and the existing multi-event opcode 25
   (16/7/1/0). Named calls, both multi spellings and AESPB use shared helpers.
2. Extend [the local event loop](../../../c/calypsi/aes-events.c). Admit once,
   require an open window only for selected input bits, publish interest and
   inspect selected queues/eligible levels without consumption. Scan at most
   sixteen button records, copying at most one immutable record per guard.
   Commit older nonmatching transitions only with a successful selection.
3. Reuse one absolute alarm and the selected receive/timer signal masks.
   Recheck after arming; never clear a signal between empty observation and
   `Wait`. Generalize the existing clock check to any ready non-timer source.
   Freeze the result, retire the alarm outside guards, then commit selected
   heads/message and outputs after the required epoch/state check. Later
   arrivals belong to the next decision. Own exactly one terminal alarm reply.
4. Apply the design's output composition and errors: button snapshot first,
   key-publication snapshot for key-only results, otherwise coherent latest
   pointer state; combine captured modifiers as specified. Unsupported calls,
   timer failures or loss must not consume unrelated payloads. Clear interest
   on every path and expose source loss through the generated diagnostic.

Validation: extend `aes_events.c`/`aes_timers.c` fixtures and the AES runner.
Exercise all fifteen nonempty event-mask combinations with simultaneous ready
sources and staggered arrivals, plus named/PB equivalence. Cover single/inverse
down/up, repeated level waits, buffered down/up, no-match scans, unsupported
arguments, ignored unselected arguments and windowless message/timer calls.
Inject arrivals at inspect/arm/wait and freeze/retire/commit boundaries;
cover spurious wakes, zero timers, deadline wrap, expiry/cancellation races,
timer errors, pending loss, unselected queues and cooperative owner shutdown.
Prove combined failures preserve message payloads. Add raw/optimized wrapper
probes; verify idle waits sleep and warm input waits issue no presenter RPC.

Exit: the full proposed event profile works through the public binding without
new kernel scheduling or wait services. Update AES reference/profile docs.
Suggested commit: `aes: add caller-local keyboard and button waits`.

## AI6 — Add an interactive GEM application

1. Add a small resident C application with a VDI-drawn control and keyboard
   label. Keep its body on `<gem.h>`; keep Exec attachment and Task lifetime
   in the wrapper. Use ordinary windows, redraw messages, private workstations
   and local hit testing, without introducing public object/form calls.
2. A press inside the control highlights it; release inside activates it and
   release outside cancels. Keep the highlight until release; continuous
   hover/leave tracking is not promised. Display translated keyboard input
   and retain a timer-driven indicator so combined waits are observable.
3. Release update/display ownership before the normal event wait. Cancel an
   armed control on input loss, handle top/move/redraw/close normally and unwind
   partial startup. Close/delete/exit must leave no route, inbox, alarm,
   workstation, signal or window behind.

Validation: add optimized application fixtures following the existing counter
test structure, keeping test hooks out of the application body. Check exact
pressed/released pixels and label changes, quick clicks during redraw,
outside release, timer/message progress, translated shortcuts, input-loss
reset, repeated open/close and allocation-failure cleanup. Measure stack peaks.

Exit: one application demonstrates ordinary GEM input end to end. Suggested
commit: `demo: add an interactive GEM input application`.

## AI7 — Demonstrate coexistence and record cost

1. Run two independent instances beside the shell with independent FIFOs,
   windows and workstations. Keep the established resource budget: six public
   Tasks at the prompt (shell, presenter, SIO, filesystem and two apps), rising
   to eight for two pipeline children. Include the controller registration in
   registration/layer accounting. Test an optional native panel separately
   within the same fixed limits.
2. Exercise focus and activation isolation, rapid typing/clicks while the
   recipient draws, outside release, movement/close and shell cancellation
   during disk/scroll load. Run the existing disk pipeline and verify bounded
   progress, filesystem integrity, guards and resource recovery after exit.
3. Extend focused timing instrumentation for capture-to-route,
   route-to-event-return and event-return-to-visible feedback. Record median,
   p95, maximum and caller/presenter CPU under idle, console scrolling and
   disk load, with event provenance to avoid mixing stages from different
   clicks. Include an unobserved replay to separate tracing cost. Report native
   regressions and measured capture overhead; do not claim to close PI4/HY4.
4. Add an optional interactive-input profile to
   [the demo builder](../../../tools/build_demo.py), following the existing
   counter profile. Include OF816, pinned ROM and license notices; preserve
   the default five-second standard shell/PRIMES autoboot and existing profiles.
   Produce `exec816-demo.zip` with boot files, a short profile-specific guide,
   notices and checksums only. Keep manifests/intermediates in development.
5. Validate the exact extracted ZIP: startup, two applications, input/focus,
   shell/disk activity and cooperative exit. Record pins and actual test scope,
   finish the history/evidence records and update the guide, roadmap and
   indexes. Preserve explicit unsupported behavior in the current contract.

Exit: the new profile has reproducible development evidence and a usable
OF816 bundle, with **zero reserved bank-zero growth** and measured upper-memory,
stack and latency costs. Suggested commit:
`demo: validate GEM input coexistence and package the interactive profile`.

## Completion criteria

All seven slices must pass their focused checks and have individual commits.
The final evidence must connect capture, routing, public event delivery and
visible feedback, including loss recovery and resource cleanup. Documentation
must distinguish this supported single-button/input profile from a complete
GEM desktop or donor `form_do` implementation. Broader compatibility and the
existing latency gates remain separate milestones.
