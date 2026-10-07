# AES application mouse and keyboard input

[GEM integration](README.md) · [Window applications](aes-window-app-design.md) ·
[Hybrid model](hybrid-aes-vdi-design.md) · [Current AES contract](../../reference/aes.md)

Status: implementation in progress, 2026-10-07. This note defines the next
application-input milestone after WA1–WA6. The
[implementation plan](aes-application-input-implementation-plan.md) has seven
executable slices. AI1–AI5 capture, routing and public input waits pass development
checks; AI6–AI7 remain pending. This note is not a qualification claim.

Give an ordinary GEM application keyboard events and left-button press/release
events through `evnt_multi`. Add the corresponding `evnt_keybd` and
`evnt_button` wrappers. The application body continues to use `<gem.h>`; its
Exec wrapper owns attachment and Task lifetime.

Keep routing in the existing presenter and event matching in the caller.
Use the application's existing receiving-port signal and `timer.device` alarm
with Exec `Wait`. No additional server Task, kernel wait operation, polling
timer, per-wait presenter RPC or priority change is required. Broader latency
tuning remains deferred; PI4/HY4 and the observed flicker remain open.

## Starting point

The current [application profile](../../guides/aes-applications.md) has windows,
durable GUI messages, private VDI workstations and caller-local message/timer
waits. Its mouse/keyboard result words are zero and unsupported event bits fail.
The counter demo therefore exercises drawing and window controls, but cannot
accept ordinary input inside its work area.

Relevant existing boundaries are:

- [INPUT](../../reference/input.md) captures keyboard and ST/port-1 pointer
  input independently. IRQ code uses fixed adapter storage and captured route
  identities; it does not traverse application pointers.
- [DESKINPUT](../../../lib/desktop/deskinput.act) consumes accelerated pointer
  positions, routes graphical keys, and lets the native window manager handle
  titles and closers. AES content clicks currently only request topping.
- [CONSOLEINPUT](../../../lib/console/consoleinput.act) offers graphical routes
  to DESKINPUT before console translation. The shared keyboard lease currently
  filters Ctrl-C into a durable cancellation notice for every route.
- [AESINPUT](../../../lib/aes/aesinput.act) is a deferred native-gesture queue
  under GUI locks. It is not an application input inbox.
- [AES event binding](../../../c/calypsi/aes-events.c) already combines the
  receiving-port signal and one absolute timer deadline without a presenter
  event-wait engine.

Extend these boundaries. Do not connect GEM clients directly to exclusive
hardware leases or revive GEM4XE's polling scheduler.

## Public source profile

The named calls, `evnt_multi_moblk` and `aes_call(AESPB *)` must share one
implementation. Retain private parameter blocks and the one-call-per-Task rule.

| Interface | Proposed behavior |
| --- | --- |
| `evnt_keybd()` | Return one GEM key word, blocking until a routed key is available. Opcode 20, counts 0/1/0/0. |
| `evnt_button(clicks, mask, state, ...)` | Wait for the supported button condition and return one, with pointer/button/modifier outputs. Opcode 21, counts 3/5/0/0. |
| `evnt_multi` / `evnt_multi_moblk` | Support any nonempty combination of `MU_KEYBD`, `MU_BUTTON`, `MU_MESAG`, `MU_TIMER`; retain opcode 25 and counts 16/7/1/0. |
| Keyboard result | GEM scan code in the high byte and ASCII in the low byte. Consume at most one key per result. |
| Button result | Accelerated screen coordinates and button state for the selected condition; one match, with no double-click delay. |
| Combined result | All selected conditions ready at the frozen decision, consuming at most one key, one button match and one message. |

These signatures and encodings follow the
[GEM event reference](https://freemint.github.io/tos.hyp/en/evnt.html) and the
[pinned binding inputs](../../../ports/gem4xe/aes-binding-inputs.json).
The routing, bounded buffering and failure rules below are Exec816 policy.

Initially support `mask=1`, `state=0` or `1`, and `clicks=1` or `$0101`.
The high bit selects the donor's inverse predicate:

```text
matches = ((buttons & mask) == (state & mask)) XOR ((clicks & $0100) != 0)
```

Thus ordinary waits can select left-button down or up; the inverse form remains
available without introducing multiple-button hardware support. Reject other
click counts, zero/unsupported masks, unsupported state bits, and event masks
containing unsupported events. Do not silently reduce a double-click request
to a single click. Ignore button/rectangle arguments when their bits are absent.

Input waits require the registration's open application window; otherwise
return `AES_IDENTITY`. Message/timer waits retain their existing windowless use.

`MU_M1`, `MU_M2`, `evnt_mouse`, multiple clicks, `evnt_dclick`, right/middle
buttons, wheel events, normalized-key extensions, `graf_mkstate`, menus and
public form/object calls are outside this milestone. In particular, this does
not yet suffice to import a complete donor `form_do`: rectangle tracking and
multiple-click semantics need their own extension.

Keep the existing timer rules, including immediate zero-duration `MU_TIMER` and
the separate nonzero wait of `evnt_timer(0)`. A successful message/timer-only
`evnt_multi` now returns a coherent last-published pointer snapshot rather than
six unconditional zeros. `key` is zero without `MU_KEYBD`; `clicks` is zero
without `MU_BUTTON`. Errors return zero and set `ExecAESDiagnostic()`.

## Focus and gesture ownership

Use committed desktop focus and window/open identities, not an assumption that
the top layer is focused. Closing the focused window still clears focus; this
milestone adds no automatic successor policy.

| Input location/state | Recipient |
| --- | --- |
| Focused, visible AES work area; fresh left press | That application's input inbox. |
| Inactive AES window; fresh left press | Window manager: request `WM_TOPPED`; consume the entire click. |
| Title, closer, other frame area or desktop | Window manager/native policy; never an application content click. |
| Native console or widget window | Existing native route. |
| Key with an AES capture-time keyboard route | The application owning that live open-window route. |
| Key with a console route | Existing console translation and foreground cancellation. |

The first click in an inactive AES window activates it through the existing
`WM_TOPPED`/`WF_TOP` exchange. A release after the application acknowledges top
does not become an orphan content click. A later fresh press can activate a
control. Requests which the application declines do not change focus.

A press admitted to application content establishes a presenter-owned gesture
identity until release. Motion can update that owner's pointer snapshot; the
release goes to the same application even outside its work area or over another
window. Do not clip release coordinates to the work rectangle: the application
needs to distinguish release inside and outside its control. One gesture cannot
activate two applications. Do not retain an application tree or callback in the
presenter.

An already admitted gesture survives a programmatic focus change until release,
but close, delete, exit or input loss cancels it. A new recipient cannot inherit
the held button. After cancellation, observe physical release before admitting
another press. No synthetic successful release is generated to clear a widget.

Keyboard identity is captured when the event occurs. A queued key for A remains
A's key if B gains focus before it is consumed; it is never redirected to B.
Buffered keys may therefore be returned after focus changes. Close/reopen is
different: a new open epoch must not inherit the previous opening's keys.
Recreate/retire keyboard routes at that boundary, draining old native references
before retiring the route; retain old storage until that drain completes.

## Keyboard translation and modifiers

Translate in Task context, before publishing the GEM key record. Freeze a small
machine-readable mapping for the supported Atari keyboard using the donor's
[key translation](https://github.com/slaapliedje/gem4xe/blob/e413c39d2f8e1bec8fe16596f610b923de4a0ae9/src/vdi/vdi.c)
as a behavior reference. Do not invoke its hardware polling or copy a private
scan-code table into several clients. Keep provenance for any extracted code.

Cover printable ASCII, Return, Tab/Shift-Tab, Space, Escape, Backspace, Delete
and Atari cursor chords mapped to GEM arrow scan codes. For example Return is
`$1C0D`, Escape `$011B`, and cursor-left `$4B00`. Ctrl-letter combinations retain
both the letter's scan code and control character. Do not return native POKEY
scan values as GEM scan codes or reuse the console's LF for GEM Return.
Unsupported physical keys produce no invented GEM key. Deliver captured repeat
events; this milestone adds no software repeat timer.

Map native Shift to GEM left-Shift bit 1 and Control to bit 2. The hardware does
not distinguish two Shift keys and has no Alt key; do not advertise those inputs.
Caps state belongs to the shared desktop keyboard translator and survives GEM
focus changes; Caps is not an ordinary text key. Console editing retains its
existing translation policy.

Key records retain the key's captured modifiers. Button records must also
retain modifiers when the button edge is captured; sampling only when a delayed
application resumes would lose Shift-clicks. Extend the generic pointer capture
representation to carry native qualifier bits, preferably using unused bits in
the existing sample flags, and propagate them through relative normalization
and any retained BUTTON record. Do not alter the motion interval encoding.
Sample modifiers on button changes/baselines, not on every idle 4 kHz sample.

The pinned donor documents a platform limit: Shift has a live POKEY status bit,
but Control is observable through a held key's scan value. Follow that bounded
hardware behavior and test it; do not claim a standalone Control-click when no
ordinary key is held. Shift-click and Ctrl-key shortcuts remain useful. An
unmodified baseline must clear stale modifiers after key release.

For a combined key/button result, pointer coordinates/buttons come from the
button match and `kstate` includes that snapshot's modifiers OR the returned
key's captured modifiers. With only a key result, use the pointer snapshot at
key publication and that key's modifiers. With neither input bit returned, use
the latest coherent published snapshot. This is an explicit composition of
asynchronous sources, not a claim that every source occurred at one physical
instant.

### Preserve console cancellation

The current global Ctrl-C filter consumes the original key before routing.
Add a generic keyboard route option to bypass configured key filters, selected
for AES application routes. Existing console and native widget routes retain
their present behavior. Store the option in fixed upper adapter state and
publish it atomically with the selected route. IRQ work remains a constant-cost
flag check against resident state, without window or application lookups.

Do not remove Ctrl-C filtering globally or replace durable console cancellation
with an ordinary FIFO entry. On a GEM route Ctrl-C is an ordinary GEM key. The
physical BREAK key remains a durable cancellation notice; when addressed to a
GEM application it produces one Escape key as a documented platform mapping.
Repeated BREAK notices may coalesce. During a native title gesture Escape/BREAK
belongs to the window manager and is not delivered a second time to the app.

## Bounded input storage and wakeups

Allocate one upper-memory input inbox with registration, publish it with the
existing endpoint, and retain it until exit withdrawal and publisher retirement
finish. Use separate bounded key and button FIFOs so an unselected key cannot
block a requested button. Initially budget sixteen records per FIFO. Motion is
a latest-state snapshot, not a third FIFO, and does not wake `MU_KEYBD` or
`MU_BUTTON` waiters solely because the pointer moved.

The presenter is the only producer; the application's event binding is the only
consumer. A record contains immutable result data and an input epoch associated
with the open window in the inbox header; it need not repeat every window ID.
Unselected input stays queued within these bounds. Ordinary sixteen-record
`appl_write` capacity and the separate durable GUI record remain unchanged.
Input is not disguised as a GEM message and cannot be consumed by `evnt_mesag`.

Use short Task-side `Forbid` sections for inbox publication, reader state and
wake decisions. Application storage is never touched from IRQ/NMI context.
Reuse endpoint publication/lifetime holds across the producer's final wake so
an exiting client cannot free or reuse its receiving port/signal underneath it.
Do not hold a Forbid across a FIFO walk, VDI call, timer operation or wait.

Publish a selected-input interest mask before the caller's final readiness
check. Signal the existing receiving port's owner/bit when relevant input or
loss becomes available. The same signal already announces messages; it is a
wake hint, not proof that `GetMsg` will return a message. A message-only call
must tolerate an old input wake. A button/key-only call must tolerate an ordinary
message wake without consuming that message. Clear interest on every return
and error path; input admitted while the caller is drawing remains buffered.
Focus/ownership changes and return from a native gesture also publish eligibility
and wake an interested caller whose level condition can now be satisfied. A
button-up wait must not require another edge after the manager releases control.
Within each FIFO ordering is publication order; there is no promised total
ordering across keyboard, button and message sources.

No per-event heap allocation, whole-tree validation, geometry division, new
signal allocation, service RPC or unconditional context yield belongs on this
path. Establish pointers/ownership at registration; check supported arguments
once at the public call boundary. Preserve the state and lifetime checks which
make publication safe.

## Button matching and local wait transaction

Keep transitions as well as the current level. If a down and up both arrive
while a caller is painting, its next down wait must still see the retained
press, followed by the release when it asks for up.

For a button wait, inspect pending transitions in order. Select the first
matching record, retiring any older nonmatching transitions only when that
selection commits. If none match, use the current button level only when the
application currently owns eligible mouse input. This preserves immediate
state waits, including waiting for up when already released. Buffered edges
retain their original gesture recipient even if the pointer has since left.
A background application cannot satisfy a level wait from somebody else's
held button.

For level matching, the owner is the active content-gesture recipient or the
explicit mouse-control owner. When neither exists and no manager gesture is
active, the focused open AES window can observe the released state, even with
the pointer outside its work area. A held press belonging to the manager never
becomes eligible just because focus or pointer position changes. Publish this
eligibility beside the current snapshot; callers do not hit-test Layers.

Level matching is intentionally repeatable: requesting down twice while an
eligible button is held can return twice. Applications implement a click by
waiting for down and then up, rather than assuming `MU_BUTTON` is always a new
edge. A single-click result returns one immediately; it never arms a click
aggregation timeout. A failed timer or rejected call does not consume a key,
button selection or message.

Extend the existing caller wait as one transaction:

1. Admit the call and its supported arguments once. Compute a timer deadline
   once if selected; prepare caller-owned result scratch.
2. Publish input interest and inspect selected queues/level state using short
   guarded snapshots. Inspect message readiness without removing its payload.
3. If nothing is ready, submit the existing absolute alarm when needed, recheck
   after submission, and call `Wait(receivingMask | timerMask)` for the sources
   selected by this call. A wake never restarts the deadline.
4. If key/button/message readiness races timer expiry, apply the existing
   combined-wait clock check to any non-timer source, not only messages. Freeze
   one result, with the selected FIFO positions and their epochs.
5. Retire a submitted alarm outside the inbox guard. Successful cancellation or
   completion owns exactly one terminal reply. Arrivals during retirement belong
   to the next decision, not an expanded result after the fact.
6. Revalidate only the selected state/epoch against intervening loss or window
   retirement, commit the selected queue advances, detach at most one message,
   copy outputs and clear input interest. On failure preserve unrelated queued
   messages/keys; lifecycle or loss invalidation retires its own stale input.

Copy at most one immutable record per guarded section. Scan at most the fixed
sixteen button records outside a long critical section, with an epoch/head
check at commit. A full producer queue latches loss and stops admission; it
must not overwrite a record selected by an in-flight wait. No signal is cleared
between an empty observation and `Wait`; publication in that interval remains
latched. With no selected source ready, the Task sleeps.

## GUI locks and display access

The current blanket `MouseBlocked` path must be split: blocking native gestures
must not block input needed by the application owning a mouse hold. Otherwise
an owner waiting for button-up could deadlock the desktop.

- An implicit mouse hold from `BEG_UPDATE` freezes native focus/geometry/widget
  gestures. Application content input and gesture release can still be routed
  using committed geometry. It does not redirect all input to a background
  application which is repainting.
- Explicit `BEG_MCTRL` gives its owner application mouse control, including
  coordinates/releases outside its window. Other application/native mouse
  gestures wait. A registration without an open window can retain the existing
  exclusion behavior but does not become an input destination.
- Acquiring explicit control cannot steal an existing physical gesture from
  another owner. Keep draining capture so its release can make acquisition
  eligible. The gesture's own owner may acquire/recurse without waiting for its
  own release. Native drag/close captures remain manager-owned to completion.
  Track physical release even for a sequence awaiting native replay: a released
  deferred sequence keeps its destination but must not prevent an existing
  update owner from upgrading its lock and later unlocking it.
- Keyboard routing follows capture-time focus in this profile; `BEG_MCTRL`
  does not implicitly focus a window or take another application's keyboard.
  Full modal-dialog ownership is a later policy extension.

Classify each physical button sequence once. Records already delivered to an
application must not also enter the native replay queue. A deferred native
press owns its subsequent release until replay/cancellation; new input must not
overtake it and start a conflicting application gesture. Unlock/exit wakes the
existing presenter path; no new input edge is required to make progress.

The pointer overlay continues through the physical display arbiter. Routing and
matching need no display grant and do not wait for blitter completion. Never
wait for events while holding a physical DISPLAY borrow or a scene transaction.
Holding logical GUI ownership does not prevent messages/timers or the owner's
eligible input from being delivered. Typical applications release `BEG_UPDATE`
before returning to their event loop.

## Overflow, cancellation and retirement

Treat input loss as loss, not a fabricated click. On raw/normalized capture loss
or a full application FIFO, latch a durable input-loss condition outside the
FIFO, invalidate the incomplete input sequence and cancel its gesture. Wake an
input waiter and return zero with a new generated `AES_INPUT_LOST` diagnostic.
Publish the loss epoch without overwriting records a caller may have selected;
the consumer discards that source's old entries after retiring its frozen wait.
The caller acknowledges that boundary before later input is eligible. Preserve
ordinary application/GUI messages; a combined failure does not consume them.
Message/timer-only waits continue and leave the input-loss report pending.

Require a fresh observed released baseline after pointer loss. Keyboard loss
does not fabricate held keys or repeat counts. Record the affected source(s)
internally, retaining unrelated input where possible. The initial application
must discard any armed control on an input-loss return. This is an explicit
extension of the existing Exec816 diagnostic convention, not a standard GEM
loss event that arbitrary unmodified applications already understand.

On close/delete, withdraw routing for that open epoch before retiring its input.
Notify a wait selecting input with the existing identity-error convention if
its input window retires; message/timer-only clients need no window. On exit,
withdraw endpoint admission, cancel gesture ownership, clear interest, finish
publisher wakes, drain native route references and queued input, retire any
alarm, and then free the inbox with the existing context. An ordinary Task
cannot call close concurrently with its own blocking event call; cross-Task
teardown tests use the supported shutdown request/owner cooperation.

Signals retained from an earlier lifetime may wake a Task, but never authorize
using a retired inbox, route or window. Exhaust nonrepeating identities before
wrap. Do not add forced Task termination recovery in this milestone.

## Memory and measured cost

Target zero new reserved bank-zero bytes: **0 fixed + 0 per public Task +
0 private idle**, including guards, alignment and unused capacity. Keep loading
reservations, eight public Task slots, four AES registrations, four desktop
layers and fixed VRAM unchanged. No larger stack class is assumed.

Use a planning envelope of **640 bytes per registered application** for two
sixteen-entry FIFOs, headers, interest/epoch state and caller selection scratch:
512 bytes if records fit sixteen bytes, leaving 128 bytes for control/scratch.
At four registrations that is 2,560 bytes, plus a provisional **1 KiB shared**
upper-memory envelope for translation tables, route-filter state, pointer
snapshot/gesture state and binding pointers. These are design ceilings, not
measured layouts or permission to reserve another bank by default.
Resident code growth is separate and must be reported from the linked image.

Freeze generated layouts and heap-rounded allocations in implementation. Count
both live and reserved upper bytes; if capture metadata needs a larger fixed
extent, report all alignment/spare capacity and prove no overlap. Native IRQ
additions must fit the existing adapter/code reservations or be redesigned.
Keep substantial C scratch off the 1,024-byte application stacks and measure
actual peaks, including interrupt headroom.

Measure capture-to-routing, routing-to-event-return and event-return-to-visible
feedback separately under idle, console scroll and disk load. Record median,
p95 and maximum plus caller/presenter CPU. Single clicks add no artificial
delay. Demonstrate no idle AES polling, no warm input-wait RPC, and bounded IRQ
cost from route filtering/button modifier capture. These diagnostics do not
close the older latency gates.

## Acceptance and implementation boundaries

Keep the current reference/API documents unchanged until code exists. Extend
the private AES wire/context ABI, generated GEM constants and binding provenance
together; rebuild Action!/C callers. Extend the generic INPUT ABI for route
filter selection and qualifier semantics through its generators. No private
AES-only kernel operation is allowed. Donor sources remain read-only.

Development coverage must include:

- Named and parameter-block calls, both multi-call spellings, unsupported masks,
  single/inverse down/up predicates and immediate level satisfaction.
- Down/up during repaint, release outside, inactive-window topping without
  click-through, declined topping, title/closer exclusion, repeated focus
  changes and keys captured before a focus change.
- Printable/control/special-key mapping, Shift-Tab, Caps across GEM focus,
  held-key modifier limits, Ctrl-C as GEM input versus durable shell BREAK,
  and graphical BREAK mapping without duplicate native cancellation.
- All ready-bit combinations, zero/nonzero timers, messages and keys retained
  when unselected, arrivals at the inspect/arm/wait boundary, spurious wakes,
  deadline wrap, alarm cancellation races and timer errors without payload loss.
- Own and competing GUI locks, button-up while the owner waits, pending lock
  acquisition during a gesture, deferred native replay, and no display borrow
  held across an event wait.
- Raw/inbox overflow, durable loss, no stuck capture after lost release,
  close/reopen route isolation, exit publication races and partial-init rollback.
- A small GEM-only application with one drawn control: press highlights it,
  release inside activates it, release outside cancels it, keyboard input
  updates a label, and timers/messages remain responsive. Run two instances
  beside the shell, including the existing eight-Task disk pipeline budget.

Use optimized emitted-code tests for behavior and pixel/ownership/OS-return
checks. Add small raw/optimized probes for changed generated records and C
calling conventions. Because the proposal touches resident capture, include
targeted IRQ/NMI route-publication and SIO coexistence tests; do not expand this
into a full qualification matrix automatically. Build any demo through
`tools/build_demo.py` with OF816 and its five-second default preserved.

The demonstration can use VDI rectangles/text and local hit testing. Public
`objc_*`, form handling, editable fields and resource loading belong to the next
design. Before that extension, resolve rectangle events, multiple-click waits
and modal keyboard policy explicitly rather than hiding them inside a widget
callback.
