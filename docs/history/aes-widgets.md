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
