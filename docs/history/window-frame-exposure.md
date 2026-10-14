# Window frames and desktop exposure

[History](README.md) · [Implementation plan](../plans/gem4xe/window-frame-exposure-plan.md) ·
[Desktop contract](../reference/desktop.md#private-window-snapshots)

2026-10-14. Focused development checks, not hardware or hosted-system qualification.

## Changes

FE1 packs a complete narrow frame side into the existing 5,120-byte widget
scratch. Its 8-byte pitch handles aligned sides; a 16-byte pitch handles the
extra packed byte at an odd edge. Even 240 rows occupy at most 3,840 bytes.
The destination is calculated from fill coordinates with a shift, without
screen-address division. Titles, INFO text, widgets and menus retain their
ordinary strip layout. Nonintersecting scrollbar/sizer groups are skipped.
List capacity, completion fences, pointer protection and the scene token remain.

FE2 saves outer-window pixels in the same two 76,800-byte slots. A warm exposure
copies the body below the title, including sides, scrollbar and bottom. The
title is rendered live, never replayed with stale focus/name pixels. Captures
require the complete outer image to be visible and clean, with acknowledged
client pixels. Small completed client updates still patch only their rectangle
at an outer-local offset. Changed INFO/slider values invalidate the image;
unchanged setters do nothing. Hidden updates, resize, eviction and conventional
versus opt-in exposure retain their existing semantics. The selected body
partition also survives the copy's source pin. The first focus diagnostic found
that recomputing it through the unpinned-cache lookup truncated the pending
area to the client and copied the bottom band twice. FE2's final whole-window
regression requires exactly one completed body copy.

FE3 removes false title damage from a borderless owner on focus changes. In the
unchanged baseline, closing `[120,24,582,220]` after iconifying Shell generated
both that exposure and `[0,11,640,22]` for the desktop's nonexistent title.
Layers retained the two rectangles, but the AES handoff joined them into
`WM_REDRAW(0,11,640,209)`. The desktop obeyed that broad clip and repainted icons.
The fix produces only `WM_REDRAW(120,24,462,196)`. There is no new rectangle
queue, desktop cache, interface or Task. General disjoint AES redraw coalescing
is unchanged.

## Matched package measurements

Both packages use PAL, a 65C816 at ×8, 4 MiB RAM, 512 KiB VBXE at `$D600`, ST
mouse, compiler `05c01f39ff3beef97af0e65b0a16666f5a1bd805`, and the same ROM and
emulator pins as the [preservation record](window-preservation.md). Files uses
462×196 outer bounds. Each open/close series contains three physical-input
samples; screenshots are sampled once per PAL frame. These are medians and
maxima, not p95 estimates.

| Endpoint | Previous median / max | FE median / max |
| --- | ---: | ---: |
| New Window, correct frame including resolved path title | 1404.0 / 1404.0 ms | 942.8 / 962.7 ms |
| New Window, complete folder pixels | 1865.3 / 1885.3 ms | 1404.0 / 1424.0 ms |
| Close folder wholly right of icons, desktop draw complete | 902.6 / 922.8 ms | 601.7 / 601.7 ms |
| Warm SYS: whole window | 1163.3 / 1163.3 ms | 641.6 / 641.9 ms |
| Warm Shell whole window | 280.8 / 280.9 ms | 280.7 / 280.9 ms |

The focus comparison reuses the previous two-sample reference and observes
three final samples. SYS: uses one 42,735-byte body copy, no tall-side rendering,
no Files repaint and no exposure-triggered capture/patch. Whole-window
completion improves about 45%; client completion stays near 642 ms. Shell is
unchanged within one PAL frame. Live title work also includes exposed pieces
of the outgoing window, so global frame-call counts are not a per-window count.
Repeated warm File/View/dismiss responses are 200.3–200.6 / 220.5 /
140.2–140.5 ms, matching the earlier warm samples within one PAL frame. Their
first responses remain about 361 / 361 / 261 ms. Comparing a three-sample menu
median with the previous two-sample average would misleadingly suggest a gain.

A new window uses four initial frame batches, down from 24. Files then changes
its provisional `Files` title to the resolved path: the complete observed action
therefore contains **5 frame calls instead of 25**, including exactly two tall
side batches. The observer checks the four initial batches plus that live
path-title update.

Across the whole New Window observation, private renderer list submissions fall
from 104 to 84 and fence calls from 381 to 315. These include other UI work and
idle maintenance; they are not frame-only CPU costs. The frame appears about
33% sooner, while the whole folder improves about 25%. Directory/application
setup and client drawing still take time after reducing frame construction.

Closing the right-hand folder shows **zero changed icon-column frames** in all
three samples, versus 16–17 previously. Sampled Layers damage and the delivered
redraw stay wholly to the right of the icons, so the desktop's clipped object
renderer has no icon intersection. This check observes damage/messages and
screen pixels; it is not an independent hardware trace of every VRAM write.
A separate close covering the icons restores their correct pixels and passes
the complete desktop oracle (862.4 ms, one sample; previous 922.6 ms).

## Validation scope

- Optimized presenter fixture: 117 native assertions and independent pixels,
  including partial/odd exposure. This ran at FE1 before the pitch correction.
- Optimized AES cache fixture on the corrected renderer: 194 C and four native
  assertions across 31 phases. Exact whole-frame pixels, INFO/slider changes,
  no-op setters, small patches, conventional/preserved exposure, fully hidden
  changes, sibling updates, same-size moves, resize and eviction. Normal EXIT,
  stack/domain guards and native context restoration passed.
- Exact packaged image: three cold opens, three right-hand closes, one close
  covering icons, Shell iconification/restoration, and independent final scene
  pixels. The final package is rerun after the pinned-copy correction; its full
  runtime record includes normal EXIT and intact guards.
- Exact package focus/menu observer: three Shell/SYS: pairs and three
  File/View/dismiss cycles, independent settled pixels, no duplicate application
  paint/cache maintenance, normal EXIT and intact guards.
- Focused host checks: VBXE table generator (2), desktop contract (5), desktop
  packaging (3), demo packaging (12). Documentation links and whitespace checked.

The frame pixel comparison caught an invalid use of the existing sixteen-row
work table for tall scratch offsets. Using a power-of-two pitch removed that
lookup and passed the new scrollbar comparison. No compiler pin changed.

Testing stayed at development scope. The maximum-height scratch limit is
established by the admitted geometry and capacity calculation above; no new
240-row canary fixture or full failure matrix was run. Existing quiesced-failure
and ownership evidence is retained in the preservation record; transfer
lifetime/completion code was not changed.

## Memory and package

Reserved bank-zero delta for every slice: **0 fixed, 0 for each public Task,
0 idle**, including guards, alignment and unused capacity. Runtime reservations
remain 10,528 fixed bytes, 800 idle bytes and public Task reservations
`[1824,1600,1600,1600,1600,1600,2848,2848]`: 26,848 bytes excluding OS reservations.
The adapter adds two upper-RAM words (four bytes) for scratch pitch/mode. FE2 and
FE3 add no persistent records. VRAM reservation delta is zero.

A default saved window uses 45,276 bytes instead of 38,106 client bytes. Its
restorable body below the live eleven-row title is 42,735 bytes. Shell retains
its dedicated backing surface.

Previous ZIP: `build/window-preservation/demo-final/exec816-demo.zip`, SHA-256
`a3d93292f287574ab6f42863063e8b929f5a9276ce2e63dfd5ab59d2dd476536`.
New ZIP: `build/frame-exposure/demo/exec816-demo.zip`, 631,558 bytes, SHA-256
`8e1fcde77dd49cf98fa0a4087d5eeb65c7e82cb89d51057aaf2816b5dfbc801c`.
It includes OF816, five-second autoboot, matching disks, pinned ROM, license
notices and checksums. Development manifests/traces remain outside the ZIP.
The final image was built while the continuation correction was uncommitted,
so its label is `0dc761e-dirty`; its executable source matches `7f3992c`.

```sh
python3 tools/build_demo.py --gem-desktop --release-compiler --output build/frame-exposure/demo
python3 tools/measure_frame_exposure.py --bundle build/frame-exposure/demo
python3 tools/measure_window_preservation.py --bundle build/frame-exposure/demo --count 3
open /Users/michalkurcewicz/action/exec816-public/build/frame-exposure/demo/launch-altirra.command
```

Local evidence: `build/frame-exposure/aes-cache/results.json`,
`build/frame-exposure/presentation/presentation-results.json`, and the demo's
`frame-exposure-results.json` / `window-preservation-results.json`.
