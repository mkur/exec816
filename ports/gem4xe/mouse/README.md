# GEM mouse selection

Use GEM4XE for rendering; use MagiC for multitasking ownership.

`inputs.json` pins the selected upstream source independently of the existing
VDI/raster and reference-media pins. `upstream/gemdata.py` is unchanged donor
source; its MFORM artwork was transcribed from EmuTOS `aes/mforms.c` (GPLv2),
as its module notice records. Preserve that provenance with generated artwork.
The alert artwork in this source is not selected by the mouse generator.

`tools/generate_gem_cursor.py` selects all eight immutable standard MFORMs
(592 upper readonly bytes).
`upstream/cursor-vbxe.c` preserves the pinned form-expansion selection, with
original and selection hashes in `inputs.json`. The adapted renderer packs
even/odd AND/OR strips dynamically in existing upper scratch, maps logical pens
and uses clipped saved geometry after hotspot subtraction. It retains the
256-byte save and 1,024-byte mask VRAM reservations.
The shared native AES policy owns application hide
contributions; the screen device owns its separate VDI hide counter. Input and
hardware ownership continue through Exec's existing drivers and display grants.

See the [implementation plan](../../../docs/plans/gem4xe/gem-mouse-plan.md) and
[MagiC source cross-check](../../../docs/history/gem-mouse-magic-review.md).
