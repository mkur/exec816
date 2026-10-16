# Menu title repaint and pointer response

[Plan](../plans/gem4xe/menu-title-response-plan.md) ·
[Measurements](../development/menu-title-response.json) ·
[LR2 baseline](layers-rebuild.md)

## MT1 Complete feedback and heading crossings

The passive observer resolves coordinate stores in `DESKINPUT.Fresh` and the
pending-heading store in `DESKMENU.Heading` from emitted instructions. It
records the first normalized position inside an enabled destination heading,
then its routing. Deferred input, recrossing and loss are distinguished.
Crossing observations add no guest code, data, stopping breakpoints or timers.
Pixel sampling retains the existing frame rendezvous.

The new cohort submits one physical quadrature burst and immediately samples
each frame. The historical positioning helper advances seven frames per
coarse movement before returning; its roughly 281 ms result therefore cannot
measure early repaint completion. Historical actions remain available as a
separate cohort. Complete feedback includes the changed headings and both
popup footprints. Only the current/previous cursor footprint is masked;
keyboard checks compare all title pixels without a cursor mask.

On the unchanged LR2 archive, warm keyboard popup pixels settle near 60 ms,
but complete feedback takes **120 ms**. The three physical samples reach
complete pixels **140–161 ms after submission**, with crossing-to-visible
intervals **108–128, 106–126 and 108–128 ms**. Crossing-to-routing is 1.8–1.9 ms.
These intervals retain PAL-frame sampling uncertainty. They are a corrected
baseline, not a production speedup or a p95 estimate.

Six new host tests pass; the host suite passes 497 tests with four historical
skips. The initial capture completed all timed actions, then failed an obsolete
Counter observer assertion expecting the previous 16-row title geometry.
The corrected observer uses the current geometry constants. The affected
complete-feedback and Counter cases pass on the same archive, including
guard checks, normal EXIT and OF816 autoboot. Counter advances and visibly
repaints during 30 application and 30 native menu highlights.

Artifacts: `build/menu-title-response/baseline` and
`build/menu-title-response/baseline-complete`. The first pointer-completion
attempt used the positioning helper and is excluded from the compact record.
Reserved bank-zero delta: **0 fixed, 0 per public Task, 0 idle bytes**, including
guards, alignment and unused capacity. MT1 changes only host observers/tests.

## MT2 Skip empty caption phases

`DESKMENUPAINT.Paint` skips captions outside its clip and finishes the bottom
rule in the same call as an ordinary application-title repaint. The existing
object budget, index/phase continuation, Layers retirement and input boundaries
between actual work units remain in place. The change adds no mutable storage.

The optimized AES-menu fixture passes **321 AES checks**, all seven existing
menu pixel phases and eight injected input cases. Seven new title cases check
full/partial clips, both separated headings, full-bar and Windows-caption
painting, failure with retained damage and successful retry, and a three-title
tree that forces the real four-object renderer continuation. Small title clips
take **one painter call**, full bars take three, and the three-title case takes
four. The independent oracle compares every bar pixel after each case.

The 497-test host suite passes with four historical skips. Guards, ownership
cleanup and normal OS return pass in `build/menu-title-response/mt2-menus`.
No raw or qualification matrix was run. Reserved bank-zero delta is **0 fixed,
0 per public Task, 0 idle bytes**, including guards, alignment and unused
capacity. DP, stack, Scene, VRAM and upper-memory reservations are unchanged;
production code and local-stack costs are recorded below with the final demo.

## MT3 Matched results and demo

The clean `bbc3e763` package uses the same compiler revision and binary, ROM,
emulator and PAL/65816x8/VBXE/63-bank configuration as LR2. The observer retains
the original actions and adds complete keyboard/pointer feedback measurements.
The preserved baseline supplies 30 historical/control actions; its corrected
six-action completion cohort was rerun separately. The final package passes
all 36 actions with identical cache-transfer counters and zero Files paints or
timed disk events.

Median milliseconds, three samples per cohort:

| Action and endpoint | Elapsed LR2 → MT3 | Presenter CPU LR2 → MT3 |
| --- | ---: | ---: |
| Warm open, historical full area | 140.454 → 140.203 | 90.402 → 84.098 |
| Highlight | 60.122 → 60.122 | 25.569 → 25.598 |
| Warm File → View, historical full area | 120.498 → 100.288 | 71.334 → 65.023 |
| Dismiss | 120.497 → 100.288 | 71.423 → 64.207 |
| Keyboard, complete popup and headings | 120.245 → 100.288 | 73.033 → 66.601 |
| Single pointer burst, complete popup and headings | 160.411 → 140.203 | 103.846 → 95.601 |

For the pointer cohort, the medians of the crossing-to-visible interval bounds
move from **108–128 ms to 88–108 ms**. Two forward transitions improve by a
frame; the reverse transition is essentially unchanged. Crossing-to-routing
remains about 1.8 ms. The old travel-helper cohort stays at 281 ms and the
three-heading keyboard sequence near 241 ms; their cache misses and measurement
boundaries remain separate from warm complete feedback. Native-menu dismissal
also improves 120 → 100 ms, while native opening remains near 120 ms.

The representative warm switch now has **one `PaintStrip` call instead of
three**, four `Pump` calls instead of six, one explicit input boundary instead
of three and 12 pointer-presentation attempts instead of 14. Pump CPU falls
18.139 → 14.811 ms; the single application-tree render stays near 8.07 ms.
These nested costs are not additive. Complete keyboard title retirement moves
from a median 86.343 → 79.030 ms after submission. Removing empty phases saves
about 6.4 ms of complete-feedback presenter CPU and crosses a visible PAL-frame
boundary; it does not eliminate the actual text/object rendering work.

Minimum/median/maximum and individual frame brackets are retained in the JSON.
No p95 claim follows from three samples. Pointer pixel checks mask only the
cursor footprint; the companion keyboard cohort and emitted oracle check
the unobscured title pixels. Timing includes scanout and frame sampling.

The final package passes Counter progress during 30 application and 30 native
highlights, guards, normal EXIT, zero-live-Task cleanup and five-second OF816
autoboot (249 PAL frames). All 22 archive checksums verify. Validation is
development tier; no raw, broad filesystem or release/hardware matrix ran.

Native code grows **1,095,330 → 1,095,444 bytes** (+114), entirely in the changed
painter. Native data stays 13,544 bytes; its fixed frame stays 44 bytes and
local stack peak 64. The memory reservation manifest is identical to LR2:
**0 fixed bank-zero bytes, 0 per public Task, 0 idle**, including guards,
alignment and unused capacity. Scene, DP, stack, VRAM and upper-memory
reservations are unchanged. Observed presenter use is 833/2,560 bytes with
1,471 above its floor remaining; kernel use is 295/1,536 and idle 129/512.
These are workload observations, not whole-program bounds.

Artifacts:

- `build/menu-title-response/demo/exec816-demo.zip`
- `build/menu-title-response/demo/launch-altirra.command`
- `build/menu-title-response/menus` (development capture outside the ZIP)

The archive contains OF816 boot, matching disks, pinned ROM, guide, notices and
checksums. SHA-256:
`115ff551b9e663299e9a9760d70301f587f9795d3614dd163e839930df01909b`.

Launch from the repository:

```sh
./build/menu-title-response/demo/launch-altirra.command
```
