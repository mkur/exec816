# Clipped menu text

[Implementation plan](../plans/gem4xe/clipped-menu-text-plan.md) ·
[MT3 baseline](menu-title-response.md) ·
[Measurements](../development/clipped-menu-text.json)

## CG1 Private encoder

The existing glyph-run encoder accepts one through eight atlas rows. Its donor
wrapper offsets the atlas once; record construction emits one stencil record
per nonblank glyph portion at either X parity. Existing full-height callers
still request row zero and height eight in this slice.

Full-height capacity tables conservatively reserve each prefix. One lookup in
the existing work table charges the aggregate written width and actual row
count. No table, cache or per-glyph validation was added. The emitted encoder
and record writer call no multiplication, division or remainder helpers.

Development checks pass: four extraction tests, four widget host tests, two
table-generator tests and all 37 optimized emitted widget pixel stages. The
new stage checks all 72 valid first-row/height/parity combinations against the
independent font oracle. The builder also checks actual list work, mixed-list
record/work limits, blank-only suffixes and failed submission/reopening.
Existing full-height, strip continuation, pointer, guard and cleanup cases pass.

The fixture now uses the pinned release compiler executable, matching the AES
runner. Its initial debug-executable compilation was stopped for excessive
build time before execution; the release-executable run completed successfully.
This changes neither compiler revision nor target optimization mode.

Artifacts: `build/clipped-menu-text/cg1-pixels` and the adjacent host logs.
Reserved bank-zero delta: **0 fixed, 0 per public Task, 0 idle bytes**, including
guards, alignment and unused capacity. VRAM, upper-memory, Scene, DP and stack
reservations are unchanged. Final production code/stack costs and timings will
be recorded with CG3. No raw or release qualification matrix ran.

## CG2 Widget and menu routing

`GemWidgetText` intersects the vertical cell once and routes horizontally
complete nonzero-ink cells through the row-span encoder. Partial horizontal
cells and hardware-zero ink retain the general path. Scratch publication,
menu geometry, painter budgets and scheduling remain unchanged.

All 38 optimized widget pixel stages pass. The added stage exercises the same
72 row/parity combinations through `GemWidgetText`, plus 16 cases covering
combined edge cuts, a single cut cell, zero ink, blanks, empty clips, screen
edges and one visible row. Emitted list assertions require one stencil record
per nonblank complete cell. Mixed-list and failed-submission checks also run
through the new routing. The four widget host tests pass.

The optimized AES-menu fixture passes all seven pixel phases, the long
checked/disabled odd-X menu, replacement input, title continuation/failure,
native menu controls and cleanup. Artifacts: `build/clipped-menu-text/cg2-pixels`
and `build/clipped-menu-text/cg2-menus`. Both use the same pinned release
compiler binary as the MT3 demo; no compiler override was used.

Reserved bank-zero delta: **0 fixed, 0 per public Task, 0 idle bytes**, including
guards, alignment and unused capacity. Other reservations remain unchanged.
The widget fixture observes 658/2,560 presenter stack bytes, with 1,646 above
the floor remaining; this is a workload observation, not a stack bound.

## CG3 Matched dropdown results

The clean `f68c25c4` demo uses the same compiler revision and executable, ROM
bytes, emulator binary and PAL/65816x8/VBXE/63-bank configuration as MT3.
The original 36-action passive observer is unchanged. All cache-transfer
counters match; no timed action repaints Files or performs disk I/O. External
firmware identifiers differ because Altirra hashes the extracted ROM path;
the actual ROM SHA-256 is identical.

For the representative uncached Desk popup:

| Work | MT3 | CG3 |
| --- | ---: | ---: |
| Popup paint CPU | 114.408 ms | 64.229 ms |
| Text CPU, inclusive | 68.681 ms | 21.937 ms |
| Eight split-label calls, inclusive | 55.938 ms | 10.288 ms |
| Popup records | 283 | 159 |
| Submitted lists | 11 | 11 |
| Separate heading paint CPU | 7.965 ms | 8.023 ms |
| Whole-action presenter CPU | 191.307 ms | 141.606 ms |

The four split labels emit exactly the projected **186 → 62 records**:
New Window 54 → 18, Text 24 → 8, Counter 42 → 14 and Quit Desktop 66 → 22.
Existing passive C return markers count `glyph_record` calls in each text
span; the old `blit_mask` calls identify fallback records. No new observer
markers or baseline recapture were needed. Both parity/row combinations are
also checked directly by the emitted pixel fixture.

Popup drawing CPU falls **44%**, with the same six paint calls and eleven
lists. Conservative prefix admission and existing paint/flush boundaries
remain; the gain comes from fewer records and less per-character fallback
work. Neither version uploads pixel staging data inside these paint calls.

The CPU partition below subtracts nested calls before adding categories;
the inclusive rows in the preceding table must not be added together.

| Exclusive popup work | MT3 ms | CG3 ms |
| --- | ---: | ---: |
| Text outside masked construction and submission | 34.351 | 16.302 |
| Generic masked-command construction | 27.447 | 0.825 |
| Object traversal, layout and other batch work | 27.121 | 27.124 |
| Submission and fences | 17.245 | 11.716 |
| Fills | 6.207 | 6.238 |
| Outer Action/C call overhead | 2.036 | 2.024 |

Sampled response for the original keyboard heading sequence:

| Uncached menu | Elapsed MT3 → CG3 | Presenter CPU MT3 → CG3 |
| --- | ---: | ---: |
| View | 180.620 → 140.454 ms | 141.985 → 108.132 ms |
| Desk | 240.743 → 180.377 ms | 191.307 → 141.606 ms |
| File | 300.864 → 220.785 ms | 242.297 → 174.187 ms |

These are individual samples of three different menus, not three repetitions
of Desk. Their historical pixel endpoint compares `(128,32,640,208)` and
excludes headings and the top popup rows. It is not complete feedback or a
p95 estimate. The old pointer-positioning cohort remains near 281 ms because
its helper waits before sampling; it cannot resolve the earlier completion.

Warm controls remain effectively unchanged. Three-sample medians:

| Action and endpoint | Elapsed MT3 → CG3 | Presenter CPU MT3 → CG3 |
| --- | ---: | ---: |
| Open, historical sampled area | 140.203 → 140.454 ms | 84.098 → 84.118 ms |
| Highlight | 60.122 → 60.122 ms | 25.598 → 25.561 ms |
| File → View, historical sampled area | 100.288 → 100.288 ms | 65.023 → 65.074 ms |
| Dismiss | 100.288 → 100.288 ms | 64.207 → 64.324 ms |
| Keyboard, complete popup and headings | 100.288 → 100.288 ms | 66.601 → 66.378 ms |
| Pointer burst, complete popup and headings | 140.203 → 140.454 ms | 95.601 → 95.633 ms |

Complete feedback includes both popup footprints and changed headings.
Pointer checks mask only the pointer footprint; keyboard checks cover all
title pixels. Individual last-nonmatch/first-match frames and pointer
crossing-to-visible intervals remain in the measurements. Native-menu
controls also remain in their previous response ranges. The ordinary
full-height heading paint changes by only 0.058 ms CPU; no material warm-path
regression is observed.

The demo passes Counter progress during 30 application and 30 native menu
highlights, intact guards, normal EXIT, zero-live-Task cleanup and five-second
OF816 autoboot (249 PAL frames). All 22 archive checksums verify. These are
development checks, supplemented by the CG1/CG2 pixel and menu checks above;
no raw, broad filesystem or release/hardware qualification matrix ran.

C text grows **222,182 → 222,330 bytes** (+148); C data stays 20,773 bytes and
BSS 23 bytes. Native Action code stays 1,095,444 bytes and data 13,544 bytes.
The memory reservation manifest is byte-for-byte unchanged: **0 fixed
bank-zero bytes, 0 per public Task, 0 idle**, including guards, alignment and
unused capacity. Scene, DP, stack, VRAM and upper-memory reservations are
unchanged.

Fixed C entry allocation, including saved DP registers but excluding outgoing
arguments, return addresses and descendants, changes from 36 → 40 bytes in
`GemWidgetText`, 10 → 14 in its donor run wrapper and 42 → 48 in
`blit_glyph_run`; `glyph_record` stays at 10. Observed presenter stack use
changes 833 → 835 of 2,560 bytes, leaving 1,469 above the floor. Kernel use
falls 295 → 293 of 1,536 bytes; idle stays 129/512. These observations are not
whole-program bounds.

Artifacts:

- `build/clipped-menu-text/demo/exec816-demo.zip`
- `build/clipped-menu-text/demo/launch-altirra.command`
- `build/clipped-menu-text/menus` (development capture outside the ZIP)

The archive contains OF816 boot, matching disks, pinned ROM, guide, notices
and checksums. SHA-256:
`ecddfabd73c555be9e84b48e5cad3a3d898df77addc0f00160dd5877eab1369e`.

Launch from the repository:

```sh
./build/clipped-menu-text/demo/launch-altirra.command
```
