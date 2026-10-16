# Warm menu input implementation plan

Status: planned. Two small executable/delivery slices; commit each after its
focused checks.

[Analysis](../../history/warm-menu-bookkeeping-analysis.md) ·
[Previous results](../../history/clipped-menu-text.md) ·
[Testing policy](../../contributing/testing.md)

## Goal and scope

Start feedback for a captured keyboard menu change in the same presenter turn,
and avoid selecting a paint candidate when no visible damage exists. Preserve
the current pointer/focus ordering, popup replacement transaction, input-loss
handling, ordinary-paint fairness, strip/control/output budgets and preemption.

The preserved baseline is `build/clipped-menu-text/demo`, with the 36-action
passive capture in `build/clipped-menu-text/menus`. Three complete warm keyboard
switches spend 7.008, 7.916 and 7.007 ms between `DESKMENU.Key` returning and the
next `DESKMENU.Advance`. Each crosses a policy offer and an empty paint call,
without another Task running. The representative empty paint call costs
1.613 ms CPU **within** that delay; these potential savings overlap.

Saved-popup visibility/damage reconstruction, cache capacity, renderer changes
and scheduler/interrupt policy are outside this slice. A frame-sampled latency
improvement is a measurement outcome, not an assumed consequence of less CPU.

## WI1 Advance keyboard feedback and skip empty paint selection

In the worker-only `CONSOLEINPUT.Service`, call the existing `DESKMENU.Advance`
once after a bounded keyboard drain that consumed at least one event. Do not
repeat widget, drag or focus advancement. Keep the earlier pointer/menu path.

Calculate the retained input hint **before** advancing the menu: a heading
change can stop the drain with keys still queued, and advancing may clear the
menu block. Those keys must keep their next-turn hint without a new signal.
An empty/blocked drain does not add another advancement attempt. Existing menu
policy/readiness checks remain responsible for accepting or deferring work.

In `DESKPAINT.Pump`, consult the existing Layers `visibleDamage` summary before
candidate selection, only when `paintToken=0`. Return no work for an empty
summary. An active paint token must continue and retire regardless of that
summary. Keep the menu quota, focused-window preference and round-robin scan
unchanged when visible damage exists. Add no second summary or dirty flag.

Development checks: run the existing optimized AES-menu fixture, which covers
queued input during both copy phases, Escape/loss/outside clicks, ordinary-paint
fairness, title/strip continuation, failures, pixels and cleanup. Run the focused
host observer checks. The packaged trace in WI2 verifies same-turn ordering and
the empty-paint cost through actual emitted code. No compiler ABI changes need
raw-mode execution; no release matrix is planned.

Expected reserved bank-zero change: **0 fixed, 0 per public Task, 0 idle bytes**,
including guards, alignment and unused capacity. No cache, Scene, DP or stack
reservation changes. Record actual code and observed stack costs in WI2.

## WI2 Compare matched feedback and refresh the demo

Build a clean production package through `tools/build_demo.py --gem-desktop
--release-compiler`, retaining OF816, its five-second autoboot, the matching
system disk, pinned ROM, notices and distributable ZIP.

Use the unchanged 36-action passive observer with native and Counter controls
against that package. Reuse the preserved baseline; compare compiler/emulator/
ROM hashes and machine settings. Record individual complete keyboard/pointer
samples, heading-crossing brackets, popup commit/title retirement and presenter
CPU. Separate CPU through title retirement from CPU after it. Verify that a
queued keyboard heading reaches advancement before the next policy offer;
report empty paint CPU and unchanged copy/cache behavior. Keep cold opening,
highlight, dismissal, native menus and Counter as regression controls.

Archive the compact comparison in `docs/development`, with an execution record
in `docs/history` and links from both indexes. Check normal EXIT/OS return,
guards, resource reservations and ZIP checksums. Report development scope and
frame-sampling limits; three complete samples do not establish p95 or hardware
qualification. Provide the new demo launch command.
