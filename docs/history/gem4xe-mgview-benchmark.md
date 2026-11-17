# MGVIEW on standalone GEM4XE

[History index](README.md) · [Evidence](../development/gem4xe-mgview-benchmark.json) ·
[Exec scroll comparison](gem-direct-scrollbar.md)

GEM4XE v0.15 at `2bf10f6788372dcfa94f6d9416e4b957eb4ce394` reaches the complete
viewport after **240.67 ms** on all six observed one-line scrolls. The frozen
Exec scratch-paint pair reaches it at **120.28/120.62 ms**. The largest measured
gap is the overlapping screen copy. The interval from `vro_cpyfm` entry to
exposed-row draw entry takes **146.03–148.42 ms** on GEM4XE and **18.90–20.78 ms**
on Exec.

| Elapsed interval | GEM4XE, six actions | Exec, down/up |
| --- | ---: | ---: |
| Slider helper entry to viewport copy entry | 26.77–28.99 ms | 38.76–38.86 ms |
| Viewport copy entry to exposed-row draw entry | 146.03–148.42 ms | 18.90–20.78 ms |
| Exposed-row draw entry to mouse-show call | 40.98–41.08 ms | 23.16–23.48 ms |
| Key offered to first complete viewport observation | 240.67 ms | 120.28–120.62 ms |

Every GEM4XE scroll calls the app and driver raster-copy entry once, then
draws one exposed row. The driver enters `copy_rows` once for each one-pixel
edge and calls `blit_move` once for the aligned interior between them. The
first edge pass alone takes **65.79–65.94 ms** before `blit_move` starts. Exec
keeps the packed edges in VBXE memory through the aligned copy and restoration.
These intervals include the software and device work in each observed bracket.
[GEM4XE copy source](https://github.com/slaapliedje/gem4xe/blob/2bf10f6788372dcfa94f6d9416e4b957eb4ce394/src/vdi/dev_vbxe.c#L1880-L1924) · [Exec copy implementation record](gem-copy-grant.md)

The fixture links the prepared MGVIEW sources with the pinned GEM4XE SDK and
Calypsi 5.18 at `-O2`, using its large data model and native G4DOS media. The
compatibility layer substitutes `Fseek` for the file-size query and finds the
top window for a key event. A startup-only fixture opens `VIEW.TXT` and crops
GEM4XE's 617-pixel rounded work rectangle to the same **616×200** painted
viewport as Exec. Both copies start at X=1, move **616×192** pixels, and have
the same 8×8 glyph cells and parked pointer at `(639,0)`. The viewer's scroll
operation order and both window managers and renderers are their respective
production paths. The 3,840-byte GEM4XE application near allocation includes
its 1,024-byte stack and the SDK's direct page. Exec reserved bank-zero change
is **0 fixed bytes and 0 bytes per Task**.

Both guests use the pinned PAL 800XL, 8× 65C816, VBXE FX 1.26, ROM and bridge
binary. GEM4XE uses the SIO patch only during untimed boot and setup. Glyph
coverage matches independently generated expected pixels with each system's
palette. GEM4XE's complete viewport was first observed at frame 12, after a
mismatch at frame 11. Exec's two matches are bounded by the previous frame
observations at 100.39/100.56 ms. Six GEM4XE scrolls run at the same keypress
phase, and the Exec report uses an earlier two-action capture. These development
results describe this odd-edge scroll workload on the pinned emulator.

Run from the repository root with the [Exec comparison fixture](gem-direct-scrollbar.md)
available. Add `--replay` to reuse the native GEM4XE executable and disk.

```sh
python3 tools/bench_gem4xe_mgview.py
```

The bootable benchmark image is `build/gem4xe-mgview/mgview.atr`. It opens
MGVIEW directly. Use Control+= and Control+- to scroll down and up. The
captures and build intermediates remain under `build/gem4xe-mgview/`.
