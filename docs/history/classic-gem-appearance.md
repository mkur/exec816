# Classic GEM desktop appearance

[History](README.md) · [Design](../plans/gem4xe/classic-gem-appearance-design.md) ·
[Implementation plan](../plans/gem4xe/classic-gem-appearance-implementation-plan.md)

## GA1 — Shared geometry and classic frames

Status: implemented; optimized development checks pass.

The frame uses a one-pixel black outline, white margins, centered title text,
the flat GEM active-title pattern and the existing font's closer glyph on the
left. Inactive titles are plain. Shell and application work rectangles retain
their previous dimensions. Metrics come from `abi/desktop.json`; native paint,
dragging, AES mouse gesture classification and caller-local `wind_calc` agree.

The presenter composes disjoint frame fragments in the existing widget strip.
Each callback draws at most sixteen title glyphs and publishes only after the
fragment is complete. Window-relative pattern phase survives clipped repairs.
Application-owned work pixels are never part of the fragment. Work-area-only
damage takes the direct client path without constructing frame fragments.

Private console drawing packet version 10 adds FRAME without growing the
78-byte layout; its existing fillX field carries the glyph continuation for
that operation. The packet and title borrow end at each call. The added C
scratch is one 16-word glyph array and a temporary full-address packet pointer;
the native continuation reuses the existing painter fields. There is no new
VRAM allocation or bank-zero reservation.

The physical window fixture now tops an inactive AES window through its closer,
cancels focused closer presses by release outside and Escape, and drags through
the old right-hand closer position. The older presentation/drag expectations
also include the desktop menu bar introduced before this milestone.

Reserved bank-zero delta: **0 fixed, 0 per public Task, 0 private idle**,
including guards, alignment and unused capacity. The early integrated build uses 4,928/5,120 native global-arena bytes and
63/64 manifest extents. The C callback adds 36 upper scratch bytes; VRAM is
unchanged. Presentation passes 117 assertions, background/repair passes 57
(including long, empty and minimum-width titles), and AES windows pass 176 C
plus four native checks. Host checks pass 417 tests with four existing skips.
Native physical drags, both screen clamps and all cancellation/retirement cases
pass exact scene comparison. The three-release smoke sample spans 279 ms median
to 400 ms maximum; the older 250 ms repair target is not claimed. GA4 compares
a matched input sequence and load.
See [GA1 evidence](../development/classic-gem-appearance-ga1.json).

The early OF816 package builds; the exact extracted distribution walkthrough
is reserved for GA4. This is development evidence, not hosted qualification.

## GA2 — Menus and controls

Native fallback and Windows popups now use inside black outlines, inverse
selection and the existing GEM disabled stipple. Border pixels cannot select an
item. A row is composed in the existing widget strip before publication; long
labels resume after sixteen glyphs. The private packet is version 11, still
78 bytes. It adds MENU_ROW and borrows its label only for the call.

Files owns a one-pixel G_BOX border and inset entries in its compiled menu tree.
The general application-menu renderer continues to honor caller geometry and
OBJECT specifications. Existing Control Panel, Counter and calculator controls
already use the extracted GEM rendering, so their semantics and palettes stay
application-owned.

The native painter adds one two-byte upper continuation; C reuses the frame
callback scratch. Additional VRAM and reserved bank-zero delta are **0**,
including **0 fixed, 0 per public Task and 0 private idle** with guards/padding.
Optimized menu, two-Files-instance and panel-control fixtures pass, including
exact native-popup pixels, all four border hit edges, menu replacement/withdrawal,
keyboard navigation, radio/default activation and press cancellation. Host checks
pass 417 tests with four existing skips. See [GA2 evidence](../development/classic-gem-appearance-ga2.json).

## GA3 — Patterned desktop

Desktop exposure repair now composes grey fill and the existing white GEM
stipple in the widget strip, then publishes the complete fragment. Both nibble
edges and odd scanlines preserve absolute screen phase. Active-title phase
remains relative to its window. Drawing uses strided blitter operations, not
per-dot calls, and retains the presenter's sixteen-row/input-service boundaries.

The private packet is version 12, still 78 bytes, adding DESKTOP. There is no
new mutable state, table, framebuffer or reservation: upper scratch, VRAM and
reserved bank-zero delta are **0**, including **0 fixed, 0 per public Task and
0 private idle** with guards, alignment and spare capacity.

The independent raster computes each background pixel from absolute coordinates.
The sparse-repair fixture also checks half-open closer/title edges explicitly.
Scrolling drags exposed an existing ordering hazard: a redraw move committed
geometry after the console's origin had been synchronized for that turn.
Output could then stamp an old-position caret into the new frame margin.
The move helper now rebases the console immediately on a successful redraw
move, using its existing copied-move rebase helper and discarding any old
scroll gather. Normal worker ordering and batching remain unchanged.

The fill observer now stops at Display.OwnerEnter, replacing its obsolete
Display.Valid observation point. Presentation passes 117 checks, including
zero producer overtakes and observed two-row batches. Background/repair passes
66 checks across fifteen independent pixel scenes; the maximum observed paint
unit is 15.44 ms CPU and long-text input boundaries pass. Three physical moves
each under idle, scrolling and disk load pass, as do both screen clamps, Escape,
event loss, cooperative close, hiding and retirement while held. These small
move samples do not close the older 250 ms repair target. Host checks pass
417 tests with four existing skips. See [GA3 evidence](../development/classic-gem-appearance-ga3.json).

## GA4 — Integrated package and appearance cost

Status: implemented; focused optimized development checks pass. This is not
hosted release qualification.

Both walkthroughs boot the exact extracted OF816 ZIP: first Shell, Files,
Counter and Control Panel, then the calculator alongside the other applications.
They cover pointer/keyboard menus, covered-window access, focus restoration,
left closers, title dragging, settings/radio/default controls, shell/disk output,
Files launch/Stop/reload, two private calculator resources, and session shutdown.
Heap and ownership return, stack guards and register/OS restoration pass. The
monitor delay remains 249 PAL frames; the default shell/prime profile is
unchanged. Walkthroughs now use the Windows menu to reach Files: their former
left-title focus click became the closer in GA1.

The first matched comparison exposed extra focus repaint cost. Plain side and
bottom fragments now skip title scanning and glyph preparation. Both narrow
side fragments share a bounded paint step, each still composed and published
through the existing scratch strip. The focused raster fixture passes 66 checks
and observes a 15.37 ms maximum paint unit, within its 20 ms CPU bound.
No state, reservation or public interface is added by this refinement.

Thirty Ctrl-Tab changes and thirty physical panel presses use the same input
sequence and four-application load as the exact AM6 package. Focus measures
submission to matching title scanout; button measures submission to matching
button scanout. Polling is PAL-frame granular. These are limited appearance
observations, not the HY4/PI4 workload matrix or isolated AES-call costs.

| Observation | AM6 package | Classic GEM package |
| --- | ---: | ---: |
| Focus median | 441.1 ms | 441.3 ms |
| Focus p95 | 1424.0 ms | 1343.9 ms |
| Button median | 100.3 ms | 100.3 ms |
| Button p95 | 160.4 ms | 160.4 ms |
| Largest paint unit, CPU | 8.13 ms | 13.52 ms |
| Largest paint unit, elapsed | 21.15 ms | 23.58 ms |

Decorated title composition costs more per unit than the old solid frame. The
plain-edge path and paired side fragments recover that extra focus delay while
retaining input service between bounded paint steps. CPU charges exclude native
interrupt bodies and time assigned to another Task; elapsed time includes both.
The pre-refinement focus observations were 501.2 ms
median and 1,544.2 ms p95. The evidence retains that run as well as the final
comparison. HY4/PI4 and the older 250 ms native move-repair target remain open.

Frame-sampled focus captures show complete title fragments. Source inspection
also confirms that desktop fill and stipple stay offscreen until publication.
This does not qualify sub-frame tearing or establish a flicker-free desktop.
Independent settled scenes pass for both menu paths, repaired overlaps and
application controls. Captures are available in native 640×240 pixels and a
640×480 display-aspect view with duplicated scanlines:

| Scene | Native pixels | Display aspect |
| --- | --- | --- |
| Desktop | [PNG](../../build/classic-gem/screenshots/desktop-native.png) | [PNG](../../build/classic-gem/screenshots/desktop-display.png) |
| Control Panel | [PNG](../../build/classic-gem/screenshots/control-panel-native.png) | [PNG](../../build/classic-gem/screenshots/control-panel-display.png) |
| Windows menu | [PNG](../../build/classic-gem/screenshots/windows-menu-native.png) | [PNG](../../build/classic-gem/screenshots/windows-menu-display.png) |
| Files menu | [PNG](../../build/classic-gem/screenshots/files-menu-native.png) | [PNG](../../build/classic-gem/screenshots/files-menu-display.png) |
| Two calculators | [PNG](../../build/classic-gem/screenshots/two-calculators-native.png) | [PNG](../../build/classic-gem/screenshots/two-calculators-display.png) |

Reserved bank-zero delta is **0 fixed, 0 per public Task and 0 private idle**,
including guards, alignment and unused capacity. The native global arena uses
4,931/5,120 bytes, one byte more than AM6 after the two-byte menu continuation
and literal/layout changes. C declares 36 additional scratch bytes. Upper-bank
and VRAM reservations are unchanged; the manifest uses 63/64 extents. The smallest
observed public-Task stack margin is 38 bytes above its floor; the presenter
retains at least 1,530 bytes. Heap allocations are unchanged by the appearance work.
Cartridge compression remains separate; no uncompressed size gate was applied.

The host suite runs 417 tests with four existing skips. Generated definitions,
Python syntax, whitespace and documentation links pass. No raw system matrix is
repeated: the private packet remains 78 bytes, with unchanged native/C calling
conventions. See [GA4 evidence](../development/classic-gem-appearance-ga4.json)
for exact pins, hashes, stack observations and the matched samples.

The [tested OF816 demo ZIP](../../build/classic-gem/final/exec816-demo.zip)
contains boot files, ROM, matching disks, the short guide, notices and eighteen
verified checksums. Its SHA-256 is
`c64e2ab42d1f10ca89fbda360a2477dfa9996277b85664f9cea312f856159b27`.
Build intermediates, traces and screenshots stay outside the ZIP.

Reproduce the final checks with:

```sh
python3 tools/build_demo.py --gem-desktop --output build/classic-gem/final
python3 tools/test_gem_desktop_boot.py --bundle build/classic-gem/final
python3 tools/test_calculator_desktop.py --bundle build/classic-gem/final
python3 tools/measure_classic_gem.py --bundle build/classic-gem/final \
  --output build/classic-gem/comparison/final
```

Run these sequentially when sharing a bundle directory; the recorded parallel
runs used independent development copies containing identical ZIP bytes.
