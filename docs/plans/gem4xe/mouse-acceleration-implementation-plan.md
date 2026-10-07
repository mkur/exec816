# Mouse acceleration implementation plan

[GEM integration](README.md) · [Design note](mouse-acceleration-design.md) ·
[Current input contract](../../reference/input.md) · [Current desktop contract](../../reference/desktop.md)

Status: MA1 implemented at the development tier, 2026-10-07; MA2–MA4 pending.
See the [execution record](../../history/mouse-acceleration.md).
Implement the design in four executable slices, committing after each slice.
Keep PI3 (`7f9a25d`) and its tested desktop demo as the existing baseline; no
separate baseline-establishment slice is needed. PI4/HY4 remain open and deferred
while the desktop gains functionality.

The result is a PAL ST-mouse desktop with an optional mild acceleration curve,
fine slow motion, faster cross-screen travel and consistent sensitivity under
load. GEM/native GUI clients retain absolute screen-coordinate interfaces.

## Working rules

- Follow the [platform contract](../../reference/platform.md), repository
  ownership and [testing policy](../../contributing/testing.md). Use the pinned
  compiler and mouse-capable emulator/ROM configuration; record actual hashes
  and overrides with evidence.
- Generate changed ABI bindings together and rebuild affected programs. Retain
  one current INPUT API and one capture implementation. Keep current reference
  pages accurate at each executable slice.
- Do not alter sampling frequency, presenter budgets, scheduling, timers,
  button/drag policy or GEM4XE donor source to implement acceleration.
- Keep configuration validation at acquisition and trust internal motion
  records. Preserve queue limits, loss/route lifetime and IRQ/NMI protocols.
- Report reserved bank-zero delta in every slice: target **0 fixed + 0 per
  public Task + 0 idle bytes**, including alignment, guards and spare capacity.
  Separately report upper-memory live/reserved growth and linked bank counts.
- Default to optimized emitted-code checks. Use small raw/optimized tests for
  changed ABI layouts and language/interrupt bridges; do not duplicate every
  loaded desktop scenario in raw mode. These are development checks, not full
  hosted qualification.

## MA1 — Deliver timed relative motion

Implemented. The desktop still selects absolute input and fixed 2× scaling.
The 32-slot capacity diagnostic required 64 slots; the final upper layout is
recorded in the design and [MA1 evidence](../../development/mouse-acceleration-ma1.json).

1. Define version-3 relative-mode and event flags, `motionInfo` encoding,
   reset semantics and unused configuration-field requirements in
   [input.json](../../../abi/input.json). Keep the public 32-byte configuration
   and 24-byte event layouts. Define native run length, clock/history fields,
   interval-class table and 28-byte sample layout in machine-readable inputs.
2. Update [generate_input.py](../../../tools/generate_input.py) and
   [generate_input_native.py](../../../tools/generate_input_native.py), generated
   Action!/assembly/C outputs, consumers and fixtures together. Audit the C
   event adapter's reserved-field checks. Generate stride/index constants rather
   than retaining handwritten assumptions about 24-byte raw records.
3. Add the saturating capture interval clock and persistent producer history
   in [pointer.s](../../../platform/altirraos/pointer.s). Cover normal/fine timer
   transitions, frame wrap and restart/reset paths. Preserve the idle fast path
   after history expires. The IRQ supplies timing classes and counts only.
4. Coalesce only equal vectors/classes within identity, epoch and button
   boundaries, up to 64 transitions per record. Make pending records immediately
   readable. Preserve cumulative hardware counts and existing absolute-mode
   coordinate behavior. Add relative delivery in
   [input.act](../../../lib/input/input.act), including motion-before-button
   splitting with a zero-delta retained button event.
5. Start with the existing 32-slot ring and 1,536-byte guarded upper-memory
   reservation. Pin the exact new header, record and guard extents. Exercise
   alternating-axis and timing-boundary traces at realistic service delays
   before freezing capacity. If 32 slots cannot cover the selected PI3 load
   traces, enlarge upper storage, audit adjacent native code/state reservations
   and update the design's exact memory account in this slice.

Validation:

- Extend [ABI host checks](../../../tests/test_input_abi.py) and small raw/opt
  emitted layout/bridge cases for event size, flags, signed deltas, metadata,
  offsets and zero fields in keyboard/absolute modes.
- Extend [capture tests](../../../tools/test_pointer_capture.py) and
  [failure tests](../../../tools/test_pointer_failures.py) for timing boundaries,
  a partial run consumed early, vector changes, reversal, pause, buttons,
  route/discard/loss, wrap and bounded run splitting. Compare delivered facts
  with an independent transition/timestamp oracle.
- Compare the same captured stream with different consumer drain schedules.
  Require identical ordered transition/timing information after expanding runs;
  producer history must survive an empty ring. Require correct durable loss
  when capacity is deliberately exceeded.
- Use targeted native/emulation entry and NMI boundary cases to verify register,
  stack and direct-page restoration. Check raw-ring guards and cleanup.
- Run [mouse/SIO boundary checks](../../../tools/test_desktop_mouse_boundary.py)
  with movement and active-idle history, including timer-mode changes. Preserve
  the existing capture-gap and SIO wire-timing gates. Record per-path capture
  cycles and queue high-water marks under selected delayed-drain traces.

Exit: relative timing is independent of Task service, absolute users still
work, layout fits, and capture/transport gates pass. If the interval-clock or
capacity proof fails, resolve it here before applying acceleration.

Update the INPUT/platform contracts with implemented behavior and record MA1
evidence. Suggested commit: `input: preserve timed relative pointer runs`.

## MA2 — Apply the profile once in the desktop

Deliver both profiles through one Task-side transform. Keep `off` as the
intermediate default until MA3's loaded checks and tuning pass.

1. Add a small desktop pointer-transform module, provisionally
   `lib/desktop/deskmouse.act`, owning pixel position, fractional remainders,
   reset/direction state and profile selection. Generate a conservative gain
   table from recorded parameters: slow/reset 1×, ordinary around 2×, fast
   capped at 4×, with intermediate gains. `off` is constant 2×.
2. Implement quarter-pixel accumulation, common X/Y gain, pixel-space clipping
   and immediate reversal after clipping. Keep the curve identical during a
   drag. Use capture metadata to reset history; never infer speed from Task
   elapsed time, event batch size or GUI load. Inspect emitted code for general
   multiply/divide/remainder helpers and replace such arithmetic with the
   specified bounded shifts/adds.
3. Switch [deskinput.act](../../../lib/desktop/deskinput.act) to relative
   acquisition and apply the transform once to each newly taken input event.
   Publish absolute coordinates before cursor tracking, hit testing and AES
   deferral. Queued [AES input](../../../lib/aes/aesinput.act) must replay without
   a second transform. A button-only event uses the position after all preceding
   movement, including the motion part of the same hardware sample.
4. Add explicit `off`/`mild` build selection through the existing desktop
   generator/build path. Record the profile, parameters/table hash and clock
   profile in build metadata. Retire the fixed-scale-only desktop assumption
   and update affected callers/tools together; no new public GUI settings API
   or preferences window is required.

Validation:

- Add a small independent host motion oracle and optimized emitted transform
  fixture. Cover gain boundaries, reset/idle, repeated fractional movement,
  positive/negative symmetry, diagonal traces and all edges/corners.
- Compare different partitions of an identical timed stream: final position,
  fractional state and button coordinates must agree. Include run-length limits,
  reversal and clipping. Do not require every intermediate cursor presentation
  to be identical under different scheduling.
- Exercise simultaneous motion/button samples, click/drag/release, route and
  loss cancellation, and an AES lock that queues input before replay. Assert
  that replay does not apply acceleration again.
- Update [pointer-scale tests](../../../tools/test_desktop_pointer_scale.py) for
  both profiles and the intentional odd-edge change documented in the design.
  Rename tests if their names no longer describe their scope. Keep existing
  cursor, client-event and hit-test coordinates consistent.
- Measure the transform's emitted CPU cost and bounded completion. Verify no
  new wakeup, timer request, Task or bank-zero reservation.

Exit: both selectable profiles work end to end, with deterministic displacement,
correct button positions and immediate edge reversal. Update the desktop
contract with supported behavior and the intermediate default.

Suggested commit: `desktop: add task-side mouse acceleration profiles`.

## MA3 — Check loaded behavior and choose the mild default

Deliver a usable profile with evidence from the actual physical-input path.
Keep the PI3 renderer and budgets unchanged to isolate the feature.

1. Update [desktop_mouse.py](../../../tools/desktop_mouse.py) and affected
   integration runners. They currently assume an inverse fixed scale for
   positioning. Generate physical motion using an independent profile-aware
   oracle or deliberate slow/reset movements; do not bypass capture by writing
   the guest cursor position. Read profile metadata explicitly.
2. Replay selected slow adjustments, fast traversals, diagonal/alternating-axis
   movement, near-threshold motion, pauses, reversals and edge returns under
   idle, scrolling and disk load. Include Control Panel clicks and window
   dragging. Check selected no-loss traces and deliberately overflowing traces
   separately, with queue high-water marks in the evidence.
3. Separate exact captured-stream determinism from physical sampling variation:
   replaying identical captured facts must be exact, while an external transition
   near a sampling/class boundary can acquire slightly different timing.
   Report that variation and tune the table if it causes obvious speed jumps.
   Do not loosen correctness assertions to conceal changed capture or queue loss.
4. Use existing [desktop measurement tooling](../../../tools/measure_desktop.py)
   for a focused matched comparison: capture cost, Task transform cost, input
   service gaps and visible response under the selected loads. Record medians
   and tails where available. Acceleration is not expected to close PI4/HY4;
   investigate regressions caused by this feature before changing the default.
5. Once these checks pass, set `mild` as the default desktop profile, retain the
   explicit build-time `off` option and document the exact chosen curve. Leave
   runtime preferences and broader latency work for later desktop work.

Validation includes focused [drag](../../../tools/test_desktop_drag.py),
[AES input](../../../tools/test_aes_input.py), capture/failure and mouse/SIO
boundary cases affected by the integration. Re-run failed or newly affected
cases after changes; do not automatically run the full qualification matrix.
Include cleanup, guard and context checks in the selected scenarios.

Exit: mild motion gives fine slow positioning and greater fast travel without
load-dependent gain, broken gestures, new selected-trace overflow or failed
capture/SIO gates. Record actual memory growth, clock/profile parameters,
configuration hashes, scope and remaining limitations in a development record
and linked history entry. Final subjective tuning can follow user testing of
the next slice's artifact.

Suggested commit: `desktop: validate and enable mild mouse acceleration`.

## MA4 — Refresh the desktop demo

Build the desktop distribution with [build_demo.py](../../../tools/build_demo.py),
including OF816, matching disk/ROM, licenses and checksums. Preserve the
five-second OF816 autoboot and the standard shell/prime demo path. Package only
the boot files, short guide, licenses and checksums in `exec816-demo.zip`; keep
intermediates and development evidence outside the archive.

Document the default profile and how to build the off variant. Test the exact
extracted archive using the updated physical-mouse helpers and
[demo runner](../../../tools/test_demo.py): autoboot, fine and fast motion,
Control Panel buttons, dragging and edge reversal, shell/disk/pipeline use,
loss/exit cleanup where applicable, and unchanged guards. Record artifact hashes
and actual execution scope. Keep targeted failure evidence separate from the
ordinary user walkthrough.

Update the current guides, history and indexes, mark implemented slices in this
plan and link their evidence. Report zero bank-zero reservation growth and the
actual upper-memory/bank cost, including any MA1 queue growth. PI4/HY4 remain
open; this is a development-tested usability feature.

Suggested commit: `demo: document and verify accelerated desktop pointer`.
