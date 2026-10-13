# Reuse unchanged backgrounds while switching menus

[Design basis](aes-layers-vram-design.md) · [GEM plans](README.md) ·
[Previous measurements](../../history/aes-layers-vram.md)

Status: implementing, 2026-10-13.

The reported case is an idle Files window and switching File/View headings,
without selecting a command. The AV6 warm switch takes 702 ms even with a
rendered-popup hit. There are no successful background saves in that cohort.
Directory scans, sorting and changes to Files content are outside this fix.

Two existing rules prevent useful reuse: an UPDATE for one desktop-owned window
creates repaint obligations in untouched sibling windows, and hiding a popup
creates exposure before the next background capture. Restored historical pixels
must never certify an unreported model change, so do not simply remove the
pending-paint checks or acknowledge arbitrary untouched windows.

## MS1 Scope the shipped desktop's painting to its actual window

Add optional `ExecAESBeginUpdate(window)` using the existing UPDATE exchange and
lock. The caller promises that this outer update changes only that window;
`wind_update(END_UPDATE)` ends it. Nested updates retain the outer scope.
Standard `wind_update(BEG_UPDATE)` continues to cover all owned windows and
retains conservative empty-update behavior. This introduces no per-draw RPC,
new kernel service or new queue.

Keep the active handle in the existing AES service. Restrict change tracking,
cache holds and published update ownership to the named window. Reset scope on
release/owner exit. Generate the changed protocol/import versions and rebuild
clients. Convert the desktop background and folder drawing entry points to the
scoped helper. A fully hidden or empty update still invalidates its target;
untouched siblings remain eligible. Do not expand this into a Files refresh or
selection-renderer refactor.

Validate the new C/native call boundary, sibling eligibility, nested and empty
updates, delayed lock grant and cleanup. Retain the ordinary-caller tests.
Commit this executable slice after focused checks pass.

MS1 implemented: the cache fixture exercises a contended scoped grant, nested
ordinary BEGIN, an empty hidden sibling update, and an empty target update.
Host checks passed (459 tests, four skips); focused emitted cache and raw/optimized
context checks passed. The older lock fixture times out at 118 checks without
assertion failures; a control using the pre-change C UPDATE implementation and
native lock/window-state/service sources reproduces that timeout. This is not
claimed as a passing lock regression. The new contended/nested scoped case passes.
The active scope adds one 16-bit service field (1,812 → 1,814 bytes;
both round to 1,816 heap bytes); no client,
window, direct-page, stack or VRAM reservation grows. Reserved bank-zero delta:
**0 fixed / 0 per public Task / 0 idle bytes**.

## MS2 Retain one menu-interaction background across headings

For an application menu, compute the union of its admitted popup bounds once at
interaction start. Save that bounded screen rectangle in the existing 75 KiB
menu-under slot. Native menus use their existing footprint. Reuse the existing
popup layer identity when dimensions change, with hidden `Layers.Bounds`.

Allow Layers to restore a contained old-popup rectangle from the saved image
and retain the image for a following heading. Source coordinates/pitch refer to
the saved union; destination is just the old popup footprint. Hold its pin and
scene token until DMA completion or established quiescence. Failed/stale saves,
odd alignment, ownership/menu replacement and changed geometry keep normal
redraw fallback. Reuse requires a valid image covering the next popup.

Accumulate exposure notifications during a menu interaction and publish them
when it ends, after the menu bar is repaired. A successful intermediate restore
repairs manager pixels without creating a fresh application paint obligation.
Keep the normal final `WM_REDRAW` contract. No application wait holds a scene
token, and unrelated Tasks continue running. Real drawing/console changes and
geometry/lifetime changes still invalidate intersecting saves. On a cache miss,
ordinary visible repair remains runnable; never save residual old-menu pixels.

Keep one background slot, two existing popup slots, one scene token and one
active display transfer. Do not add a general compositor or a second production
cache path. Add only the bounded restore rectangle/continuation state needed by
this transition. Commit after emitted transaction/pixel/failure checks pass.

MS2 implemented: one capture covers application headings; restore copies only
the retiring popup, retaining its layer identity and background while switching.
Exposure is accumulated until dismissal. Optimized Layers passes 60,162 checks;
raw/optimized boundary probes pass 124 each; AES menu pixels/input/mutation/exit
and the 53-check native cache regression pass. Host checks: 459, four skips.
Added fixed upper metadata is 10 bytes (two bytes plus an aligned eight-byte
rectangle); `Scene.copyTarget` is reused. No VRAM, per-client or reserved bank-zero
growth: **0 fixed / 0 per public Task / 0 idle bank-zero bytes**.

## MS3 Measure and package the corrected transition

Reuse the immutable AV6 ZIP as baseline with the same compiler, ROM, emulator,
media and geometry. Extend the existing menu timing tool to correlate background
captures/restores and Files repaint counts, and exercise repeated File/View
switches before dismissal. Cover keyboard and physical pointer transitions,
including different popup sizes and highlighted rows. Assert clean old-menu
removal, correct new-popup pixels and final application repaint.

Run 20 samples per idle/cold interaction. Aim for warm File/View switching at
most 300 ms median/p95 (baseline 702 ms), background hits during the idle gesture,
and no extra Files repaint between successful cached heading replacements.
Retain the previous 100 ms valid-dismissal goal and report any missed gate.
Compare opening/highlight/fallback/final-repaint times with AV6; disclose any
regression beyond one PAL frame. Keep observations outside timed intervals.
Use a counter-disabled control if adding executable diagnostics; prefer the
existing counters and caller paint count.

Exercise a real underlying change while a menu is open, invalid-save fallback,
replacement/owner exit, and failed/unquiesced DMA. Run host checks and focused
optimized Layers/AES/menu regressions; use small raw/optimized probes for changed
call/record boundaries. Reuse unchanged AV6 broad app results, and run the exact
new OF816 desktop ZIP through the Files/Counter/Panel/Text/dialog walkthrough.
No release matrix or real-hardware qualification is implied.

Update reference contracts and record source/artifact hashes, raw samples,
remaining limits and a demo launch command. Build with `tools/build_demo.py
--gem-desktop`; preserve pinned ROM, notices, matching disks and five-second
OF816 autoboot. Commit the final evidence and tooling.

## Memory budget

No VRAM reservations change. Production remains 375,296 bytes; the background
union must fit the existing 76,800-byte slot. Target less than 64 added fixed
upper-RAM metadata bytes; report generated/actual aligned growth per slice.
No added per-client journal storage is required. Reserved bank-zero delta is
**0 fixed / 0 per public Task / 0 idle bytes**, including guards, alignment and
unused capacity. No stack or direct-page reservation grows.
