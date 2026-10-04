# Desktop development

[Plan](../plans/gem4xe/desktop-implementation-plan.md) · [Roadmap](../roadmap.md)

## DT0 Inputs and budgets

The [baseline record](../development/desktop-dt0.json) freezes the existing
bitmap shell, companion disk, OF816 image, compiler, ROM and actual mouse-capable
emulator. A fresh unchanged-package smoke passed five-second autoboot, TASKS,
system volume navigation, disk HELLO, shared-cache reads, CAT/WC pipeline and
EXIT with ownership/OS restoration checks.

The current shell runs in the root Task. Console, filesystem and SIO bring
prompt occupancy to four; a two-command pipeline peaks at six. The proposed
second application raises these to five/seven of eight public slots. The
presenter will reuse the existing 2,560-byte worker pool, admitted before other
clients. Root owns the shell window/controller; the second Task registers itself.

The Layers scene occupies 4,782 upper-RAM bytes. Client queues, window records
and retained command storage will be heap allocations, not additions to the
2 KiB resident globals arena. The existing aperture and command arena remain.
Combined stack use and final UI storage are later slice measurements, not
established by the separate Layers fixture.

Existing CAT and ST capture evidence is retained rather than rerun. The saved
short-echo trace ends at drawing return, not visible scanout. DT3 must run its
new visibility observer against the frozen unchanged image as well as the
desktop; no visible-latency baseline is inferred from that older trace.

Reserved bank-zero change is **0 bytes fixed, root/kernel, per public Task and
idle**, including guards, alignment and unused capacity. DT0 adds no runtime
state. This is development evidence and does not qualify the desktop.

## DT1 Client and event service

[Native service](../reference/desktop.md) now implements four registered
clients/windows, retained fill/text batches, bounded event queues, durable
loss/focus/close bookkeeping and separate control/content/event/cancel lanes.
The service retains each owner through final reply publication. It uses ordinary
Exec messages and a recording Layers backend; hardware integration is DT2.

[Raw and optimized evidence](../development/desktop-dt1.json) each passed 143
assertions with two independent client Tasks and a presenter. The fixture covers
a waiting peer, cancellation while a paint defers controls, completion winning
a late cancellation, queue overflow/motion coalescing, invalid batches, stale
IDs, capacity exhaustion and final cleanup. A separate held-removal case reaches
the expected Exec launch fault. Stack/domain guards, native context restoration
and successful-run allocation ownership checks passed. The host suite passed
337 tests with four historical skips. These are development checks.

Service payload is 10,372 upper-RAM bytes. The fixture adds a 32-byte guard and
a separate 710-byte source batch. Three public Task slots are occupied during
the test; the production desktop has not yet been attached to the console.
Reserved bank-zero growth is **0 fixed, 0 root/kernel, 0 per public Task and
0 idle bytes**, including guards/alignment and unused pool capacity.

## DT2 Framed console and retained painting

The existing console worker now presents a 64×20 shell through Layers, with
pixel clipping for partial glyphs and odd packed-pixel edges. It paints bounded
sixteen-scanline stripes or four retained commands per turn and keeps one Layers
token through a repaint continuation or asynchronous scroll. Fully covered
damage stays retained without keeping the worker runnable. The console’s
short-write pass and fully visible scroll path remain available.

[DT2 development evidence](../development/desktop-dt2.json) contains six exact
framebuffer/scanout comparisons and 40 assertions in each raw/optimized image:
typing, circular-row scrolling, translated placement, an odd-edged overlapping
panel, clear/hidden content and close/exposure. Both runs return cleanly with
stack/domain/context and allocation ownership checks. Selected optimized
full-screen bitmap, standard text window lifetime/isolation, and the 143-check
native desktop service regressions passed. The host suite passed 337 tests
with four historical skips.

The packaged framed shell also passed the OF816 five-second cold boot, TASKS,
MOUNT, disk HELLO, physical cached reads, CAT/WC pipeline and EXIT walkthrough.
It peaks at six Tasks; the second independent graphical application is DT5.
This is a local shell-only development artifact, not the completed DT7 preview.
Pointer routing, gestures, loaded failure/timing checks and final preview
packaging remain later slices.

The scene/service payload is 10,378 bytes, rounded to 10,384 by AllocMem. Runtime
and root-controller globals add 138 payload bytes in upper image RAM, with
compiler alignment; no resident arena or bank-zero region grows. The worker
used at most 678 stack bytes in these raw/optimized fixtures, leaving 1,626
bytes above the reserved interrupt floor in its existing 2,560-byte pool.
The root peak is 372 bytes; kernel peak is 266 bytes. These observations are
workload-specific lower bounds, not a new universal stack qualification.

Reserved bank-zero delta against **DT0** is **0 fixed, 0 root/kernel, 0 per
public Task, 0 idle bytes**, including guards/alignment and unused capacity.
Older shared harness `bank_zero_delta` fields compare against pre-large-stack
compaction and therefore include the already-existing 3,072-byte enlargement;
`reserved_bank_zero_delta` explicitly compares the desktop slices with DT0.


## DT3 ST input, focus and pointer checkpoint

The existing presenter now owns the ST/port 1 pointer source, route and wake
signal. Keyboard focus publishes a graphical window route or the console's
current foreground route; KEY and BREAK keep their capture-time destination.
Pointer capture and Timer 1 policy are unchanged. Input draining is bounded and
idle checks remain cheap. A new release observation is required after source
loss. Shutdown restores the pointer and releases input before display storage.

The shared drawing backend removes intersecting overlays before drawing and
retains both odd/even masks in VRAM. The initial measured move call took about
28 ms with a mask upload; the retained-mask version takes about 6.2 ms. Showing
new motion before another output quantum also reduces loaded response. These
changes stay in the drawing/presenter layers, above Exec and the sampler.

[DT3 development evidence](../development/desktop-dt3.json) separates functional
checks from timing acceptance. Raw/optimized exact scene checks, graphical
KEY/BREAK routing, captured electrical counts, ordered buttons, source/port
cleanup and native guards pass. The supported-rate case decodes 97 diagonal
transitions at 1.029 ms spacing. The independent negative control emits 256
transitions per axis at intervals down to 64.282 µs; the consumer misses
movement, so this rate remains unsupported even without a LOSS notice.
The focused FASTEST125 and ordinary 57.6k physical SIO cases pass the shared
sampler/timer checks. An unobserved replay preserves functional results.

Each optimized idle/scroll/disk latency case has 100 paced motion observations
and thirty clicks (sixty separately observed edges). The observer compares
actual completed scanout and reports an upper bound, not drawing completion.
The final early-presentation run records these capture-to-visible values:

| Load | Median | p95 | Maximum |
| --- | ---: | ---: | ---: |
| Idle | 43.63 ms | 46.41 ms | 46.66 ms |
| Sustained console output | 45.02 ms | 65.61 ms | 80.01 ms |
| Physical disk reads | 43.87 ms | 62.15 ms | 85.94 ms |

All maximum-latency and button-consumption targets pass in that run. **The p95
pointer targets remain open**: 40 ms idle and 60 ms loaded. DT4 can proceed with
this explicit limitation; DT6 must retain it in the two-client record and final
preview unless a measured follow-up closes it. Idle input-service intervals
include intentional waiting; they are not equivalent to queued-event delay.
The trace records IRQ elapsed share and drawing-call elapsed time separately;
neither is a whole-system CPU-utilization qualification.

The new scanout observer also runs on the frozen DT0 shell image. Twelve short
key echoes measure identical full-screen baseline/current p95 and maximum,
35.63 ms, meeting the regression target. The framed shell is recorded separately
at 55.87 ms p95/maximum. These are completed-scanout observations with PAL frame
resolution, not sub-frame hardware-display measurements.

Service payload is 10,532 upper-RAM bytes, rounded to 10,536 heap bytes. Desktop
runtime/controller globals have 280 payload bytes plus compiler alignment.
Pointer storage grows from 1,024 to 1,280 reserved VRAM bytes: one save plane
and both AND/OR mask pairs. This consumes former slack and 256 additional
reserved bytes; no extra aperture is introduced. No Task is added.
Reserved bank-zero growth against DT0 remains **0 fixed, 0 root/kernel,
0 per existing public Task and 0 idle bytes**, including guards and slack.
