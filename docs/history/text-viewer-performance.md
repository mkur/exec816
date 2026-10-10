# GEM text viewer performance

[Plan](../plans/gem4xe/text-viewer-performance-plan.md) ·
[Viewer](text-viewer.md) · [Evidence](../development/text-viewer-performance.json)

The viewer now uses the existing native text uploader for complete even-X VDI
chunks and limits scroll damage to changing content. The matched page median
falls from **1281.5 to 942.6 ms**, and p95 from **1321.7 to 964.7 ms**. These are
26% and 27% reductions; the plan's twofold improvement target remains open.
Application APIs, the four-row UPDATE limit and event service between bands
are unchanged.

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

## Smaller viewer redraws

After TVP2, one representative page still spends 91.0 ms of viewer CPU in
`v_bar`, alongside 157.3 ms in text calls. TVP3 skips margin/background calls
outside the current clip and limits scroll/status damage to the content that
changes. Padded text continues to erase replaced characters. Exposure, move,
resize and document replacement retain full work-area damage; pending damage
still unions with new damage. No screen copy, cache or new damage structure is
introduced.

The same three-run, 30-action cohorts give these results. All values are ms;
each cell is median / nearest-rank p95.

| Operation | TVP1 baseline | TVP2 text uploader | TVP3 final |
| --- | ---: | ---: | ---: |
| Page completion | 1281.5 / 1321.7 | 1062.5 / 1080.9 | 942.6 / 964.7 |
| Page first changed band | 239.1 / 583.0 | 184.8 / 504.0 | 178.6 / 525.9 |
| Line completion | 1281.5 / 1502.1 | 1061.0 / 1080.9 | 940.5 / 960.4 |
| Line first changed band | 241.9 / 559.5 | 184.8 / 499.2 | 191.4 / 524.7 |
| Panel raise and action | 1143.5 / 1425.5 | 1026.5 / 1117.8 | 981.0 / 1222.9 |
| Panel gesture through completed repaint | 645.8 / 984.2 | 585.3 / 856.9 | 538.3 / 781.8 |

The final build improves the input cohorts against the frozen TVP1 comparator,
including first-band feedback. It does not improve every intermediate result:
TVP3's Panel raise/action p95 is **105.1 ms worse than TVP2**, while gesture-only
p95 improves by 75.0 ms. First-band p95 also rises by 22.0 ms for pages and
25.5 ms for lines relative to TVP2. These deterministic changes exceed the
20.05 ms comparison tolerance and are retained as tradeoffs, not dismissed as
measurement noise. Acceptance here uses the plan's original TVP1 comparator;
it does not establish monotonic improvement at every step or close a general
desktop latency gate.

All measured actions complete once, with no timeout or growing backlog. The
key cohorts serialize completed actions; they do not establish a sustained
key-repeat rate. The Panel raise is offered at a fixed offset during a viewer
repaint and the actual button gesture follows focus acknowledgment. Model-change
observations remain around 60.4 ms, bounded by the three-frame key pulse.

A separate short replay adds `CAT LONG.TXT` disk/console activity. Its single
Panel raise/action falls from 1517.2 to 918.3 ms, and gesture-only completion
from 694.9 to 557.3 ms. These are individual observations, not another p95
cohort. The same replay verifies replacement of the viewer model during painting,
physical shell BREAK, retirement and heap return. The four traced key actions
on both baseline and final images reproduce the replay's exact clock milestones
and settled pixels with detailed tracing disabled.

CAT retirement after BREAK is longer in the final short replay: 1015.3 ms
versus 282.4 ms. BREAK follows the variable-duration Panel transaction, so CAT
has reached different output/read progress at cancellation. This does not
isolate a cancellation-path regression, and **cancellation latency remains
unqualified**. Functional Escape/Stop/BREAK passes are not a timing acceptance
claim. A longer pilot that waited for the entire covered-window CAT stream
timed out; the retained bounded workload cancels it through the normal shell.

TVP3 adds **245 file bytes** to TEXT.APP (16542 to 16787), including 233 code
bytes. Its 563 constant bytes, 1678 zero-fill bytes, 67777-byte load span and
133312-byte rounded image backing are unchanged. It adds **0 fixed bank-zero
bytes, 0 per public Task and 0 private idle**, including guards, alignment and
unused reservations, and no upper-memory buffer, stack or VRAM capacity.

The development host suite passes 423 tests with four historical skips. The
final extracted ZIP passes the viewer's 14 scene oracles, including minimum and
wider resize, partial cover/exposure, failed Open, interrupted selection and
read-time Escape. An additional physical page reversal during an unfinished
repaint verifies that the latest model repairs already painted bands. Boundary
no-op scrolling, Stop, counter progress, warmed heap/ownership return and EXIT
pass. The ordinary-task minimum is 156 bytes above the 256-byte stack floor,
against the unchanged 128-byte headroom target.

## Remaining page cost

The first traced page provides a reconciled example, not component percentiles:

| Charged interval | TVP1 | TVP2 | TVP3 |
| --- | ---: | ---: | ---: |
| Viewer CPU | 565.3 ms | 381.6 ms | 282.8 ms |
| Interrupts while viewer owns CPU | 121.1 ms | 81.4 ms | 60.0 ms |
| Viewer blocked, off CPU | 425.0 ms | 475.5 ms | 433.9 ms |
| Viewer runnable, off CPU | 169.9 ms | 109.1 ms | 110.5 ms |
| Complete page | 1281.3 ms | 1047.6 ms | 887.2 ms |

TVP3 reduces bar calls from 25 to one and display borrows from 61 to 37, while
retaining 17 document rows, 18 text calls and five UPDATE bands. There are 36
native text uploads and one bar submission. The native uploads bypass
`VbxeOwnerSubmit`: its recorded list sizes alone therefore no longer describe
all lists. Each full 56-character row uses 32/24-character chunks, whose native
uploader constructs 33/25 records including the background record. The trace
counts 37 hardware launches and 76 `VbxeOwnerFence` calls; internal native
uploader polls remain separately visible. Paging still transfers zero staging
pages.

CPU work is almost halved, but 544.4 ms of this final page is off CPU. The first
UPDATE acquisition is short in this sample; the second takes 343.3 ms. Remaining
UPDATE holds range from 62.1 to 97.8 ms. Faster construction changes which band
encounters presenter/peer work; it does not remove that work. The 13.8 ms sum of
hardware launch-to-idle-return bounds is small and includes scheduling delay.
These observations point to display admission and bounded presenter work as
future investigation, not another staging-transfer optimization.

Cold document observation falls from 6342.2 to 5431.0 ms in the individual
traced runs. Loader and DOS code are unchanged, and this is not a cold-load
distribution or a claim about APP loading. The final trace remains below the
256 MiB cap (69.1 MB). The intermediate TVP2 trace completed the functional run
but required offline reanalysis after correcting the first observed scheduler
state boundary; its three unobserved cohort runs independently pass cleanup and
EXIT. The corrected analyzer completes directly for the final trace.

## Package and limits

The final OF816 package is
`build/text-performance/exec816-demo.zip` (SHA-256
`5366248c6df85bfddf793c345f3001bbb1dc8bc44ad46e140a4ec39b9c66191f`).
Its 18 payload checksums and all 150 production source inputs match. The ZIP
contains boot files, the matching system/work disks, pinned AltirraOS ROM,
guide and license notices; manifests and observations stay outside it. OF816
retains its five-second autoboot (249 observed PAL frames).

Both exact-ZIP viewer and Files workflows pass through EXIT with intact guards,
zero live tasks, ownership/heap return and restored OS state. Files checks cover
quoted document paths, copied launch arguments, one-child behavior, selector/read
Stop, native/GEM launch, Panel keyboard interaction, relaunch and parent close.
Ordinary-task minimum stack headroom is 156 bytes in the viewer workflow and
169 bytes in the Files workflow. TVP4 adds **0 fixed bank-zero bytes, 0 per public
Task and 0 private idle**, and no code, upper-RAM, stack or VRAM reservation.

These are development checks on the pinned PAL 8× 65C816 emulator, AltirraOS
3.44, VBXE FX 1.26 and paced `generic56k` disk, using the pinned Action! compiler
and Calypsi 5.18. They do not qualify real hardware or close HY4/PI4. Settled
pixel oracles pass; scanout and transient flicker are not qualified. Four-row
painting still exposes intermediate bands, and the twofold median/p95 target
remains open. There is no new scheduler policy or interrupt change in this pass.
