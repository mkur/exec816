# Desktop drag and drop implementation plan

Status: DD1–DD4 implemented and development-checked. Actual execution scope and
measurements are recorded in [the implementation history](../../history/desktop-drag-drop.md).

[Design and historical comparison](desktop-drag-drop-design.md) ·
[Roadmap](../../roadmap.md#colour-gem-desktop-roadmap) ·
[Existing batch copy plan](desktop-selection-batch-plan.md)

Implement copying a regular-file selection between desktop folder windows in
icon and list views. The pointer chooses the destination; one small outline
follows it. Release delivers one AES message, and the receiving desktop event
handler starts the existing sequential copy job with its 16 KiB buffer.

Retain the current colour icons, palette and window style. This work adds
interaction, not another appearance pass. Keep ordinary click, Shift-click,
double-click, keyboard selection and standalone Files behavior intact.
Directory sources, Move, desktop-icon rearrangement, automatic scrolling,
hover-opening and independent application receivers remain outside this plan.

## Current code and changes needed

- `lib/aes/aesinbox.act` already publishes a coherent latest pointer snapshot,
  but motion does not wake an event waiter. `c/calypsi/aes-input.c` matches only
  keys/buttons; `aes-events.c` explicitly rejects rectangle events. Add `MU_M1`
  using that snapshot and the existing signal/interest handshake.
- Add `wind_find` to the AES bindings and presenter window queries. Use the
  current layer stack; never infer the destination from
  `ExecAESInputWindow(MU_BUTTON)`, which identifies the captured source.
- `lib/desktop/deskdrag.act` owns native title/size/slider gestures. Adapt its
  single outline slot for application ownership, without routing application
  drags through native move/resize completion.
- `examples/gem-browser/browser.c:folder_event` already defers selection until
  release. The desktop must intercept eligible presses and threshold movement
  before forwarding ordinary folder clicks.
- `desktop.inc:desktop_copy_start` currently assumes an active editable Copy
  dialog. Separate its small job-admission portion so a completed drop can
  supply a directory directly. Keep one allocation/transfer/cleanup path.

## DD1 — motion readiness and authoritative window targeting

Extend `evnt_multi` and `evnt_multi_moblk` with standard `MU_M1` inside/outside
rectangle conditions. The existing parameter-block layout already has the
rectangle fields. Keep `MU_M2` explicitly unsupported. Ignore unselected
rectangle fields as today.

Use caller-owned upper-memory wait scratch, the registration's latest pointer
snapshot and its existing receive-port signal. Publish rectangle interest
before the final readiness check. Motion may coalesce: do not allocate or
enqueue motion messages, clear signals between observation and Wait, introduce
a polling timer, or perform presenter RPC for each match. Wake interested
waiters when a changed eligible pointer snapshot needs reconsideration; a
stationary pointer must not keep the presenter runnable. Keep the predicate
in the caller rather than adding an application rectangle evaluator to every
hardware sample.

Extend the frozen-decision and loss/epoch handling to rectangle readiness.
An M1-only result returns its coherent selected pointer state. When a retained
button event also returns, preserve that event's coordinates and recipient;
the desktop evaluates release against the retained release position. Do not
replace an old release with newer motion. Reconcile the M1 predicate at the
decision boundary, with the existing lifetime checks after alarm retirement.
Loss affecting the captured pointer also invalidates M1-only waits.

Add `wind_find(x,y)` and its AES parameter-block operation. Return the topmost
normal AES window's global handle, including a window owned by another
application. Return zero for desktop/background or a topmost native window;
a native hit must block a covered AES window, not fall through it. Include
window borders in the query; the desktop subsequently restricts acceptance to
its target content area. The query changes neither focus nor stacking.

Update `abi/aes-server.json` and `tools/generate_aes_server.py` outputs together
where shared records/constants change. Update named wrappers, parameter-block
dispatch and recorded binding inputs. Rebuild clients against the new layout;
do not retain an old-layout profile.

Development acceptance: focused emitted input/window tests for enter/leave,
immediate readiness, boundaries, simultaneous key/button/message/timer results,
fast down/up, close/reopen, input loss and rearming. Demonstrate no lost wake
at interest publication and no timer request for an untimed motion wait.
Exercise overlapping native and foreign AES windows, borders and background.
Use small raw/optimized layout/access probes for changed shared records and
optimized runtime cases for behavior.

## DD2 — application-owned moving outline

Add the bounded AES extension
`ExecAESDragOutline(window,dx,dy,width,height)`. A positive source handle starts
one outline at a signed offset from the captured pointer. Dimensions are
8..80 by 8..32 pixels; clamp the displayed outline to the desktop without
altering the logical pointer or destination. Passing zero for all arguments
stops the caller's outline. Put its service operation in the existing
machine-readable AES ABI, not the kernel gateway.

Start requires the caller's active source capture and explicit MCTRL hold.
Establish ownership and geometry once at admission. Starting after physical
release returns a normal failure; the desktop can still process the retained
release without starting a visual. Stop is harmless when this caller's visual
has already retired. No filenames, Browser or OBJECT pointers cross into the
presenter.

Keep one visual slot with a native/application owner distinction and source
open lifetime. Follow the presenter's latest pointer directly; do not require
a synchronous start/update RPC per movement. Release, input loss, source
close, final MCTRL release and client detach retire the application visual.
They must not produce `WM_MOVED`, `WM_SIZED` or other native completions.

Reuse `CONSOLEBITMAP.Outline` and the current serialized display ownership.
Audit native drawing, console scrolling, exposure repair and caller-local VDI
grant entry/exit: erase the outline before overlapping drawing and restore it
afterward while it remains live. Preserve logical ownership across temporary
paint suspension. An application outline under MCTRL must allow its owner's
UPDATE acquisition; do not keep the existing native-drag MCTRL suppression in
front of this application path. Preserve the current lock policy: another AES
client's UPDATE waits for MCTRL release, and a queued lock can pause native
painting too. Do not add a drag-specific exception to that policy or claim
uninterrupted concurrent AES repaint.

Development acceptance: an emitted small AES client starts, tracks and stops
the outline while the shell scrolls and another client requests redraw. Compare restored
pixels after release, Escape, loss, close and detach; repeat at odd x and screen
edges. Verify balanced ownership, the owner's UPDATE upgrade, prompt peer
UPDATE/painting resumption after release, a second gesture, and unchanged native
title/size/slider operation.

## DD3 — desktop gesture, AES delivery and copy admission

Add one upper-memory drag record to the desktop. Keep explicit phases for an
armed click, active drag and queued completion; retain cancellation state until
any queued completion is consumed. Store source/target handles, pressed entry,
press position, visual geometry and a 128-byte destination directory, matching
current Browser path capacity. Report an ordinary path-length error if joining
a subdirectory does not fit. Keep paths off the Task stack.

Arm only an ordinary file entry in a desktop folder with no active dialog or
copy/delete job. Use a four-pixel threshold on either axis. Below threshold,
forward the unchanged press/release selection semantics. At threshold, retain
an existing selected group or select the pressed entry alone. Reject a group
containing directories. Freeze source navigation, sorting, refresh and selection
until cancellation or job admission; defer pending refresh as with current
dialogs. Continue dispatching redraw, child completion and close/shutdown.

Include `MU_M1` only while armed/tracking. After threshold, acquire MCTRL and
start a representative outline no larger than 80 by 32. Use a small rectangle
around the last processed point to wait for subsequent movement; the presenter
still moves the outline independently. Detect threshold crossing from a
retained release too, so a quick drag is not lost merely because no motion wait
ran while the button was held. Once a drag starts, consume its release and
clear the ordinary armed/double-click state.

Resolve targets using `wind_find` followed by existing folder geometry. Accept
an exposed other-folder content background or a visible directory entry within
it. Reject files, toolbar/status areas, borders, dialogs, foreign windows and
the desktop. Passing over a target must not raise it or change its selection.
Use transient feedback for the target cell or status strip, restoring the
underlying selection on leave. Redraw only changed feedback regions, not the
directory. Resolve once more at the captured release coordinates, then copy
the destination path into the pending drop record. Use the existing
case-insensitive directory comparison for common same-directory no-ops.

Publish the design's `DESKTOP_DROP` eight-word message with
`appl_write(d->id,16,words)`. Reserve the one pending record before publication;
reject another gesture until it is consumed. Release outline feedback and
MCTRL before returning to message dispatch. Queue-full failure cancels and
reports the failed admission without a direct-copy fallback. Handle the drop
opcode before the generic `message[3]` window dispatch, and process it once.
No new public file-transfer service or application port is needed.

Source or target close before message consumption cancels the pending drop.
Clear any freed folder references and retain a cancelled-pending marker until
that message is drained; never reuse its state early. Escape during a held drag
also consumes the eventual release. Shutdown retires visuals/locks before
closing windows and uses the existing `appl_exit` inbox drain.

Factor job allocation/admission out of `desktop_copy_start`; keep the menu's
text-entry completion (`objc_edit(...,ED_END)`) only on its dialog path. The drop
path creates the existing copying/progress UI directly. A single-file drop
joins destination directory and source filename once before admission; batches
retain the existing per-file join in `job_next`. Do not infer a single drop's
directory as a replacement filename. This preserves current menu Copy semantics
without introducing another transfer engine.

After admission, retain the source Browser under the existing file-job owner
lifetime. The job owns the destination path, so closing the target is then safe.
Keep Replace/Skip/default-Cancel, temporary publication, accurate counts, cleanup
and affected-view refresh unchanged. Start no DOS calls while MCTRL or UPDATE
is held, and add no scans, allocations or drag logic inside the Read/Write loop.

Development acceptance: physical icon/list drags with single, multiple and
offscreen selection; Shift-click versus Shift-drag; subdirectory and overlapping
targets; same-directory rejection; fast release; loss/Escape/close/shutdown;
queue-full and cancelled queued completion; repeated gestures and ordinary
double-click afterward. Independently read back copied bytes, including a
single-file target directory and a batch with Replace/Skip. Exercise normal
copy allocation/I/O failure cleanup through the shared job.

## DD4 — integration, latency evidence and distributable demo

Extend the existing colour-desktop observers/walkthrough and native-drag/AES
fixtures. Keep one set of layout observations and pixel oracles. Run host checks
and focused optimized emitted-code cases; use raw only for the ABI probes or
diagnosing a compiler defect. Do not run compiler qualification or duplicate
the full system matrix.

Record median/p95 press-to-feedback, threshold-to-outline, motion-to-outline
and release-to-visible-copy-admission separately from disk transfer. Measure
with an idle desktop and with concurrent shell output or a redrawing app.
Retain the accepted 16 KiB throughput tradeoff: compare one matched single-file
copy with menu Copy and check that message delivery adds no per-chunk work.
Observe target feedback redraw area and restoration after cancellation; an
unrelated full-folder repaint on each motion is a defect.

Report stack/domain guards, actual Task stack margins, heap cleanup, upper-RAM
record sizes and orderly shutdown/OS return. Build with
`tools/build_demo.py --gem-desktop`, preserving OF816, five-second autoboot,
pinned toolchain/ROM/configuration and notices. Exercise the extracted
`exec816-demo.zip`, including an actual two-folder drag and independent disk
readback. Provide the ZIP and its launch command; keep traces/manifests outside
the distributable.

Update `docs/reference/aes.md`, `docs/reference/desktop.md`, the demo guide,
roadmap and plan index as slices become usable. Save measurements and source/
build hashes in development evidence with a history page. Mark only executed,
passing slices complete; emulator development checks do not qualify hardware.

## Memory budget and completion

Every slice plans **0 additional fixed bank-zero bytes, 0 bytes per public
Task and 0 idle bytes**, counting guards, alignment and unused reservations.
Add no Task, signal, timer service, directory snapshot or VRAM save surface.
Account for actual emitted upper-memory input scratch, outline ownership and
one desktop drag record. Keep the existing 32-byte selection bitmap frozen
until job admission copies it; retain the one 16 KiB copy buffer.

Completion means both desktop views can copy selections by dragging, use one
AES completed-drop notification, restore all feedback without full-window
motion repaint, and preserve current copy results and ordinary selection.
Independent application drops remain a subsequent payload-lifetime design,
using this same AES delivery channel.


## Implementation record

DD1 adds AES wire version 14 and loadable C ABI version 15. M1 frozen pointer
scratch costs 20 upper-memory bytes per registration. The input inbox is 754
bytes; registration storage is 1,306 bytes before heap rounding. No motion queue,
new signal or timer is introduced. Raw/optimized native probes and C layout
objects cover the changed shared record; optimized input checks cover all 31
combined masks, boundary/wake/loss cases and timer retirement.

DD2 adds nine logical bytes of presenter ownership state and reuses the existing
outline geometry and display path. A pending foreign UPDATE cannot repeatedly
erase or spin the owner visual; it retains the existing MCTRL wait policy.
Native title/size/slider gestures pass their existing emitted/pixel fixture.

DD3 adds a 148-byte desktop record, bringing the application model to 2,352
bytes. The Browser, 974-byte file job and 16 KiB buffer are unchanged. Source
selection is the feedback before dragging; no extra source-status repaint delays
outline admission. Only changing target feedback repaints a status strip.
Queue-full and cancelled-pending lifecycle checks execute the actual gesture
source in a host fixture; physical copies and the ABI run in the target emulator.

DD4 passes the extracted demo walkthrough in icon and list views, independent
disk readback, the existing menu Copy regression and 12 outline trials each
with an idle desktop and Counter running. Cancellation restores exact source
pixels; a waiting peer UPDATE resumes after release. The final scene, shell
command and orderly EXIT pass with guards intact. The host suite passes 455
tests with four historical skips. Input/window fixtures pass 705/256 checks,
plus four native checks each; small ABI probes pass 39 checks in each native
mode and C layouts pass at O0/O2. The history records timing scope, observed
stack margins and remaining limits rather than claiming every proposed stress
case was exercised on the target.

All slices add **0 fixed bank-zero bytes, 0 bytes per public Task and 0 idle
bytes**, including guard/alignment/reserved capacity. The demo's memory
reservations match the previous desktop-style build. Full release/hardware
qualification remains separate from these development checks.


For throughput regression, DD4 reuses the existing matched four-file menu Copy
corpus (49,226 bytes, including empty/exact-buffer/tail cases) and its recorded
baseline instead of introducing another single-file benchmark fixture. The
actual Read/Write loop remains unchanged. Lifecycle fault outcomes are isolated
in a host test of the production gesture source; the physical path, shared ABI,
copy results, native gestures and shutdown run as emitted target code. These
scope choices are recorded rather than presented as full qualification.
