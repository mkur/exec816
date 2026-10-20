# Editing FastBasic in GEM

[Guide index](README.md) · [Limits](../reference/fastbasic-workbench.md) ·
[Command-line compiler workflow](fastbasic.md)

Build the optional demo with `python3 tools/build_demo.py --basic-workbench`.
Start `BASIC` from the Shell, or launch `C:BASIC.APP` from Files. The WB2 scratch
editor supports typing and selection; Open/Save and compiler controls are still
being implemented. Closing this slice discards its buffer.

Use the File and Edit menus, or these shortcuts:

| Action | Control |
| --- | --- |
| Move caret | Atari cursor keys (Control with their printed arrow key) |
| Extend selection | Shift with a cursor key, or drag over source |
| Select all | Control+A |
| Undo / Redo | Control+Z / Control+Y |
| Insert newline / tab | Return / Tab |
| Delete before / at caret | Backspace / Atari Delete |
| Quit | Control+Q or the close gadget |
| Scroll | Vertical arrows or slider |
| Resize / move | Size gadget / title bar |

Tabs occupy eight-column stops. Long lines pan to keep the caret visible.
Capacity errors leave the previous source intact. Undo includes selection
replacement and has a fixed 16 KiB budget; very large replacements are refused.
