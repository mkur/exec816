# Direct scrollbar paint comparison

[History index](README.md) · [Previous scrollbar audit](gem-scrollbar-raster-audit.md) · [Captured evidence](../development/gem-direct-scrollbar.json)

The pinned MagiC slider setter updates the selected axis and calls `wind_draw`
with `O_VSCROLL` or `O_HSCROLL`. `objc_wdraw` intersects the operation with
the visible frame rectangles and draws the selected tree into the clipped
screen. Exec already uses the same selected subtree. Its renderer redirects
the drawing to scratch, then publishes the finished region to the screen.
[Pinned MagiC source map](../architecture/magic.md)

The comparison keeps the existing GEM4XE object traversal, clip, fills and
stipple. The direct variant draws that callback into the clipped screen under
one display grant. It prepares intersecting overlays before drawing and uses
the ordinary fence and overlay restoration at the end. Both scrollbar axes
use this path in the comparison image. The fixture generates two edited C
source copies under `build/` for this experiment. The production build still
selects scratch.

The baseline uses the frozen mouse-show fixture at `301bed51`. Only the two
comparison sources are recompiled for the viewer. The other C objects and
MGVIEW APP are reused, and the native image is rebuilt against the comparison
provider. Both captures use the same document, viewport, cursor position,
compiler, PAL emulator and ROM. A two-window fixture provides matched screen
captures for both axes, including a partially covered horizontal scrollbar.

## Results

| Measured work | Scratch down / up | Direct down / up |
| --- | ---: | ---: |
| Scrollbar paint CPU | 14.18 / 14.36 ms | **12.37 / 12.38 ms** |
| Scrollbar paint elapsed | 18.02 / 18.17 ms | **15.85 / 15.85 ms** |
| Scrollbar command lists | 19 + 12 + 5 records | **19 + 12 records** |
| Scrollbar fence calls | 8 | **5** |
| Scrollbar display admissions | 1 | 1 |
| Key to copy entry | 58.09 / 60.56 ms | 57.52 / 54.27 ms |
| Key to exposed-row draw return | 100.82 / 101.72 ms | 100.27 / 98.96 ms |
| Key to first complete viewport observation | 120.28 / 120.62 ms | 120.24 / 120.56 ms |

Both paths visit objects 9 and 10 exactly once. The missing five records are
the scratch-to-screen publication, including the packed edge masks. The 29
solid and two stipple records for the objects and paper still execute. The
direct variant saves 1.81 and 1.98 ms of scrollbar CPU and 2.16 and 2.32 ms
elapsed. Across the whole scroll, submissions fall from eight to seven and
fence calls from 26 to 23. Both variants use six display admissions.

Draw return comes 0.55 and 2.76 ms earlier in these traces. Scheduling and
interrupt time vary between samples, and the observer polls at PAL frame
boundaries. The two pairs show a local saving with the same observed
viewport completion frame. They provide no normalized MagiC timing or
physical hardware latency measurement.

Both viewer builds complete the down/up pixel oracles, one copy and one exposed
row per action, three clean Process lifetimes and stack/domain checks. Their
full settled scanout hashes match. The track starts at odd X=617, so retaining
the neighboring packed nibble contributes to that comparison. These observations
check completed images. Direct rendering publishes individual drawing commands
during a frame and may show transient updates that the settled check cannot see.

The two-window probe matches full scanout bytes before and after each of six
setters, with the caller still holding UPDATE. The uncovered horizontal
and vertical samples change pixels. Two updates to the partially covered
horizontal scrollbar run the selected paint paths and leave the scanout
unchanged. This checks that the direct path preserves the covering window.
The older full frame fixture has stale observer fields. When driven through
its later assertions, both variants report four C assertion failures, first
at line 53, and terminate with `$FF93`. The focused probe ends at its last
paint checkpoint. MGVIEW runs through clean termination in both variants.

The native program reservation maps match. The comparison adds **0 reserved
bank-zero bytes** fixed or per Task, including guards, alignment and spare
capacity. C direct-page workspace stays at 23 bytes. Host checks pass 740 tests
with four skipped. The experiment uses focused development checks and no demo
or release build.

## Reproduce

From the repository root, with that pinned fixture available:

```sh
python3 tools/compare_scrollbar_paint.py --suite viewer --output build/gem-direct-scrollbar/viewer
python3 tools/measure_mgview.py --cache build/gem-mouse-show/viewer --output build/gem-direct-scrollbar/scratch-scroll --slider-detail --expect-copy-units 1
python3 tools/measure_mgview.py --cache build/gem-direct-scrollbar/viewer --output build/gem-direct-scrollbar/direct-scroll --slider-detail --expect-copy-units 1
python3 tools/compare_scrollbar_paint.py --suite scratch-frame --output build/gem-direct-scrollbar/scratch-frame
python3 tools/compare_scrollbar_paint.py --suite frame --output build/gem-direct-scrollbar/frame --reference-frame build/gem-direct-scrollbar/scratch-frame
```
