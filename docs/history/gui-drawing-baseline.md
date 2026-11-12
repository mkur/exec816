# Current GUI drawing baseline

[History](README.md) · [Evidence](../development/gui-drawing-baseline.json) ·
[Display ownership](../reference/display.md) ·
[Earlier viewer measurements](text-viewer-performance.md)

## Scope

This development baseline measures the current optimized Text Viewer on a newly
built OF816 package. Runtime sources are revision
`775f68fda4434385e88d6dfa7379415030a8f79e`, including the shared borrowed-completion
cleanup. Only host measurement tools change in this slice. Drawing limits,
Task preemption, application painting and public interfaces are unchanged.

Both scenes use the same 456×170 work area at (40,43), 56 text columns, 18 document
rows, 8×8 font and packaged `SYS:STORY.TXT` (6,663 bytes, 220 lines). The viewer
is fully visible and the pointer stays at (630,230). The idle scene retains the
desktop and loaded Terminal. The loaded scene adds a Desk-launched Counter and
the existing GFLOAD four-pass disk read/verify/write workload on a separate ATR.
The shell runs the viewer in its one background slot and disk work in the
foreground; no extra shell, Task pool or synthetic kernel operation is needed.

Four alternating page actions and four alternating one-line actions return to
the initial viewport in each scene. Each observed run has an identical-package
companion with tracing disabled. These small deterministic cohorts establish a
reproducible development baseline, not latency tails or release qualification.
The fixture differs from the longer MagiC comparison document; no cross-machine
speed ratio is inferred.

## Idle result and first target

The idle page median is **1,212.1 ms**, and the one-line median is **1,198.1 ms**.
All eight action timestamps match the untraced companion exactly. Line scrolling
still repaints the document viewport rather than copying retained pixels.

The following means reconcile to elapsed time. The unclassified prefix precedes
the first scheduler publication in the capture: 13.45 ms on the first page,
zero on the other seven actions. It is not silently assigned to a lock or queue.

| Mean per action, ms | Page | Line |
| --- | ---: | ---: |
| Elapsed | 1210.146 | 1196.175 |
| Viewer CPU | 500.684 | 499.688 |
| IRQ/NMI on viewer | 109.160 | 108.832 |
| Blocked off CPU | 102.695 | 97.795 |
| Runnable off CPU | 494.244 | 489.859 |
| Unclassified off CPU | 3.363 | 0 |

Each repaint makes seven BEGIN and seven END calls, 21 physical grants and 23
hardware launches. The five generic submit calls are only a subset of those
launches; the native text producer launches directly too. There are 20 VDI text
calls, including clipped status fragments, and 31 owner-fence calls. The mean
text-call CPU cost is 9.70 ms for pages and 9.66 ms for lines.

BEGIN/END_UPDATE accounts for **199.1 ms of page CPU**, about 40% of its total,
and **604.3 ms inclusive elapsed time**. These calls include publication and
cache work as well as ownership coordination; this is not a pure uncontended
lock cost. The page's combined hardware BUSY duration is bounded between
**10.0 and 34.0 ms** on average, versus 9.7–23.5 ms for lines. Scheduling can
inflate the upper bounds. They establish that hardware occupancy is a small
part of the measured second, without assuming every off-CPU interval is a
drawing wait.

The next focused candidate is UPDATE bookkeeping around the existing paint
bands. Measure and simplify one repeated BEGIN/END operation first. Physical
DisplayEnter/Leave CPU is much smaller; the baseline does not justify changing
preemption or increasing drawing ownership duration. Retained-pixel scrolling
remains a separate application improvement.

## Counter and disk load

Counter's work area is (488,43,128,35), with its digits visible beyond the
viewer's right edge. The loaded page median is **2,175.6 ms**, and the line
median is **2,113.3 ms**. All eight timings match the untraced companion exactly.
The disk command remains active through every measured repaint; its final
persisted bytes match the source fixture.

| Mean per action, ms | Page | Line |
| --- | ---: | ---: |
| Elapsed | 2127.197 | 2117.951 |
| Viewer CPU | 560.855 | 548.928 |
| IRQ/NMI on viewer | 195.718 | 157.561 |
| Blocked off CPU | 271.896 | 320.491 |
| Runnable off CPU | 1095.675 | 1090.971 |
| Unclassified off CPU | 3.052 | 0 |

The drawing counts remain 21 grants and 23 launches per repaint. Page hardware
occupancy is bounded at 9.6–26.9 ms on average, and lines at 9.5–31.7 ms.
UPDATE accounts for 241.0 ms of page CPU and 1,142.7 ms inclusive elapsed time.
Most of the added page time is runnable off CPU: about 601 ms of the additional
917 ms. It cannot all be described as waiting for drawing ownership. The result
strengthens the case for reducing repeated UPDATE work and handoffs while
preserving ordinary preemption.

## Observations

`tools/measure_gui_baseline.py` reuses the production desktop session, physical
keyboard input, raw-document pixel oracle and passive viewer trace. It waits for
the initial document commit and inbox wait before timing. A cleared loading
phase alone is insufficient: `TextStep` clears it before title, viewport and
damage publication finish. It also observes actual application readiness before
reading its allocated inbox.

Completion is the first IRQ observation of cleared viewer damage after a key
offer. The three-frame physical key pulse bounds model-change observations;
IRQ sampling adds up to a PAL frame at the endpoint. Settled scanout pixels are
checked separately, outside the timed interval. Initial, final page and final
line work areas are compared to the independent oracle. A top-boundary key must
cause no repaint. Cleanup checks include viewer collection, exact heap return,
stack/domain guards, bank ownership and normal EXIT. The loaded scene also checks
Counter progress and persisted disk bytes.

The trace partitions elapsed time into viewer CPU, its IRQ/NMI time, blocked
off-CPU time, runnable off-CPU time and any unobserved scheduler-state prefix.
Exclusive CPU buckets reconcile to the
CPU total; inclusive routine costs overlap those buckets. Individual `v_gtext`
calls provide the text-row measurements inside the real repaint.

Hardware occupancy is bounded using the existing launch-store call and actual
BUSY-read results in the synchronous driver. The upper bound includes store-call
overhead and delay until the first observed idle read. A lower bound spans the
latest possible first positive read to the earliest possible last positive read;
it is zero when the polls do not establish a positive interval. Neither bound
claims exact hardware edges. Hardware intervals overlap CPU and scheduling time
and must not be added to the exclusive accounting. Polling CPU is reported
separately. Selected CPU observations are retained without bridge session metadata.

## Development checks

The four optimized boots cover 16 measured actions and 16 identical-input replay
actions. All twelve work-area checkpoints match the independent oracle, 77,520
pixels each. Both scenes return the warmed heap exactly and pass no-op scrolling,
stack/domain guards, ownership restoration and EXIT. The host suite passes
**702 tests, four existing historical skips**. ZIP checksums, license notices,
69 SYS inputs and nine disk APP identities match the frozen build. Each boot
preserves the five-second OF816 autoboot.

The retained excluded pilots repair fixture startup/layout assumptions, covered
title clicks, the 32-bit debugger-clock epoch and a capture beginning inside an
outer IRQ. The latter prefix is accepted only before the first context selection;
unmatched exits afterward still fail. The guest image did not change during
these fixture repairs. Older viewer timings and the GF15 ZIP are not substituted
for this current-source baseline.

## Reproduction

Use fresh output directories. Build once; all captures and replays use that
package and its pinned ROM, emulator, compiler and PAL 8× 65C816/FX 1.26 settings.
The package retains OF816 and its five-second autoboot, standard shell/prime
startup, writable SYS disk and upstream notices. QED is not selected here.

```sh
python3 tools/build_demo.py --output build/gui-baseline/current/demo \
  --gem-desktop --release-compiler
python3 tools/build_gem_load.py --output build/gui-baseline/load
python3 tools/measure_gui_baseline.py --bundle build/gui-baseline/current/demo \
  --output build/gui-baseline/idle-baseline --count 4 --observe
python3 tools/measure_gui_baseline.py --bundle build/gui-baseline/current/demo \
  --output build/gui-baseline/idle-baseline-replay --count 4
python3 tools/measure_gui_baseline.py --bundle build/gui-baseline/current/demo \
  --output build/gui-baseline/loaded-final --count 4 --observe \
  --load build/gui-baseline/load
python3 tools/measure_gui_baseline.py --bundle build/gui-baseline/current/demo \
  --output build/gui-baseline/loaded-final-replay --count 4 \
  --load build/gui-baseline/load
```

Each run writes `results.json`; observed runs also retain `cpu-trace.log`, checked
markers and `text-performance-breakdown.json`. Reanalysis uses the same command
with `--analyze-only`. Development logs, disk copies and raw frames remain under
`build/`; the distribution ZIP contains boot files, its short guide, notices and
checksums.

Fixed, root/kernel, each public Task and idle reserved bank-zero deltas are all
**0 bytes**, including guards, alignment and unused capacity. Guest upper-RAM
and VRAM reservations also change by zero.
