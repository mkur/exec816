# Console responsiveness measurements

[Historical records](README.md) · [Console contract](../reference/console.md)

Batched aligned text reduces sampled loaded input latency from about 204 ms to
79–110 ms, but fast-console acceptance remains open. These three slices measure
complete worker turns, optimize their dominant cost, and repeat the loaded input
and scrolling checks. The production baseline is the single asynchronous rectangle scroll from
[drawing validation](drawing-validation-and-async-scroll.md).

## Worker turn baseline

The [first slice evidence](../development/console-responsiveness-s1.json) records
the unchanged eight-Task workload: an 80×24 producer, two 40×3 interactive tiles,
physical SDFS reads, ST mouse capture, keyboard and BREAK. It uses the pinned
PAL 65C816 ×8, 4 MiB, VBXE FX 1.26 configuration and compiler without overrides.

Passive instruction boundaries cover complete turns from one worker Collect
call to the next. Task selection is observed after the native adapter restores
the selected direct page. Native interrupt entry and the matching saved-stack
return boundary separate IRQ/NMI body time. Nested interrupts are accounted once;
an identical stopped interrupt entry repeated by the debugger on resume is
coalesced only while that same frame remains live.

Charged CPU includes the Task's C and kernel calls, scheduler/return overhead
and bus stalls. Interrupt eligibility/restore tails remain conservatively charged
to the current/selected Task. It is not an instruction-only execution count.
No guest instructions, allocations, priorities or scheduling policy are changed.
The producer's first submission and final collection delimit the loaded window;
startup, shutdown and incomplete boundary turns are excluded.

| Baseline measurement | Result |
| --- | ---: |
| Complete loaded turns | 119 |
| Maximum charged CPU per turn | 67.26 ms |
| Maximum elapsed turn | 208.50 ms |
| Maximum time off CPU per turn | 107.19 ms |
| Maximum text-call charged CPU | 49.78 ms |
| All text-call charged CPU | 2357.91 ms |
| All synchronous idle-wait charged CPU | 28.51 ms |
| Maximum input-service gap | 200.76 ms |
| Sampled raw glyph / cooked glyph and caret | 203.97 / 204.97 ms |

Routine totals are inclusive and overlap; do not sum nested entries. The slowest
elapsed turn comprises 65.12 ms charged CPU, 107.19 ms off CPU and 36.19 ms native
interrupt bodies. Text accounts for 47.15 ms of that turn's CPU charge. Rendering
and command preparation dominate synchronous blitter waiting, while scheduling
and interrupt load further stretch the interval before the next input check.

## Batched aligned text

The [second slice evidence](../development/console-responsiveness-s2.json) records
aligned ordinary drawing calls batched through a checked driver
operation. The complete CPU string, screen rectangle, colours and atlas extents
are validated before any drawing. A native helper builds a background fill and
up to 32 fixed glyph records directly in the existing command arena. Each batch
fits the existing record/work limits and completes before storage reuse. Blank
glyphs and hardware-zero ink have the same bounded path. Odd-X text and VDI
opcode 8 retain the existing device path; public raw-list validation is intact.

The [adapter contract](../../ports/gem4xe/adapter/README.md) describes the
limits. Raw and optimized emitted checks cover all 256 glyphs, all pens, both X
parities, batch boundaries, CPU string and VRAM destination bank crossings,
screen edges, invalid arguments with no drawn prefix, owner preemption and
display restoration. Fault cases stop the first full text batch and require no
later batch, covering both quiesced cleanup and retained reset-required state.

The first loaded comparison reduces maximum text-call charged CPU from 49.78 to
6.18 ms, total text-call charge from 2357.91 to 446.71 ms, and maximum complete
turn charge from 67.26 to 21.99 ms. Visible-input samples improve to 94.24 ms for
the raw glyph and 105.55 ms for cooked glyph/caret. The 40 ms goal still fails.
Time off CPU remains substantial (up to 96.54 ms per turn), and input/model
editing plus multiple drawing operations also exceed a 4 ms complete-turn budget.
The third slice repeats the benchmark at the existing input phases and replays
the final image without observers; these first samples are not a worst-case bound.

The whole-rectangle asynchronous scroll remains the production geometry. No
scheduler policy, worker quantum, input deadline or font was changed. Fixed,
root/kernel, per-Task and idle bank-zero reservation deltas are all **0 bytes**,
including guards, alignment and unused capacity. The new assembly uses the
existing call-clobbered DP area, not additional reserved workspace. Its 16-byte
stack packet is covered by the existing C stack reservations and emitted guards.

## Final phase measurements

The [third slice evidence](../development/console-responsiveness-s3.json) uses the
same optimized image at all three phases. Each phase also passes an unobserved
replay with matching final pixels and physical input phase. SIO deadlines, ST
sampling, input order, ownership, stack/domain guards and OS restoration pass
without changing their limits.

| Key timing relative to observed BUSY | Raw glyph upper bound | Cooked glyph and caret upper bound | Maximum turn CPU charge | Maximum input-service gap |
| --- | ---: | ---: | ---: | ---: |
| Immediate | 94.24 ms | 105.55 ms | 21.99 ms | 114.84 ms |
| About 2 ms later | 110.14 ms | 78.81 ms | 22.47 ms | 71.10 ms |
| About 8 ms later | 106.07 ms | 90.64 ms | 22.46 ms | 71.12 ms |

Every phase observes an incorrect frame after 40 ms, so these are definite
misses, not merely late sampling of an already correct screen. The samples are
not an exhaustive phase search. Raw input may lose focus, so its oracle checks
the glyph; cooked input checks both glyph and new caret.

On the final image the two isolated full-screen scrolls take **30.77 and
33.19 ms**; repeated scrolls take **38.23–44.75 ms**. Repeated scrolls are slower
than the earlier D6 samples (32.69–38.19 ms); the text improvement does not
establish a scroll-latency improvement. The geometry is still one whole copy/fill
list. The full repaint reaches its final fence in **251.21 ms**. This measurement
does not identify its first visible scanout, so the 500 ms visible repaint goal
remains unqualified. Thirteen exact pixel scenes and their unobserved replay
pass. The scroll observer now counts native generated glyph records as well as
the old glyph callback, preserving the check against redrawing unchanged cells.

The implementation and all three measurement slices are complete; **fast-console
performance acceptance remains open**. Complete turns still exceed 4 ms CPU
charge, visible input exceeds 40 ms and whole-screen scrolling exceeds 20 ms.
Exact hardware BUSY edges remain unmeasured. Future work should use the retained
turn traces to reduce non-text work and distinguish ready-queue delay from
deliberate worker yielding before changing scheduling policy. No priorities,
Task quantum, input deadline or scroll geometry were changed in these slices.

## Validation and reproduction

Run `tools/measure_async_scroll.py --output DIR --profile-turns` for the loaded
measurement; `--reuse` reuses the built image and `--replay` removes passive
observers. Build `s1-baseline` at commit `7b26417`, before applying the text
optimization in `adebac9`; do not label a current build as that baseline.
The final phase directories reuse the `s2-loaded` build's `program`,
`drawing`, `selected`, C-image record and generated Action sources; use
`--phase 3547` or `--phase 14188` for the additional base-cycle offsets.
Run the isolated scenes with:

```sh
python3 tools/test_console_bitmap_scroll.py --mode opt --output DIR --observe --performance
python3 tools/test_console_bitmap_scroll.py --mode opt --output DIR --replay
```

`tools/record_console_responsiveness.py` checks image/pin,
phase, pixel and memory-budget agreement before recording the final evidence.

`tools/console_turn_profile.py` rejects mismatched interrupt frames,
incomplete spans and Task ownership inconsistencies. Host regressions cover
nested interrupts, preemption, interval clipping and debugger resume boundaries.
All **315 host tests** pass (four historical audits skipped). Emitted checks
include 77 shared drawing checks in each of raw and optimized mode, six fault
cases in each mode, thirteen final pixel scenes, three loaded phases and their
unobserved replays. G1 extraction also links without introducing a drawing
dependency into its context-only fixture; that check did not execute G1.
These are development checks, not release qualification or a demo refresh.

Reserved bank-zero change for every slice is **0 bytes**: fixed storage,
root/kernel, every public Task and idle, including guards, alignment and unused
capacity. Only the second slice changes production code. The targets remain **4 ms
charged CPU per presentation turn**, **40 ms visible input**, and **20 ms complete
scroll**; the baseline does not meet them.
