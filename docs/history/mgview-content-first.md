# MGVIEW paints the viewport before the scrollbar

[History index](README.md) · [Development evidence](../development/mgview-content-first.json) ·
[Prior scrollbar comparison](gem-direct-scrollbar.md)

The Exec port now copies the visible viewport and draws the exposed strip
before updating the scrollbar on a short scroll. `set_shift` holds the same
UPDATE across the operation. It hides the cursor for viewport drawing,
restores it, paints the thumb synchronously through the existing slider
setters, then releases UPDATE. Jumps beyond one page still update the thumb
before handing off to the full redraw path.

| Keypress to observed pixels | Slider first | Content first |
| --- | ---: | ---: |
| Down, viewport | 120.28 ms | **80.15 ms** |
| Up, viewport | 120.62 ms | **100.21 ms** |
| Down, viewport and thumb | 120.28 ms | 120.44 ms |
| Up, viewport and thumb | 120.62 ms | 120.26 ms |

The text reaches scanout two PAL frames earlier down and one frame earlier
up. The completed text and thumb still appear together on the sixth observed
frame in both runs. The thumb crop is sampled in the same raw scanout as the
viewport and compared with the crop after UPDATE has retired. The per-action
settled thumb hashes and full final images match across the two builds.
This comparison uses one down/up pair per build on the pinned emulator.

Exposed-row drawing returns **67.38/65.71 ms** after the keypress, down from
**100.82/101.72 ms**. Whole `set_shift` elapsed time is **92.91/92.77 ms**,
compared with **96.62/91.74 ms**. Each scroll still makes one viewport copy,
one exposed-row draw and six display admissions. The glyph oracle checks all
123,200 viewport pixels. The separate loaded-app fixture checks vertical and
horizontal key scrolling, the horizontal left-arrow gadget, and three clean
Process lifetimes with memory ownership and guards intact. The development host
run reports 741 tests with four skipped.

Only MGVIEW was rebuilt. The candidate uses the byte-identical frozen Exec
native image and resident C provider, with the same document and machine.
Added reserved bank-zero bytes are **0 fixed, root, kernel, idle and per
public Task**, including guards, alignment and unused capacity. The
standalone GEM4XE reference rebuild uses the earlier slider-first MGVIEW
patch to reproduce its historical workload.

To replay the prepared fixtures:

```sh
python3 tools/measure_mgview.py --cache build/gem-mouse-show/viewer --output build/mgview-content-first/baseline --slider-detail --expect-copy-units 1
python3 tools/measure_mgview.py --cache build/mgview-content-first/viewer --output build/mgview-content-first/scroll --slider-detail --expect-copy-units 1
python3 tools/test_mgview.py --reuse --scroll --output build/mgview-content-first/functional
```
