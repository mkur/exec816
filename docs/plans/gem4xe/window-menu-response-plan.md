# Window and menu response implementation plan

[GEM plans](README.md) · [Roadmap](../../roadmap.md) ·
[Gadget atlas plan](frame-gadget-atlas-plan.md) ·
[Current measurements](../../history/window-frame-exposure.md) ·
[Desktop contract](../../reference/desktop.md)

Status: implementation in progress. See the
[development record](../../history/window-menu-response.md) for completed
slices, selected checks and memory accounting.

Make window opening, focus changes and dropdown interaction respond sooner by
removing redundant application/AES exchanges and shortening the path from a
completed blit to the next visible operation. Integrate the existing gadget
atlas work without replacing AES, Layers or the existing presenter with a
new scheduling system.

## Starting point

The GEM4XE comparison suggests useful implementation choices: direct frame
construction, a short save/draw/restore menu path, fixed gadget images and cheap
selection changes. It is not a matched speed comparison. Use Exec's existing
FE4 package and measurements as the baseline, with unchanged machine/compiler
pins and default window geometry.

| Observed work | Current cost or consequence | Planned change |
| --- | --- | --- |
| Folder `WM_TOPPED` | Fourteen enable and three check RPCs precede `WF_TOP` | Raise first; publish only changed shared-menu bits |
| Repeated enable/check requests | Even unchanged values increment the menu revision and damage objects | Successful no-ops preserve revision and popup images |
| New Window | Four initial frame batches, followed by a path-title repaint | Supply the known path before opening |
| Warm File / View / dismiss | About 200 / 221 / 140 ms to complete pixels | Shorten completion-to-continuation gaps |
| Fixed frame gadgets | Repeated tiny fills and record construction | Implement the linked GAT1–GAT3 atlas slices |
| Moving between menu entries | Damaged rows redraw their background and labels | Invert eligible monochrome rows |

Warm SYS: completion is about 642 ms, Shell about 281 ms. A new frame with its
final path title takes about 943 ms; the complete folder takes about 1,404 ms.
These are whole-action elapsed measurements, not blitter time or exclusive
renderer CPU time. Existing entry-only traces cannot assign all of that time
to rendering. A presenter turn also does not necessarily imply a VBI wait.

## Sequence and limits

Implement and commit small executable slices in this order:

1. **UI1:** remove redundant menu work and raise folders promptly.
2. **UI2:** use the final initial title before `wind_open`.
3. **GAT1–GAT3:** install and use the [gadget atlas](frame-gadget-atlas-plan.md).
4. **UI3:** continue foreground menu work promptly after completed transfers.
5. **UI4:** optimize eligible menu selection changes.
6. **UI5 / GAT4:** one combined measurement record and demo refresh.

UI1 and UI2 can land independently of the atlas. Keep renderer-specific
measurements at GAT3 so the final result can distinguish its gain from the
application and presenter changes. Do not create another baseline-only slice.

Keep current geometry, colours, application ownership, preservation opt-in and
ordinary `WM_REDRAW` behavior. Keep large existing cache restores, two popup
image slots and current window cache capacities. No new Task, Task priorities,
kernel operation, timer protocol, public menu API or generic rendering layer
is needed. Correct caller use remains assumed; retain synchronization and
operational failure handling without adding repeated request validation.

## UI1 Raise promptly and publish only menu changes

Primary files: `examples/gem-browser/desktop.inc`,
`examples/gem-browser/browser.c` and `lib/aes/aesmenu.act`.

For folder `WM_TOPPED`, issue the existing `wind_set(WF_TOP)` before publishing
menu enable/check changes. Keep exactly one raise and the normal caller choice
to accept `WM_TOPPED`; do not make AES automatically raise arbitrary clients.
Preserve editing-caret teardown/setup, active-folder selection and error paths.

The desktop shares one installed menu tree between folders. Compare each
desired `DISABLED` or `CHECKED` bit against that actual tree before calling its
setter. A previous per-folder `menuEnabled` value does not describe the shared
bar after another folder has been active. Remove the forced reset and replace
the obsolete cache, rather than maintaining two competing menu-state models.
Use the same comparison for desktop/no-folder and view changes. Read the bits;
continue to change an installed tree through its existing AES calls. Finish
publishing the new state before dispatching the next application menu command.

At AES operations 31 and 32, leave damage and `menuRevision` unchanged when the
requested bit already has its requested value. Still return ordinary success.
Real changes retain current invalidation. Do not apply a blanket early return
to `menu_tnormal`: it also acknowledges menu interaction. A repeated
`menu_text` pointer may refer to changed bytes and is not proof of a no-op.

Focused development checks: one optimized menu fixture for unchanged versus
changed enable/check bits, retained popup reuse and normal acknowledgement;
one desktop interaction covering two folders with different selections/view
modes, Shell focus and return. Observe request counts and ordering. An unchanged
folder activation should send no enable/check RPCs, preserve the menu revision
and reuse an otherwise valid popup. Changed state must still update correctly.

## UI2 Open with the correct title

Primary file: `examples/gem-browser/browser.c`.

Set the initial `WF_NAME` from the already known folder path before
`wind_open`, using the same bounded display-label rule as later navigation.
Remove the provisional `Files` title. Directory enumeration still supplies
counts and contents afterward; a title need not wait for it. Retain actual
title updates when navigation changes the path and avoid resending an unchanged
title merely to update the summary.

Keep the existing window-open and scan lifecycle. Do not add another worker,
delay or asynchronous directory API. Measure the first correct frame separately
from completed contents; moving enumeration ahead of `wind_open` would defeat
the purpose.

Focused check: one New Window observation and one parent/subdirectory
navigation. Require the correct path on the first completed frame and no
post-scan title repaint for an unchanged path. Update the existing observer's
five-call expectation to the four initial batches for this window, without
ignoring unrelated frame damage or changing the final pixel oracle.

## UI3 Shorten menu completion and continuation

Primary files: `lib/desktop/deskmenu.act`, `deskmenucache.act`, `deskhost.act`,
`lib/console/consoledriver.act` and `console-bitmap-display.inc`; touch the
existing VBXE completion path only if the observations justify it.

Extend the existing passive observer for one warm File-to-View transition.
Record input consumption, copy submission, hardware completion when observable,
completion adoption, scene-token retirement, next-popup submission and final
title/selection pixels. Distinguish active CPU, off-CPU time and DMA wait using
existing Task observations. When hardware completion cannot be observed
independently, label the completion-detection interval accordingly. Reuse the
current package if extra baseline boundaries are needed.

Continue an already eligible foreground transition immediately after adoption:
retire the old popup save/restore, prepare or restore the next popup, and publish
its heading through the existing state machine. Avoid returning through unrelated
console/control/cache-maintenance work between every already-ready step.
Use a small bounded continuation allowance, initially at most four state
advances in a worker turn. Stop on pending DMA, blocked admission, cancellation
or no progress. Service input between visible units and preserve the existing
turn's control/output budgets; continuation must not renew them. Background
work resumes at the ordinary boundary, not only when the mouse becomes idle.

Keep notification-driven completion as the normal path. If the trace shows a
transfer already complete while its notification is pending, evaluate one
nonblocking completion probe for that newly submitted foreground operation.
Retain it only if it reduces measured latency. A busy result uses the existing
notification/wait path; there is no spin-until-finished loop or polling on every
idle turn. Do not route these copies through the existing synchronous rectangle
helper unchanged: it splits work into sixteen-row fenced copies.

Preserve operation identity, pin and scene-token lifetime, timeout/recovery and
deferred exposure behavior. Retire once, after completion; recheck ordinary
owner/lifetime state through existing gates when a gesture changes. Keep IRQs
and preemption enabled. Driver completion policy stays in the driver; do not
hold a per-call adapter admission across `Wait` or `Yield`.

Check pointer publication on this path and the GAT frame path. Reuse existing
drawn/erased/position state to avoid restoring an unchanged pointer between
fragments only to erase it again. Keep moving-pointer feedback at the bounded
input boundaries and normal overlap protection. Change this only where a trace
shows redundant erase/restore work; do not keep the pointer hidden through a
long repaint.

Focused checks: warm heading switch and dismiss, a cold popup fallback, a menu
over a changing Shell, and interruption by an owner/window change. If completion
handling changes, add small optimized cases for immediate completion, BUSY then
notification, late notification after retirement and the existing failed-copy
cleanup. Preserve fixture guards and pins. Verify unrelated console output can
progress between bounded interaction units. Acceptance requires shorter measured
completion-to-next-operation gaps, not just fewer calls in the source.

## UI4 Invert eligible selection rows

Primary files: `lib/desktop/deskmenu.act`, `deskappmenu.act` as applicable,
`ports/gem4xe/aes/menu-render.c` and the private drawing adapter.

Keep existing old/new-row damage tracking. For a fully presented, clean, enabled
plain-text row whose only change is selection, replace background/label painting
with a blitter XOR that exchanges the actual hardware black and white indices.
Invert the previous row and the new row in one admitted batch where possible.
Use existing packed-edge and clipping primitives; never include popup borders
or a pointer/outline in the inversion.

Start with ordinary unadorned entries. Disabled, checked, coloured, custom,
dirty or incompletely presented rows retain the current renderer. Eligibility
uses existing menu metadata and current presentation state, not a framebuffer
scan or a generic menu-style classification system. A generation/content change
also uses ordinary painting.

Track selection from the last completed pixels, not each incoming pointer
event. Coalesced motion must not invert an unpainted row; repeated events must
not invert a row twice. Advance the committed selection only after the batch
completes. Keep cached normal popup images immutable and retain the existing
rules preventing captures of transient selection pixels.

Focused optimized pixel check: A-to-B-to-A movement, repeated/coalesced input,
entry/exit, clipped nibble edges and one ineligible-row fallback. Check dismiss
and warm reopen after selection. Eligible changes must produce no glyph draws
or staging uploads and must match the normal renderer's final pixels.

## UI5 Measure the combined result and refresh once

Complete GAT4 here rather than building and checking a second equivalent demo.
Use `tools/measure_frame_exposure.py`, `tools/measure_window_preservation.py`
and the narrow menu observer; extend their existing boundaries instead of
creating another benchmark application.

Compare the frozen FE4 package with the final optimized package under the same
pins. Use three samples for New Window, warm Shell/SYS focus and File/View/dismiss;
record the first cold popup separately. Report medians and maxima, not p95 from
three samples. A difference below the screenshot sampling interval is not a
demonstrated visual improvement. Keep the observer's independent final pixels.

Report application menu RPCs/revisions, frame-only CPU and command work,
completion-to-continuation intervals, first correct frame, complete folder and
complete menu pixels separately. Fewer gadget fills cannot establish a faster
whole interaction by themselves. Keep only optimizations that meet their
structural/correctness checks and improve their measured path without a
repeatable regression in the other selected interactions. Record remaining
limits rather than promising GEM4XE timings without a matched donor run.

Build through `tools/build_demo.py`, retaining OF816, five-second autoboot,
matching disks, pinned ROM, licenses and checksums. Run the focused interaction
checks on the actual packaged image. Keep traces and intermediates outside
`exec816-demo.zip`; provide the ZIP and launch command. Update affected current
references, plan status, indices and one development evidence record. Run only
affected development checks, not full qualification or a compiler-pin matrix.

## Memory accounting

Every UI slice targets **0 additional fixed bank-zero bytes, 0 per public Task
and 0 idle**, including guards, alignment and unused reserved capacity. No stack
or direct-page growth is planned. Reuse existing state where possible; report
any small upper-RAM continuation/selection fields and linked code-size changes.

UI1–UI5 add no VRAM reservation. The linked GAT slices reserve **4,096 bytes**
for immutable gadgets, including unused page capacity; count that once in the
combined result. Existing popup and window caches retain their reservations.
