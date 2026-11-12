# GEM desktop scene and frames

[Reference](README.md) · [AES](aes.md) · [Layers](layers.md)

AES owns application registration, windows, focus and stacking. The graphical
system Task presents frame/menu damage and delivers ordinary AES notices.
Applications, including the desktop and terminal, paint their own work areas.

One scene-owned array contains six authoritative window records. Each holds
frame data, AES owner, input association, pending GUI notices and its borrowed
caller view. The AES service keeps an index of pointers to these same records.
Layers owns derived geometry and visible regions; caller views and input-route
snapshots are derived publications. Internal identities, GEM handles and
nonreused lifetime epochs remain distinct.

`abi/desktop.json` describes private scene records and shared frame metrics;
it is not an application message protocol. The old DESKTOP packet interface,
retained command/widget window kinds and native shell frame have retired.
See the [historical contract](../history/native-desktop.md).

## Window appearance

GEM windows use dark ink outlines, warm off-white frame margins and
centered titles in the existing 8×8 Atari ST font. Title text starts two rows
below the outer top edge, centering seven-row capitals within the eleven-row
bar; iconified tile labels use the same offset. The focused title carries
a dotted pattern, blue text and a blue lower rule; inactive titles are plain.
The closer uses a short, wide GEM-style X on the left . The full/restore gadget uses a distinct diamond mark. Both
marks occupy 10×7 pixels within 16×11 control cells. Iconify uses a matching
10×7 window symbol; scroll arrows occupy 10×5 pixels. Controls share the window
outline and single separators instead of drawing inset boxes. Scroll arrows
are centered on the rail, with the track and resize cell supplying their
horizontal borders. Close hit bounds retain the existing cell inset.
Release outside, Escape and input loss cancel a close gesture. An inactive
AES window still requires a topping gesture before its closer can activate.

Ordinary work insets are left 8, top 11, right 8 and bottom 2 pixels.
Vertical scrollbars reserve 16 pixels on the right; SIZER reserves 11 at the
bottom. INFO adds ten rows below the title. Frame fragments
are reconstructed in the existing offscreen strip and published only when
complete, without clearing application-owned work pixels. The frame and local
`wind_calc` geometry use constants generated from `abi/desktop.json`.

Exposed desktop regions use a flat warm grey (GEM pen 8). Each damaged strip
is composed offscreen before publication. There is no periodic background
repaint or separate desktop framebuffer.

GEM desktop builds use a fixed sixteen-colour palette with warm paper, dark
ink and muted blue/teal accents. Logical GEM pen numbers and hardware nibble
ordering stay unchanged; standalone VDI builds retain the standard GEM palette.
The palette is installed during the existing display open, with no new drawing
pass or runtime theme manager. The [style record](../history/desktop-style.md)
records the artwork, validation and memory costs.

## Iconification

The Windows menu can iconify an ordinary window into its slot's bottom tile.
AES retains its normal bounds and caller-owned model; the published visible
work area becomes empty. Focus moves to the nearest eligible shown window.
Clicking its tile, or topping it through AES, restores normal geometry and
focus. Closing an iconified window still retires its normal window lifetime.
No additional Task, window slot or private console attachment is created.

## Admission, painting and lifetime

Use the public AES window API. Four AES registrations and six window slots
include hidden windows. Exhaustion returns the normal AES resource error.
The system loop admits at most four queued AES requests per service turn;
a reserved late admission follows active paint. Scene mutations remain under
the AES gate; physical calls suspend it and reacquire it before publication.

GEM application menus use a private 50-byte drawing packet with DRAW and INVERT
operations. The presenter borrows the admitted menu tree through its scene
transaction. It stores no native widget context or application window policy
in the renderer. Shared GSX writes remain under DISPLAY ownership.

The terminal obtains copied console snapshots, associates keyboard routing with
its ordinary AES window, and paints with its own VDI workstation. Stream/model
progress does not depend on UPDATE or drawing. Closing a source and closing its
window remain separate lifetimes; see [console views](console-views.md).

No native graphical preview build profile remains. The supported GUI demo is
`tools/build_demo.py --gem-desktop`; standalone shell/prime, text and bitmap
console profiles remain available. The scene allocation and renderer packet
use upper memory and add zero reserved bank-zero bytes, including Task stacks,
direct pages, guards, alignment and unused capacity.

## Private window snapshots

Two 75 KiB compact VRAM slots at `$50000–$62BFF` and `$62C00–$757FF` store
eligible AES windows. Capture requires a fully visible outer window, clean
manager damage and completed application repaint obligations. The title is
drawn live on restoration. Window identity, visual revision and dimensions
determine validity; position is not part of the saved image. Resize, changed
INFO/slider values and UPDATE invalidate it; unchanged frame setters do no work.

A pinned slot cannot be evicted before DMA retirement. Invalid slots are used
first, then the least recently used unpinned slot. Capture holds a Layers read
token and strips overlays; validity publishes only after matching completion.
Restore borrows the paint token until completion. Close invalidates the snapshot
identity before clearing the window. An unquiesced fault retains referenced
storage. This is private presentation storage, with no public offscreen API.
Ordinary restoration does not acknowledge application repaint; the explicit
[preservation contract](aes.md#opt-in-window-preservation) governs that case.
