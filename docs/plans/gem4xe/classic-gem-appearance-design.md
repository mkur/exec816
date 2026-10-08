# Classic GEM desktop appearance

[GEM integration](README.md) · [Implementation plan](classic-gem-appearance-implementation-plan.md) ·
[Desktop contract](../../reference/desktop.md) · [Roadmap](../../roadmap.md#next-desktop-milestones)

Status: adopted; GA1 is implemented. See the [execution record](../../history/classic-gem-appearance.md).

Make the desktop recognizable as classic flat Atari GEM: outlined windows,
centered titles, patterned active title bars, a boxed closer on the left,
consistent monochrome menus and controls, and a lightly patterned desktop.
Use the existing 640×240 VBXE display and hybrid AES/VDI execution model.

This is the appearance step before window resizing and vertical scrolling.
Establish the frame conventions and shared geometry now; add scrollbar, arrow,
size and fuller gadgets only with their corresponding behavior. Drive, folder
and document icons belong to a later Files/desktop milestone, including the
object and resource support they need. There is one built-in appearance, with
no theme registry, runtime skin selection or new application-facing style API.

## Starting point and visual reference

The [application menu milestone](../../history/application-menu-bars.md)
provides application-owned menus, window switching and focus restoration.
The existing object renderer already supplies GEM button outlines, selection,
disabled appearance and default-button emphasis. The hosted font is the
GEM4XE/EmuTOS Atari ST 8×8 face, recorded in the
[renderer inputs](../../../ports/gem4xe/inputs.json); a replacement font is not
needed for this milestone.

The largest visual differences are in
[deskpaint.act](../../../lib/desktop/deskpaint.act): red/magenta title strips,
left-aligned names, a right-hand text `X`, and grey frame margins that merge
into the grey desktop. The menu bar is already much closer to the intended
appearance.

Use the flat window branch in GEM4XE's `src/aes/wind.c` at Exec816's renderer
pin, `e413c39d2f8e1bec8fe16596f610b923de4a0ae9`, as the visual reference:
centered window names, patterned topped titles and boxed control glyphs. The
local donor checkout at `fbfea9b0b1233a5d659d5ec583c63f863cceadfa` and its
`docs/shots/02-window.png` were inspected read-only. Its screenshot illustrates
the visual conventions, not the required resolution or a new renderer pin.
Keep donor analysis here; do not alter that checkout. Any extracted source or
assets must use recorded inputs and retain their upstream notices.

## Appearance decisions

| Element | Chosen appearance |
| --- | --- |
| Window outline | One logical pixel in black, white frame margins, black title/work separator. |
| Active title | The pinned donor's flat active-title pattern in black/white, with a solid white backing behind the centered black name. |
| Inactive title | Plain white with a readable black name; no active pattern. |
| Closer | Box on the left using the existing font's GEM closer glyph, not the letter `X`. |
| Menu bar | White with black text and bottom rule; selected heading inverted. |
| Dropdown | White, bounded black outline, inverted selected entry and the existing GEM disabled treatment. |
| Controls | Existing flat GEM object rendering, with consistent spacing in bundled applications. |
| Desktop | Alternating light-grey/white pixels, reversed on alternate rows; no animated texture or desktop-owned icons yet. |

Keep the full application palette available. These choices apply to desktop
decorations and bundled application resources; they do not remap palette entries
or override colors, borders or coordinates requested by an application's OBJECT
tree or VDI calls. Preserve meaningful default-button outlines and the existing
keyboard-focus indication. Focus must be distinguishable without color.

The menu bar remains 16 logical pixels high. Use the existing 8×8 font with its
current baseline consistently in titles, menus and controls. Review screenshots
both at native pixels and at the pinned emulator's normal display aspect: the
640×240 image must not be judged only as a square-pixel 640×480 mockup. The
display mode, font metrics and application character-cell resource conversion
stay within the current profile.

## Frame geometry and input

For an outer half-open rectangle `(left, top, right, bottom)`, keep the current
work rectangle `(left+8, top+16, right-8, bottom-8)` for this appearance step.
The visible outline becomes thin; the remaining side/bottom margin becomes
white. This is a deliberate first-pass compromise: it removes the broad grey
surround without moving application pixels or changing shell cell alignment.
It does not claim that the actual client insets have become one pixel.

Put these fixed metrics in the existing machine-readable desktop definitions
and generate the small Action!/C constant set needed by their consumers. Use a
small desktop geometry helper for work, title and closer rectangles. Migrate
the corresponding arithmetic in painting, hit testing, snapshots, content
translation and `wind_calc`; avoid a general layout engine, per-window metric
allocation or an additional RPC for local geometry.

The title band occupies the first 16 rows, with its lower rule at `top+15`.
The closer's painted and hit rectangle is
`[left+1, top+1, left+15, top+15)`, with the 8×8 glyph centered inside. A
close-capable window's name/drag area begins at `left+16`; the shell has no
closer and uses the whole inner title span. Center the title in that remaining
span, provide two pixels of horizontal text padding, and truncate to complete
glyph cells when necessary. Keep the existing bounded title string length.
Paint no placeholder fuller or size gadget.

Painting and input use the same rectangles. A press in the closer never starts
a drag. Release inside completes the existing close request; release outside,
Escape, input loss or retirement cancels it. Preserve the current inactive AES
window policy: the first press requests `WM_TOPPED` and consumes that gesture;
closing requires a subsequent accepted closer gesture. The shell remains
non-closeable. Moving the closer changes no message payload or focus policy.

Retain nonblocking outline dragging and existing routing/GUI locks. The active
pattern and menu owner follow committed focus, so a pending top request does
not paint a window active prematurely. Closing, hiding and keyboard/window-menu
switching use the existing focus-restoration path.

The resizing design will extend this same geometry boundary with kind-dependent
work insets and working arrow/slider/size gadgets. It must revisit shell cell
alignment explicitly if it reduces real margins; this note does not establish
the current eight-pixel margins as a permanent GEM requirement.

## Menus, controls and application ownership

Keep application menu registration, `MN_SELECTED`, title normalization and
Windows access as implemented. Native fallback/Windows menus should use the
same font baseline, monochrome selection and disabled treatment as application
menus. Draw outlines within the admitted popup bounds; neither border pixels
nor text may spill into a neighbouring layer. A frame border is not a menu item.

Application-owned menu geometry and OBJECT state remain authoritative. Adjust
the bundled Files tree/resource where its spacing needs improvement; do not
silently relayout arbitrary application trees. Maintain the Windows heading's
current reserved area and the current keyboard navigation and cancellation.

Review Files, GEM Control Panel, Counter and calculator together for consistent
backgrounds, text spacing and button states. Reuse the extracted object routines
for selected, disabled, radio and default states. Changes to generated resources
belong in their source or generator; shared renderer corrections belong in the
extraction patches. Keep application-only spacing changes in the applications.
An appearance update must not turn caller-local object drawing into presenter
RPCs or cause full-window repaint on every button change.

## Bounded rendering

The existing presenter remains the sole window/desktop painter. Application
content continues to draw through its existing display grant and visible work
rectangles. Keep current scene tokens, pointer serialization and input service
boundaries; add no Task, timer, signal, polling loop or priority change.

Use the existing font atlas, fills and blitter builder for the outlines and
closer. Render title and desktop patterns through a small fixed-pattern helper
using bounded strips or repeated source tiles. Reuse suitable raster/stipple
machinery, but do not issue one gateway call or blitter submission per dot.
Keep any pattern source immutable and all persistent continuation state in
upper memory. No per-window bitmap backing store is required.

Reuse the presenter's existing offscreen strip composition for decorated frame
fragments. Clip work to the disjoint title, side and bottom frame rectangles,
finish each fragment's background/pattern/text in scratch, then publish it.
Do not clear or copy uninitialized scratch over application-owned work pixels.
The strip stays under its existing exclusive ownership and capacity limits;
frame and widget/menu continuations cannot use it concurrently.

Anchor the title pattern to the window origin and the desktop pattern to screen
coordinates. A repaint of several clipped rectangles must produce the same
pixels as one complete repaint, including odd X positions and partial glyphs.
Emit the complete intended pixels of each published strip; never expose a
separate background-clear frame as an animation step.

Retain the existing 16-scanline paint limit and bounded text/object steps. If a
new pattern operation cannot finish within one existing work quantum, resume it
at the existing input boundary. Trust admitted geometry and generated drawing
commands; retain hardware completion/error handling and synchronization without
adding repeated geometry validation to the hot path.

## Memory, evidence and completion

Target **0 additional fixed bank-zero bytes, 0 per public Task and 0 private
idle**, including guards, alignment and unused reserved capacity. Keep the
existing Task/stack/DP, four application-window and six-Layer reservations.
Record upper-memory, code, heap and any VRAM changes separately. Small pattern
tables and continuations must not consume new public-Task stack arrays.

The current [menu implementation record](../../history/application-menu-bars.md)
contains the upper-arena, manifest and observed stack margins. Check the actual
build during implementation. More upper RAM is acceptable; uncompressed
cartridge size is informational and compression is separate work. Executable
segment/manifest limits and stack guards still have to pass.

Completion means independent emitted-pixel checks for active/inactive frames,
title truncation, closer placement, menu/control states and patterned exposure
repair, plus physical pointer/keyboard interaction with overlapping windows.
Exercise focus changes and close/drag cancellation while Counter and shell/disk
output continue. Check guards, stack margin, cleanup and bounded completion.

Use the development tier and refresh the exact OF816 demo ZIP through
`tools/build_demo.py`, retaining its five-second standard shell/prime autoboot.
Record visual comparisons and the cost of affected paint/input operations.
This milestone does not close PI4/HY4 or qualify physical hardware. Further
latency tuning remains deferred while the desktop gains functionality.
