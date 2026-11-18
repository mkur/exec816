# Atari MagiC MGEDIT port audit

The current Exec bindings cover much of MGEDIT's application shell. Three gaps
block a source rebuild from opening an editable document. Exec has no MagiC
`G_EDIT` engine, its resource loader rejects the original resource, and the
stock document allocation exceeds the C heap limit even for New. Modeless
dialogs, font selection, clipboard interoperability and desktop messaging add
separate requirements for feature parity.

## Source and release examined

The target is Atari `MGEDIT.APP` from `Atari-MagiC-2026-11-04.zip`. Its 17,366-byte
executable and the installed 17,960-byte `EDITOBJC.SLB` match the checked-in
upstream binaries byte for byte. The release's German, English and French
resources also match their source-tree copies. `MGEDIT.PRJ` builds `MGEDIT.C`,
`MGEDWIND.C` and `OPT_DIAL.C` using Pure C startup, utility and SLB bindings.
[Reference pin](../../toolchain/atari-st-reference.json) ·
[Atari MGEDIT source](https://gitlab.com/AndreasK/Atari-Mac-MagiC-Sources/-/tree/28cfdd29aa16fef692cc287bad3046b44ddcce3d/MagiC/APPS/MGEDIT) ·
[EDITOBJC source and test application](https://gitlab.com/AndreasK/Atari-Mac-MagiC-Sources/-/tree/28cfdd29aa16fef692cc287bad3046b44ddcce3d/MagiC/EXTENSIO/EDIT_SLB)

## Opening the first editor window

### The multiline edit object

`MGEDIT.C` opens `EDITOBJC.SLB` before registering with AES. The library installs
AES functions 210–217 and the renderer for `G_EDIT` (object type 37). For each
document, `MGEDWIND.C` creates a one-object tree whose `ob_spec` points to editor
state, sets a caller-owned mutable text buffer and configures the font, colors
and tab width. The engine owns editing, caret, selection, line layout, scrolling
and dirty state. The app supplies events and window messages, updates the four
scrollbar values and saves the live buffer or a selected range. It closes and
deletes the edit object before freeing the buffer.
[Window setup and message handlers](https://gitlab.com/AndreasK/Atari-Mac-MagiC-Sources/-/blob/28cfdd29aa16fef692cc287bad3046b44ddcce3d/MagiC/APPS/MGEDIT/SRC/MGEDWIND.C) ·
[Library initialization](https://gitlab.com/AndreasK/Atari-Mac-MagiC-Sources/-/blob/28cfdd29aa16fef692cc287bad3046b44ddcce3d/MagiC/EXTENSIO/EDIT_SLB/SRC/EDIT_SLB.C) ·
[MagiC object dispatch](https://gitlab.com/AndreasK/Atari-Mac-MagiC-Sources/-/blob/28cfdd29aa16fef692cc287bad3046b44ddcce3d/MagiC/KERNEL/AES/SRC/AESOBJ.S)

Exec's `objc_edit` edits a single TEDINFO field. Its object renderer has neither
`G_EDIT` nor a public user-draw callback. A native rebuild needs the editor
contract and a way for AES to draw the object. The donor engine is largely C and
uses a 68k `memchr2` routine for line scanning. Its buffer and event fields need
an explicit mapping to Calypsi `WORD`, `LONG` and huge pointers. The existing C
APP loader can run the rebuilt client. Native linkage and state ownership are
design decisions, with the 68k SLB startup and trap-table patching as donor
details. The donor's `TST_APP/EDIT` provides a small fixture for exercising the
edit object before bringing up MGEDIT's menus and file dialogs.
[Exec object contract](../reference/aes.md#application-object-trees-and-forms) ·
[Editor engine](https://gitlab.com/AndreasK/Atari-Mac-MagiC-Sources/-/blob/28cfdd29aa16fef692cc287bad3046b44ddcce3d/MagiC/EXTENSIO/EDIT_SLB/SRC/EDITOB.C)

### The original resource

All three stock `.RSC` files use classic version zero, with 63 objects, 23
TEDINFO records, seven free strings and four trees (About, menu, preferences and
color palette). The trees contain 6, 27, 13 and 17 objects respectively, within
Exec's tree and menu limits. The loader rejects the one About `G_IMAGE` with
its BITBLK, 3D flags and unsupported object state bits. The editor's `G_EDIT`
is constructed at runtime. A first resource conversion could preserve the
original tree indices, strings and actions while adapting those visual fields.
Loading the stock resources with their original visuals requires generic
support for the resource features above. The stock menu includes six desk
accessory placeholders. Exec's menu can be installed before a window opens,
but its visibility follows the focused shown window. MGEDIT's menu-only state
at launch with no arguments, and after closing the last document, therefore
needs a desktop policy decision.
[Exec resource contract](../reference/aes.md#resources-and-popup-menus) ·
[Loader admission checks](../../c/calypsi/aes-resource.c)

### Document storage and I/O

MGEDIT uses `Fopen`, `Fcntl(FSTAT)`, `Fread` and `Fclose` to load a document,
then writes a NUL just past the loaded bytes. It asks `Malloc` for file size
plus a default 65,536 bytes of editing space. Exec's `Malloc` allows 65,520
payload bytes. A bounded first port would need an explicit capacity and room
for the terminator. For larger documents, Exec already provides
`AllocMem(..., MEMF_LINEAR)` for physically contiguous cross-bank storage.
Using it would require checking compiler-emitted pointer arithmetic and scans,
the editor's 16-bit line and pixel fields, and reclamation on APP exit. The
current C runtime tracks its own allocations.
[GEMDOS compatibility](../reference/gemdos-compatibility.md) ·
[C runtime allocation](../reference/c-runtime.md#allocation-and-arguments) ·
[Exec memory](../reference/memory.md)

The existing GEMDOS layer also covers `Fcreate(path, 0)` and `Fwrite` for Save.
The donor checks for a short write and discards the `Fclose` result. On Exec,
close can report a terminal failure, so check it before clearing the dirty flag.
Carry over the dirty-close prompt and test its save, discard and cancel paths.
The app also copies paths into 128-byte fields, while Exec's command tail can
carry a longer path. Bound those copies and reserve space for the dirty-title
marker within Exec's 64-character window title limit.
[GEMDOS compatibility](../reference/gemdos-compatibility.md) ·
[APP arguments](../reference/c-runtime.md#allocation-and-arguments) ·
[AES window contract](../reference/aes.md)

## Drawing and input integration

- Ordinary GEM windows, messages, sliders, menu and alert calls, visibility
  enumeration, mouse hide/show, text/fill drawing and screen-to-screen
  `vro_cpyfm` are available. The editor's `wind_scroll` copies visible content
  and paints the exposed strips, much like work exercised by MGVIEW. MagiC
  routes `objc_wdraw` through window work/visible clipping. Exec's `objc_draw`
  already intersects the explicit clip with the selected window's visible work
  region. Native bindings can reuse those facilities and the existing GRECT
  adapters. The donor's `form_xerr` and `objc_grect` map to alert and object
  geometry helpers. Its Full operation uses `graf_growbox` and
  `graf_shrinkbox` animation, which the current bindings lack. Exec has six
  window slots across the desktop, and a handle-naming call selects the VDI
  target. MGEDIT's 64-entry window array gives the donor app's own ceiling.
  [AES window contract](../reference/aes.md) ·
  [GRECT adapters](../../c/compat/gem/rect.c) ·
  [MGVIEW port record](mgview-port.md)
- The editor draws and erases the caret with an XOR `v_pline` and inverts
  selection rectangles with XOR fill. Exec exposes replace and transparent
  write modes, and the client VDI has no line primitive. Correct caret and
  selection pixels need a native drawing path with defined clipping and
  restoration. MagiC calls the editor from object drawing, but a literal
  callback into public VDI would try to reenter an already-busy Exec AES
  context. The integration needs to use the admitted draw context or choose a
  different render boundary explicitly. The GEM4XE v0.15 source used in the
  MGVIEW benchmark has TEDINFO `objc_edit` and VBXE raster code. Its AES source
  has no `G_EDIT` or `EDITOBJC` implementation.
  [Exec VDI contract](../reference/gem-vdi.md) ·
  [Object draw path](../../c/calypsi/aes-objects.c) ·
  [GEM4XE object code](https://github.com/slaapliedje/gem4xe/blob/2bf10f6788372dcfa94f6d9416e4b957eb4ce394/src/aes/objc.c) ·
  [GEM4XE VBXE rendering](https://github.com/slaapliedje/gem4xe/blob/2bf10f6788372dcfa94f6d9416e4b957eb4ce394/src/vdi/dev_vbxe.c)
- MGEDIT waits first and then acquires UPDATE for its dispatch. Inside
  `edit_evnt`, drag selection can wait again for release, a mouse-rectangle
  transition or an autoscroll timer. Exec provides these event kinds and
  independent input delivery while SCRENMGR waits for UPDATE. Preserve the
  outer ordering and verify the nested drag, lost input and target retirement
  boundaries with a second window active. Exec reports keyboard and button
  targets separately with `ExecAESInputWindow`. The donor queries the window
  that is top at dispatch time. Use the standard UPDATE and
  workstation ownership for redraw, copy and caret repair.
  [Exec input and ownership contract](../reference/aes.md) ·
  [MagiC editor input loop](https://gitlab.com/AndreasK/Atari-Mac-MagiC-Sources/-/blob/28cfdd29aa16fef692cc287bad3046b44ddcce3d/MagiC/EXTENSIO/EDIT_SLB/SRC/EDITOB.C)

## Remaining application features

| MGEDIT feature | Exec gap or adaptation |
| --- | --- |
| Open and Save As | MagiC's `fslx_open/evnt/close` keeps a modeless selector in the app event loop. Exec's `fsel_exinput` is synchronous, requires entry outside UPDATE/MCTRL, and uses native volume paths and 8.3 leaves. The original modeless flow needs a corresponding selector lifecycle. A modal first-port adaptation needs an explicit decision. Save As can hold a document or selected-range reference until completion, so verify its lifetime across further events. [File selector](../reference/aes.md#file-selector) |
| Preferences and colors | The donor uses `wdlg_*` for a modeless windowed dialog and `form_popup` for the palette. Exec has `form_do`, `form_dial`, `menu_popup` and lower-level form/object calls. Preserving the donor's callbacks and event flow needs a window-dialog contract and a palette popup with the right semantics. [Exec forms](../reference/aes.md#application-object-trees-and-forms) |
| Fonts | MGEDIT uses `fnts_*` in Preferences. `EDITOBJC` uses GDOS font loading, VDI width/height queries and proportional extents. Exec currently offers one fixed 8×8 face. A fixed-font slice still needs correct tab, caret, line-width and scroll metrics. [Exec VDI](../reference/gem-vdi.md) |
| Cut, copy and paste | `EDITOBJC` locates `SCRAP.TXT` through `scrp_read` and uses create/truncate/update flags on `Fopen`. Exec has no scrap-path service, and its GEMDOS `Fopen` accepts only access modes 0–2. Existing `Fcreate` and `Fread/Fwrite` cover the data path. Cross-app interoperability still needs a common location and clipboard contract. [Engine source](https://gitlab.com/AndreasK/Atari-Mac-MagiC-Sources/-/blob/28cfdd29aa16fef692cc287bad3046b44ddcce3d/MagiC/EXTENSIO/EDIT_SLB/SRC/EDITOB.C) · [GEMDOS calls](../reference/gemdos-compatibility.md#supported-calls) |
| Startup, desktop and preferences paths | Use the existing C APP arguments for launch-by-file and map the Pure C `_GemParBlk` color lookup to the workstation inquiry. `VA_START/AV_STARTED`, `AP_TERM`, `HOME`/`shel_find` and Atari drive paths need native counterparts if those behaviors are in scope. Preserve dirty-close handling for application-level Quit. [Application source](https://gitlab.com/AndreasK/Atari-Mac-MagiC-Sources/-/blob/28cfdd29aa16fef692cc287bad3046b44ddcce3d/MagiC/APPS/MGEDIT/SRC/MGEDIT.C) · [APP runtime](../reference/c-runtime.md) |

## First slice to decide

Use the donor's edit-object fixture as the first gate. A single native window
can prove multiline insertion and deletion, caret placement, clipped redraw
and scrolling with the system face. Then integrate MGEDIT's resource/menu and
its New, open-by-argument, Save to an existing path and dirty-close paths using
a bounded buffer if approved. Untitled Save takes the donor's Save As path.
Check a short write or failing close, overlapping redraw and a second window's
input before widening to the original dialogs and clipboard.
The audit identifies no new kernel service required for that bounded slice.
The open decisions are native `G_EDIT` integration, resource conversion versus
stock resource support, buffer capacity, the windowless menu, and the scope
of original dialogs.

Development evidence is source and ABI inspection, byte-for-byte comparison of
the release artifacts and host decoding of all three resource variants. Runtime
behavior, stack use and paint performance remain unmeasured. This documentation
slice changes zero reserved bank-zero bytes, fixed or per Task.
