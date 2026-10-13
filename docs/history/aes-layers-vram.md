# AES and Layers VRAM caching

[Plan](../plans/gem4xe/aes-layers-vram-plan.md) ·
[Design](../plans/gem4xe/aes-layers-vram-design.md) ·
[Layers contract](../reference/layers.md) · [AES contract](../reference/aes.md)

The shared cache paths and incremental repairs are implemented. Optional copied
AES moves remain disabled; numeric latency acceptance is separate from functional
completion. Development checks below do not qualify a release matrix or real
hardware. AV1/AV2 used the original compiler pin; the AV3 compiler dependency
and final matched baseline are recorded below.

## AV1: external repaint bookkeeping

External layers retain pending client repaint independently of presenter
damage. A successful handoff retires only presenter work. Explicit completion
subtracts the reported rectangle for its observed generation; stale reports,
failure and excess fragments retain pending repair. No application wait holds
a scene transaction or causes repeated redraw delivery.

The existing outer UPDATE exchange publishes eight caller-local completion
records. Drawing accumulates changed bounds before visibility clipping; later
overlapping writes revoke earlier claims. Failure remains sticky across later
successful calls. Nested UPDATE preserves the journal. Snapshot publication
after a title/geometry call does not erase accumulated changes. Counter and
Files/desktop call the optional helper after successful reconstruction.

AES wire version 15 and C-program import ABI 16 require rebuilding clients.
Ordinary GEM clients without the helper continue on the existing redraw path.
No cache or copy admission changes in this slice.

Memory: Scene grows from 8,496 to 9,162 bytes (+666 fixed upper-RAM bytes).
Request/context grows by 114 bytes per registered client; each published
window view grows by 14 bytes, at most 84 for six owned windows. Combined
caller growth is at most 198 bytes. VRAM remains 243,200 bytes. Reserved
bank zero changes by **0 fixed / 0 per public Task / 0 idle bytes**, including
guards, alignment and unused reserved capacity.

Development checks: 459 host tests (455 pass, four existing skips); optimized
Layers regression (60,070 checks); raw/optimized far-record Layers probes;
raw/optimized C/Action! context/layout probes; optimized VDI pixel/ownership
regression including nested journals, bounded overflow, superseded completion
and sticky failure. Both exact OF816 packages pass the timing walkthrough and clean EXIT. Baseline
ZIP SHA-256 is `81c339570194b9041be0407fa85c096d79d596236bc133795c23ccfc3d95b2a2`;
AV1 is `ee2ce02ca941399f025cf8314cee3bf838b08468f0e89f3980394d870aeb7d63`.
The packaged bank-zero budget, runtime reservations and Task pools match.

Twenty samples per interaction, median/p95 milliseconds:

| Interaction | Baseline | AV1 |
| --- | ---: | ---: |
| File opens | 401.2 / 401.2 | 401.2 / 401.2 |
| File highlight | 80.3 / 80.3 | 80.3 / 80.3 |
| File to View | 782.1 / 782.3 | 802.3 / 802.3 |
| View closes / Files finishes | 401.2 / 401.2 | 421.1 / 421.4 |
| Windows opens | 180.6 / 180.6 | 180.6 / 200.6 |
| Windows highlight | 80.3 / 100.3 | 100.3 / 100.3 |
| Windows next row | 100.3 / 100.3 | 100.3 / 100.3 |
| Windows closes, visible pixels | 501.4 / 501.4 | 521.4 / 521.7 |
| Windows closes, Files finishes | 501.4 / 501.4 | 541.6 / 541.6 |

The overhead gate remains open: dismissal approaches/exceeds its one-frame
allowance, and final Files completion after Windows dismissal adds two frames.
Raw samples, source hashes and check artifacts are in the
[machine-readable record](../development/aes-layers-vram.json). No loaded or
cold-cache latency acceptance is claimed by this idle comparison.

## AV2: shared cache policy and menu backgrounds

Layers now owns a single saved-scene rectangle and shared two-slot identity,
revision and pinning policy. Native client snapshots use that policy too. A
menu captures only completed visible contributions. Its own drawing is exempt
from invalidation; underlying content, console damage and geometry changes
invalidate intersecting saves. Unsupported alignment and incomplete source
paint use ordinary rendering without waiting for an application.

The coordinated hide/restore transaction pins its storage through display
completion. Successful restoration subtracts only that footprint from manager
damage. AES exposure is retained and published after the selected menu heading
has been repaired, so an application UPDATE cannot delay that repair. Failed
or unquiesced transfers cannot publish a valid save or release a live pin.

Scene gains 22 bytes (9,184 total); cache records replace the old native
metadata without increasing their size. Adapter state adds 26 bytes, plus the
one-byte pending-show state. VRAM gains 76,800 bytes, for 320,000 total.
Reserved bank zero changes by **0 fixed / 0 per public Task / 0 idle bytes**.

Development checks: 459 host tests (four skips), 60,136 optimized Layers checks,
raw/optimized far-record probes (105 each), the AES menu fixture and twelve
native cache scenes. The native fixture also opens and dismisses a real Windows
menu whose saved background spans several owners, then compares every pixel
against an independent oracle. Identity reuse, native eviction, odd exposure,
geometry, failure and external pending-paint cases remain covered.

An intermediate exact demo showed real saves/restores: Windows dismissal fell
from 501.4 to 240.7 ms (median/p95), while final Files repaint was 361.0 ms.
After fixing menu-heading/exposure ordering, 20-sample median/p95 Windows
visible dismissal is 140.5 / 140.5 ms; final Files repaint is 361.0 / 380.9 ms.
The 100 ms gate remains open. File-to-View drops to 341.0 / 341.0 ms, but its
following uncached View dismissal regresses to 661.9 / 682.1 ms. This shift of
application work is a failed fallback gate, not an accepted latency result.
Cold File opening is 421.1 / 421.4 ms; Windows opening 220.5 / 240.7 ms.
Both menu types retain Counter progress under 30 highlight changes. This is
coexistence evidence, not the required loaded pointer-latency cohort.

## Compiler dependency found during AV3

Popup-key record assignment exposed an existing NIR promotion defect: a promoted
loop index was rewritten in ordinary loads/stores but not in `CopyBytes` source
and destination addresses. Raw compilation worked; optimized compilation failed
verification. The fix belongs to actionc, on `fix/nir-copy-address-promotion`;
Exec now pins that clean local commit. It has not been pushed upstream.

The focused regression covers both copy directions and all three target layouts,
including native promotion policy and optimizer idempotence. The failing full
Exec input also passes interface emission with the fix. No compiler-wide tests
or release qualification were run. The compiler ABI is unchanged; reserved bank
zero remains **0 fixed / 0 per public Task / 0 idle bytes** relative to baseline.
The baseline used `81dd7dc5`; final comparisons must record this dependency.

## AV3: rendered popup images

Two fixed 16 KiB images reuse the shared slot and display-transfer policy.
The key includes owner, menu lifetime, source revision, heading, dimensions
and exact selection. Native menu revisions change with their retained window
contents; application menus use the installed menu generation and mutation
revision. There is no hot-path string hash. Only the initial selection is
captured at idle, once per unchanged state; highlighted rows still use targeted
painting. Full matching popups restore in one transfer rather than 16-row steps.
Odd edges, oversized menus and misses retain normal rendering. Restart drops
old popup identities.

Development checks: raw/optimized far-record probes pass 107 checks each,
including both indexed record-copy directions; the emitted AES menu suite
compares a demonstrated warm File hit with independent pixels, then exercises
identical titles in different owners, replacement/disable while pressed,
selection changes, long labels and odd clipping. Host checks pass (459, four
skips). Idle and explicitly cold timing cohorts are recorded separately; cold
control invalidates only unpinned rendered-popup entries before opening.

Fixed upper-RAM metadata/counters grow by 130 bytes including alignment.
VRAM grows by 32,768 bytes to 352,768. Reserved bank zero changes by
**0 fixed / 0 per public Task / 0 idle bytes**. No caller journal growth.
Warm File opening is 200.6 / 200.6 ms (median/p95), with 20/20 observed popup
hits; controlled cold opening is 421.1 / 421.4 ms. Warm File-to-View is
240.7 / 240.8 ms, compared with 341.0 / 341.0 ms cold and the original
782.1 / 782.3 ms. Windows opening improves less: 180.6 / 180.6 ms warm
versus 220.5 / 240.7 ms cold. Its half-time gate remains open. Windows
dismissal stays at 140.5 ms; final Files repaint is 361.2 / 381.2 ms.
Uncached View dismissal remains regressed at 641.6 / 681.8 ms. Counter
progress during highlight changes is not a loaded latency measurement.


## AV4: completed AES client images

Both client slots now hold 76,800 bytes, including a full 640×240 image.
Capture uses actual client geometry and completed application pixels. Native
and AES restoration share the same policy and DMA continuation; AES still
receives `WM_REDRAW`. Title and position changes preserve images; resize,
ambiguous UPDATE and drawing failures do not. An empty UPDATE now leaves a
full repaint obligation, preventing an immediate idle recapture of old pixels.
Text, Panel, Calculator and shared dialog full redraws report completion.

Development checks pass: 459 host tests (four skips), 60,142 Layers checks,
107 checks in each raw/optimized boundary probe, twelve native cache scenes
(53 checks), full-screen capture/restore through both slots including VRAM bank
crossings and failed/unquiesced transfer retention (83 checks), and the new
AES fixture covering complete paint, title, aligned move, empty UPDATE, odd-X
fallback, resize and retained exposure notification. Exact client pixels are
checked independently. Final app walkthrough/timing remains AV6 work.

The fixed adapter counters add 20 upper-RAM bytes; caller records do not grow.
VRAM increases by 22,528 bytes, to 375,296. Reserved bank zero changes by
**0 fixed / 0 per public Task / 0 idle bytes**, including guards and capacity.


## AV5: bounded client-image repairs

At outer UPDATE, a matching unpinned image becomes temporarily unavailable.
One repair rectangle per slot retains a possible base. END requires a matching
successful completion covering the changed bounds and completed client pixels;
otherwise it discards the base. Repeated completed changes coalesce in client
coordinates. Idle maintenance reads only the visible acknowledged repair and
publishes it after DMA/read-token retirement. Eviction, resize, an ambiguous
update, an unacknowledged part or a stale revision loses eligibility. Failed
maintenance does not trigger a full recapture loop for that revision.

The optimized AES fixture passes complete client capture, two 16×8 repairs
(64 bytes each with no whole-client recapture), and exact restored pixels after
a subsequent move. A half-acknowledged change stays invalid until a complete
redraw. The twelve-stage snapshot fixture passes 109 checks, including failed
patches, unquiesced pin retention and a superseded patch revision.
Raw/optimized record/policy probes pass 116 checks each, including
coalescing, ambiguous updates, stale revisions, exhaustion and retained DMA pins.

Two ten-byte repair records and eight counter bytes add **28 fixed upper-RAM
bytes**. Service is 18,656 bytes. VRAM remains 375,296 bytes; bank-zero delta
is **0 fixed / 0 per public Task / 0 idle bytes**. Caller records do not grow.

Copied AES moves remain disabled and unaccepted. Client-image restoration on
exposure is enabled; it does not substitute for the unproven screen-to-screen
move path or waive application redraw. Final loaded maintenance/timing and
combined desktop evidence follow in AV6.

The new C fixture exposed a separate Calypsi 5.18 optimized-code defect in
`r[2]=r[0]+15; r[3]=r[1]+7`: the listing loaded the old destination elements
(`adc 9,s` / `adc 11,s`) instead of source elements at `5,s` / `7,s`.
Runtime input was `(64,84,239,115)`, rather than `(64,84,79,91)`, and the
cache correctly rejected the smaller completion claim. The fixture now forms
screen coordinates from separate x/y values and asserts the changed bounds.
This does not fix Calypsi or change production rendering; the third-party
compiler defect remains a limitation for future toolchain work.


## AV6: combined desktop and measured limits

The final desktop enables shared save-under transactions, two exact-key popup
images, two completed client snapshots and bounded idle patches. Screen-to-screen
AES copied moves remain disabled. Cache restoration preserves exposure messages;
applications still reconstruct their current model. A failed or unquiesced
transfer cannot release a live pin or publish a valid image.

Counter's eight measured six-digit updates produced eight 192-byte patches
(1,536 bytes total), no whole-client captures and no captured bytes. Its existing
exact-pixel test also passes odd X, partial/full coverage, exposure and close.
That maintenance record uses the AV5 ZIP; AV6 adds only the explicit-discard
counter to production code. It does not claim a maintenance saving for every
application or an entire-window cache hit for every redraw.

The forms fixture still assumed four desktop slots. It now fills the current
six slots with five windows across three peer Tasks plus the shell, retaining
its resource-exhaustion and cleanup checks. This is a stale fixture correction,
not a change to desktop capacity.

Final development checks pass: 459 host tests (four skips), 290 emitted AES
menu assertions and 198 form assertions, plus four native checks in each
suite. AV1–AV5 record/call probes, Layers, cache and fault checks above are
reused. The exact final ZIP walkthrough passes Files, Panel pointer/keyboard
activation, Counter progress, Text document hash/scrolling, file-selector
cancellation, close/focus restoration, disk HELLO and orderly EXIT. Final
retained pixels and stack/domain guards pass. No broader qualification matrix
was run.

### Memory and supported behavior

Added fixed upper-RAM metadata/counters total **897 bytes**, including alignment;
added per-client storage is at most **198 bytes** (114 in the request/context and
14 for each of six published window views). AV6 contributes four bytes for
explicit discards. These fit the 2 KiB fixed and 256-byte caller budgets.
Production VRAM is **375,296 bytes**, up 132,096 bytes, with 148,960 bytes free
after the unchanged 32-byte diagnostic exclusion. Reserved bank-zero delta is
**0 fixed / 0 per public Task / 0 idle bytes**, including guards, alignment and
unused reserved capacity; no Task stack, DP or kernel API grows.

`explicit_discards` counts calls that retire a nonzero cache revision. It is not
an eviction count or a count of every temporary UPDATE hold. Transfer counters
count completed captures/restores/patches and their bytes. The measurement tools
read these outside timed intervals. An observer-disabled development build
removes only diagnostic counter increments from the three cache modules;
cache decisions, data transfers and completion checks remain enabled.

Pending paint and exact lifetime/revision matching remain correctness conditions.
The conservative empty-UPDATE rule added in AV4 invalidates all owned windows
that lack drawing/completion reports. In the combined desktop this also makes
menu-background saves frequently ineligible. The earlier AV3 save-under timing
is therefore historical, not the final combined result. A future improvement
needs more precise application update attribution without treating an
unreported hidden model change as completed painting.

The first restored image and final application repaint are distinct endpoints.
The timings below do not certify flicker-free intermediate frames: a subsequent
application redraw remains possible even when restoration gives correct initial
pixels. No whole-system release or real-hardware qualification is claimed.

### Final latency comparison

The original `35a75e4` tree was rebuilt with the same corrected actionc pin as
AV6; that compiler pin is its only source change. Its idle timings reproduce
the original baseline. Calypsi 5.18, PAL 8× 65C816, 63 upper banks, VBXE,
AltirraOS ROM and emulator/media profiles are recorded by hash in the JSON.
Each idle cohort has 20 samples per interaction, polled every PAL frame
(about 20.1 ms). Numbers are **median / p95 milliseconds**; decimal places do
not imply sub-frame resolution. Cold control explicitly clears only unpinned
popup validity before each opening/switch. A duplicate warm run whose directory
was initially named `final-cold` is labelled warm in the evidence and is not
used as cold evidence.

| Interaction | Matched baseline | Final warm | Final cold |
| --- | ---: | ---: | ---: |
| File open | 401.2 / 401.2 | 160.4 / 160.7 | 401.1 / 401.1 |
| Application highlight | 80.3 / 80.3 | 80.3 / 80.3 | 80.3 / 80.3 |
| File → View | 782.1 / 782.3 | 702.0 / 702.0 | 822.3 / 822.3 |
| View close: first pixels | 401.2 / 401.2 | 421.1 / 421.4 | 421.4 / 441.3 |
| View close: final repaint | 401.2 / 401.2 | 421.1 / 421.4 | 421.4 / 441.3 |
| Windows open | 180.6 / 180.6 | 140.5 / 140.5 | 180.6 / 200.6 |
| Native highlight | 80.3 / 100.3 | 100.3 / 100.3 | 100.3 / 100.3 |
| Native next row | 100.3 / 100.3 | 100.3 / 100.3 | 100.3 / 100.3 |
| Windows close: first pixels | 501.4 / 501.4 | 521.4 / 521.6 | 521.4 / 521.7 |
| Windows close: final repaint | 501.4 / 501.4 | 541.4 / 541.6 | 541.6 / 541.6 |

Warm File opens and warm Windows opens each record **20/20 rendered-popup
hits**, transferring 259,200 and 133,120 bytes respectively across their twenty
samples. The twenty warm heading switches reuse 118,080 popup bytes. Background
save-under records no successful capture/restore in this final cohort; the
visible sources do not satisfy completed-paint admission. Client captures and
patches are also zero during these measured menu interactions. The emitted
cache fixtures separately demonstrate eligible background/client restoration,
so zero activity here is not a claim that these paths are disabled.

The File half-time gate passes. The Windows half-time and heading-switch gates
remain open. Cold switching and View dismissal regress; Windows final repaint
adds about two frames. The original AV1 overhead gate is not closed. There is
no final valid-save dismissal cohort meeting the 100 ms target. These limits
are retained rather than waived on the basis of correct screenshots.

### Loaded feedback and observer control

Thirty physical Panel presses and thirty physical pointer motions run beside
Counter and continuous `CAT WORK:LOAD.TXT`, with 0/2/4/6/8-frame phase offsets.
The boot XEX and SYS disk come from each exact ZIP. WORK uses the same 66,560-byte
load fixture and identical disk hash in all three runs. Button pixels are
reconstructed independently; pointer completion checks the actual arrow pixels.
After ordinary BREAK/retirement, the complete desktop matches its retained
model and EXIT releases Tasks without guard failures.

| Interaction | Matched baseline | Final | Diagnostic increments disabled |
| --- | ---: | ---: | ---: |
| Button feedback | 100.3 / 140.5 | 120.2 / 140.5 | 120.2 / 160.4 |
| Pointer feedback | 100.3 / 120.2 | 100.3 / 120.2 | 100.3 / 120.2 |

The loaded p95 gate passes for both interactions. Button median is one frame
higher; the p95 does not worsen. Counter ticks/paints advance, and console
content generation advances 38 times in the baseline, 40 in the final build and
37 with diagnostic increments disabled. CAT remains active at every sample.
Final correctness and progress are checked in addition to the timing counts.

With diagnostic increments removed, warm opening/switch timing is effectively
unchanged at this resolution; View-close p95 is one frame higher. Loaded button
p95 is also one frame higher and pointer p95 is unchanged. All observer-control
counters remain zero while popup reuse still accelerates opening. Code-layout
and phase differences prevent treating those differences as a precise counter
cost; there is no observed diagnostic penalty beyond the frame-level allowance.
The development-only observer build is not the distributed demo.

### Reproduction and demo

The exact final ZIP is built with `tools/build_demo.py --gem-desktop`, using the
pinned compiler and the release-built compiler executable. OF816, its notices,
the pinned ROM, matching disks and five-second autoboot are included; manifests,
test output and intermediates remain outside the archive.

ZIP SHA-256: `4bce7e01482af1176361d9ebc53b67ecd8e2c125b69e617956720de36137c12b`.

Launch locally:

```sh
build/aes-layers-vram/final-demo/launch-altirra.command
```

Focused measurement commands (choose fresh output directories):

```sh
python3 tools/measure_menu_feedback.py --bundle build/aes-layers-vram/final-demo --output build/cache-warm --count 20
python3 tools/measure_menu_feedback.py --bundle build/aes-layers-vram/final-demo --output build/cache-cold --count 20 --cold
python3 tools/measure_cache_load.py --bundle build/aes-layers-vram/final-demo --output build/cache-loaded --count 30
python3 tools/test_cache_desktop.py --bundle build/aes-layers-vram/final-demo
```

For old baseline binaries, both timing tools accept `--layout-revision 35a75e4`
to interpret that revision's recorded ABI layouts. This is host evidence support,
not a second production ABI. The compiler fix is a clean **local, unpushed**
commit on `fix/nir-copy-address-promotion`; the public pin cannot be fetched
from upstream until that compiler commit is published separately.
