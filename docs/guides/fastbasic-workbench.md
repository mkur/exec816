# Editing FastBasic in GEM

[Guide index](README.md) · [Limits](../reference/fastbasic-workbench.md) ·
[Command-line compiler workflow](fastbasic.md)

Build the optional demo with `python3 tools/build_demo.py --basic-workbench`.
Start `BASIC` from the Shell, or launch `C:BASIC.APP` from Files. The editor supports Open, Save and Save As. Compiler controls are still being
implemented for WB9. Unsaved changes are resolved before New, Open or Quit.

Use the File and Edit menus, or these shortcuts:

| Action | Control |
| --- | --- |
| New / Open | Control+N / Control+O |
| Save / Save As | Control+S / Control+W |
| Move caret | Atari cursor keys (Control with their printed arrow key) |
| Extend selection | Shift with a cursor key, or drag over source |
| Select all | Control+A |
| Undo / Redo | Control+Z / Control+Y |
| Find / Find Next / Replace | Control+F / Control+G / Control+R |
| Insert newline / tab | Return / Tab |
| Delete before / at caret | Backspace / Atari Delete |
| Quit | Control+Q or the close gadget |
| Scroll | Vertical arrows or slider |
| Resize / move | Size gadget / title bar |

Find and Replace compare letters without case. Enter up to 80 bytes in each
field; Find Next wraps once, and All replaces every non-overlapping match as
one Undo group. A replacement that exceeds the undo budget is refused without
changing the source. Escape cancels a running search or replacement.

Return repeats the line's leading spaces and tabs. Strings, comments and common
keywords have separate colours. The Navigate menu moves between procedures and
toggles the current procedure's fold. Folds affect display only; editing clears
them. Use the compiler for syntax checking when the Run workflow is available.

Tabs occupy eight-column stops. Long lines pan to keep the caret visible.
Capacity errors leave the previous source intact. Undo includes selection
replacement and has a fixed 16 KiB budget; very large replacements are refused.

Select a writable destination such as `WORK:` or `RAM:` in the standard file
selector. Paths longer than 127 bytes are rejected. New source uses ATASCII
line endings; existing uniform LF/CRLF/CR/ATASCII endings are preserved. Opening
mixed endings makes the normalized source dirty.

Save writes a snapshot, so subsequent edits remain unsaved. Escape cancels a
file job. If publication fails, paged error dialogs name temporary/backup recovery
copies (File → Recovery paths displays them again); retain those files until you have recovered the desired version. The
old destination can have moved to its backup before the final rename fails.
Choose Save, Discard or Cancel when asked about unsaved changes; canceling an
Open/Save As selector also preserves your current source and committed path.
