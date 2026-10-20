# FastBasic workbench

[Reference index](README.md) · [Controls](../guides/fastbasic-workbench.md) ·
[Development evidence](../history/fastbasic-workbench.md) ·
[Implementation plan](../plans/fastbasic-workbench-implementation-plan.md)

`C:BASIC.APP` is a loadable native GEM application. WB0–WB2 provide the document
model and an editable window. File transactions and the integrated compiler
workflow are subsequent slices; the first complete edit/Run delivery is WB9.
Debugging and native graphics are outside WB0–WB9.

The document holds at most 32,768 counted bytes, 4,096 editable lines and
255 bytes per line. Empty input has one line; a final LF leaves an editable
trailing line. Source bytes are printable ASCII, tab and internal LF. Tabs
advance to eight-column stops; caret and selection positions count source bytes.
Rejected edits preserve source and undo state.

Undo/Redo share a 16 KiB log including metadata and both old/new bytes. Oldest
whole groups are discarded when necessary. A single edit that exceeds this
budget is rejected. New accepted edits invalidate Redo; saved and current
source generations are separate from the monotonically allocated edit identity.
Document storage requests 65,540 upper-RAM bytes, rounded to 65,544. Model and
menu storage belong to each application image and survive until AES detach.

The editor obtains cell metrics and work geometry from GEM, preserves logical
caret/selection during geometry and focus changes, pans horizontally to reveal
the caret and supports a vertical slider. Painting holds UPDATE for at most
four text rows, releases it and obtains fresh visible rectangles for the next
unit. Input loss cancels pointer selection. Large gap moves yield in units
of at most 1 KiB without exposing partial logical text.

The default workbench demo leaves two public Task slots after normal startup:
one for BASIC.APP and one sequential compiler/program child. Other applications
can consume those slots. The current WB2 build advertises only implemented
editing controls; unsaved text is discarded on closing its scratch window.
The build selection is `tools/build_demo.py --basic-workbench` and retains the
standard desktop, Shell, prime demo and five-second OF816 autoboot.

All reserved bank-zero costs remain unchanged from the enabled GEM/guest
profile: zero added fixed, root/kernel, per-public-Task and idle bytes, including
guards, alignment and unused capacity. Build-specific image sizes, timings,
stack peaks and machine pins are in the development record.
