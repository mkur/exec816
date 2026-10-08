# Editable TEDINFO and Files dialogs

[GEM integration](README.md) · [Implementation plan](editable-dialogs-implementation-plan.md)

Add caller-local `objc_edit` and editable-field traversal to the existing
windowed object/form subset. Then Files uses ordinary OBJECT/TEDINFO trees for
Path, New Folder and Rename. The desktop remains multitasking while a dialog
is open; no update lock or display ownership spans an input wait.

## Editing contract

Application-owned writable text, template and validation strings keep the GEM
TEDINFO layout. `te_txtlen` includes the terminating byte. Support G_TEXT,
G_BOXTEXT, G_FTEXT and G_FBOXTEXT with EDITABLE, ED_INIT, ED_CHAR and ED_END.
ED_INIT places the caret at the end; ED_CHAR changes text/index; ED_END removes
the caret. Retain the active edit identity/index in the caller's AES context so
ordinary WM_REDRAW repairs it. There is one active field per application.

Support insertion, Backspace, Delete, left/right, Home/End and Escape-to-clear.
Respect capacity and GEM validation classes; a short validation string repeats
its last class. Form traversal includes eligible editable objects. Tab and
Shift-Tab move focus; Return activates DEFAULT and Space edits text when focus
is editable. Existing button/radio behavior remains unchanged. Use a steady
caret, without another timer or signal. Ordinary text fields scroll their
visible text horizontally to keep the caret in view; formatted fields use
underscore slots in a bounded template. Document supported text/template bounds.

Keep text mutation caller-local and trusted. Rendering retains its existing
visible work-area clipping and complete strip publication. Resource loading
validates stored text capacity once and relocates writable storage; do not
replace declared editable capacity with the current string length. No repeated
tree audit is added to editing or drawing. The caller must end editing before
freeing/replacing its tree; normal application teardown clears the association.

## Files interaction

Each dialog temporarily replaces Files' list within the same application
window. Its compiled-in tree contains a title, editable text field, default OK
and Cancel. It is modal only to Files, not the desktop. WM_REDRAW, movement,
resizing, topping, child completion and WM_CLOSED continue through the existing
event loop. Cancel restores the list without mutation. Closing also cancels.

Path accepts a directory and replaces the current snapshot only after it opens.
New Folder accepts one leaf name; Rename starts with the selected name. Reject
empty or path-separated leaf names in these commands, then use ordinary DOS
CreateDir/Rename and preserve their operational error. No overwrite, recursive
change or new filesystem service is added. Failed operations keep the dialog
open with a useful status; success refreshes the snapshot and selects the result.
Menu actions are disabled when inapplicable. Resources, directory storage and
child Processes retain the existing explicit cleanup paths.

Reserved bank-zero delta is **0 fixed, 0 per public Task and 0 private idle**.
Use upper context/application storage and existing VRAM scratch. General
screen-modal `form_do`, multiline text, clipboard, selection ranges, Unicode
and dialog windows independent of the owner's one-window profile are deferred.

## Validation

Small emitted tests cover capacities, editing/navigation, class/template rules,
two independent contexts and resource capacity relocation. Physical desktop
checks cover mouse/keyboard OK/Cancel, redraw/overlap while editing, path entry,
creating and renaming on disposable writable media, failure preservation and
closing during a dialog. Run the exact refreshed OF816 ZIP, retain guard/stack
and heap-return evidence, and report development scope rather than qualification.
