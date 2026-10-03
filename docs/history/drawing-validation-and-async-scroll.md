# Drawing validation and asynchronous console scrolling

[History](README.md) · [Implementation plan](../plans/drawing-validation-implementation-plan.md) ·
[Console contract](../reference/console.md) · [Development evidence](../development/drawing-validation-d6.json)

Development measurements, 3 October 2026. Public drawing calls now validate the
owner once. A synchronized console scroll launches one rectangle copy and one
exposed-strip fill in a single asynchronous list. The existing worker polls it,
services input and retains completion separately from its wake notifications.
No extra Task, semaphore, IRQ producer, command arena or kernel operation was added.

The implementation and pixel/lifetime checks pass. Responsiveness acceptance
remains open: the full-screen scroll exceeds 20 ms, and loaded typing exceeds
40 ms. These experiments do not qualify the hosted system or a release package.

## Matched scroll results

The pinned machine is PAL 65C816 ×8, 4 MiB RAM, AltirraOS 3.44 and VBXE FX 1.26
with private 512 KiB VRAM. Reports pin the compiler, ROM, emulator and exact XEX
hashes. Routine elapsed time includes preemption.

| Path | Isolated 80×30 scroll | Repeated scrolls | Launches per scroll |
| --- | ---: | ---: | ---: |
| D0 baseline | 121.82–122.22 ms | about 126 ms | 30 |
| D3, one admission per public call | 97.33–97.50 ms | 104.33–106.18 ms | 30 |
| Historical synchronous whole rectangle | 29.55–29.56 ms | 43.3–45.2 ms | 1 |
| D6, asynchronous whole rectangle | 31.21 ms | 32.69–38.19 ms | 1 |
| Experimental asynchronous 64-row copies | 47.81–52.62 ms | 52.79–55.51 ms | 4 |

The production path is about 3.9 times faster than D0 and 3.1 times faster than
D3 on the isolated scenes. It has one Start and four Poll calls in those scenes,
each with its own owner admission: five checks in total. No admission is cached
across a return or Yield. The small offset tile takes 14.11 ms. Separate exact
pixel scenes using the shell/prime geometry measure 27.52 ms for 80×24 and
14.13 ms for 80×6. They exercise the tile geometry, not an interactive shell
application or a refreshed distribution.

The synchronous experiment is a historical comparison, not the same current
implementation with a flag switched. Its reproduction revision and measurement
limits remain in the [original record](whole-rectangle-scroll-benchmark.md).

## Input and loaded results

The loaded fixture has eight live Tasks, an 80×24 output producer, two 40×3
interactive tiles, physical SDFS reads, keyboard/BREAK and active ST mouse
capture. Keyboard presses start during observed hardware BUSY, then in additional
runs about 2 ms and 8 ms after that observation. This is a small phase sample,
not an exhaustive worst-case search. All four captures in the detailed run fall
between launch and confirmed completion. Separate emitted raw/optimized control
tests read the real BUSY register after publishing the READ reply, proving
read completion before the hardware finishes.

Frame sampling checks the raw-key glyph and, for the cooked key, both the glyph
and its new caret. A sampled incorrect frame is a lower bound; the first sampled
correct frame is an upper bound. The production path's first correct samples
fall at 177–216 ms after capture, with incorrect samples already beyond 40 ms.
Thus the visible-input target fails; this conclusion does not substitute an I/O
reply or a fixture presentation marker for actual scanout.

The 64-row candidate improves the phase-zero first-correct samples to about
106 ms for the raw glyph and 125 ms for cooked glyph/caret, while slowing isolated
scrolling to 48–53 ms. It also misses 40 ms. It remains an experiment; the
production path retains one full rectangle for its throughput benefit. Neither
geometry is accepted as meeting the responsiveness target.

For the detailed production run, raw delivery takes 65.49 ms and BREAK becomes
durable in 18.46 ms. The maximum input-service gap during sustained scrolling is
200.76 ms; the candidate reduces this to 143.73 ms. Launch-to-confirmed-idle
bounds reach 34.99 ms and 44.68 ms respectively under load. These include delayed
polling and are **not exact hardware BUSY durations**. The larger service gaps
show that reducing hardware rectangle size alone is insufficient; work between
service calls and scheduling need separate CPU attribution.

All recorded loaded runs retain the existing SIO, ST and Forbid limits and pass
their checks. Unobserved replays preserve pixels, input order, request ownership,
guards and OS restoration. These passes do not turn the failed 40 ms target into
an acceptance pass. Exact per-Task CPU accounting, the 4 ms complete-turn target
and exact BUSY edges remain unqualified. No scheduler, font renderer or input
latency limit was changed to obtain these results.

## Completion during presentation changes

The loaded experiment found a completion-bookkeeping issue. A focus transaction
can finish DMA while the registry is marked PRESENTING. Discarding that completion
forces an unchanged output tile to redraw; sustained output may then prevent it
from becoming synchronized again.

D6 keeps one completion-ready byte with the scalar unit/generation association.
Polling can retire hardware while a presentation transaction is active, allowing
its queued control to proceed. Model acknowledgement waits until that transaction
publishes the window. No pointer is borrowed while PRESENTING. A matching unchanged
view adopts the completion; changed or retired identities cannot. Raw and optimized
control cases specifically check that a cursor transaction preserves the completed
scroll without triggering a full redraw, alongside cancellation, hide, generation
changes, destruction/reuse and last-binding Stop.

This adds one upper-RAM byte beyond D5's thirteen-byte association. The affected
native console routines grow 159 code bytes in both modes. C code and reservations
are unchanged. Reserved bank-zero delta is **0 bytes** for fixed storage,
root/kernel, every public Task and idle, including guards, alignment and unused
capacity. Emitted guards and stack observations pass; no stack pool was enlarged.

## Reproduction

Use `tools/test_console_bitmap_scroll.py` for the thirteen production scenes and
`tools/test_console_bitmap_control.py` for the thirteen continuation/lifetime
cases, in raw and optimized modes where recorded. `--replay` reuses each image.

`tools/measure_async_scroll.py --output DIR` runs the loaded phase-zero experiment;
`--phase 3547` and `--phase 14188` select offsets in base scheduler cycles.
`--reuse` measures an existing image; `--replay` disables passive trace observers.
`--bounded` builds the fixture-only 64-row candidate. `--tiles` runs the 80×24 and
80×6 exact-pixel scenes. Generated candidate source and hashes stay under `build/`.
The [evidence](../development/drawing-validation-d6.json) records exact report
paths and hashes, including the D5 fault and direct-driver evidence retained by
the [plan](../plans/drawing-validation-implementation-plan.md).

The next performance work should measure complete worker-turn CPU time and the
long loaded input-service gaps, including text runs and time spent off CPU.
The 20 ms scroll and 40 ms visible-input targets remain unchanged.
