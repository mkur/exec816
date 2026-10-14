# Window and menu response work

[History](README.md) · [Implementation plan](../plans/gem4xe/window-menu-response-plan.md) ·
[Gadget atlas plan](../plans/gem4xe/frame-gadget-atlas-plan.md)

2026-10-14. Implemented in executable slices with focused development checks;
no hardware qualification claim.

## UI1 Menu state and folder focus

Folders raise through their ordinary `WM_TOPPED` handler before publishing menu
changes. Files compares each desired enable/check bit with its shared installed
tree and calls AES only when that bit differs. The obsolete per-folder menu
mask is removed. AES accepts repeated enable/check values without damaging the
object or advancing `menuRevision`. Menu normalization still acknowledges
selection, and text setters retain their normal behavior.

The desktop application builds with its emitted Browser layout probe, and the
five desktop contract host checks pass. The optimized menu fixture adds
unchanged/changed enable/check revision assertions alongside its existing
physical interaction and durable acknowledgement checks. All seven physical
phases pass, including independent menu pixels, disabled/replaced menus and
normal exit/ownership checks (`build/window-menu-response/ui1-menus`).
The pinned compiler's release build is used
for the runtime check; an initial slow debug-compiler invocation was stopped
before execution.

Memory: **0 fixed, 0 per-public-Task and 0 idle reserved bank-zero bytes added**,
including guards, alignment and unused capacity. Each Browser loses two bytes
of upper-RAM state. No VRAM reservation change in UI1.

## UI2 Initial folder title

Files publishes the known path before `wind_open`; directory enumeration only
updates the summary/content. Navigation still publishes an actually changed
path. The initial-frame observer now expects four batches for the new window,
without the former fifth path-title repaint.

The desktop application and emitted Browser layout probe pass in
`build/window-menu-response/ui2-desktop`. Physical open/navigation and timing
checks are shared with the final packaged-image pass. Reserved bank-zero delta:
**0 fixed, 0 per public Task, 0 idle**, including guards/padding/capacity. No
persistent data or VRAM reservation is added.

## GAT1 Immutable gadget atlas

Seven existing marks are packed at build time in even/odd X phases. Extraction
records the asset, generator, VRAM map and generated-header hashes. A display
session uploads the 2,688-byte atlas before enabling presentation, using the
existing failure cleanup and upload path. Drawing remains procedural in GAT1.

Two host checks compare both packed phases with the independent procedural
frame raster and verify deterministic generation/storage bounds. The optimized
`tools/test_frame_gadgets.py` fixture passes ten assertions: upload readback,
normal close/reopen, adjacent VRAM sentinels, injected upload failure and
successful reopening afterward. Normal ownership/context/stack checks pass;
results are in `build/window-menu-response/gat1/results.json`.

The atlas reserves **4,096 VRAM bytes** at `$39000–$39FFF`, including 1,408 bytes
unused by the images. Totals are 420,352 reserved and 103,936 unassigned VRAM
bytes. Its immutable source pixels occupy 2,688 bytes in the existing upper
table bank. Reserved bank-zero delta is **0 fixed, 0 per public Task, 0 idle**,
including guards, alignment and unused capacity. No CPU staging buffer is added.

## GAT2 Title gadget copies

Close, full-size, iconify and iconified-tile marks now append atlas records to
the existing frame batch. The helper clips once, selects the original X phase
and maps either ordinary or compact scratch coordinates. Aligned opaque images
use one copy; partial packed bytes retain their neighboring pixels. No separate
admission, upload or fence is added per gadget.

The optimized atlas fixture passes 20 assertions and five independent full-screen
pixel comparisons: active and inactive titles, odd X, clipped marks, Shell's
title and an iconified tile (`build/window-menu-response/gat2/results.json`).
The fixture supplies explicit clip coordinates; an initial Calypsi 5.18 local
struct-expression build produced incorrect stack loads for derived clip bounds.
No production renderer change was made to accommodate that fixture issue.

The seven descriptors add 42 bytes of immutable upper-image data. Reserved
bank-zero delta: **0 fixed, 0 per public Task, 0 idle**, including guards/padding/
capacity. GAT2 uses GAT1's VRAM page without further reservations.

## GAT3 Scrollbar and resize copies

Arrows and the resize grip use the same atlas helper; tracks, thumbs and shared
separators retain their existing solid fills. The optimized fixture passes
36 assertions and nine independent full-screen pixel cases, including both X
phases, full scrollbars, clipped marks, a 240-row compact fragment with scratch
canaries and a subsequent ordinary title batch. Ownership and stack checks pass
(`build/window-menu-response/gat3/results.json`). Renderer and whole-interaction
measurements follow in the combined packaged-image observations.

Reserved bank-zero delta: **0 fixed, 0 per public Task, 0 idle**, including
guards, alignment and unused capacity. No further VRAM or persistent state is
reserved.

## UI3 Bounded menu continuation

A completed foreground save/restore retires before unrelated control admissions.
Ready menu strips continue within the worker's existing four-step allowance,
with input between units and unchanged control/output budgets. The existing
two-menu-transaction fairness rule remains. Idle captures use their old path.
No additional hardware polling, completion identity, Task or priority is added.

The optimized menu fixture passes its seven physical phases, acknowledgement,
menu replacement, disabled entry, ownership and guard checks
(`build/window-menu-response/ui3-menus`). The passive observer now records
C call returns and native completion/continuation boundaries, separating Task
CPU charge from elapsed time. The observed baseline View transition has about
8 ms from blitter IRQ completion to polling; this alone does not justify an
extra immediate probe. Combined latency acceptance follows in UI5.

Reserved bank-zero delta: **0 fixed, 0 per public Task, 0 idle**, including
guards/alignment/capacity. No additional persistent state or VRAM is allocated.

## UI4 Plain menu-row selection

Clean, fully visible application popups invert up to two disjoint plain enabled
rows in one synchronous admitted batch. Eligibility is limited to ordinary
white menu paper and unadorned `G_STRING` children inside the border, at most
16 scanlines high. Source changes, unfinished pixels and other styles retain
normal painting. The existing selection becomes committed only after the paint
transaction finishes; failed drawing retains ordinary damage, not an XOR retry.
No glyph rendering, staging upload or popup-cache mutation occurs in this path.
The private widget operation adds a constant, without changing packet layout.
Native fallback menus keep their normal row renderer.

The optimized physical menu fixture passes all seven phases. Added independent
pixel comparisons cover A→B→A, repeated input without a second inversion, entry/
exit and both odd packed edges. The fixture observes exactly four inversion
batches for four changes. Its existing checked/disabled long-label, replacement,
cache reopen, keyboard and cleanup cases pass as well
(`build/window-menu-response/ui4-menus/results.json`). Generated widget
definitions and the focused widget contract host checks pass.

Reserved bank-zero delta: **0 fixed, 0 per public Task, 0 idle**, including
guards/alignment/capacity. No persistent selection storage, new CPU staging or
VRAM reservation is added; the existing widget packet carries two rectangles.

## UI5 / GAT4 Packaged measurements

The final executable source is `40a9fd4`; documentation/observer edits account
for its `-dirty` build label. Compare the frozen FE4 package from
[window frame/exposure](window-frame-exposure.md), without changing the
`05c01f39ff3beef97af0e65b0a16666f5a1bd805` actionc pin, Calypsi 5.18,
AltirraOS 3.44 ROM, emulator, PAL, 65C816 ×8, 4 MiB RAM, VBXE 512 KiB at `$D600`
or default 462×196 Files geometry. Physical completion is sampled once per
PAL frame. Three samples give the following medians/maxima, not p95 estimates.

| Completed visible action | FE4 median / max, ms | Response work median / max, ms |
| --- | ---: | ---: |
| New Window, correct path frame | 942.8 / 962.7 | 782.3 / 802.3 |
| New Window, complete folder | 1404.0 / 1424.0 | 1323.7 / 1343.7 |
| Close folder wholly right of icons | 601.7 / 601.7 | 521.4 / 521.4 |
| Warm SYS: focus | 641.6 / 641.9 | 280.9 / 280.9 |
| Warm Shell focus | 280.7 / 280.9 | 280.9 / 280.9 |
| Warm File opening | 200.6 / 200.6 | 200.6 / 200.6 |
| Warm File → View | 220.5 / 220.5 | 220.8 / 220.8 |
| Warm dismissal | 140.5 / 140.5 | 140.5 / 140.5 |
| Plain application-row highlight, separate cohort | 100.3 / 100.3 | 80.3 / 80.3 |

The New Window/close baseline uses the retained FE4 three-sample record; one
additional frozen-package New Window run supplies the richer CPU/record trace
and reproduces its 942.8/1404.0 ms endpoints. Focus, warm menus and highlight
have fresh matched three-sample comparisons. The first File/View/dismiss cycle
is recorded separately: 361/361/261 ms before, 261/361/261 ms after. These first
responses are not included in the warm medians. The separate highlight cohort
includes ordinary open/switch/close and remains within the same sampling band
for those actions.

SYS: still uses one 42,735-byte body restore, with no Files repaint, cache
capture/patch or side-frame reconstruction. Its first frame call moves from
about 531.5 to 197.0 ms after input, consistent with raising before publishing
menu state and removing unchanged enable/check exchanges. Clicking an already
focused title still does no work. Exact desktop exposure on close remains:
icons outside the closed window do not change, while actually covered icons
are restored.

### Renderer work and remaining menu costs

The passive observer matches native/C entries and returns and separates the
presenter's conservative CPU charge from peer-Task time and native interrupts.
VBXE completion is observed at its IRQ handler; this is not an independent
measurement of the hardware BUSY falling edge. `VbxeOwnerSubmit`'s emitted
entry receives the record count in A, supplying frame-local record totals.

| Frame fragment | CPU charge before / after, ms | Records before / after | Fill calls before / after |
| --- | ---: | ---: | ---: |
| Matching `SYS:` title | 26.09 / 13.59 | 110 / 44 | 42 / 9 |
| Bottom | 10.19 / 7.86 | 25 / 14 | 20 / 8 |
| Left side | 6.13 / 6.73 | 14 / 14 | 2 / 2 |
| Right side | 20.12 / 16.91 | 80 / 58 | 25 / 15 |

Before values are one representative frozen-package trace; after CPU values
are medians of three opens. The matching-title comparison uses the baseline's
later `SYS:` title, not its initial `Files` title. The left side has no fixed
mark to optimize; its small CPU variation does not establish an improvement.
All frame calls perform **zero atlas uploads**. Total frame CPU charge falls
from 93.72 to 45.17 ms per open, including removal of the extra title update;
this combined number is not an atlas-only gain. The independent frame fixture
establishes unchanged gadget pixels, clipping, packed edges and scratch bounds.

Warm View's completion-adoption → next-copy interval decreases from a median
61.56 to 60.44 ms; scene-token retirement → next-copy decreases from 57.59 to
56.51 ms. UI3 therefore has a small measured continuation benefit, but **no
established whole-dropdown speedup**. IRQ completion → adoption remains around
9–12 ms. No immediate-poll optimization or pointer-lifetime change was retained.
The much larger remaining interval contains state-machine/scene work; it must
not be reported as DMA time or an obligatory VBI wait. Warm opening, switching
and dismissal remain useful future targets.

### Scope, memory and delivery

Checks are development tier only: two atlas host checks, four widget contract
host checks, five desktop contract checks, generated widget definitions, the
optimized frame/atlas fixture, optimized menu fixtures, and the selected exact
package interactions above. No release qualification or compiler matrix ran.
The package's frame and selection observers check normal EXIT, ownership and
stack/context restoration. Supplemental two-folder checks cover independent
view/selection state and parent/subdirectory titles.

The first combined observer completed its timing samples, then its supplemental
folder check used an obsolete menu-row coordinate. The observer also initially
assumed a public AES Service layout for a private record. These host-only
assumptions were corrected; the supplemental checks run separately, reusing the
completed timing samples. They read the presenter's settled revision directly.
No production code was changed for these observer corrections.

Relative to FE4, `runtime_reservations`, every Task pool and the complete
bank-zero budget are identical: **0 fixed, 0 per public Task, 0 idle bytes**,
including guards, alignment and unused capacity. No stack/DP enlargement.
The emitted native program's executable segments grow by 5,770 bytes; the C
image's executable segments grow by 559 bytes and its initialized data by
2,970 bytes. The atlas's 2,688 bytes plus 42 descriptor bytes are immutable upper
image data. VRAM grows once by **4,096 bytes**, including 1,408 unused atlas
bytes; total reservations are 420,352, leaving 103,936 unassigned bytes.

Final ZIP: `build/window-menu-response/demo/exec816-demo.zip`, 634,203 bytes,
SHA-256 `75380ddaaa2b1da3070cd6080c433cf2c5378e303414376ac51daef644231485`.
It retains OF816, five-second autoboot, matching SYS/WORK disks, the pinned ROM,
license notices and checksums. Traces, manifests and intermediate files stay
outside the ZIP. OF816 development inputs remain in the demo's `of816/` folder.

```sh
python3 tools/build_demo.py --gem-desktop --release-compiler --output build/window-menu-response/demo
open /Users/michalkurcewicz/action/exec816-public/build/window-menu-response/demo/launch-altirra.command
```

Evidence: `build/window-menu-response/gat3/results.json`,
`ui4-menus/results.json`, `frame-observer/frame-exposure-results.json` and
`frame-exposure-trace.json`, `demo/window-preservation-results.json` and
`window-preservation-trace.json`, `selection/menu-results.json`, and
`contracts/response-contract.json` / `window-preservation-runtime.json` under
that same development directory. The matching baseline selection and archived
passive logs are retained alongside them.

## Follow-up: one initial folder paint

The opening path called `refresh()` immediately after `wind_open()`, painting
all contents before returning to the event loop. AES had also queued the
ordinary initial `WM_REDRAW`, so dispatching that event cleared and painted the
same contents again. The earlier observer stopped its completion timer at the
first complete image and checked frame batches, but did not reject this second
application paint.

The initial scan now prepares the listing and slider state while the folder is
not yet ready; the queued `WM_REDRAW` performs its first content paint. Initial
scan failures likewise leave their status text for that event. Refresh and
navigation of an already-ready folder still paint immediately. This uses the
existing readiness field; AES messages and exposure semantics are unchanged.

The focused frame observer records the folder's completed content paints and
watches its pixels for another 80 PAL frames after the first complete image.
Its `--open-only` mode selects one New Window, verifies an explicit Refresh,
then exits normally. The frozen response demo reproduces **two** content paints
and **21** differing frames after its first complete image.

The corrected package completes **one** initial content paint, with **zero**
changed frames during that same observation interval. Ctrl-L completes exactly
one further paint with the same final listing. Four initial frame batches remain;
there is no extra title repaint. Normal EXIT, ownership and stack/context checks
pass. Development scope is five desktop contract host checks and one selected
packaged opening per version, with Refresh on the corrected version. No broad
qualification or compiler matrix ran.

The single first-image observation is 1,343.7 ms before and 1,463.9 ms after.
The old endpoint precedes its second repaint, so these values do not compare
time to a stable completed window or establish an overall speedup. The fix
removes the redundant content painting and its visible clearing pass.

Evidence is under `build/window-open-once/baseline` and
`build/window-open-once/demo`: `frame-exposure-results.json`,
`frame-exposure-runtime.json` and the corrected `new-window-checks.json`.
The refreshed OF816 ZIP is `build/window-open-once/demo/exec816-demo.zip`,
634,259 bytes, SHA-256
`dd11de91ff8974e65fffd68bb4fce66fcf1b1511ab08b7b155eee76ddf589c96`.
Its archive and per-file checksums pass; distribution contents retain the pinned
ROM, matching disks, licenses and five-second autoboot.

```sh
open /Users/michalkurcewicz/action/exec816-public/build/window-open-once/demo/launch-altirra.command
```

Reserved bank-zero delta: **0 fixed, 0 per public Task, 0 idle**, including
guards, alignment and unused capacity. No extra VRAM or persistent state.

## Follow-up: keyboard selection without unchanged-content repainting

`paint_selection()` previously repainted the summary strip for every selection
change, even when its text remained `1 selected`. Keyboard focus also made it
redraw complete old and new icon cells, including their unchanged colour
bitmaps. Each intersecting object draw could erase and restore the software
pointer. The frozen pre-fix keyboard observer found no change in either input
or renderer pointer coordinates, but recorded two cursor hides over the summary
and three over an icon during one arrow-key action.

Files now compares the new summary text before painting it. Icon selection
updates draw only the label rectangle; focus moves erase the old outline's
four one-pixel edges and draw the new outline. List selection still paints the
changed rows. An unchanged selection/focus/status returns without opening a
drawing transaction, and scrolling that already painted the new selection does
not repeat the selection pass. This relies on the existing stock icon policy:
selection changes the label, not the colour bitmap.

The pointer driver and general AES object renderer are unchanged. A pointer
over genuinely changed text or an outline can still be hidden during that
draw. That first fix left the separate preservation-cache completion issue
open: `paint_selection()` did not report completed painting, so a later
exposure could require application repainting. The next follow-up closes it.

The focused packaged check passes with unchanged pointer coordinates and zero
changed summary frames in all five observed actions. In the three icon cases,
pointer pixels remain stable and cursor-hide calls fall from **2 / 3 / 0** to
**0 / 0 / 0** (pointer over summary / icon / outside the window). The list case
still overlaps a changed focus edge; cursor-hide calls fall from five to two.
Repeated Up on the first item performs zero paints and zero drawing borrows.
One keyboard scroll performs one content paint without a second selection pass.

Each incremental result, including the scrolled grid, matches a normal full
Refresh pixel-for-pixel. Changing the selected count still updates the summary.
Normal EXIT and stack/domain guards pass. The observer initially used a fixed
delay for entering `SYS:C`; the supplemental scroll case now waits for the
directory scan to finish. No application change was needed for that correction.
Scope is development: this one selected physical keyboard scenario before and
after, archive/checksum checks and source checks; no qualification matrix.

Evidence: `build/files-keyboard/baseline/keyboard-results.json` and
`build/files-keyboard/demo/keyboard-results.json`. The updated OF816 package is
`build/files-keyboard/demo/exec816-demo.zip`, 635,371 bytes, SHA-256
`c15c819d243ad8d920ce972b4038931cb177ad58bacbd76eb8107eaed01b643c`.
It retains the pinned ROM, matching disks, licenses and five-second autoboot.

```sh
python3 tools/measure_files_keyboard.py --bundle build/files-keyboard/demo
open /Users/michalkurcewicz/action/exec816-public/build/files-keyboard/demo/launch-altirra.command
```

Relative to the preceding opening fix, runtime reservations, every Task pool
and the complete bank-zero budget remain identical: **0 fixed, 0 per public
Task, 0 idle bytes**, including guards, alignment and unused capacity. No
additional persistent state or VRAM reservation.

## Follow-up: retain completed selection changes in the window cache

AES accumulates a bounding rectangle for an UPDATE's drawing. Reporting only
the individual labels and outline edges would leave gaps inside that rectangle
unacknowledged. Reporting the whole rectangle unconditionally would be wrong if
older exposure damage still needed reconstruction.

The published view now uses its former padding byte for `pixelsReady`: Layers'
work-area readiness at snapshot publication, including the UPDATE grant. No
record size or offset changes. Iconified views explicitly publish zero. The
caller-local `ExecAESPaintedChanges(window)` helper reports the accumulated
change rectangle only when that starting image was complete. The caller still
promises that all its drawable changes finished successfully. Existing visible
clipping, generation matching, journal capacity and sticky failure checks apply.
Incomplete starting pixels remain on the repaint fallback; the helper does not
acknowledge earlier unfinished content.

`paint_selection()` calls the helper once after its successful small draws and
before END_UPDATE. It adds no RPC, update scope, allocation or rendering pass.
The cache can patch the changed span, then restore the updated selection on a
later exposure. The C application import ABI advances to 18 for the helper;
the desktop provider and every packaged application are rebuilt together.

The first physical preservation check passed for icons but exposed another
miss in list view: its one-pixel button borders put the completed change on
odd X edges. `DESKCACHE.EndChange` now rounds the local patch span outward to
packed-pixel byte boundaries. At most one adjacent pixel is copied on each
side; the existing client-bounds, readiness and visible-source checks still
gate the expanded copy. No drawing is widened and no new storage is needed.

The existing software-pointer rule still applies to cache maintenance: when
copying screen pixels into a saved image, the copy path removes an intersecting
pointer so its pixels cannot be baked into the cache. The keyboard observer
distinguishes this necessary source cleanup from per-object cursor hiding.

The optimized AES cache fixture passes all 31 phases and 220 application
assertions, including completed patches, incomplete starting pixels, partial
completion, hidden/model-only changes, eviction, exact restored pixels and
normal cleanup with intact guards. The new helper is exercised both with a
ready starting image and with an unfinished image where it must record no
completion. This run selects `release=True` for the existing pinned host
compiler via the runner's `native_program.compiler` binding; the compiler
revision and optimized guest build are unchanged. Evidence is
`build/files-selection-cache/aes-cache/results.json`.

The final packaged keyboard check passes in icon and list view. After changing
selection, switching to Shell and back restores identical work-area pixels with
**zero Files paints, zero captures and zero patches** during exposure. The
observer records one cache restore for the icon switching sequence and two for
the list sequence, which includes Windows menu interaction. Each incremental
selection and keyboard scroll still matches a full Refresh; boundary Up does
no painting and scrolling adds no duplicate selection pass. Summary text and
both input/renderer pointer coordinates remain unchanged in all five samples.
Cache-source cleanup can briefly hide the pointer; the trace rejects cursor
hiding from unchanged icon-object drawing. Normal EXIT and guards pass.

Development scope: nine selected host checks, generated-file and unchanged
record-layout checks, the optimized AES cache fixture, the packaged keyboard
and focus scenario, and archive/checksum checks. No qualification matrix ran.
The final package and cache fixture use the final patch-alignment code.
Bank-zero reservation delta is **0 fixed, 0 per public Task, 0 idle bytes**,
including guards, alignment and unused capacity. No stack/DP enlargement or
VRAM reservation change; the view uses its existing byte of padding.

The updated OF816 ZIP is `build/files-selection-cache/demo/exec816-demo.zip`,
635,683 bytes, SHA-256
`ce1ea7a48bf487dd01f0ff0932437197d1c7e573482204bbdda45a7e429fa0ef`.
It contains the matching ABI-18 applications/system disk, pinned ROM, WORK
disk, licenses and five-second autoboot. Evidence is
`build/files-selection-cache/demo/keyboard-results.json`.

```sh
python3 tools/measure_files_keyboard.py --bundle build/files-selection-cache/demo --preservation
open /Users/michalkurcewicz/action/exec816-public/build/files-selection-cache/demo/launch-altirra.command
```
