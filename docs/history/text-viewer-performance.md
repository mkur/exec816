# GEM text viewer performance

[Plan](../plans/gem4xe/text-viewer-performance-plan.md) ·
[Viewer](text-viewer.md) · [Evidence](../development/text-viewer-performance.json)

The viewer's ordinary text path spends substantial CPU time setting up and
rendering individual glyphs. The selected TVP2 change is to reuse the existing native
text uploader under the caller's delegated display grant, preserving application
APIs, the four-row UPDATE limit and event service between bands.

## Measurement method

`tools/measure_text_viewer.py` boots the OF816 ZIP and uses physical keyboard
and mouse input. It closes Files, opens `SYS:STORY.TXT` beside the shell,
Control Panel and counter, and alternates page and line scrolling. It compares
settled pixels against the independent desktop oracle, checks a boundary no-op,
and requires counter progress, exact warmed allocation return and EXIT.

The Panel workload offers a raise click six PAL frames after the page key.
GEM must acknowledge focus before the subsequent 80 ms button gesture. The
record separates the complete raise/action transaction from the button gesture.
Completion means the Panel has returned to its inbox wait after synchronous
drawing; a paint counter alone cannot distinguish an earlier focus/press repaint
from completion of the release action. This is a physical focus transaction,
not a key injected into an inactive viewer. Viewer damage at the two input
boundaries is retained with each sample.

Times are software observations in emulator base-clock units, excluding scanout.
Key model/band/completion observations stop at native IRQ entry. Detailed traces
also identify the first synchronous text return. The comparison tolerance was
fixed at **20.05 ms**, one PAL frame, before candidate measurements.

`tools/text_performance_trace.py` resolves emitted call sites, checks public
callee operands and matches return PCs and stack pointers. Local helper names
alone are ambiguous. Exclusive CPU categories reconcile to the measured interval;
IRQ/NMI, runnable off-CPU and blocked time are separate. Inclusive routine times
must not be added to those categories. Launch-to-idle-return spans bound hardware
occupancy and include polling/scheduling delay; they are not BUSY-edge timings.

## Baseline attribution

A representative 1,281.3 ms page takes **565.3 ms viewer CPU**, **121.1 ms
interrupt time on the viewer**, and **594.9 ms off CPU**. Of the off-CPU time,
425.0 ms is blocked and 169.9 ms runnable. The first UPDATE acquisition takes
329.7 ms; later acquisitions and peer execution also contribute to completion.

`v_gtext` accounts for 339.7 ms of viewer CPU, including 189.2 ms in the donor
text renderer. Row formatting uses 16.7 ms. The page formats 17 document rows
and draws a padded status row in five application bands. It makes 18 text calls,
25 bar calls, 61 display borrows, 61 list submissions and 244 owner fences.
Normal page text makes **zero staging-page reads and writes**; the 4 KiB adapter
transfer is not this workload's bottleneck.

## Baseline results

Three deterministic runs complete 30 page actions, 30 line actions and 30 Panel
transactions, with matching settled pixels, heap return, guards and EXIT. The
runs reproduce the same offered sequence; these percentiles describe that
sequence, not a randomized user population.

| Operation | Median | p95 |
| --- | ---: | ---: |
| Page completion | 1281.5 ms | 1321.7 ms |
| Line completion | 1281.5 ms | 1502.1 ms |
| Panel raise and action | 1143.5 ms | 1425.5 ms |
| Panel gesture through completed repaint | 645.8 ms | 984.2 ms |

The two traced page intervals reproduce the unobserved clock times and viewer
pixels. The cold document observation spans 6342.2 ms: eight bounded loader
steps take 3902.0 ms elapsed, including five Read calls totaling 3477.5 ms.
The trace separates their charged CPU and off-CPU time; it does not include
loading the APP itself. Scrolling performs no document I/O.

Early observer pilots exposed unsupported raw cursor key names, the bridge's
bank-zero-only breakpoints, and a fixed second click offered before GEM focus
was ready. The passing workload uses Atari Ctrl-minus/equal cursor chords and
observes the Panel's public inbox wait after its focus acknowledgment. Those
pilots are retained separately and are not passing timing runs.

Model timestamps are upper bounds observed after the three-frame key pulse;
first-band and complete-repaint times use subsequent IRQ stops. Display scanout
is not timed. The baseline does not establish freedom from transient flicker.

TVP1 changes **0 fixed bank-zero bytes, 0 per public Task and 0 private idle**,
including guards, alignment and unused reservation, and adds no guest upper RAM
or VRAM. It passes the development host suite (423 tests, four historical skips).
The emitted viewer remains the TV4 package. These checks do not qualify real
hardware or close HY4/PI4.

## Accelerated VDI text

`GemVdiPaint` recognizes complete even-X chunks inside the already admitted
clip. It packs the low byte of each glyph into existing renderer scratch and
calls `vbxe_text_run`, which fences before scratch reuse. This avoids donor
workstation save/select/restore and per-glyph C rendering for those chunks.
Odd X and partial horizontal/vertical clipping keep the existing renderer.
There is no new public API, native-owner admission, validation layer or cache.

The optimized VDI fixture passes **179 checks**. Its independent pixels cover
named and parameter-block text, high-byte glyph truncation, spaces, zero/nonzero
hardware pens, long strings, bank-crossing source bytes, clipping, two-client
preemption, cursor repair, complete cover and exposure. It also checks unchanged
pixels when opening virtual workstations and exact allocation return. The fixture
oracle now includes the desktop pattern and menu bar introduced since its original
qualification. The host suite passes **423 tests, four historical skips**.

TVP2 passes the same 30-action cohorts. Page completion improves to **1062.5 ms
median / 1080.9 ms p95**; Panel raise/action improves to **1026.5 / 1117.8 ms**,
and the button gesture alone to **585.3 / 856.9 ms**. First-band page feedback
improves to **184.8 / 504.0 ms**. All changes exceed the baseline's reproducible
variation in the favorable direction; the twofold page target remains open.

The delegated-display fault fixture also passes **168 checks**, including fault
release/cleanup. This exercises the shared borrow/fence failure machinery; the
VDI fixture exercises the new text branch. No new interrupt or ABI bridge was
introduced, so these production checks use optimized emission.

`GEMSYS.BIN` grows **344 bytes**, from 196520 to 196864. Shared zero-fill remains
12855 bytes; the C DP workspace remains 23 bytes. TEXT.APP is byte-identical.
TVP2 reserves **0 additional bank-zero bytes**, fixed, per public Task and private
idle, and adds no upper-RAM buffer, VRAM reservation or stack capacity.
