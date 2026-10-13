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
