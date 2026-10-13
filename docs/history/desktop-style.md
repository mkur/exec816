# Exec816 desktop style

[Current appearance](../reference/desktop.md#window-appearance) ·
[History index](README.md)

The desktop combines GEM's centred patterned titles and application menus with
Workbench's recognisable tool icons and persistent workspace. Its own visual
identity is warm grey paper, dark ink outlines and restrained blue/teal accents.
The fixed 8×8 font and window work insets remain unchanged.

## Appearance and interaction

The desktop is a solid grey field. Icons use transparent exteriors and compact
labels that blend into the background; selection reverses the label. SYS: and
WORK: retain blue floppies. C: uses a gold folder, Panel has sliders, Calculator
a keypad, Text a folded page and Counter a chart. All are standard 32×16 G_CICON
artwork, accounting for the display's tall pixels. The Files window's existing
monochrome icons use ordinary light paper rather than coloured label strips.
The editable assets remain in
[resource.json](../../examples/gem-browser/resource.json).

The focused title has an ink-blue name and lower rule, with the existing dotted
pattern around its light title label. Inactive titles are plain. The closer is
a nested square drawn with the existing rectangle primitive.

Widget desktop builds install a fixed sixteen-colour palette at display open.
GEM's logical pen numbers and packed hardware colour indices are unchanged;
standalone VDI builds retain their standard palette. The palette is recorded in
[gem-desktop-palette.h](../../ports/gem4xe/adapter/gem-desktop-palette.h): warm
paper `#f6f6ee`, dark ink `#202728`, desktop grey `#b4b7b0`, ink blue `#35566d`
and teal `#47777c`. There is no runtime theme selection API.

The menu bar keeps a fourteen-character focused-window caption at the left.
Clicking it opens Next window/Close, including for GEM applications. Unnamed
windows and the desktop show Exec816. Application titles occupy x=128..559,
with Windows at x=560..639. Application trees retain their existing x=0..431
coordinate space: drawing, title damage and pointer hits receive the same
128-pixel translation. Dropdowns are translated and clamped onto the screen;
the Windows popup remains 208 pixels wide and starts at x=432.

## Cost and development checks

DESKTOP.RSC grows from 2,004 to 4,744 bytes, a 2,740-byte increase for five extra
colour icons and descriptors. The palette adds 48 bytes of read-only data.
Desktop's existing CICONBLK array and shared staging/VRAM allocations are reused.
There are no new Tasks, timers, icon caches or persistent drawing buffers.
Fixed, per-public-Task and idle reserved bank-zero changes are each **0 bytes**,
including guards, alignment and unused capacity.

The development scope is the host suite, the focused emitted-code menu fixture
and the exact OF816 desktop package walkthrough. The menu fixture's old
client-addressed close injector was updated to the current window-addressed
AESGUI.Post contract; production message policy is unchanged. This is a fixture
maintenance change needed to run the existing lifecycle checks.

[Development evidence](../development/desktop-style.json) records 454 passing
host checks and four historical skips; 284 menu fixture checks plus four native
checks; seven menu pixel scenes (86,528 compared pixels), an exact native popup
and physical pointer/keyboard interaction. The focused-window caption menu,
heading transitions, disabled/hidden items, held replacement and cancellation
all pass.

The exact OF816 ZIP passes desktop selection, overlapping folder windows,
resize/full/scroll, a separately launched counter, background restoration,
folder reopening, shell HELLO and orderly EXIT. Six desktop screenshots match
the independent pixel model. The smallest public-Task stack margin is 195 bytes;
idle retains 127 bytes above its floor. Stack guards remain intact. Build
memory records match the previous colour-icon demo's reservations exactly.
The ZIP includes the pinned ROM, OF816, notices and verified checksums.

Both builds use the release host executable at the unchanged actionc pin;
Calypsi remains 5.18. An initial package comparison reached matching desktop
pixels before a second shared screenshot helper applied the old palette. That
helper now takes an explicit palette; standalone VDI expectations remain
unchanged. The successful package run uses the same target binaries, without a
development-media override. Development checks do not establish release or
real-hardware qualification.
