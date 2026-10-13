# Dropdown menu latency implementation

Based on the [design note](menu-latency-design.md). Keep changes within the
existing presenter, renderer and menu tests. No public ABI or compiler change.

ML1–ML4 are implemented and development-checked. The
[execution record](../../history/menu-latency.md) and
[machine-readable evidence](../../development/menu-latency.json) contain the
matched timing samples, functional checks, demo hashes and memory accounting.
File/Windows opening medians improve by 44%/36%; native highlight p95 is
unchanged at the frame sampling resolution. Save-under remains deferred.

## ML1 — Record comparable menu feedback

- Add a reusable measurement helper for physical open, highlight, heading
  switch and close. Measure visible completion, not just accepted input.
- Record the unchanged implementation first using the exact desktop ZIP and
  settled reference images; retain raw samples and machine/build pins. Use the
  optimized menu fixture for independent pixel and lifetime checks.
- Include complete popup and bar pixels, not one early-changing pixel. State
  frame polling and workload limits alongside the result.

## ML2 — Batch bounded menu drawing

- Replace 96-pixel fragments and one-object callbacks with complete labels,
  up to four drawn objects and 80 visible text cells per callback.
- Walk at most the admitted 32 objects; keep the 16-row scratch transaction and
  existing done/more continuation protocol.
- Draw native labels up to 24 characters at once and visit only rows that
  intersect the current strip.
- Extend emitted pixel coverage for long and checked labels and a clipped
  popup. Overlap two long objects in a strip to exercise a budget continuation
  and a vertically clipped glyph. Verify disabled, hidden and title rendering.

## ML3 — Limit damage and prefer ready menus

- Separate full menu invalidation from native selection damage; repaint only
  the old/new rows on highlighting.
- Limit bar damage on menu transitions to affected headings/segments; retain
  full damage for menu ownership/content replacement where needed.
- Prefer popup/bar at a new paint boundary, with at most two preferred menu
  transactions before ready ordinary work gets its round-robin turn.
- Preserve source publication, input capture and all update-lock/scene gates.
- Run the optimized menu regression and check ordinary application progress.

## ML4 — Measure and package

- Repeat ML1 interactions on the final code. Report median/p95 independently
  for each interaction; investigate any material regression.
- Run the host suite, the affected optimized menu fixture and an exact-ZIP
  desktop menu walkthrough with another updating application.
- Rebuild through `tools/build_demo.py` with OF816, five-second autoboot,
  pinned ROM and notices. Provide the ZIP and launch command.
- Update current contracts, this plan, index and execution record with actual
  results and remaining limits. Keep save-under deferred unless a separate
  correctness design is warranted by dismissal results.

Every slice adds **0 fixed / 0 per-Task / 0 idle reserved bank-zero bytes**.
Check actual build accounting, including guards, alignment and capacity.
Tests are development tier; no full qualification matrix or compiler test run.
