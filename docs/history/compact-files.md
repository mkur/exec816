# Compact Files windows

[Current desktop contract](../reference/aes.md#small-gem-desktop) ·
[Desktop appearance](desktop-style.md) · [History index](README.md)

Files and desktop folder windows use the same compact layout. The large File
button is removed; its commands remain in the active application's global menu.
Up and Refresh are monochrome glyphs with 24×12 mouse targets. Parent also has
a menu command and Backspace; Refresh also has a menu command and Ctrl+L.

The title carries the path. A single bottom line shows comma-separated byte
totals and item counts, selection counts or operation feedback. The separate
INFO row and repeated path status are removed. New windows start at 360×184;
navigation preserves their bounds, and saved desktop settings retain the user's
window sizes. The existing 104×40 grid keeps space for twelve-character labels.

File icon artwork remains unchanged when selected; only its label reverses.
The existing monochrome artwork is stored in CICON records without selected
variants, using the current colour-icon renderer. Desktop selections use white
labels on black while unselected labels blend into the grey background. The
palette and window furniture are unchanged.

Keyboard navigation adds a dotted border around the lead file object. Selection
and focus remain separate, including Shift-arrow selection. The freed File
object slot holds a non-hittable decorative container with four stippled edges;
it uses existing OBJECT rendering. Mouse input removes keyboard focus. Ordinary
mouse selection retains direct object drawing; clearing an old focus border
repaints only its cell, not the folder.

The menu stays within its existing 32-object capacity. A checked Sort by name
command replaces the separate Name/Disk order entries, freeing a slot for
Parent. Unchecking it retains disk order. This adds no AES opcode, kernel
operation, Task, signal, timer or palette mechanism.

## Memory and build scope

Reserved bank-zero changes are **0 fixed bytes, 0 bytes per public Task and
0 idle bytes**, including guards, alignment and unused capacity. Browser grows
from 3,973 to 4,039 upper-memory bytes: 64 bytes for sixteen CICONBLK descriptors
and two bytes for keyboard focus. Four extra OBJECTs add 96 heap bytes per open
folder. The desktop record, file jobs and 16 KiB copy buffer are unchanged.

The demo rebuilds Files and Desktop with private layout probes and packages the
matching resource through `tools/build_demo.py`. It reuses the unchanged resident
image and other application/command binaries from the drag/drop demo, at the
same compiler pin. OF816, five-second autoboot, ROM, licences and checksums remain
part of the distributable. Measurements and executed development checks are
recorded in [development evidence](../development/compact-files.json); this is
not release or hardware qualification. Desktop grows by 708 executable bytes
and Files by 582; DESKTOP.RSC grows from 4,744 to 6,272 bytes.

## Development checks

The packaged demo passes physical Up/Refresh glyph activation, equivalent menu
and keyboard commands, selection preservation across refresh/sort, exact icon
artwork comparison before/after selection, and keyboard/mouse focus transitions.
Icon and list focus screenshots match the independent raster. Resizing, navigation
between sparse and populated directories, full/restore and scrolling preserve
the chosen geometry and pass pixel checks.

The drag walkthrough passes both views, one-file and selected-file copies to
folder backgrounds/subdirectories, independent disk readback, cancellation,
overwrite cancellation and Counter coexistence. Twelve idle and twelve loaded
outline trials restore exact pixels. The standalone Files run passes independent
multi-selection, list view, resizing and collection; its before/after heap totals
are identical. All three runs complete orderly EXIT with guards intact. Minimum
observed ordinary-Task headroom is 193 bytes; idle retains at least 127 bytes.
No stack reservations change.

The host suite passes 455 tests with four existing skips. The private Browser
layout passes emitted C probes at O0 and O2. No compiler qualification suite or
full hosted qualification matrix runs for this presentation change.

Two observation fixes were needed. Directory status can still contain the old
selection during a new scan, so the navigation helper now also waits for the
scan lock to retire. The pixel oracle must draw the focus edges after icons,
matching object-tree order; its previous order incorrectly covered four dotted
border pixels beside the selected label. Neither required a target workaround.
