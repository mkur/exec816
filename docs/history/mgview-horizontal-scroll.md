# MGVIEW horizontal strip repaint

[History index](README.md) · [Implementation plan](../plans/gem4xe/mgview-horizontal-scroll-plan.md)

MGVIEW uses the damage rectangle to select the document columns it sends to
VDI. The caller retains UPDATE through the existing MagiC copy and exposed-strip
repaint. The draw callback clears the rectangle once, expands tabs from document
column zero, and emits the intersecting glyphs, including cells cut by either
edge. A second slice bounds line lookup with the existing line index or file
end and trims CR, LF, or CRLF. Both changes are in the port patch.
[MGVIEW port patch](../../ports/magic/mgview/native.patch)

## Matched arrow clicks

The 616×200 viewport exposes one 8×200 strip per click. Three untraced right/left
pairs per APP used the same document, arrow coordinates, button pulse, 2 kHz ST
mouse capture with mild acceleration, and pinned PAL emulator with VBXE. Each
direction produced the same rounded bracket in all three pairs. The brackets
run from the last different scanout to the first scanout matching the expected
viewport or settled track crop. A PAL frame is 20.06 ms. The settled viewport
pixels, thumb crop, and resident slider position matched across APPs.

| Action | Viewport before | Viewport after | Thumb before | Thumb after |
| --- | ---: | ---: | ---: | ---: |
| Right | 321–341 ms | **160–181 ms** | 361–381 ms | **201–221 ms** |
| Left | 301–321 ms | **160–181 ms** | 341–361 ms | **181–201 ms** |
| Down control | 100–120 ms | 100–120 ms | 140–160 ms | 140–160 ms |
| Up control | 120–140 ms | 120–140 ms | 140–160 ms | 140–160 ms |

Each APP also ran one traced right/left pair. The inclusive figures below give
viewer Task CPU charge and elapsed time in milliseconds. Nested stages overlap.
CPU charge excludes native interrupts and time charged to other Tasks. The
right-side exposure still traverses the tab-aware prefix before the visible
cell, which accounts for the remaining directional difference in preparation.

| Phase | Right before CPU / elapsed | Right after CPU / elapsed | Left before CPU / elapsed | Left after CPU / elapsed |
| --- | ---: | ---: | ---: | ---: |
| Whole `set_shift` | 268.57 / 296.73 | **124.73 / 138.48** | 255.44 / 282.33 | **118.27 / 131.42** |
| `vro_cpyfm` | 17.94 / 20.74 | 18.27 / 21.19 | 17.73 / 20.60 | 17.89 / 20.76 |
| Exposed strip | 213.05 / 234.64 | **69.05 / 76.12** | 197.85 / 217.91 | **59.21 / 65.31** |
| Line lookup | 12.81 / 14.15 | 1.41 / 1.58 | 12.81 / 14.15 | 1.41 / 1.63 |
| Glyph preparation | 89.39 / 97.83 | 20.02 / 21.98 | 89.60 / 98.72 | 0.85 / 0.90 |
| `v_gtext` total | 87.97 / 97.43 | 42.54 / 46.82 | 78.98 / 86.81 | 51.90 / 57.18 |
| VDI glyph conversion | 38.35 / 42.29 | 0.80 / 0.84 | 27.26 / 30.04 | 0.99 / 1.20 |
| VDI painting and clip | 38.86 / 43.12 | 27.02 / 29.82 | 35.48 / 38.97 | 32.66 / 35.86 |
| Background fills | 17.60 / 19.40 | 2.64 / 2.90 | 11.18 / 12.38 | 2.64 / 2.90 |
| Thumb update | 22.65 / 25.07 | 22.46 / 24.72 | 24.93 / 27.45 | 25.36 / 27.88 |
| END_UPDATE | 2.05 / 2.23 | 2.05 / 2.23 | 2.05 / 2.23 | 2.88 / 3.30 |

The first slice took exposed-strip CPU to 80.36 ms right and 69.64 ms left.
Line lookup still accounted for about 13 ms per direction. With indexed lookup,
it costs 1.41 ms in either direction. The 19 right and 23 left single-glyph text
calls are the largest remaining strip cost and charge 43 and 52 ms inclusive.
The shared renderer still paints each row separately.

| Caller count | Right before → after | Left before → after |
| --- | ---: | ---: |
| Glyphs prepared and submitted | 2,394 → 19 | 2,394 → 23 |
| Strip text calls | 25 → 19 | 25 → 23 |
| Strip fills | 7 → 1 | 7 → 1 |
| Strip display grants | 26 → 20 | 26 → 24 |
| Total display grants | 30 → 24 | 30 → 28 |
| Strip blitter lists | 26 → 20 | 26 → 24 |
| Total blitter lists | 35 → 29 | 37 → 35 |
| Hardware rectangle copies | 1 → 1 | 1 → 1 |

## Development checks

The same optimized APP passed two moves of a covering window and the final
exposure on close. The pixel oracle checked both partial-cell edges and the
adjacent front window. The fixture includes short and empty lines, tabs at
the covered edges, literal tab mode, embedded NUL, CR/LF/CRLF, and an
unterminated final line. Three page clicks reached columns 77, 154, and 195
of the 272-column capped document, with full viewport and thumb checks.
Exit, memory ownership, and stack guards passed. The APP still requests the
existing 2,560-byte Task stack class. Added reserved bank-zero bytes are
**0 fixed, root, kernel, idle, and per public Task**, including guards,
alignment, and unused capacity. The host checks ran 43 tests.

Only `MGVIEW.APP` was rebuilt. The comparison used the existing OF816 XEX
and resident image on writable development volumes.

| Artifact | SHA-256 |
| --- | --- |
| Baseline APP | `b1b5c03915b2d6e0626d7f68ac7aaca56504da3b59298d6d0a76b39d101598f9` |
| Glyph-span APP | `2cafcd300f6add074abe2f1942bff0dec92f82d256fc2dde0e908dcf40c957c7` |
| Final APP | `c16f601bfc32e5b4f4b18ef33896966b9db715170837fc2c83b99b1282fe5de3` |
| Resident provider ELF | `8467b898c32737108742970f0f4a141fd0108f8db6e7adab240c4eb02b0af19c` |
| Native XEX | `eac9fbc0686c722387c4bf58b36ec0451ba0cfc2779fd6ec6fa4231e4392b188` |
| Timing document | `3c338011bb36f3582fb445e4978e721252510f32473cae062df59b1ac22b2a16` |

To replay with the frozen 2 kHz MGVIEW-only bundle and a fresh optimized APP
build, run the [observer](../../tools/measure_mgview_horizontal.py) on each
artifact.

```sh
demo=build/mouse-refactor/demo
out=build/mgview-horizontal
python3 tools/build_mgview.py --output "$out/final-app"
python3 tools/measure_mgview_horizontal.py "$demo" "$out/before-timing"
python3 tools/measure_mgview_horizontal.py "$demo" "$out/before-list-trace" --trace
python3 tools/measure_mgview_horizontal.py "$demo" "$out/after-timing" --app "$out/final-app"
python3 tools/measure_mgview_horizontal.py "$demo" "$out/after-list-trace" --app "$out/final-app" --trace
python3 tools/measure_mgview_horizontal.py "$demo" "$out/after-fixture" --app "$out/final-app" --fixture
```

## Sustained right-key input

A saved Altirra session showed Exec's normal exit with status zero and the
retired viewer window at document row 41 and column 17. The demo startup
script executes `EXIT` when MGVIEW returns, which restores the Atari screen.
The saved state ends after cleanup. A separate replay of sustained right-key
input traced `ExecAESInputRecover`, a zero return from `evnt_multi_moblk`,
and MGVIEW immediately taking its exit branch.

MGVIEW now re-enters its event wait after `AES_INPUT_LOST`. AES has already
acknowledged the lost input at that point, so the next wait accepts new
input. The focused regression starts at the bottom of the sample, sends
100 right-key pulses, observes the keyboard epoch advance from 1 to 4, and
checks that the viewer accepts another key and renders the exact viewport.
The refresh reuses the native and OF816 images. Added reserved bank-zero
bytes are **0 fixed and 0 per Task**, including guards, alignment, and
unused capacity.

```sh
python3 tools/measure_mgview_horizontal.py build/mgview-right-repeat/demo build/mgview-right-repeat/keyboard-burst-replay --keyboard-burst
```
