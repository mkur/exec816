# GEM drawing simplification

[Display contract](../reference/display.md) ·
[Development evidence](../development/gem-drawing-simplification.json) ·
[MagiC operation boundaries](magic-operation-boundaries.md)

## S1: shared borrowed completion

Borrowed AES/VDI painting and screen copies now share `borrow_leave` in
[`gem-vbxe.c`](../../ports/gem4xe/adapter/gem-vbxe.c). The helper flushes queued
drawing and fences it, restores the outline and pointer, then releases physical
access. Previously both paths maintained their own finish sequence and performed
another flush/fence after restoring overlays, including when no overlay changed.

That last check duplicated the driver's completion guarantee. `outline_toggle`
submits synchronously, including its packed-edge fallback; `cursor_render`
flushes prior work and submits synchronously. The private driver's `submit`
fences before launching a list and waits for completion afterward. CPU transfers
also complete before returning. Consequently overlay restoration leaves neither
queued drawing nor an active list for another adapter fence to retire.

The shared finish still checks completion after the drawing callback, including
callbacks with no pending records. Driver dependency fences, bounded waits,
first-error latching and reset-required recovery remain in place. An overlay
failure is reported before the handoff. Future asynchronous overlay work would
need its own completion protocol before physical access could be released.

This follows the MagiC analysis's coordination-first direction. Current 16/32-row
object splitting, visible intersections, per-list work/record limits, FIFO
arbitration and normal Task preemption remain unchanged. There is no new kernel
operation or public ABI. The existing borrow observer now marks the shared exit;
the host copy regression extracts that helper along with the copy implementation.

## Development checks

The evidence compares the new optimized corpus with the saved GF13 prepared-object
capture. The compiler binary and platform pin match; among maintained runtime
sources recorded by both captures, only `gem-vbxe.c` changes. This is a development
comparison, with eight measured draws per object cohort after two warmups, and does
not establish latency tails or qualify the hosted system.

| Object cohort | Grants / submissions per draw | Fence checks before → after | Mean drawing CPU before → after |
| --- | --- | --- | --- |
| Five objects | 12 / 16 | 56 → 44 | 26.930 → 26.332 ms |
| 33 siblings | 40 / 46 | 172 → 132 | 90.849 → 89.294 ms |
| Nine nested objects | 56 / 90 | 292 → 236 | 137.909 → 136.136 ms |

Grant and submission counts are unchanged. The observed CPU reduction is modest
(1.3–2.2%); the physical unit sizes are unchanged. All eleven full-frame
checkpoints match the saved control, covering 153,600 pixels each, and stack guards
remain intact. The new run passes 478 C assertions; the control passed 486. Those
totals include message/exposure draining with variable iteration counts. Object
cohort sample counts and the image checks match.

The largest observed nested-case Enter-entry to Leave-return bracket increases
from 4.783 to 5.160 ms; the corresponding maximum Enter-return to Leave-entry
interval changes from 4.321 to 4.366 ms. These are different timing scopes and
small samples. This slice does not establish improved input latency.

`tools/test_display_borrow.py` passes 196 C checks across 48 physical units and
2,788 exact pixels, with no overlapping renderer access. It observes interrupts
and Task switches while a grant is held, including a fixture-only yield with
staging live, and preserves inherited Forbid nesting. Four fault cases cover
quiescent STOP cleanup and reset-required ownership retention for both painting
and a copy interrupted after a real completed strip. The host suite passes
692 tests with four existing skips.

Two excluded fixture runs remain in the evidence. The private admission command
needed to participate in the presenter's settled-work check; otherwise an idle
notification shortcut went back to sleep before processing it. The old assertion
requiring native console scrolling also became obsolete when output moved to
the console model and loaded Terminal. The current fixture checks console-model
I/O and native pointer interference; it does not exercise asynchronous visual
Terminal scrolling.

Fixed, root/kernel, each public Task and idle reserved bank-zero deltas are all
**0 bytes**, including guards, alignment and unused reserved capacity. No renderer
data or VRAM reservation is added. The standard OF816 demo was not rebuilt for
this development slice.
