# Hosted AES widget application

[History index](README.md) · [Widget contract](../reference/widgets.md) ·
[Implementation plan](../plans/gem4xe/aes-widgets-implementation-plan.md)

AW5–AW6 are implemented at the development tier on 2026-10-05. The
[AW5 evidence](../development/aes-widgets-aw5.json) records application and
timing checks; [AW6 evidence](../development/aes-widgets-aw6.json) pins the
tested local preview. Functional acceptance passes. The original responsiveness
targets remain open.

AW5 replaces the optional desktop's retained-command demonstration with a
Control Panel on the same ordinary Exec Task. The eight-object compiled-in
form exercises a toggle, sibling radios, disabled/default/momentary buttons and
cancellation. Semantic actions trigger an authoritative state read and a
one-label patch. Application work stays outside the presenter. The client
retries stale revisions between turns, checks Stop before retrying, rejects
old-epoch actions and resynchronizes LOSS without inventing application actions.

AW0–AW4 already selected and adapted GEM4XE object traversal, object drawing
and form-button behavior. The hosted interface adds bounded validation, copied
contexts, revisioned atomic updates, event-driven capture and paint continuations.
It does not add AES scheduling, a modal form loop, editable fields, resource-file
loading, menus or complete AES source/binary compatibility. The donor source
and extraction pins remain unchanged.

## AW5 development checks

The optimized emitted application passes independent panel/model/pixel checks
with a second test-owned widget context, disabled/raw-input rejection, Tab and
Shift-Tab traversal, Space, Return, Escape and BREAK. Each of the idle,
console-scroll and physical-SDFS cohorts contains 100 actions, cycling through
toggle, Large, Apply, Small and Cancel. A second 300-action run with passive
observers disabled passes the same state/pixel checks. Both retirement orders
pass full-scene recomposition and ownership restoration. The second form adds
no production Task. AW3/AW4 retain the unchanged renderer fault, capture,
queue-loss and ABI-boundary evidence; no broad raw system matrix was repeated.

The workload runner distinguishes captured button consumption, widget commit,
application consumption and visible feedback. It uses physical ST transitions,
keeps the shell/controller running, and verifies each resulting panel against
an independent AES oracle. Scroll and physical SDFS cohorts also require
continued output/read progress. Each action releases after its pressed pixels
appear and waits for the complete scene before the next action; these are paced
interactions, not a rapid-click saturation test. Passive native traces separate presenter CPU
from interrupts and other Tasks. Completed scanout observations are upper bounds
with one-frame quantization. First-focus repair is recorded separately from
steady interaction; it can keep the scene token for several seconds.

A matched test compares a one-label patch with SetTree of the same eight-object
form, selection state, focus and final pixels. The fixture alone supplies this
control. Requested label damage is 1,280 pixels versus 21,120 for the full client.
Work counts include physical primitives/list submissions, and timing includes
the same input and application path. This comparison is not a renderer speedup
claim against the former application, whose workload was different.

| Same toggle action and final scene | Label patch | SetTree/full redraw |
| --- | ---: | ---: |
| Click through settled scene | 495.12 ms | 10,359.75 ms |
| Charged widget-paint CPU | 128.83 ms | 7,857.69 ms |
| Paint calls | 10 | 24 |
| Fill/text helper entries | 35 / 5 | 151 / 19 |
| Hardware starts / list submissions | 30 / 30 | 117 / 117 |
| Release to first visible status label | 339.45 ms | 319.49 ms |

The patch reduces total work and settlement time, but this pair does not show
faster first label visibility: the label is near the top of the full redraw.
The matched run explicitly starts both trials with Toggle focused and off;
the earlier cohort runners' end-of-run comparisons began with different focus
and are excluded from this comparison.

## Responsiveness and remaining work

The targets remain 40/60 ms p95/max at idle and 60/100 ms under load; maximum
button consumption is 40 ms idle and 100 ms loaded. Widget commit, application
consumption and visible feedback are measured separately from pointer movement.
Both kinds of latency still miss targets.

For the panel cohorts, all pairs below are **p95 / maximum in milliseconds**:

| Load | Widget commit | Application consumption | Pressed pixels | Status label |
| --- | ---: | ---: | ---: | ---: |
| Idle | 305.74 / 334.87 | 332.88 / 340.71 | 430.64 / 431.91 | 640.31 / 660.52 |
| Console scroll | 280.54 / 296.75 | 299.54 / 316.97 | 414.73 / 432.66 | 640.31 / 660.52 |
| Physical SDFS | 625.47 / 774.82 | 696.14 / 797.94 | 868.93 / 928.80 | 1,342.58 / 1,442.62 |

Commit uses 200 edges per load; application and each feedback column use 100
samples. Maximum button intake is 58.04 / 57.53 / 113.08 ms respectively.
The scroll run completes 73 console writes; the disk run completes 4,775 reads.
The observer-disabled run reports the same progress counts and passes all
states, pixels, ownership and guard checks. Intake is only the first stage;
successful capture does not imply prompt widget commit or visible feedback.
Charged widget-paint CPU totals 28.01 / 27.20 / 28.15 seconds across those
100-action cohorts; their largest Paint calls charge 53.37 / 51.29 / 55.55 ms.
The evidence also records requested damage, helper calls and hardware work.
Hardware starts/list submissions include console work in the same load window;
requested damage counts logical union rectangles, not physical pixel writes.

The existing pointer workload with a panel activation every ten moves gives:

| Load, 100 moves each | Visible p95 / max | Maximum button consumption |
| --- | ---: | ---: |
| Idle | 119.67 / 126.49 ms | 69.34 ms |
| Console scroll | 106.28 / 142.66 ms | 103.33 ms |
| Physical SDFS | 121.11 / 145.82 ms | 102.49 ms |

A matched 100-move idle control keeps the same panel present without periodic
application keys: visible p95/max is **46.409 / 46.663 ms**, essentially the
frozen DR7 idle result of 46.408 / 46.661 ms. The repeatable extra delay therefore
belongs to the active widget workload. The previous compute application's keys
did different work, so its two-client result is not a matched renderer baseline.
The active-panel capture sample gaps remain below 1 ms in all three cohorts;
MP3's unchanged capture-envelope evidence is reused.

In the matched run, first-focus pressed pixels take 3.683 seconds. Its release
is consumed in 18.37 ms, but widget commit waits 6.346 seconds and the status
label appears after 6.938 seconds. Input intake continues while the immutable
scene token delays model edits. The longest Paint call charges **1.394 seconds**
of CPU (1.751 seconds elapsed); Pump charges 1.406 seconds. These call costs
exclude IRQ and other-Task time and conservatively bound uninterrupted rendering.
Four objects and sixteen scanlines per call bound geometry, not elapsed CPU.

Source inspection identifies concrete follow-ups: clipped glyphs fall back from
the blitter path to CPU drawing in `dev_vbxe.c`; the hosted aperture adapter
flushes whole 4 KiB pages. The panel's captions cross sixteen-line paint strips,
making partial glyph clipping relevant. Old/new keyboard focus can also request
a large union rectangle. These are optimization candidates consistent with the
measurements, not separately proven causal cost breakdowns. Shorter rendering
calls and shorter scene-token holds are the next latency work; AW5–AW6 introduce
no scheduler rewrite or wider acceptance limits.

## Memory

AW5–AW6 change reserved bank-zero bytes by **0**: fixed/root/kernel, every public
Task and private idle Task, including guards, alignment and unused capacity.
The panel keeps its 1,024-byte Task stack, one DP and existing Task/window slot.
The demo retains its 4 KiB upper global arena; the larger measurement fixture
uses its existing 8 KiB arena. No new VRAM reservation is needed.

The application replaces a 710-byte content buffer (712 rounded) with one
3,072-byte tree/update/snapshot allocation. The new live widget context reserves
4,096 bytes (2,200 used), so its additional upper heap reservation is 6,456 bytes.
Service storage stays 12,342 bytes (12,344 rounded). C code/data banks and DR7's
two snapshot slots remain reserved as before.

The measured application stack peak is 159 bytes, with 609 bytes remaining above
its floor; the presenter peaks at 712 with 1,592 remaining. Root/kernel peaks
are 374/287 bytes, and idle peaks at 58. Observed and observer-disabled runs
have identical peaks and intact guards. These are exercised high-water marks,
not a general worst-case proof for every future form.

## AW6 local preview

The optional desktop is built with `tools/build_demo.py --desktop`, including
OF816, matching system/work disks, pinned AltirraOS ROM and upstream notices.
The combined `exec816-demo.zip` keeps the standard five-second shell/prime
autoboot at the root and the desktop under `desktop/`. Publishing remains
separate. Development checks do not qualify physical hardware or the whole
hosted system.

The exact extracted root and desktop boot/media bytes pass `test_demo.py
--boot-smoke`. Both count down for 249 PAL frames and reach a seven-Task pipeline;
desktop checks also exercise toggle/radio/Apply/Cancel/disabled/default controls,
full-scene pixels, dragging, shell focus, physical disk commands and writable
WORK media. EXIT restores ownership with intact guards and no live Tasks.
The host suite runs 361 tests: 357 pass and four historical checks are skipped.
Generated widget/desktop definitions are current.

The archive is `build/aes-widgets/aw6/preview/exec816-demo.zip`, 525,762 bytes,
with 25 members and 24 checked file hashes. Its SHA-256 is
`3a17d7e6513ff06b6e8531531ab28204c74f8f59d3bf6130adba7c1f125e6edd`.
It contains boot files, guides, notices and checksums; traces, manifests and
build intermediates remain in the development directory.

Builds identify the actual base as `cf9fe39-dirty`; the evidence records the
working-tree source hashes rather than assigning a later commit to earlier
artifacts. They use actionc `f1ff4ce`, Calypsi 5.18, GEM4XE `e413c39`, OF816
`8c92362`, AltirraOS 3.44 and the pinned mouse-capable emulator. The machine is
PAL 65C816 at 8×, 4 MiB, VBXE FX 1.26 at `$D600`, ST mouse port 1 and 2× travel.
Physical SDFS uses Generic 57.6k, with SIO patch/burst disabled and normal
4 kHz/fine-SIO timer policy unchanged. Exact tool/ROM/emulator hashes and
walkthrough results are in the AW6 record.

## Clipped-text and startup follow-up

The [follow-up evidence](../development/aes-widgets-clipping.json) records the
2026-10-05 response to slow initial Control Panel drawing and a reported mount
timeout. The sixth VDI extraction patch draws clipped replace/transparent
glyphs directly from the existing even/odd font atlases. Up to three masked
blits preserve partial edge nibbles. Hardware-zero ink uses inverse-mask AND;
XOR/erase keep their previous raster path. No donor checkout is changed.

In the same matched full-panel redraw scenario, elapsed time falls from
10,359.75 ms to 1,084.22 ms and Paint CPU time from 7,857.69 ms to 481.86 ms.
The final scene hashes match. The small label-patch control stays approximately
unchanged (495.12 ms before, 500.93 ms after). First-focus press feedback in
this fixture falls from 3,683.07 ms to 312.92 ms. These are focused development
measurements, not a repeat of the AW5 load matrix or a claim that the interaction
targets now pass.

Seven emitted pixel scenes include 64 clipped glyph cases plus four screen-edge
cases, checked against the upstream software oracle. They cover both X parities,
single-nibble clips, partial rows, hardware-zero/nonzero ink, blank glyphs and
replace/transparent modes. The panel fixture also checks controls, independent
contexts, final pixels, stack guards and ownership restoration. The demo links
the same tested C image. Fixed, per-public-Task and idle bank-zero reservation
deltas are all zero, including guards, alignment and unused capacity; upper-RAM
and VRAM reservations are unchanged.

The disk failure is independent of panel painting: mounting precedes application
startup. Filesystem initialization mounts the entire configured set before
publishing it. With the correct SYS disk in D1 but WORK absent from D8, the D8
read times out and neither mount becomes available. The saved GUI profile placed
WORK in D2. The same GUI executable and copied profile succeed with WORK in D8;
no emulator change is needed. Startup now reports a filesystem-wide failure,
lists the other required drives and explains that a SIO timeout requires a cold
boot. The missing-WORK regression retains a usable console, checks that attaching
the disk does not clear the offline latch, and exits through the existing
reset-required path.

The initial GUI experiment was invalid: the isolated test profile omitted the
GUI's disk-retention setting, so Boot Image ejected its disks. That observation
does not establish an emulator regression. The shared harness now explicitly
retains disks across GUI boot, and the recorded valid controls use that policy.

The refreshed archive is `build/clipped-glyphs/preview/exec816-demo.zip`. Its
desktop boot, disks, guide, ROM and notices are checked from extracted ZIP bytes.
The root keeps the unchanged AW6 standard shell/prime package and five-second
OF816 autoboot. The follow-up record pins the archive and test results.

## Button feedback follow-up

The [button feedback evidence](../development/aes-widgets-feedback.json) records
a focused idle comparison on the pinned PAL 8× machine. The presenter previously
cleared the client separately and charged hidden/out-of-clip objects against its
four-object turn budget. A clear could therefore reach the display before the
affected control was drawn. Painting now budgets only intersecting visible
objects, keeps background initialization with the first object chunk, and draws
widget strips offscreen until they are complete. Tree order, outward borders,
focus marks and the existing sixteen-row/four-object limits are preserved.

The buffer reuses 5,120 bytes of screen padding at VRAM `$12C00`. Intermediate
command-list drains remain offscreen, while the completed clip is copied with
odd edge nibbles preserved. Pending scratch writes and publication share an
ordered list when capacity and pointer restoration permit. This is strip
publication, not an atomic swap of a whole frame or window.

Five paced actions give these capture-to-pressed-pixel observations:

| Control | Before | After |
| --- | ---: | ---: |
| Toggle | 139.12 ms | 159.08 ms |
| Large | 379.87 ms | 319.49 ms |
| Apply | 379.87 ms | 339.70 ms |
| Small | 179.29 ms | 138.87 ms |
| Cancel | 379.87 ms | 339.45 ms |

The improvement is modest and not uniform: Toggle takes one additional PAL
frame in this sample. The ten press/release edges show **48 → 0 observed frames**
with button pixels matching neither their old nor final colour. Observation
starts after the model/application checkpoint, stops at the first exact match
and excludes the pointer footprint; it is not continuous scanout or proof for
every possible gesture. Final button hashes match across builds.

Across those actions, Paint calls fall from 66 to 35 and hardware starts from
250 to 189. Charged Paint CPU rises from 1,202.72 to 1,233.71 ms, with maximum
call cost rising from 53.17 to 63.89 ms. Reduced scheduling/clearing delays account
for the faster controls; this is not a CPU-throughput gain. Neither build enters
the 4 KiB CPU staging adapter in the measured cohort. Old/new focus still produce
one union rectangle, so painting between distant controls remains a latency
cost. The existing responsiveness targets remain open.

Optimized emitted checks cover twelve independent pixel scenes, including
transparent/hidden roots, overlapping objects, odd clips, an unfinished strip
that must stay offscreen, and rejection of a mismatched continuation. The panel
fixture retains keyboard, disabled-control, independent-context, final-pixel,
guard and ownership checks. An aligned ten-scene cache/exposure run passes on
the buffered renderer before the final redundant-flush removal; final emitted
pixel and application checks exercise the resulting ordered-list publication.
The host suite runs 361 tests: 357 pass and four historical checks are skipped.
This is development coverage, not release or physical-hardware qualification.

Reserved bank-zero growth is **0 bytes** for fixed/root/kernel, each public Task
and private idle, including guards, alignment and unused capacity. Six words and
one longword use 16 more bytes within the existing upper C data reservation.
Upper-RAM and total VRAM reservations do not grow.

The refreshed archive is `build/widget-feedback/preview/exec816-demo.zip`, SHA-256
`7024a53cda56b96ff5bd3e5f7adfe3fd33c39aa805314004dfc52e23abd4bca1`.
All 24 file hashes verify. Its root retains the unchanged standard shell/prime
boot artifacts; the extracted desktop passes the OF816 countdown, controls,
dragging, physical disk commands, writable WORK, pipeline, BREAK, guards and EXIT
checks. The measured panel and demo link the identical C renderer image.

The initial walkthrough timed out after a BREAK checkpoint selected only by
multiple dirty console rows. Command echo can satisfy that condition before CAT
starts. The runner now waits for CAT's foreground scope and active console write
as well as dirty rows; the same packaged image passes that precise scenario.
The evidence retains the failed attempt and the successful checkpoint.
