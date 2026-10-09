# Standard GEM dialogs

[GEM integration](README.md) · [Implementation plan](standard-dialogs-implementation-plan.md)

Status: FD1 host lifetime is implemented; `form_do` and `form_alert` remain
planned. The [AES contract](../../reference/aes.md) records current behavior.

Add bounded synchronous GEM dialogs on top of the existing caller-local object,
editing and event routines. This removes the need for a custom form loop in
simple ports while other Exec applications continue running. A dialog uses its
application's work area, or a temporary ordinary window when that application
has no window. There is no new Task, kernel operation or desktop-wide modal
lock.

## Scope and compatibility

Provide the named calls and equivalent AES parameter-block dispatch:

| Call | Opcode | Counts: integer in/out, address in/out | Result |
| --- | --- | --- | --- |
| `form_do(tree, start)` | 50 | 1/1/1/0 | Accepted EXIT object index; -1 for interruption, dismissal or failure |
| `form_dial(type, x1, y1, w1, h1, x2, y2, w2, h2)` | 51 | 9/1/0/0 | One on success, zero on failure |
| `form_alert(default_button, text)` | 52 | 1/1/1/0 | One-based button number; zero for interruption, dismissal or failure |

Keep opcode 54 for `form_center`. The signatures/counts follow the donor
`src/app/gemlib.c`; record them in the existing
[binding manifest](../../../ports/gem4xe/aes-binding-inputs.json).
This remains a rebuilt source interface, not a GEM binary ABI.

`form_dial` is a necessary small companion, since the donor calculator uses
`form_center`, START/GROW, `objc_draw`, repeated `form_do`, SHRINK/FINISH.
Support that lifecycle with the existing object types, 32-object/eight-level
tree limit and editable TEDINFO bounds. START establishes the drawing host;
FINISH releases it and requests underlying-content repair. GROW and SHRINK
succeed without animation inside a started session; they change no ownership.
Document these as animation-free operations, not implemented visual effects.

The first version does not implement TOUCHEXIT, double-click return bits,
rectangle events, nested dialogs, arbitrary callbacks, additional application
windows, a file selector or general bitmap objects. Existing `form_button` and
`form_keybd` semantics remain usable by event-driven applications.

The important compatibility limits are deliberate: dialogs must fit their
host, callers must not hold UPDATE/MCTRL across the call, and an event requiring
application policy interrupts the synchronous loop. A port must check the
negative `form_do` result before indexing its tree. This is not a claim that
every original modal GEM loop can run unchanged.

## Dialog host and lifetime

Use one small upper-memory session attached to `ExecAESContext`. It records the
borrowed tree through FINISH, edit/press state, original root position, host
ownership and cleanup progress. It is private binding state, not a new desktop
object model. Never copy the application's whole tree to the presenter.

With a shown application window, borrow that window and temporarily replace its
work-area content with the dialog and a neutral background. Preserve its handle,
kind, geometry, title, registered menu and virtual workstation. The form's
complete drawing extent, including outward borders, must fit. Do not resize an
application's window behind its back. A fit failure returns `AES_RESOURCE`
before painting.

With no allocated application window, create a temporary NAME/CLOSER/MOVER
window through the existing window service. It occupies one of the four current
desktop slots and belongs to the same AES registration. Give it the title
Dialog or Alert and size it around the requested work rectangle. A full desktop
returns `AES_RESOURCE`; do not reserve a fifth slot or evict another window.
A caller that already owns a closed window must open or delete it first;
return `AES_BUSY` without changing that handle.

Reuse an existing virtual workstation. If absent, open one with the existing
default attributes and display grant, then close only that internally opened
workstation at session end. Allocate setup arrays and dialog storage in upper
RAM, not in a large automatic stack frame. No second workstation is created.
Preserve all attributes of a borrowed workstation.

`form_center` continues centering in a shown window's work area. Without a
window, it computes a desktop-centered rectangle that leaves room for the
temporary frame below the menu bar. It changes tree coordinates but allocates
nothing. START takes that rectangle; the usual subsequent `objc_draw` can then
use the hosted window and workstation under a short UPDATE section. Starting
with an out-of-bounds rectangle fails once at admission.

A direct `form_do` without START creates an implicit session, performs the
initial draw and finishes the session before returning. On a borrowed window it
uses the caller's tree position; when creating a temporary window it centers
the tree and restores the original root position on finish. With explicit
START, `form_do` leaves the host alive, permitting calculator-style repeated
calls on the same tree; FINISH owns teardown. `form_alert` always uses an implicit
session. Sequential `form_do` calls inside START/FINISH are supported; recursive
entry while a form is running and alerts inside an existing session are not.
End any caller-managed `objc_edit` association before starting a session.

START and `form_do` do not leave `c->busy` set while invoking other public AES
helpers: that flag protects individual operations. A separate session/running
state prevents recursive form entry. Named and AESPB callers use the same
implementation; save input arguments before nested calls reuse context arrays,
and publish the outer result only after cleanup.

## Waiting and interaction

The dialog loop executes in the application Task and calls the existing
`evnt_multi` for keys, left-button transitions and messages. Use the current
receive signal and input routing. No periodic polling, new signal protocol or
presenter-run form loop is introduced. The presenter continues owning windows,
focus and input delivery; no borrowed application callbacks run there.

Acquire UPDATE only for a bounded draw, then release it before every event
wait. Never retain a Layers token, physical display grant or MCTRL hold while
waiting. Reject entry with caller-owned UPDATE/MCTRL using `AES_BUSY`; do not
silently release and reacquire a caller's locks. If a lock depth is not currently
published to the binding, record it on successful `wind_update` transitions,
not by adding a service query to each event. Ordinary correct-call ownership
rules still apply.

`start == 0` chooses the first eligible editable field; a nonzero start names
the initial editable field. Without one, use the first eligible button as
keyboard focus. Reuse `objc_edit` for insertion, validation, viewport and caret;
reuse form helpers for buttons and radio groups. Tab/Shift-Tab traverses eligible
controls, Space activates button focus, and Return activates DEFAULT. Up/Down
traverse eligible editable fields; Left/Right remain editing keys.
Escape cancels a held press; otherwise it retains the existing editable-field
clear behavior. Do not infer a Cancel action from a translated button label.

A left press arms an eligible object and paints feedback. Release on that
object accepts; release outside cancels. Restore the saved pre-press state
before committing through `form_button`, so preview state is not toggled twice.
There is no motion/hover tracking promise in this first profile. Finish a held
sequence before allowing another activation, including on entry and after
input loss. Loss cancels feedback and rearms only after an observed release.

Paint only changed controls/radio peers or the edited field for normal input.
The initial draw and exposure repair reconstruct the form from its live tree.
An accepted EXIT returns its index with SELECTED set, matching the conventional
`form_do` caller that clears that bit before another call. Adapt this at the
`form_do` boundary: the existing event-driven helper's momentary EXIT behavior
must not change. End editing on every return, retaining text, accepted toggle
and radio state. Remove only transient focus/press decoration.

## Window events and message preservation

Use the provenance and epochs already carried by GUI delivery. An ordinary
`appl_write` message containing WM_REDRAW-shaped words is still an application
message and must not be consumed as presenter damage.

| Event during the loop | Action |
| --- | --- |
| Live host WM_REDRAW | Paint the form/background within the damage and visible region under UPDATE. Remember that borrowed application content needs repair later. |
| Live host WM_TOPPED | Acknowledge through `WF_TOP`, then repaint as needed. |
| WM_MOVED for an internally owned temporary window | Accept through `WF_CURRXYWH`, translate the form root by the committed work-area delta and repaint. Restore the caller's original root position at FINISH. |
| WM_CLOSED for an internally owned temporary window | Dismiss without selecting a button. Return -1/zero with `AES_OK`; tear down at implicit finish or the caller's explicit FINISH. |
| Move, size, scroll or close request for a borrowed application window; menu selection; ordinary application message | Preserve the exact message and return to the application with `AES_PENDING`. Do not make the application's geometry, command or shutdown decision. |

Preserve an interrupting message in the existing one-message deferred slot,
including its window/menu epochs, and stop consuming immediately. An already
deferred message is handled first and cannot be overwritten. The next public
message wait retrieves it before later queued messages, subject to the existing
retired-epoch rules. Do not add another message FIFO or wait mechanism.
If a message interrupts a combined input result, cancel that result's gesture
and do not activate a control after deciding to return.

On FINISH, borrowed work-area contents need an ordinary application repaint;
the binding cannot reconstruct the caller's model. Retain one coalesced local
repair fact for that window/open epoch, independent of the deferred slot. Expose
it as WM_REDRAW on a subsequent message wait, after the interrupting deferred
message and before later queued messages. Repeated repairs union; close/reopen
retires the fact. This requires neither an `appl_write` to self (which could
fail on a full queue) nor a saved screen image that could become stale behind
another window. The caller must resume its event loop to restore its content.

Temporary-window close uses existing Layers damage and focus restoration.
Do not raise the dialog repeatedly or steal focus back after the user selects
another application. Borrowed-window finish preserves the current focus.
Closing the temporary host restores focus through existing desktop policy.

## Alerts

Parse `[icon][line|line][button|button]` once into an upper-memory ten-object
tree and private strings. Adopt the donor bounds: up to five 40-character
message lines and three 20-character button labels. Accept icons 0 through 3
(none, note, question and stop), doubled `||`/`]]` literals and an input bound
of 511 bytes excluding NUL. Require one to three nonempty buttons;
`default_button == 0` means none, otherwise it selects a one-based button.
Malformed syntax/invalid default returns zero with `AES_MALFORMED`; unsupported
icon or bounds return zero with `AES_UNSUPPORTED`. Do not silently truncate.

Use fixed 8x8 metrics, centered text/button layout and the existing flat GEM
button style. Layout must fit the chosen host; failure leaves the application
content unchanged. The three fixed monochrome 32x32 donor icons may be rendered
as precomputed horizontal fill runs through existing clipped drawing. Keep
their masks/runs in upper memory and pin copied assets through extraction.
This does not expose G_IMAGE, BITBLK or a general raster-copy API. Compose icon
and text exposure repair in the same bounded draw path; do not import the
donor's near-bank bitmap buffer or screen-wide save/restore code.

Use the same form interaction and lifetime implementation. Return/Space and
pointer acceptance return the chosen one-based index. Escape only cancels a
held press; there is no implicit affirmative or Cancel selection. The window
closer can dismiss a temporary alert; application-window close interrupts a
borrowed alert as above. Zero must never be interpreted as consent.

## Cleanup and resource cost

End the caret, cancel transient feedback, release owned draw locks, then close
and delete only an internally created host and close only an internally opened
workstation. Release storage after its last consumer has retired. Preserve an
interruption/failure diagnostic across successful cleanup calls; cleanup failure
takes precedence and retains the affected storage for normal teardown/retry.
`appl_exit` must also finish an abandoned explicit session before freeing its
resource tree, view or workstation. No forced Task removal or premature grant
free is introduced.

Trust valid tree links, indices, strings and caller-owned lifetimes. Check
normal operational limits at entry/allocation and parse alert strings once;
do not audit trees on each key, draw or dispatch layer. The caller keeps its
tree and TEDINFO storage live until the form/session is finished.

Target reserved bank-zero delta: **0 fixed, 0 per public Task, 0 private idle**,
including guards, alignment and unused capacity. Use current Task pools and
VRAM staging. Upper-memory additions are session state, an optional alert
tree/strings, shared icon data, the repair fact and ordinary temporary window/
workstation allocations. Record actual live and reserved sizes in implementation.
Retain the [stack-headroom](application-stack-headroom-implementation-plan.md)
128-byte measured-margin gate on ordinary Tasks. If a deeper call path needs
more stack, measure and justify a small pool increase rather than forcing a
renderer refactor; report its exact bank-zero cost and boot-arena impact.

Existing Files dialogs keep their event-driven implementation: they service
child completion and application-specific window events while editing. A small
dialog example proves the new synchronous API without rewriting Files or the
calculator solely to provide a test.

## Development evidence

Test emitted named/AESPB behavior, concurrent independent forms, message
provenance and interruption, full message queues, redraw after overlap, temporary
window exhaustion, focus, every setup/cleanup failure boundary and guard/heap
return. Exercise physical keyboard/pointer input as well as injected events.
Include a rapid-typing case that records capture, routing and insertion rather
than waiting for each character to be committed before sending the next.

Refresh and run the exact OF816 desktop ZIP with the normal shell, counter and
panel, then launch the dialog example within current Task/window capacity.
Record stack margins and resource costs. These are development checks;
hardware boot qualification and the open HY4/PI4 latency gates remain separate.
