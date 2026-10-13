# Desktop drag and drop design

Status: implemented as the bounded DD1–DD4 profile, with completed-drop delivery
through AES. See the [plan](desktop-drag-drop-plan.md) and
[implementation evidence](../../history/desktop-drag-drop.md).

[Roadmap](../../roadmap.md#colour-gem-desktop-roadmap) ·
[Selection and batch operations](desktop-selection-batch-plan.md) ·
[Current AES contract](../../reference/aes.md#small-gem-desktop)

Dragging should let a user copy a selection between folder windows without
typing the destination. Keep file selection and copy policy in `DESKTOP.APP`.
AES should supply input, window targeting and a small moving visual; the
existing sequential file job should perform the copy after release. Preserve
the 16 KiB transfer buffer and the accepted throughput/cancellation tradeoff.

The useful combination is GEM's selection and destination interaction with
Amiga-style separation between GUI events, desktop policy and completed-drop
delivery. Use the existing AES message channel for completed drops, including
between windows owned by the desktop. Keep the first payload private to that
application; cross-Task file argument ownership is a later contract.

## What classic GEM implemented

The historical source reference is the TOS 1.04/1.06/1.62 reconstruction at
`th-otto/tos1x` revision `7c6680d96642220710bddca825817d29ba86cdab`. Its desktop
retains Digital Research source ancestry. It is a concrete classic ST reference,
not a claim that every detail was identical in GEM 1.0 or every TOS release.
[Source provenance](https://github.com/th-otto/tos1x/blob/7c6680d96642220710bddca825817d29ba86cdab/README.md).

AES provides mechanical building blocks. `graf_dragbox` tracks a bounded
rectangle and returns its final position; `graf_mkstate` reads input state,
`wind_find` finds the window under a point, and `objc_find` finds an object.
These calls carry no filenames or copy policy.
[Digital Research AES reference, graphics library](https://bitsavers.org/pdf/digitalResearch/gem/Programmers_Toolkit/8039-2024_GEM_Version_2.0_Vol_1_Application_Environment_Services_Reference_Jun86.pdf).

The classic desktop uses its own selection-drag loop, rather than simply
calling `graf_dragbox` once for every file. `act_bdown` collects selected object
positions. `gr_drgplns` moves their outline polylines together; `gr_bwait` draws
them, waits for button release or `MU_M1` motion, then draws them again to erase
them. Rendering uses XOR. Window/object hit testing identifies destinations,
with temporary highlighting for suitable target objects. Release returns the
destination to desktop code. This is one application's operation over its own
windows and object trees.
[Classic desktop interaction source](https://github.com/th-otto/tos1x/blob/7c6680d96642220710bddca825817d29ba86cdab/desk/deskact.c).

`fun_file2win` constructs a destination from the target window and, when
applicable, its folder object, then invokes the filesystem operation. Disk and
trash targets dispatch separately. The desktop decides what the gesture means;
AES does not copy files.
[Classic desktop file-operation source](https://github.com/th-otto/tos1x/blob/7c6680d96642220710bddca825817d29ba86cdab/desk/deskfun.c).

Later MultiTOS application-to-application drag and drop is a different layer:
`AP_DRAGDROP` introduces a transfer over a named pipe with format negotiation.
It should not be mistaken for the original desktop's internal drag loop, or
made a prerequisite for copying between our folder windows.
[MultiTOS protocol documentation](https://freemint.github.io/tos.hyp/en/proto_dd.html).

## What GEM4XE currently does

The local donor is `~/atari/gem4xe`, revision
`fbfea9b0b1233a5d659d5ec583c63f863cceadfa`; this study changes no files there.
Its current desktop uses a simpler representative outline:

- `src/desk/desktop.c:hndl_drag` preserves an existing selection, or selects the
  pressed entry, then calls `graf_dragbox` for that entry's rectangle.
- It samples the pointer after the call and uses `wind_find`/`objc_find` to
  resolve the drop. Pointer position is the destination, not the outline corner.
- `src/desk/deskfun.c:fun_file2any` chooses copy, Shift-move or trash deletion.
  Dropping on a program has a separate launch path.
- `src/aes/grlib.c:gr_dragbox` holds `BEG_UPDATE` until release. Its XOR loop
  waits through `MU_BUTTON | MU_M1` and removes each old outline before moving.

The matching EmuTOS graphics routine has the same long UPDATE structure.
That structure protects XOR restoration, but copying it unchanged would keep
Exec816's console painting, widget feedback and background repair excluded
throughout the gesture. Reuse the interaction rules and geometry where useful;
adapt ownership and rendering to our concurrent desktop.
[EmuTOS graphics source](https://github.com/emutos/emutos/blob/02c2db75fc875265c1449efea014450466cf20b7/aes/gemgrlib.c).

## What Intuition and Workbench implemented

Intuition handles input routing, activation, windows and gadgets. Applications
receive `IDCMP_MOUSEBUTTONS` and, when requested, `IDCMP_MOUSEMOVE` as ordinary
Exec messages. They process and reply to them in their event loops. The input
system also distinguishes application input from native window gestures.
This supports application-owned interaction without putting file operations
inside Intuition.
[Intuition input and output](https://wiki.amigaos.net/wiki/Intuition_Input_and_Output_Methods).

Motion reporting is explicit: `WFLG_REPORTMOUSE` and `IDCMP_MOUSEMOVE` enable it,
while gadget `GACT_FOLLOWMOUSE` requests tracking during selection. The manual
warns that motion can generate many messages. The transferable lesson is to
request motion only while needed and consume it promptly; Exec816 can coalesce
motion while preserving button transitions.
[Intuition pointer handling](https://wiki.amigaos.net/wiki/Intuition_Pointer).

Workbench owns desktop icon dragging and file semantics. Its manual describes
moving icon images with the pointer and dragging a selected group together;
the pointer tip chooses the destination. Its filesystem behavior is distinct
from merely changing an icon's position.
[Workbench fundamentals](https://wiki.amigaos.net/wiki/AmigaOS_Manual%3A_Workbench_Fundamentals).

Graphics-library Bobs provide masked blitter images with optional saved
backgrounds. They illustrate how Amiga software can animate an image without
repainting a whole window. This is a rendering reference, not a claim about
the private implementation of every Workbench version. Exec816 already has
an appropriate VBXE overlay path; importing a GEL/Bob subsystem would add
unnecessary machinery.
[Amiga blitter objects](https://wiki.amigaos.net/wiki/Blitter_Objects).

Workbench 2.0/V36 added the public `AddAppWindow` registration for drops into
another application's window. Workbench sends one completed-drop `AppMessage`
to the application's chosen port. Its arguments contain names and directory
locks, plus the drop coordinates and application identifiers. The receiver
decides whether to open, import or otherwise use them. The message/reply
lifetime is separate from the pointer-tracking gesture. Use that separation
for Exec816, delivering the completed event through AES rather than adding a
second application-facing Exec port. Workbench's cross-Task argument lifetime
will matter when Text becomes a drop target.
[V36 AddAppWindow autodoc](https://d0.se/autodocs/workbench.library/AddAppWindowA),
[Workbench messages and examples](https://wiki.amigaos.net/wiki/Workbench_Library).

## Responsibility in Exec816

| Responsibility | Owner |
| --- | --- |
| Button capture, motion readiness, input loss and window stacking | AES/presenter |
| Moving outline, cursor ordering and restoration around drawing | Presenter and existing VBXE adapter |
| Selected filenames, acceptable targets and copy decision | Desktop application |
| Transfers, overwrite choices, errors, cancellation and refresh | Existing `DesktopFileJob` |
| Completed-drop notification | Existing AES message channel |
| Interpretation of a completed drop | Receiving application |

All current folder windows share one desktop Task. On valid release it posts
one ordinary eight-word AES message to itself, then handles that message in its
normal event loop to admit the existing copy job. This deliberately establishes
one completed-drop delivery path without adding a service, port or signal.
Standalone `FILES.APP` and other applications are not drop partners in the
first implementation.

### First completed-drop message

Use an application-private `DESKTOP_DROP` message, not the standard
`AP_DRAGDROP` name or number: that name promises the MultiTOS pipe protocol.
The planned private message value is `$6e00`, local to `DESKTOP.APP`.

| Word | Meaning |
| --- | --- |
| 0 | `DESKTOP_DROP` |
| 1 | Desktop AES application ID |
| 2 | Zero: no bytes follow the eight-word message |
| 3 | Destination folder window handle |
| 4 | Source folder window handle |
| 5, 6 | Captured release x, y |
| 7 | Captured GEM keyboard modifiers; no Move interpretation yet |

The desktop retains one pending drop in upper RAM: the frozen source selection
and a copied destination directory path resolved at release. No Browser or
filename pointer is embedded in the message. There is at most one queued drop;
another gesture cannot reuse that state until the message has been consumed.
This makes a separate descriptor allocator, transaction ID and acknowledgement
message unnecessary for the first, single-Task implementation.

Queue publication uses `appl_write(id,16,message)`. If the existing sixteen-entry
application queue is full, cancel the drop, restore feedback and report that
the drop was not accepted; do not spin, wait for queue space or start a copy
through a fallback direct path. Successful publication is notification, not
completion of any file operation. Release the visual and MCTRL hold before
dispatching the message or doing DOS work.

The event handler processes `DESKTOP_DROP` before ordinary window dispatch. It
consumes the pending state once, using the captured path rather than performing
another hit test against a newer pointer or changed view. Source/target close
before admission cancels it. If a close, Escape or shutdown cancels an already
queued drop, clear its folder references but retain a cancelled-pending marker
until that message is consumed, or until `appl_exit` drains the inbox. Never
reuse the pending slot while an older notification can still arrive.

These are distinct stages of one interaction: `MU_BUTTON`/`MU_M1` describe input;
`MU_MESAG` delivers the completed drop. Exec signals already wake the AES event
wait underneath. Applications get no second drop port or independent wait API.

## Initial interaction

The first implementation copies regular files between desktop folder windows,
in both icon and list views. Selected directories disable dragging the group,
just as they currently disable Copy. Do not silently omit them.

Arm a candidate on a left press over an entry. Leave click behavior deferred
until release or movement reaching a small threshold, initially four logical
screen pixels on either axis. A click retains today's selection and double-click
behavior. Once dragging starts, consume its release so it cannot also open a
file or click the destination.

Dragging an already selected entry carries the whole selection, including
offscreen members. Dragging an unselected entry makes it the sole source.
Shift-click without dragging continues to toggle membership; Shift during a
drag does not request Move. Freeze the source path/snapshot and membership
until cancellation or admission from the queued drop into the copy job.
A drag never changes another folder's selection merely by passing over it.

An exposed background area in another folder targets that directory. A visible
directory entry there targets that subdirectory, without opening it. A file
entry, title, scrollbar, inline dialog, desktop background or foreign application
is not a target. Do not top a window just to hit it or accept a covered rectangle.
Same-source-folder drops and a matching displayed destination path are no-ops.
Existing case-insensitive directory comparison can handle that common case;
volume aliases remain subject to normal overwrite handling, not a new resolver.

A valid release begins Copy without requesting the already-known destination
again. Preserve each source name, including for a single-file drag. Existing
Replace/Skip/default-Cancel prompts, temporary-file publication and terminal
counts remain authoritative. Source files stay in place. Recursive operations,
Move, trash, icon rearrangement, automatic scrolling and opening folders while
hovering are later work.

Escape, input loss, source close or shutdown cancels the gesture. After Escape
while held, consume the eventual release before accepting another gesture.
Cancel before freeing any referenced folder. Release visual ownership and
mouse control before DOS I/O. After admission, the existing job keeps its source
Browser alive and owns the copied destination path; the destination window is
then free to close.

## Input and target support

The existing source capture already routes a press/release sequence back to
its source window. `ExecAESInputWindow(MU_BUTTON)` therefore identifies the
source; it must not be interpreted as the window under the release point.

Add standard `MU_M1` rectangle readiness to the existing caller-local event
matcher. Use it for the movement threshold and bounded hover decisions. Keep
the latest coherent pointer sample and existing signal/interest handshake;
do not enqueue a message for every hardware motion sample. Preserve retained
button edges, captured release coordinates and loss/open-epoch handling.
`MU_M2` can use the same machinery when required; it need not enlarge this
feature's scope. No additional kernel signal or timer service is needed.

A timer-only polling implementation would require fewer initial binding edits,
but adds alarm traffic and a sampling interval to an interaction whose latency
matters. Prefer the small standard event extension. The normal event loop must
continue dispatching redraw, close and child-lifecycle work while tracking.
Source-changing commands must not mutate the frozen selection or directory.

Add standard `wind_find(x,y)` with authoritative stacking/visibility semantics.
A small presenter query is sufficient; do not duplicate the layer manager in
the desktop. A native/foreign hit must prevent falling through to a covered
folder. After resolving a desktop-owned window, local OBJECT geometry chooses
its directory entry or background. Resolve again at the captured release point,
before admitting the job. Do not perform filesystem probes while hovering.

Use `BEG_MCTRL` for the active gesture to keep mouse/focus/geometry ownership
stable. Use short UPDATE sections only for actual application feedback. Handle
cancellation and pending GUI messages before freeing a source or committing a
drop; never retain UPDATE over an event wait, overwrite prompt or filesystem
operation.

There is an existing concurrency limit: `AESLOCKS.Eligible` requires compatible
mouse ownership even for UPDATE. A different AES application therefore cannot
acquire UPDATE during this MCTRL hold. Native painting can proceed without an
UPDATE owner, but a queued lock request also makes `PaintBlocked` true, so a
waiting peer can pause native painting until release. Other Tasks still run.
The first drag implementation preserves these semantics and tests prompt
resumption; it does not promise concurrent peer AES repaint throughout a held
drag. Decoupling UPDATE from mouse capture would require a separate lock-policy
change, rather than a hidden exception for file dragging.

## Visual feedback and redraw safety

Start with one small representative outline, even for a large selection. Show
the count in the source status strip and highlight the eligible target only
when it changes. The pointer hotspot determines the drop. Selection count must
not multiply moving draw work, and movement must not repaint directory contents.

Use the existing `CONSOLEBITMAP.Outline`/VBXE outline rendering path. It already
erases an outline before conflicting pixel changes and can draw it again after
rendering. The important adaptation is ownership: current `DESKDRAG` represents
native title/size/slider gestures and suspends under AES mouse control. An
application drag needs its own owner/lifetime in that same single visual slot;
it must not impersonate a title drag or generate `WM_MOVED`.

Expose a bounded AES visual operation to start/stop an outline attached to the
captured pointer. It carries geometry and owner identity only, with no filenames,
OBJECT pointers or drop policy. Validate its bounds and ownership at admission,
then let the presenter follow its latest pointer directly. Avoid synchronous
application RPC on every visual step. This can later serve a standard
`graf_dragbox` wrapper without forcing the desktop into a blocking helper today.
The implementation plan should define this small contract explicitly; it is
not a new kernel service or general animation API.

Every rendering entry that can touch the outline or its cursor overlap must
participate in erase/draw/restore ordering, including caller-local VDI grants.
Use the existing serialized display/BCB ownership. The outline must not block
its owner's UPDATE admission, and a temporary suspension for painting must not
lose the active gesture. There is one visual owner at a time; release, loss,
close and detach all remove it. These are synchronization requirements, not
reasons to revalidate trusted geometry on every draw.

## Memory and evidence required

Keep one small drag record in upper RAM: source/target identity, pressed entry,
press position, phase, visual parameters and the captured destination path.
The frozen Browser selection can remain in place until the existing job copies
its 32-byte bitmap. Reuse the
single outline slot; reserve neither a full-screen saved image nor per-file
ghost bitmaps. Keep any retained path off the Task stack.

Expected bank-zero reservation delta is **0 fixed bytes, 0 bytes per public
Task and 0 idle bytes**, including guards, alignment and unused capacity.
Measure emitted upper-memory records and stack margins when implementing;
no Task, stack or direct-page growth is planned.

Development evidence should cover click/drag disambiguation, fast release,
multiple/offscreen selections, both views, overlap with native and GEM windows,
directory targets, same-folder rejection, loss/Escape/close, balanced mouse
ownership and a second gesture after cancellation. Copy readback and existing
failure cases should exercise the shared job rather than a second copy path.

Measure median/p95 press-to-feedback, motion-to-outline and release-to-visible
admission separately from disk transfer time. Verify unchanged pixels after
cancel/release while the shell scrolls and another application requests redraw,
including the documented lock wait and subsequent resumption. Use
small raw/optimized layout probes for any changed ABI records, focused optimized
behavior tests, and the exact OF816 demo; retain the five-second autoboot.

## Later application drops

When Text or another independent Task needs dropped files, retain AES delivery
and add explicit target registration plus an owned or retained file-argument
record with a defined release/shutdown lifetime. That public contract must not
expose this first implementation's private frozen Browser state. Decide it
when adding the first independent receiver; do not build a second Workbench
message channel alongside AES now. An argument-release acknowledgement would
end a payload lifetime, not report completion of the receiver's file operation.
MultiTOS `AP_DRAGDROP` compatibility, if needed for a real port, is a separate
adapter decision rather than a claim made by the desktop-private message.
