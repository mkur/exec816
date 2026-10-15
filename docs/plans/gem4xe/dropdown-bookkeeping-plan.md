# Dropdown bookkeeping implementation plan

[Dropdown analysis](../../history/dropdown-analysis.md) ·
[Baseline measurements](../../development/dropdown-analysis.json) ·
[Layers contract](../../reference/layers.md)

Reduce the CPU work around existing cached menu copies. A warmed keyboard
File → View switch currently takes 200.576 ms, including 143.414 ms presenter
CPU. Repeated damage queries cost 8.094 ms outside summary maintenance;
rectangle subtraction costs 31.884 ms inside the two visibility rebuilds.
Those are measured costs, not predicted savings.

Implement only the two local optimizations identified by the analysis. Keep
popup hide/show, saved-background transactions, input ordering, painting
fairness, cache keys and normal Task preemption unchanged. Combining popup
transitions remains separate work in the proposed
[popup transition design](popup-transition-design.md).

## Slices

Commit the existing analysis and this plan first, then commit each executable
slice and the final measurement record separately. Reuse the frozen QT4 capture
as the baseline; no new baseline build or qualification matrix is needed.

### DB1 Select paint candidates from the maintained damage bits

Status: implemented; [development checks](../../history/dropdown-bookkeeping.md)
pass. Reserved bank-zero delta: fixed 0, per Task 0, idle 0.

- Add a small Layers lookup that returns the requested layer only when its
  existing `Scene.visibleDamage` bit is set. Reuse the internal slot lookup;
  do not derive slots with pointer division or introduce another cache.
- Use it for popup, menu-bar and focused-window candidate lookup. Use the
  known slot's bit directly in the painter's round-robin loop.
- Preserve popup-before-bar precedence, the two-menu-transaction fairness
  limit, focused-window preference, background handling and round-robin
  advancement. Leave `Damaged` in the Layers mutation/summary path.
- Extend the existing emitted readiness checks to compare lookup results
  with the independent intersection oracle for visible, covered, hidden,
  deleted/reused and background slots. Retain failure/retirement checks.
- Run host checks, optimized Layers checks and one optimized desktop
  presentation fixture to exercise the changed painter and pixel restoration.

Expected memory: no new persistent storage, layout or reserved bank-zero bytes.
Record emitted code size and local stack changes.

Commit: `Use visible damage bits for desktop paint selection`.

### DB2 Subtract small regions in one pass

Status: implemented; [development checks](../../history/dropdown-bookkeeping.md)
pass. Reserved bank-zero delta: fixed 0, per Task 0, idle 0.

- Each source rectangle produces at most four disjoint output rectangles.
  When `source.count <= MAX_RECTS / 4`, begin with the existing emitting pass;
  the destination cannot overflow. Use a compile-time bound, not runtime
  division. Share the current intersection/emission code.
- Keep count-before-emit for larger source regions, preserving destination
  bytes on capacity failure. Preserve source/target separation, cut aliasing,
  signed coordinates, half-open coverage, empty-region behavior and ordering.
- Avoid adding scratch regions, heap work, mutable globals or a second
  subtraction implementation. Further special cases need measured justification.
- Extend emitted tests at and above the one-pass threshold, exact capacity,
  successful large-region subtraction, overflow with unchanged destination,
  and a cut stored inside the destination. Check coverage independently.
- Run host checks and the optimized Layers fixture, including its scene,
  cross-bank, damage-stream, transaction, guard and OS-return coverage.

Expected memory: no persistent storage or reservation growth. Report actual
code/local stack change; keep raw testing for a compiler-facing defect only.

Commit: `Subtract bounded small regions without a counting pass`.

### DB3 Measure the result and refresh the desktop demo

Status: complete; [measurements and demo](../../history/dropdown-bookkeeping.md).
Warm switch: 200.6 → 180.4 ms elapsed, 143.4 → 121.5 ms presenter CPU.
Pointer-heading response remains 280.7 ms. No reservation growth.

Build one final desktop package with `tools/build_demo.py --gem-desktop
--release-compiler`, including OF816, five-second autoboot, matching system
disk, ROM, licenses and checksums. Use the unchanged compiler/platform pins.
Keep traces, manifests and test output outside `exec816-demo.zip`.

Run the existing 18-action `trace_menu_response.py` capture on that exact
package. Compare warmed open, highlight, switch and dismiss separately from
the three-heading keyboard cache misses and physical-pointer travel cases.
Require correct final menu/background pixels, zero Files redraws during these
actions, expected cache reuse, intact guards and normal EXIT. Verify that
damage queries outside summary maintenance disappear and measure subtraction,
rebuild, presenter CPU and end-to-end response separately.

Record minimum/median/maximum for these small cohorts, not p95. Preserve the
one-frame pixel-sampling limitation and distinguish copy submission/IRQ
observation from hardware DMA time. Investigate any behavioral failure or
material regression before committing; repeat only the affected case.

Save compact evidence under `docs/development`, interpretation under
`docs/history`, update indices and slice status, and provide the demo launch
command. Report fixed and per-Task reserved bank-zero deltas, native code/data,
stack observations and VRAM reservations. Expected reservation deltas are all
zero, including guards, alignment and unused capacity. No new signal, timer,
Task, DP or stack allocation is planned.

Commit: `Record dropdown bookkeeping results and refresh the demo`.

## Validation scope

Use development checks under the [testing policy](../../contributing/testing.md).
No ABI layout, scheduling, IRQ or ownership protocol changes are planned.
Optimized emitted behavior is sufficient unless investigation exposes a
compiler-facing problem. These focused checks do not qualify real hardware
or establish worst-case response/stack bounds.
