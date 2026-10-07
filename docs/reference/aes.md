# AES application service

[Reference](README.md) · [C application guide](../guides/aes-applications.md) ·
[Development record](../history/aes-server.md)

The optional AES endpoint runs in the existing desktop presenter. Registration,
exit, window mutations and GUI locks use ordinary Exec RPC; copied messaging and event/timer waits
run in their callers. This adds no Task or kernel gateway. The native desktop
and retained Control Panel remain independent clients of their existing service.

The current source profile in [gem.h](../../c/include/gem.h) implements
`appl_init`, `appl_exit`, `appl_write`, `evnt_keybd`, `evnt_button`,
`evnt_mesag`, `evnt_timer`,
`evnt_multi`, `evnt_multi_moblk`, `wind_update`, `wind_create`, `wind_open`,
`wind_close`, `wind_delete`, `wind_get`, `wind_set`, `wind_set_str`, `wind_calc`,
`graf_handle`
and the corresponding `aes_call(AESPB *)` operations.
Other opcodes return zero with `ExecAESDiagnostic() == AES_UNSUPPORTED`.
This is a rebuilt Calypsi source interface, not a GEM binary ABI or a complete
AES implementation. Resource and form calls are pending. Selected
[private VDI workstation calls](gem-vdi.md#resident-application-workstations)
execute directly in the caller.

Startup retains the endpoint returned by `AESBOOT.Port()` until every C Task
has detached. Each application wrapper calls `ExecAESAttach(endpoint)` before
its GEM entry and `ExecAESDetach()` before ordinary Task removal. Detach calls
`appl_exit` if needed, collects its reply, then deletes the private port/context.
Failure to detach must prevent Task/image retirement. There is no forced client
recovery or discovery by name in this profile.

Each attached Task owns private parameter arrays, a request and reply port;
there is no process-global GEM parameter block. Four applications can register
at once. Successful init returns a positive signed 16-bit ID; repeated init on
the same live binding returns that ID. Exit returns one. Failed init returns
minus one. GEM IDs are never reused within a service lifetime. Native identities
and request sequences are separately checked 32-bit values; exhaustion fails
before reuse, reserving the last sequence for exit.

Registration also publishes a caller-owned receive port, sixteen 32-byte
application message records and one 36-byte GUI delivery record in the service's
shared endpoint directory. This directory works
across separate C binding instances. Its lookup, publication holds and recycling
use short Task-side `Forbid` guards; interrupts do not access it. Exit withdraws
admission, waits for existing publishers without blocking the presenter, drains
the port and acknowledges retirement before the caller frees its storage.
Direct calls validate their registration and one-call occupancy without advancing
the RPC sequence. Both named wrappers and parameter blocks use the same helpers.

`appl_write(id, 16, words)` reserves a destination-owned record, copies eight
words and publishes it with Exec `PutMsg`. It releases its independent endpoint
hold without touching the published record. FIFO order is publication order;
each registration has sixteen entries. Success means published; a full queue
returns zero with `AES_RESOURCE`, without replacing an older message or waiting
for space. Other lengths and invalid pointers fail with `AES_MALFORMED`;
unknown/retired IDs fail with `AES_IDENTITY`. The sender may reuse its buffer
after return. Borrowed pointer payloads and long messages are unsupported.

The internal GUI producer has a separate reserved record on the same receiving
port, so it does not reduce the sixteen-entry application capacity. Per-window
pending redraw/top/move/close facts remain in the presenter while that record is
queued. Repeated pending redraws union their bounds; repeated moves retain the
latest proposal. First-pending order between kinds is preserved, and published
records are immutable. Recycling the GUI record wakes the existing service
signal only when further GUI work needs it. This introduces no polling or
additional application wait mechanism. Redraw delivery remains durable while an
application is delayed or its ordinary message queue is full.

An open epoch identifies GUI records independently of their GEM payload. The
caller drops retired service-originated notifications before selecting message
readiness, without dropping ordinary `appl_write` messages with similar words.
Closing/reopening can therefore retire old GUI work without waiting for the
blocked application to receive it. GUI storage remains registration-owned until
the existing exit withdrawal, publication holds and receive-port drain complete.

`evnt_mesag(words)` returns one after copying the oldest queued message, or
blocks the application on its private receiving-port signal until a message
arrives. It recycles the detached record after copying. Other applications and
the presenter continue. Exit discards any queued messages.

`evnt_timer(lo, hi)` reconstructs an unsigned 32-bit millisecond duration and
returns one when its absolute VBI-clock deadline expires. Conversion uses the
reported 50/60 Hz rate, rounds upward and adds one tick to prevent early expiry.
Standalone zero delay therefore waits at least one tick. Overflow returns zero
with `AES_OVERFLOW`. This operation runs in the caller, without presenter RPC or
request-sequence advancement. The named wrapper and parameter-block opcode use
the same helper.

`evnt_keybd()` waits for one GEM scan/ASCII word. `evnt_button(clicks, mask,
state, ...)` waits for a left-button condition and returns one with the selected
screen coordinates, buttons and modifiers. Supported arguments are `mask=1`,
`state=0/1`, and `clicks=1` or `$0101`. The latter inverts the equality predicate;
it does not request multiple clicks. Other button arguments fail as a whole
with `AES_UNSUPPORTED`.

`evnt_multi` supports all fifteen nonempty combinations of `MU_KEYBD`,
`MU_BUTTON`, `MU_MESAG` and `MU_TIMER`. At one frozen decision it selects at most
one key, one matching button condition and one message. It scans at most sixteen
retained button transitions before considering an eligible current level; older
nonmatching transitions retire together with the selected match. A quick down/up
is retained. A down-level wait may return repeatedly while the button stays held.
The application normally changes its next wait to release after accepting down.

Input waits require an open application window; otherwise they return zero with
`AES_IDENTITY`. Message/timer-only calls still work without a window. Unselected
button and rectangle arguments are ignored. Empty/unsupported event masks,
rectangle events, right/middle buttons and multiple clicks fail explicitly.
The named wrappers, `evnt_multi_moblk` and correctly sized AES parameter blocks
use this same implementation. Key/button opcodes are 20 (0/1/0/0) and 21
(3/5/0/0); multi remains 25 (16/7/1/0).

A button result supplies the selected button snapshot. A key-only result supplies
the pointer snapshot captured when that key was published. When both return,
modifiers are ORed; when neither returns, the result uses the last coherent
presenter pointer snapshot. Key and click outputs are zero when their bits are
absent. Native Shift maps to GEM left-Shift (2) and Control to 4; there is no Alt,
separate right Shift or standalone Control-click guarantee.

Matching runs in the caller on registration-owned upper-memory scratch, using
the existing receive-port signal and one absolute timer alarm. Interest is
published before the final readiness check. Signals are hints and can arrive
without a message; no signal is cleared between an empty observation and Wait.
Each record copy has a short guard; the bounded FIFO scan and timer I/O run
outside guards. Successful alarm completion proves expiry; other readiness
checks the clock for a simultaneously due timer. Spurious wakes do not restart
the interval or issue redundant clock reads. Zero-duration `MU_TIMER` is ready
immediately and submits no alarm; standalone `evnt_timer(0,0)` still waits at
least one tick.

The caller freezes readiness and result snapshots, retires an outstanding alarm,
then rechecks only lifetime/loss epochs before committing consumer positions and
detaching a message. Later arrivals remain for the next decision. Capture/FIFO
loss returns zero with `AES_INPUT_LOST` and retires only the lost selected source;
unrelated input/messages remain queued. Message/timer-only calls leave input
loss pending. Close/reopen withdraws the input lifetime. Source epoch exhaustion
returns `AES_OVERFLOW` until a fresh open lifetime.

A clock/device failure returns zero with `AES_TIMER_ERROR` for timed waits and
preserves all selected payloads. It does not automatically reopen the timer;
retire and reinitialize the registration for a fresh binding. Untimed input and
message calls remain available. Waits allocate no input signal, make no presenter
RPC, acquire no display grant and hold no Layers transaction while blocked.

`wind_update` arbitrates recursive update and mouse-control ownership between
registered AES clients. `BEG_UPDATE` acquires update ownership and its implicit
mouse hold together; `BEG_MCTRL` adds an explicit mouse hold. Matching END calls
remove only their corresponding hold. Wrong-owner release returns zero with
`AES_IDENTITY`; nesting overflow returns `AES_OVERFLOW` without changing either
hold. `0x100` on a BEGIN call tries without waiting, returning zero with `AES_OK`
if unavailable. A normal contended BEGIN waits in arrival order among eligible
callers; an existing mouse owner can upgrade without waiting behind a dependent
peer. Exit releases every owned hold. Message and timer service continue.

Update ownership also excludes native console painting/scrolling, widget
feedback, background repair and cache capture. Mouse ownership defers native
widget gestures, focus and geometry changes; an explicit mouse hold alone
allows console painting. Acquisition waits for already admitted drawing and
hardware/scene tokens to retire. Pending acquisitions stop new conflicting work,
so continuous output cannot starve an application lock. The service holds no
Layers token while an application owns a lock.

Input capture and the serialized cursor path continue. Sixteen copied pointer
records retain deferred gestures, coalescing adjacent motion; overflow reports
input loss and cancels the gesture after release. Keyboard widget events retain
the existing bounded queue. Unlock or owner exit resumes retained controls,
gestures and damage without another input edge. Blocked paint alone does not
keep the presenter runnable. Device completions and cancelled console writes
can retire while drawing is excluded.

Each registration can own one window; native and GEM windows share four desktop
slots. The supported kind is `NAME | CLOSER | MOVER`. Create reserves a hidden
window and returns a positive handle, or minus one on failure. Open shows it;
close hides it and retires the open epoch without deleting the handle. Delete
requires a closed window. Exit closes and deletes any remaining window. Handles
are not reused during a service lifetime. The initial profile permits moves at
individual pixel positions, fixed dimensions of at least 32 by 32, and bounds
fully inside the 640 by 240 desktop. Resizing and off-screen bounds fail without
mutation.

`WF_NAME` copies at most 64 characters plus terminator from the high-word,
low-word packed address; `wind_set_str` performs that packing. `WF_CXYWH` moves
the window and `WF_TOP` raises it. Work insets are left/right 8, top 16 and bottom
8 pixels. `wind_calc` converts border/work rectangles locally; `wind_get`
provides `WF_KIND`, `WF_CXYWH`, `WF_WXYWH` and `WF_TOP` from published state.
`WF_CURRXYWH` and `WF_WORKXYWH` are aliases. Handle zero permits desktop work and
top queries; a native top window is reported as zero.

`WF_FIRSTXYWH`/`WF_NEXTXYWH` enumerate visible work rectangles locally while the
caller owns `BEG_UPDATE`. The presenter publishes the snapshot on acquisition;
no client reads Layers or retains a scene token. A zero-width/height result ends
the enumeration, including a completely covered or hidden window. An owner
mutation invalidates a previous iterator; restart with FIRST. Geometry uses
half-open internal bounds and GEM x/y/width/height at the binding.

Title clicks, completed title drags and closer clicks deliver `WM_TOPPED`,
`WM_MOVED` and `WM_CLOSED` requests. The presenter commits them only when the
application calls the corresponding set or close operation. Inactive clicks
request top first. The existing native-window behavior is unchanged.

For application windows the presenter paints the frame and transfers work-area
damage into durable `WM_REDRAW` delivery. Its explicit Layers handoff retires
manager damage after the complete frame transaction without claiming that the
application pixels have been drawn. Such windows remain ineligible for pixel
copy, copied move and VRAM-cache reuse. Applications reconstruct their work pixels through their private VDI workstation
while owning `BEG_UPDATE`.

`global[0]` is zero to avoid advertising a complete AES version, `[1]` is four,
`[2]` is the application's ID, `[10]` is four display planes, and other words
are zero. The binding exposes transport/resource errors through
`ExecAESDiagnostic()` without inventing successful GEM return values.

Registration retains the owner's Task lease and validates its original packet,
owner and reply-port relationship on subsequent calls. Requests and buffers
remain caller-owned storage, lent until the single reply is collected. This is
a cooperative shared-memory ownership contract, not memory protection against
malicious applications. Normal service shutdown refuses live registrations.

Each client lazily opens `timer.device` for timed waits, with a
private reply port and two 38-byte records: a clock query and borrowed alarm.
It publishes outstanding ownership before `SendIO`, collects exactly its reply,
and closes the original open before freeing those records on exit. Up to four
client opens fit within the device's eight-open limit; competing users can still
exhaust capacity. The presenter has no timer binding. Setup failure releases every
acquired resource and leaves message-only calls usable.

The presenter handles registration, retirement, GUI locks and its own pending
GUI delivery. Pending publishers retain an exit wake path; lock settlement and
native input/drawing gates remain active. Application message matching and
timer waits stay caller-local. There is no presenter application-message FIFO,
event-wait scan, timer alarm or periodic AES wake.
Native and AES requests share at most four admissions per turn, alternating the
first endpoint on ordinary turns. When painting or a widget gesture can advance,
at most three native requests precede the existing paint quantum, then one AES
request is admitted after it. Both phases share the four-request limit; AES is
not deferred across an entire repaint. Caller-owned messages and timer completions do not use that intake budget.
The presenter services captured input before controls when signalled, after
each native/AES admission (including native deferral), after a cache/move token
retires, after actual paint work, and after releasing a borrowed console view.
These boundaries collect input and present the pointer when drawing is
quiescent; they add no Yield or periodic wake. Widget model changes stay after
native control admission and respect the existing scene/AES ownership gates.
Each turn gives GUI painting its bounded quantum before new console
output. Widget strips can drain up to four ready steps, with captured input and
pointer presentation between them; each object step draws at most one object
part and examines at most eight objects. Frame work is a separate step when
needed. These steps share
the same control/output budgets and scene token. Ready paint may continue without a voluntary Yield; VBI preemption
provides Task fairness, and blocked work retains the ordinary signal wait path.
When painting releases the scene with a native control already pending, one new
console-output quantum may be deferred to admit that control. An eligible output
quantum must run before another such deferral, preserving writer progress.

The generated [wire ABI](../../abi/aes-server.json) is private to this source
profile: version 8 has a 112-byte request and permits init, exit, update,
window mutations and cold display delegation on the RPC endpoint. Queries and rectangle conversion are local. Public GEM arrays remain private to each caller. Rebuild
bindings and service together. Current implementation and
development evidence are tracked in the
[hybrid implementation plan](../plans/gem4xe/hybrid-aes-implementation-plan.md).

Version 8 reserves a 594-byte upper-memory input inbox per registration alongside
the existing sixteen ordinary messages and one GUI record. The combined storage
is 1,142 bytes, rounded to 1,144 by the heap. Each endpoint gains a padded
four-byte inbox pointer, adding sixteen bytes to the shared directory. The
registration owns this storage until endpoint withdrawal and publisher holds
retire. This adds no signal, Task or bank-zero reservation.

The inbox contains separate sixteen-record key/button FIFOs, immutable source
epochs, selected-input interest and a coherent snapshot. Relevant input uses the
receiving port's existing signal as a wake hint; it is not a message. Source loss
stops admission until the caller acknowledges it without discarding unrelated
messages/input. Exhausting a source epoch stops it until a fresh open-window
lifetime. [AI2](../plans/gem4xe/aes-application-input-implementation-plan.md#ai2--add-bounded-inboxes-and-safe-wakeups)
established this transport; AI3–AI5 add production routing and public input waits.

## Resident counter capacity

The optional [counter desktop](../guides/aes-applications.md#optional-of816-counter-desktop)
runs two independent GEM applications beside the native shell. Its resident
controller also registers to send shutdown messages: three registrations are
used, and shell plus counters occupy three desktop layers. Prompt services use
six public Tasks, leaving exactly two slots for a disk-command pipeline. The
native Control Panel is replaced in this bundle; adding it would leave only one
Task slot after disk services start. The separate four-layer coexistence proof
uses root-driven disk I/O rather than pipeline children.

All clients must detach before service shutdown. Closing a focused window clears
focus under the current desktop policy; click another window to restore it.
No auto-focus successor, resize, menu, resource loader or dynamic GEM launcher
is supplied. [WA6](../history/aes-windows.md#wa6--coexistence-and-the-of816-demo)
records development coverage and measured stack use, not hardware qualification.

The presenter now publishes translated keyboard records into the private input
inbox for each open AES window. The capture-time route selects the recipient,
including keys queued before a focus change. Close drains and retires that route;
reopen creates a fresh one. GEM translation uses the pinned Atari mapping and
shared Caps state. Ctrl-C is delivered as a key; physical BREAK becomes Escape,
except when a native title gesture consumes it. Public input waits consume these
records directly in their caller.

Private button routing now retains the focused work-area recipient through
release, even outside its window. Activation/chrome sequences remain native.
`BEG_UPDATE` permits application input; explicit mouse control redirects content
to its open-window owner without changing keyboard focus. A competing lock waits
for the physical sequence to end. Close/loss requires observed release before
rearming. Eligibility handback can signal a waiting caller without a new edge.
The public `MU_BUTTON`/`evnt_button` waits consume the retained transitions and
eligible levels without a presenter RPC.
