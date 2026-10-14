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
