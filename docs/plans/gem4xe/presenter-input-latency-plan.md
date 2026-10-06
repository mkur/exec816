# Presenter input latency implementation plan

[GEM plans](README.md) · [Implementation plans](../README.md) ·
[Current desktop contract](../../reference/desktop.md)

Status: PI1 is implemented and checked at the development tier;
PI2–PI4 remain pending. Its [execution record](../../history/aes-hybrid.md#presenter-input-boundaries)
documents a small CPU-gap reduction and mixed latency results. The 20 ms target
and HY4 remain open. Shorten the work the existing
presenter performs between input-service opportunities. Keep the gains from the
completed [VBXE builder refactor](vbxe-builder-refactor-plan.md), then divide
the remaining expensive work into smaller resumable operations. Implement and
check each executable slice before committing it.

## Starting evidence

Use the retained [BR4 comparison](../../development/vbxe-builder-br4.json) and
[integrated results](../../history/aes-hybrid.md#integrated-builder-results).
The starting implementation is BR3, commit `3970f83`, with BR4's profiling tools
in `1dc7ce4`. There is no new baseline milestone. Preserve the historical JSON
and hashes; write new measurements separately.

The retained `build/vbxe-builder/br3/panel-run/work-unit-analysis.json` identifies
these maxima in the original ten-gesture cohorts:

| Measured quantity, ms | Idle | Scrolling | Disk |
| --- | ---: | ---: | ---: |
| Elapsed time of gap selected by maximum CPU | 45.944 | 90.824 | 90.703 |
| Maximum input-service gap CPU | 32.708 | 60.641 | 62.523 |
| Maximum `DESKHOST.Controls` CPU | 26.281 | 25.335 | 25.937 |
| Maximum widget-paint CPU | 19.804 | 18.006 | 18.601 |
| Maximum `CONSOLEDISPLAY.Present` CPU | — | 49.837 | 50.372 |

CPU excludes interrupt handling and time when another Task runs. Routine costs
are inclusive and overlap; do not add the rows. These are measured samples,
not worst-case execution bounds. Startup/retirement are separate: the complete
trace includes an 83.634 ms CPU control pass and a 35.511 ms paint pump.

Three mechanisms explain the remaining opportunity:

1. `DESKHOST.Controls` admits up to four requests. AES admission already calls
   an input boundary; native `DESKCORE.Pump(service,1)` does not. Multiple native
   requests can accumulate before input is revisited.
2. Widget drawing permits four intersecting objects per call, with rejected
   objects scanned in the same call. Sixteen scanlines and a bounded blitter
   list do not bound all CPU spent constructing a strip.
3. Console presentation permits four rows/160 cells, and `DesktopDraw` visits
   every clipped fragment synchronously. A single clipped-text call reaches
   about 19 ms CPU, while the enclosing presentation reaches about 50 ms.

Scheduling still matters. One slow idle input sample spends 23.538 ms runnable
but off CPU and contains no widget paint. Presenter changes cannot remove that
delay directly; keep its attribution visible.

## Execution rules

An input boundary means returning to ordinary presenter code, servicing captured
events, and presenting the pointer when the renderer is quiescent. It does not
mean an `Exec.Yield`, another Task, a timer wait or a new kernel service.

- Reuse `DESKINPUT.Service` and `Present`. Preserve latched wake information,
  pending events and the existing empty-observation rule. Do not clear request,
  stop or display-completion signals as a side effect. Bound each intake pass;
  continuous motion must not prevent other work.
- Cross the boundary only after the C bridge has returned and released its
  temporary context. Never call input handling recursively from an object,
  glyph encoder, list builder or active rendering callback. Existing pending
  DMA gates pointer drawing; its command arena remains exclusive.
- Input collection and model mutation remain separate. Keep
  `DESKINPUT.Advance` after native control admission, including its scene/AES
  lock gates. Do not reorder patches and widget gestures just to make the
  input-consumption number smaller.
- Preserve four total native/AES admissions per outer turn, alternating
  endpoints, the reserved late AES opportunity and the one-handoff limit before
  console output. Smaller paint steps must not reset these budgets. Keep the
  existing preemptive Task scheduling and signal-driven idle wait.
- Keep list ceilings of 64 records/8,192 work units and existing hardware fault
  recovery. Trust admitted internal geometry; add no repeated validation.
- Retain the scene token while a widget strip is incomplete, and publish only
  a fully reconstructed strip. Preserve the existing token lifetime across the
  wider repaint in these slices. Do not acknowledge partially painted damage.

The last rule limits the outcome: input and cursor response can improve while
widget model commits still wait for repaint completion. Measure that wait
explicitly. A later change to paint-transaction lifetime would need its own
damage/version protocol; simply releasing and reacquiring the token would
either lose damage or repeatedly restart work.

## PI1 — Service input between independent presenter operations

Implemented. [Evidence](../../development/presenter-input-pi1.json) includes
the original idle cohort, a paired fixed-offer diagnostic, admission/late-input
regressions, GUI locks, cache/move pixels, console fairness and idle sleep.
The maximum idle CPU gap is 32.708 → 31.615 ms; the original input p95 regresses
19.132 → 25.449 ms. Fixed-offer p95 improves 49.855 → 48.815 ms with essentially
unchanged median. This slice establishes service boundaries; it does not yet
establish an overall GUI latency improvement.

Change `lib/desktop/deskhost.act` and `lib/console/consoledriver.act` first.
Reuse the existing input-boundary helper, making its ownership and call sites
explicit rather than introducing a second event path.

1. Give successful native admissions the same input-service boundary as AES
   admissions, including requests moved to the deferred queue. Apply it to
   both preferred and fallback native endpoint calls, exactly once per
   admitted request.
2. Separate completed cache/move continuation work from following admissions
   with a boundary when that continuation did work. Add a boundary after the
   console borrow is released, before event settlement or optional cache work.
3. Preserve stop/completion handling and avoid empty repeated service calls at
   adjacent sites. An active-work boundary may inspect input; a settled worker
   must still sleep without polling or new periodic wakeups.
4. Extend passive tracing to identify individual native admissions and their
   operation codes, widget gesture advancement, and the new boundaries. Split
   control cost into per-request work and intake overhead. A long single request
   must remain visible; this slice only removes concatenation between requests.

Validation: focused optimized native/AES control ordering and lock tests;
input arriving during a control burst and after the last boundary before Wait;
bounded progress for both ports, console writers and cancellation; the existing
settled-presenter idle check. Reuse the idle panel cohort to check overhead and
the control-dominated gap. Record the longest individual request, including
startup and retirement separately.

Commit: `Service presenter input between native control admissions`.

## PI2 — Divide widget and frame painting into smaller steps

Change `lib/desktop/deskpaint.act`, `deskwidgets.act`, and the local adaptation
in `ports/gem4xe/aes/widgets-render.c`. Keep donor GEM4XE untouched.

Start with one intersecting widget object per C call instead of four. Also cap
the number of examined objects, including clipped/hidden objects, so a rejected
tree tail cannot escape the work budget. Preserve traversal order and the next
index; do not redraw completed objects on resumption. Choose the scan cap from
the emitted timing evidence and record the chosen constant.

Keep the sixteen-row strip initially. Background setup, frame/title work and
object drawing must have separate resumable stages where their combination
exceeds the target below. A continuation may complete no visible object; it
must still advance its scan or stage. Frame setup must run once, and the widget
background must remain in scratch until all intersecting objects are complete.

Expose progress to the native presenter so it can service input after each
step. Allow consecutive ready steps within the existing aggregate allowance,
with a boundary between them, without an unconditional Yield, console pass or
fresh control budget between every object. Pending interaction can return to
the normal worker ordering. Keep a hard per-turn cap even when input is quiet.

Keep one-object drawing as the first candidate, then measure. If an individual
object still dominates, reduce the strip height or add a bounded internal
primitive continuation for that measured case. Do not assume that halving
height halves CPU: label layout, clipping and object setup repeat. Select one
production policy; do not retain multiple compatibility modes.

Validation: optimized widget pixel and presentation fixtures, including
overlapping objects, hidden tails, disabled stipple, focus XOR, long labels,
odd clip edges and fault/reopen between chunks. Inject motion/press/release
between object steps and confirm no partial scratch publication, duplicate XOR
or lost gesture. Include close/hide/patch requests while painting, with token
and context lifetime assertions. Measure both smaller step CPU and total time
until the completed button is visible; extra fences must not erase the benefit.

Commit: `Make widget paint steps resumable at input boundaries`.

## PI3 — Bound console and retained-text presentation

This slice addresses the approximately 50 ms loaded presentation call; broader
console throughput optimization remains separate. Change
`lib/console/consoledisplay.act`, its batch-display include,
`lib/console/console-desktop-drawing.inc`, and the text paths in `deskpaint.act`.

Start with one dirty-row segment of at most 32 glyphs per presentation step.
Use the existing dirty-row endpoints to retain ordinary console progress.
Advance only the portion actually drawn, keep the generation check, and retain
the existing batch and caret completion semantics. Resume at the unfinished
segment before consuming another scroll that would restart the repair.

The budget must also cover the less obvious text paths: console exposure
painting currently draws up to two full rows per strip, frame/title text can
run before widget drawing, and a retained text command can be long despite
the four-command cap. Give these paths a glyph offset/row/stage continuation.
Keep complete glyphs as the unit; screen clipping still handles partial edges.

Count clipped fragments as work too. If a 32-glyph segment across the supported
window overlaps still exceeds the target, make fragment traversal resumable
under the existing scene token. A synchronous public drawing contract must
remain synchronous; expose a private presenter continuation and have any
required synchronous caller drain it. Do not duplicate the renderer or change
public request completion semantics.

Continuations retain scalar identity, generation and bounded offsets in upper
RAM. Re-resolve console entries under their normal borrow on each turn; retain
no borrowed instance, view or caller-buffer pointer across a worker return.
Where a scene token freezes a retained model, keep it until all of that
operation's fragments retire. On cancellation, retirement, geometry change or
fault, use the existing discard/dirty/cleanup rules. Never complete a request
twice or lose damage because only a prefix was drawn.

Validation: optimized clipped console presentation and batch-lifetime cases,
including the original overlapping-panel scroll failure, bottom-row progress,
caret repair, cancellation, hide/resize/retirement and resumed rendering after
DMA. Check console fairness and exact final pixels. Run focused scroll/disk
panel cohorts and report segment CPU, full repair time and completed background
work. Tune the fixed glyph cap if needed; do not widen blitter lists to offset
the extra calls.

Commit: `Bound presenter text work between input checks`.

## PI4 — Compare latency and record the remaining bottleneck

Reuse `tools/profile_vbxe_builder.py` and `tools/analyze_vbxe_builder.py`, with
the passive markers added above. Use the original ten gestures under idle,
scroll and disk loads and the retained BR4 image/configuration. Pin the actual
compiler/ABI, ROM, emulator, workload and image hashes in each new record.

Report median, p95 and maximum for capture-to-consumption, capture-to-model
commit, button pixels and combined visible feedback. Also report:

- input-service gaps split into charged CPU, interrupts and off-Task time;
- per-operation CPU and call counts, including individual control requests,
  input service, widget steps, text segments and optional cache work;
- time retained input waits behind scene/AES locks, plus time from model commit
  to completed strip publication;
- total gesture/repair CPU, list/fence counts, stack high-water marks, request
  progress and completed console/disk/AES work.

The engineering target is **at most 20 ms charged CPU between input-service
entries in each steady gesture cohort**, down from the measured 33–63 ms.
This is a development target, not a wall-clock or worst-case guarantee. Keep
startup, first drawing and retirement maxima alongside it without hiding them
in the steady-state distribution. If a single control/model operation exceeds
the target, identify its opcode and cost before proposing a separate atomic
publication/continuation change; checkpoints around it do not make it bounded.

Completion requires correct pixels/lifetimes and a measured reduction in the
longest presenter-controlled gaps. Report the target as open if it is missed.
Do not accept an input-consumption improvement that consistently worsens
model-commit or button-pixel median/p95. Investigate such a regression with the
same offered-work diagnostic and matched input timing; completion-paced cohort
counts alone cannot distinguish scheduling phase from added work. Reuse the
existing equal-load diagnostics for this purpose rather than replacing the
original acceptance workload.

Observe the transition from capture through visible completion when checking
for flicker. The existing feedback observer starts after model observation and
excludes pointer pixels; retaining that observer alone supports only the same
limited claim. Keep exact final-pixel, guard, ownership and cleanup checks.

Record results under `docs/development`, add the implementation record to
`docs/history/aes-hybrid.md`, and update affected desktop/widget/console
contracts and plan indexes. State whether shorter CPU units translated into
faster model and pixel response, and which remaining delay is scene ownership,
rendering or scheduler time. HY4 remains separate unless all of its original
matched acceptance cases and limits are actually met.

Commit: `Record presenter input latency after bounded work steps`.

## Memory and validation scope

For every slice, target reserved bank-zero delta **0 bytes fixed, 0 per public
Task and 0 idle**, including guards, alignment and unused capacity. Use the
existing presenter Task/stack, command arena, widget scratch strip, snapshot
slots and table bank. Report any added upper-RAM continuation bytes and linked
code growth, and measure stack usage instead of enlarging a stack reservation.
No extra VRAM reservation is planned.

Follow the [development testing tier](../../contributing/testing.md): host
checks plus focused optimized emitted-code tests for changed behavior. If a
shared generated record or C bridge layout changes, update its generator,
callers and probes together and run a small raw/optimized layout/context test.
Use targeted interrupt/lifetime cases at changed continuation boundaries;
do not automatically rerun the full qualification matrix. No demo refresh is
needed to implement these slices; any later refresh uses `tools/build_demo.py`
with OF816 and the standard five-second autoboot.

Kernel priorities, time slices, timer/I/O transport, broad arithmetic cleanup,
and shorter scene-token lifetimes are follow-on work. The result of this plan
is a presenter that offers input service between bounded pieces of active work,
with measured costs and the existing ownership protocol intact.
