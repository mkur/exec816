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
