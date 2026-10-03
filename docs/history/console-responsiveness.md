# Console responsiveness measurements

[Historical records](README.md) · [Console contract](../reference/console.md)

The next three slices measure complete worker turns, optimize their dominant
cost, and repeat the loaded input and scrolling checks. The production baseline
is the single asynchronous rectangle scroll from
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

The optimization slice will batch aligned text runs through a checked driver
operation, retaining complete geometry admission and public raw-list validation.
The whole-rectangle asynchronous scroll remains the production geometry.

## Validation and reproduction

Run `tools/measure_async_scroll.py --output DIR --profile-turns` for the loaded
measurement; `--reuse` reuses the built image and `--replay` removes passive
observers. `tools/console_turn_profile.py` rejects mismatched interrupt frames,
incomplete spans and Task ownership inconsistencies. Host regressions cover
nested interrupts, preemption, interval clipping and debugger resume boundaries.
The baseline passes SIO/ST timing, exact final pixels, request ordering,
ownership, guards and OS restoration. These are development checks.

Reserved bank-zero change for this slice is **0 bytes**: fixed storage,
root/kernel, every public Task and idle, including guards, alignment and unused
capacity. No production code or reservation changes. The targets remain **4 ms
charged CPU per presentation turn**, **40 ms visible input**, and **20 ms complete
scroll**; the baseline does not meet them.
