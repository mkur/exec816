# Files navigation and appearance

[Current desktop contract](../reference/aes.md#small-gem-desktop) ·
[Implementation plan](../plans/gem4xe/files-navigation-appearance-plan.md) ·
[Development evidence](../development/files-navigation-appearance.json)

## FR1: distinct title gadgets

Close uses GEM font glyph 5; full/restore uses glyph 7. Existing borders,
hit areas and window geometry are unchanged. The linked resident C image
increases by 43 bytes. Fixed, per-Task and idle reserved bank-zero deltas are
all **zero**, including guards, alignment and unused capacity.

Development checks pass on the exact extracted OF816 ZIP: independent pixels
for active/inactive frames, full/restore, close and shell exposure, plus HELLO
and orderly EXIT with guards intact. The host suite passes 455 tests with four
existing skips. No compiler suite or release/hardware qualification runs.

The full-screen check exposed duplicate menu observations for the desktop and
its full-screen folder, which share one source tree. The oracle now counts
unique source trees. The walkthrough also uses bulk debug memory reads instead
of one bridge expression per word; target execution and pixel expectations are
unchanged.

## FR2: compact content and top summary

The default window now shows a 3×3 icon grid. The toolbar is removed and the
summary is fixed above the content. Parent uses File > Parent or Esc; roots
ignore Esc without repainting or scanning. Backspace does not navigate, and
Esc in a dialog only cancels the dialog. Refresh remains File > Refresh/Ctrl+L.

The exact packaged demo passes independent pixels for the new layout, icon/list
selection and focus, scrolling, resizing, full/restore and exposure, plus
Parent/Refresh input checks and orderly EXIT. Host checks pass 455 tests with
four existing skips. The Browser remains 4,039 upper-memory bytes; removing
two OBJECTs saves 48 heap bytes per folder (552 instead of 600). Fixed,
per-Task and idle reserved bank-zero deltas are all **zero**.

## FR3: virtual parent and upward selection

Subdirectories have a scrolling `..` item using the approved 32×16 artwork.
Display positions map to the existing snapshot; its 256 entries and 32-byte
bitmap are unchanged. Parent selection clears file membership, and file
operations and drag admission exclude it. Up reuses the existing edit buffer
to remember the child name, then selects and reveals it after a successful scan.
An unsuccessful scan does not change the path.

The optimized desktop passes the compact walkthrough with empty-directory
parent selection, refresh, Return/Esc/menu navigation, offscreen child reveal,
name/disk order, mutation exclusion and root omission. A separate real-directory
run passes 256 real entries plus parent, Select All, the final bitmap bit,
scrollbar access and list switching. Both complete EXIT with guards intact.
The host drag fixture also rejects the parent as a source and destination.
The final integration slice exercises actual disk copies and standalone Files.

The Browser grows by two upper-memory bytes to 4,041. O0/O2 emitted layout
probes pass; the host suite passes 455 tests with four existing skips. Fixed,
per-Task and idle reserved bank-zero deltas are all **zero**.
