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
AES implementation. The object/form, resource and menu subsets are described
below. Selected
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
slots. The base kind is `NAME | CLOSER | MOVER`, optionally combined with `SIZER`,
`UPARROW`, `DNARROW` and `VSLIDE`. Create reserves a hidden
window and returns a positive handle, or minus one on failure. Open shows it;
close hides it and retires the open epoch without deleting the handle. Delete
requires a closed window. Exit closes and deletes any remaining window. Handles
are not reused during a service lifetime. The initial profile permits moves at
individual pixel positions and bounds fully inside the 640 by 240 desktop.
Fixed windows have a 32 by 32 minimum and reject dimension changes. SIZER
permits dimensions of at least 64 by 48; vertical gadgets require height 80.
Off-screen bounds fail without mutation.

`WF_NAME` copies at most 64 characters plus terminator from the high-word,
low-word packed address; `wind_set_str` performs that packing. `WF_CXYWH` moves
or resizes the window and `WF_TOP` raises it. Work insets are left/right 8,
top 16 and bottom 8 pixels. Vertical gadgets increase the right inset to 16;
SIZER increases the bottom inset to 16. `wind_calc` converts border/work rectangles locally; `wind_get`
provides `WF_KIND`, `WF_CXYWH`, `WF_WXYWH` and `WF_TOP` from published state.
`WF_CURRXYWH` and `WF_WORKXYWH` are aliases. Handle zero permits desktop work and
top queries; a native top window is reported as zero.

`WF_VSLIDE` and `WF_VSLSIZE` (`WF_VSLSIZ`) set/query 0..1000 position and
size, initially 0 and 1000. Frame pixels are cached at mutation; minimum thumb
height is eight pixels. Horizontal scrollbars are unsupported.

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

Size release sends `WM_SIZED` with proposed outer x/y/w/h. Vertical thumb
release sends `WM_VSLID` with 0..1000 in word 4; arrows and track clicks send
`WM_ARROWED` with `WA_UPLINE`, `WA_DNLINE`, `WA_UPPAGE` or `WA_DNPAGE`.
Applications accept sizes through `WF_CURRXYWH`, and publish their own slider
values after scrolling. These gestures never change client content by themselves.
Size/thumb outlines are nonblocking and cancellable; arrow/track release outside
cancels. Hold repeat, horizontal gadgets and live resizing remain unsupported.

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
profile: version 11 has a 112-byte request and permits init, exit, update,
window mutations, cold display delegation and session mouse preferences on the
RPC endpoint. Queries and rectangle conversion are local. Public GEM arrays remain private to each caller. Rebuild
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

All clients must detach before service shutdown. Closing a focused window
restores the frontmost remaining shown, routable owner. Closing a background
window preserves focus. Fixed-size windows remain the supported geometry.
Window-scoped menus and resource loading are described below. [WA6](../history/aes-windows.md#wa6--coexistence-and-the-of816-demo)
records development coverage and measured stack use, not hardware qualification.

The presenter now publishes translated keyboard records into the private input
inbox for each open AES window. The capture-time route selects the recipient,
including keys queued before a focus change. Close drains and retires that route;
reopen creates a fresh one. GEM translation uses the pinned Atari mapping and
shared Caps state. Ctrl-C is delivered as a key; physical BREAK becomes Escape,
except when a native title gesture consumes it. Public input waits consume these
records directly in their caller.

The desktop reserves Ctrl+Tab/Ctrl+Shift+Tab for window cycling and Ctrl+Escape
for its Windows menu when no pointer/title gesture is held. While that menu is
open, navigation, selection and cancellation keys are consumed by the presenter
before application delivery. These commands use the existing top/close notices;
they do not add another application event transport.

Private button routing now retains the focused work-area recipient through
release, even outside its window. Activation/chrome sequences remain native.
`BEG_UPDATE` permits application input; explicit mouse control redirects content
to its open-window owner without changing keyboard focus. A competing lock waits
for the physical sequence to end. Close/loss requires observed release before
rearming. Eligibility handback can signal a waiting caller without a new edge.
The public `MU_BUTTON`/`evnt_button` waits consume the retained transitions and
eligible levels without a presenter RPC.


The [interactive example](../../examples/gem-input/input.c) exercises the input
profile with local hit testing, pressed/released drawing and a translated-key
label. Its [guide](../guides/aes-applications.md#interactive-application-example)
includes the optional `--aes-input` OF816 build. The application object/form and resource subsets below extend this profile.

## Application object trees and forms

`gem.h` declares the standard 24-byte `OBJECT`, 8-byte `GRECT` and 28-byte
`TEDINFO` layouts. Application-owned trees support `G_BOX`, `G_IBOX`,
`G_STRING`, `G_TITLE`, `G_BUTTON`, `G_TEXT`, `G_BOXTEXT`, `G_FTEXT` and
`G_FBOXTEXT`; SELECTED/DISABLED state; SELECTABLE/DEFAULT/EXIT/EDITABLE/
RBUTTON/LASTOB/HIDETREE flags. The caller supplies valid links, indices and huge string pointers,
with at most 32 objects, eight levels and 63 characters per label. Coordinates
are pixels. Unsupported object types, indirect specs and user callbacks are
outside this caller contract.

`G_TEXT` and `G_BOXTEXT` use a TEDINFO addressed by `ob_spec`, with full
32-bit text/template/validation addresses. Noneditable text supports the IBM
system font, left/right/center justification, the GEM color word and signed
border thickness. A negative thickness draws the box border outward; drawing
includes that extent in its clip. The caller owns the NUL-terminated text and
repaints after updating it.

`objc_edit(tree, object, key, &index, kind)` provides caller-local single-line
editing, also through AESPB opcode 46 (4/2/1/0). ED_START is a no-op; ED_INIT
places the caret at the end; ED_CHAR edits; ED_END removes the caret. Text
capacity `te_txtlen` includes NUL and is 1–128 bytes. Templates and validation
strings are at most 63 characters. Formatted types replace underscore slots
with text, bounded by both the slot count and capacity. Full fields reject
additional insertion. Ordinary fields scroll horizontally to show the caret.
The IBM 8×8 renderer shows at most 63 characters per field.

Support includes insertion, Backspace, Delete (both $5300 and GEM $537F),
left/right, Home/End and Escape-to-clear. ASCII validation classes 9/A/a/N/n,
F/f/P/p and X/x follow GEM case folding; a short validation string repeats its
last class. X preserves case; x folds to uppercase. The path classes also
accept `/` for Exec paths. Extended-character classes, selection ranges,
clipboard and multiline editing are unsupported.

One edit association/index/viewport is retained per caller in upper memory;
ordinary `objc_draw` repairs its steady caret. There is no caret timer.
`objc_edit` takes and releases UPDATE around its complete clipped field redraw;
recursive UPDATE ownership is supported. End editing before replacing/freeing
the tree. Normal application teardown clears the association.

`objc_draw`, `objc_find`, `objc_offset`, `objc_change`, `form_center`,
`form_keybd` and `form_button` have named and AESPB bindings with their GEM
opcodes/counts. Drawing requires an open workstation/window and BEG_UPDATE;
the explicit object clip is intersected with the caller's visible work area.
VDI's separate clip does not change the AES object clip. Local geometry and
state changes do not contact the presenter or copy the tree. `form_center`
centers within the caller's work area.

The form subset is windowed and event-driven: `form_button` commits an accepted
release/keyboard action without waiting or drawing. It toggles selectable
buttons, selects radio peers exclusively, and returns zero for a momentary EXIT
button. `form_keybd` navigates selectable and editable controls with Tab/Shift-Tab,
activates button focus with Space and DEFAULT with Return; Space remains an
unconsumed editing key on a field. `form_button` focuses EDITABLE without
toggling SELECTED; it reports the next object and
unconsumed key. These are deliberate departures from modal GEM form handling.
The application tracks press/cancel and redraws changed objects. It continues
handling WM_* messages in `evnt_multi`.

`form_do(tree, start)` (opcode 50, 1/1/1/0) now supplies a synchronous,
caller-local loop. It reuses the editor and form helpers, waits through the
existing event engine, and takes UPDATE only for painting. Zero start chooses
an editable field, then a button; Tab/Shift-Tab traverses controls and Up/Down
traverses fields. A press previews selection; an inside release commits and an
outside release or Escape cancels it. Entry/loss waits for release before a new
press. No motion/hover feedback is promised. Return activates DEFAULT; Space
activates a focused button. Accepted EXIT returns its index with SELECTED set.

A direct call creates and finishes an implicit session. START permits repeated
calls on the same tree until FINISH. Temporary windows accept movement and
close locally. Borrowed move/size/scroll/close, menu and ordinary application
messages interrupt with **-1 / AES_PENDING**, preserving the exact message for
the next wait. Check for a negative result before indexing the tree. Temporary
close returns -1 / AES_OK; failures also return -1. GUI provenance distinguishes
redraws from ordinary WM-shaped messages. Recursive forms, TOUCHEXIT,
double-click result bits and desktop-wide modal ownership are unsupported.

`form_dial` now provides START/FINISH host lifetime (opcode 51, 9/1/0/0).
START borrows a shown application window or creates a temporary ordinary
NAME/CLOSER/MOVER window when the caller has none. It opens a private workstation
only if absent. The requested form rectangle must fit; an allocated closed
window, existing session, edit association or held UPDATE/MCTRL prevents START.
`form_center` can compute a desktop-centered rectangle before window creation.
GROW/SHRINK succeed without animation inside a started session. Caller drawing
still takes a short UPDATE section.

FINISH closes only owned resources. Borrowed content receives a local WM_REDRAW
repair on the next message wait, after any deferred message and before queued
messages. Repair is tied to the open epoch and does not need queue capacity.
Cleanup failure retains the session for retry; `appl_exit` also finishes an
abandoned session. No Task, bank-zero or VRAM reservation is added. The C context
is now 340 live / 344 heap-reserved upper bytes. See the
[dialog development record](../history/standard-dialogs.md).

`form_alert(default_button, text)` (opcode 52, 1/1/1/0) uses the same implicit
session. It accepts `[icon][line|line][button|button]`, icons 0–3, up to five
40-character lines, three nonempty 20-character buttons and 511 source bytes
excluding NUL. Doubled `||` and `]]` represent literal delimiters. Default zero
means none; otherwise it names a one-based button. Malformed syntax/default
returns zero / AES_MALFORMED; bounds or unsupported icons return zero /
AES_UNSUPPORTED. Fit/capacity failure returns zero / AES_RESOURCE before painting.

Acceptance returns a one-based button number. Interruption, dismissal or failure
returns **zero**; inspect `ExecAESDiagnostic()` and never interpret zero as consent.
Return uses DEFAULT, Space uses button focus, and the temporary closer dismisses.
The fixed monochrome donor icons use clipped fill runs; this adds no general
G_IMAGE or raster API. Alert storage survives a failed retirement until FINISH
or application teardown can complete. Session storage is 315 live / 320 reserved
upper bytes; an alert adds 514 live / 520 reserved bytes. Both named calls and
AESPB dispatch use C component ABI 9; rebuild GEMSYS and applications together.

The application binding reuses the extracted GEM4XE routines with its own GSX
scratch, protected by the existing display grant. The native retained widget
binding remains presenter-owned. No additional bank-zero reservation is needed.


## Resources and popup menus

`rsrc_load`, `rsrc_free`, `rsrc_gaddr(R_TREE, index, &tree)` and `rsrc_obfix`
provide named and AESPB bindings (110/111/112/114). Load accepts classic
big-endian version-zero RSC files, at most 65,535 bytes, 256 objects and eight
trees, using the object/string subset above. Each tree ends with LASTOB within
32 objects. Up to 256 TEDINFO records support the text types above. Templates
and validation strings are NUL-terminated, at most 63 characters. Load fixes full
upper-memory addresses. Noneditable records normalize text/template lengths to
string length plus NUL, including files with zero length fields. EDITABLE records
preserve their declared 1–128-byte text capacity; the complete writable extent
and its initial NUL must be present in the file. Shared TEDINFO records are fixed
once. Text remains writable within the resource's supplied buffer.
The shipped `CALC.RSC` uses this contract for its twelve-byte numeric display
buffer. `CALC.APP` keeps the loaded tree private to each Process instance.
Icons, bitmaps, 3D flags, extensions and indirect specs are unsupported.
Character coordinates use the fixed 8×8 cell. File extents and string offsets are
checked once during loading; valid object links remain the caller's responsibility.
Already loaded coordinates are pixels and must not be passed through obfix again.

Each caller owns one resource allocation in upper RAM. Failed replacement leaves
its previous resource intact. Explicit free or successful appl_exit releases it;
borrowed tree/string pointers then expire. Application strings assigned to an
object remain application-owned.

`menu_bar`, `menu_popup`, `menu_ienable`, `menu_tnormal` and `menu_text` have named
and AESPB bindings (30/36/32/33/34). Popup menus have one level of direct children, no scrolling
or cascades, and must fit their owning window's work area. The caller supplies a
valid MENU/tree and keeps strings alive; enter without an UPDATE lock. Button release, Tab/Up/Down, Return and
Escape select or cancel. The popup acquires UPDATE only while painting and uses
ordinary caller-local evnt_multi waits. On return it restores tree positions and
states; the application repaints the underlying content. Non-redraw window
messages cancel the popup and are preserved in one deferred caller-local slot,
consumed by the next message wait. This adds no kernel signal or service queue.
`menu_bar(tree,1)` installs one borrowed application tree; `menu_bar(tree,0)`
withdraws it. Other modes fail. Installation does not focus the application and
may precede its window. The focused shown window selects the visible bar; no
installed menu uses the desktop fallback. Windows remains available at x=432.
`wind_get(0,WF_WXYWH)` returns `(0,16,640,224)`.

The supported tree has root children for the bar and dropdown container. The
bar's active container holds G_TITLE siblings paired in order with G_BOX
siblings under the dropdown container. Items are direct G_STRING children.
G_IBOX containers, selected/disabled/hidden states, 32 objects, depth eight and
63-byte labels are supported. Titles fit x=0..431; dropdowns fit 640×224 and
are repositioned on screen without changing their dimensions. Font is 8×8.
Cascades, scrolling bars, accessories, icons, check marks and editable menu
objects are unsupported. Valid pointers, links and indices remain caller-owned.

Installed-tree enable, title-state and text setters execute at a presenter paint
boundary, including while the caller owns UPDATE/MCTRL. Uninstalled helpers act
locally. `menu_text` replaces a borrowed string pointer within unchanged object
geometry; after a successful replacement returns, the old label is no longer
borrowed. Keep current labels alive and withdraw before freeing the tree or its
RSC. `appl_exit` withdraws before automatic resource cleanup. Window close retains the
installation for reopen but invalidates its commands.

A selection returns `MN_SELECTED` through `evnt_mesag`/`evnt_multi`:
`[10,0,0,title,item,tree_hi,tree_lo,box]`. The command belongs to the original
application even if focus changes. One command can await consumption and
`menu_tnormal(tree,title,1)` acknowledgment; both are required before another
selection. No ordinary `appl_write` record is consumed by menu delivery.

Click a title then an item, or drag from title to item and release. Crossing
headings switches menus. Disabled/hidden entries cannot activate. Outside click,
Escape, BREAK and input loss cancel without passing the click to a window.
Ctrl+Shift+Escape enters the application menu; Left/Right changes titles,
Up/Down or Tab/Shift+Tab selects entries, and Return activates. Ctrl+Escape opens
Windows; Ctrl+Tab/Ctrl+Shift+Tab retain window switching.

The private C context is 308 bytes. Rebuild bindings and applications with
C import ABI version 5.
The server wire record remains 112 bytes; all bank-zero reservations are unchanged.

## Small GEM desktop

`tools/build_demo.py --gem-desktop` runs a Control Panel, counter and Files beside
the shell. Files loads `SYS:DESKTOP.RSC`, caches up to 256 directory entries and shows up to sixteen reusable rows,
adapting the count and width to its work area. Arrows, page clicks and the vertical
thumb scroll continuously; keyboard selection follows into view. Refresh preserves
the selected filename. Directories above the limit report a truncated listing.
Files launches native Exec commands or C/GEM APPs using Program/Process. Its
application menu offers Open, Refresh, Stop, Quit, Path, New Folder and Rename; its window-scoped File
popup retains Open, Refresh, Stop and Cancel. Open and Stop reflect selection
and child availability, and menu Quit shares the ordinary close path.
Path (P), New Folder (N) and Rename (R) use compiled-in OBJECT/TEDINFO dialogs
inside Files' existing window. Tab/Shift-Tab, Return, Escape and mouse OK/Cancel
operate them. Fields use GEM uppercase folding for the current disk formats.
The other applications keep running. Path validates a directory
before replacing the snapshot; New Folder/Rename accept one leaf name and
preserve operational errors and entered text. Success refreshes and selects the
result; Cancel does not mutate the filesystem. Files continues servicing
geometry, exposure, child completion and close while a dialog is open. A launched command
has an empty argument tail, NIL input and RAW output in the shell; closing Files
requests native BREAK or GEM close and collects the child before Task retirement.
The three APPs use the [C image profile](c-program-loading.md); Atari ST binaries
and GEM4XE G4A files remain unsupported. Current VDI rectangles and fixed-font
text suffice. Initial apps belong to the shell; Files owns its one launched
child. Closed apps are collected at the idle prompt. `RUN C:FILES.APP` uses the
shell background job to reopen Files.

Three AES registrations and all four application-window slots are used (plus two private menu layers). Seven idle public
Tasks leave one slot for a launched command. Close one GEM window before a
shell pipeline needing two children. TICK is a disk-loaded cancellation demo;
PRIMES requires tiled-console mode and returns an error in desktop mode.
This optional profile does not change the
default shell/prime demo or its five-second OF816 autoboot.

## Session mouse preference

`ExecAESMouseProfile(profile)` in `<exec816/aes.h>` is an Exec816 extension,
separate from standard GEM. A registered application supplies `AES_MOUSE_OFF`
(fixed 2× motion), `AES_MOUSE_MILD` (the existing accelerated curve) or
`AES_MOUSE_QUERY` (-1). The result is the chosen profile; -1 indicates failure,
with `ExecAESDiagnostic()` supplying the cause. Valid enum use belongs to the
caller. AES wire version 9 adds operation 201 without changing record layouts;
C application import ABI 5 exports the binding. Rebuild the runtime and apps.

The presenter serializes this infrequent request with input processing. It
preserves pointer coordinates and clears fractional motion when the profile
changes. An already processed held-button gesture retains its old profile
through the release event; the latest requested choice then takes effect.
Input loss also ends that gesture. Query reports the chosen preference during
this deferral, so acknowledgement does not promise immediate movement changes.
Repeatedly selecting the active profile preserves fractional motion.

The choice survives application close/reload until desktop input is reacquired,
which restores the build default. There is no persistent settings file or
change broadcast. Multiple panels keep independent pending edits; Apply is
last-writer-wins and Cancel reloads the current session choice. No new Task,
signal, timer, bank-zero reservation or IRQ work is involved.
