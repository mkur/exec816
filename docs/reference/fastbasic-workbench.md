# FastBasic workbench

[Reference index](README.md) · [Controls](../guides/fastbasic-workbench.md) ·
[Development evidence](../history/fastbasic-workbench.md) ·
[Editor refresh evidence](../history/fastbasic-editor-refresh.md) ·
[Source Run evidence](../history/fastbasic-interpreter.md) ·
[Implementation plan](../plans/fastbasic-workbench-implementation-plan.md)

`C:BASIC.APP` is a loadable native GEM application. WB0–WB4 provide the document
model, editable window, file transactions and editing assistance. WB9 completed
the first integrated edit/Check/Run/Stop/Build delivery (FB7). Source Run now
uses the [interpreter](fastbasic.md#source-execution) and its buffer attachment.
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

The minimum client area is 288×128 pixels so dirty-document choices fit.
The editor obtains cell metrics and work geometry from GEM, preserves logical
caret/selection during geometry and focus changes, pans horizontally to reveal
the caret and supports a vertical slider. The editor retains character, syntax,
selection and caret appearance in a 5,120-byte private upper-RAM reservation.
Ordinary edits replace changed cell spans without clearing their source row;
unchanged status text needs no drawing. A paint turn composes at most four source
rows and reconstructs at most 96 glyph cells across visible fragments, plus
eight margin-fill fragments. It releases UPDATE and obtains fresh visibility
for subsequent work. Exposure forces reconstruction even when logical appearance
is unchanged. Deferred and hidden changes publish once before waiting; hidden
pixels do not keep the editor polling. Completion reports cover successfully
drawn pixels, with the public conditional completion shortcut for a wholly
completed edit. Deferred changes declare source, status and margin damage
separately through `ExecAESInvalidate`; an empty suffix nominates only rows
whose appearance can change. No new Task, timer or bank-zero reservation is added.
Input loss cancels pointer selection. Large gap moves yield in units
of at most 1 KiB without exposing partial logical text.

The twelve-Task demo starts six public Tasks. BASIC.APP and one interpreter
child use eight; a second shell brings that to nine. Other applications can
consume the remaining slots, with separate guest/client/window limits. The application advertises implemented
editing and file controls. New, Open and Quit resolve unsaved changes with
Save/Discard/Cancel; canceling a selector preserves the current document.
The build selection is `tools/build_demo.py --basic-workbench` and retains the
standard desktop, Shell, prime demo and five-second OF816 autoboot.

Desktop and graphical console use two of the three 2,560-byte stack pools.
BASIC declares a 1,312-byte requirement and shares ordinary pools with its
child. Another large request can use the third pool if free; small requests can
also consume large pools. Declared C requirements are enforced at admission.
Panel and Counter retain their 1,312-byte requirements. No pool is enlarged.

All reserved bank-zero costs remain unchanged from the enabled GEM/guest
profile: zero added fixed, root/kernel, per-public-Task and idle bytes, including
guards, alignment and unused capacity. Build-specific image sizes, timings,
stack peaks and machine pins are in the development record.

## Files

Paths contain at most 127 bytes before NUL; selector fields are separate from
the committed path. New source saves as ATASCII. Open normalizes LF, CRLF, CR
or ATASCII internally, preserves a uniform input style and final-EOL choice,
and marks mixed styles dirty. An unsupported byte or capacity error preserves
the old document. The candidate becomes current only after EOF and checked Close.
Load and serialization steps transfer at most 1 KiB, with a separate pending-CR
state across reads.

Save serializes an immutable 32 KiB-capacity snapshot to an exclusively created
8.3 temporary in the destination directory. Positive short writes continue;
all writes and terminal Close are checked. Publishing uses no-replace Rename.
Replacing a target moves the old file to an unused backup, then renames the
completed temporary. This is not atomic replacement. A failure retains and
reports complete or uncertain recovery paths in paged alerts; backup-deletion failure is a
warning after successful publication. Close consumes the handle even on failure.
Save As commits its path only after publication. Saving a snapshot clears dirty
state only if its generation is still current; later edits remain unsaved.

Escape cancels pending file work. A canceled save can leave a complete recovery
copy; use the displayed paths before retrying. File → Recovery paths displays them
again until the next file operation. The application processes retained
AES policy messages before repairing or reopening an interrupted selector/alert.
The three candidate allocations and the full snapshot capacity are charged to
upper heap; no Task stack or direct-page reservation grows.

## Editing assistance

Find and Replace accept up to 80 source bytes in each field and compare ASCII
letters without case. Find Next starts after the caret and wraps once. Replace
All scans an immutable source generation, prepares the minimal changed span and
commits it as one undo group. Capacity or undo-budget refusal leaves the source
unchanged. Search steps perform at most 1,024 comparisons; replacement copying
uses at most 1 KiB per step. Escape cancels pending work.

Return copies the current line's leading spaces and tabs. Lexical colouring
recognizes strings and comments before whole-word keywords; it does not change
source spelling or validate program semantics. Procedure indexing scans at most
four lines per step, retains up to 256 names of at most 31 bytes and distinguishes
names such as `A` and `AB`. Incomplete procedures cannot fold. Folding hides the
body and ENDPROC while retaining the PROC line. Navigation or a revealed caret
unfolds its destination. Source edits invalidate folds and restart indexing;
folding does not change saved bytes, selection offsets or document generations.

## Check, Run, Stop and Build

The Program menu selects floating point by default. Its Integer mode checkmark
selects FBI for Run and FBCI for Check/Build; default Run uses FB and Check/Build
use FBC. Run interprets the unsaved document. Check compiles without executing;
Build chooses a destination for a standalone release COM.
The command has no dependency on the editor or compiler after publication.
Source debugging and native graphics remain pending. Check/Build use a fresh
standalone scope; define any bindings that were supplied by an earlier Run
before compiling that source on its own.

A job freezes source edits, New, Open and replacement while retaining the caret,
selection and viewport. Save and Save As may serialize the same document during
a running program. Check/Build retain the project directory selected at job admission. The
interpreter keeps the directory chosen when its Process first starts; later
Save As/Open and Restart do not change that Process directory. Changing numeric
mode or reopening BASIC starts a new session using the current project directory.
Unsaved buffers initially inherit the application's directory. Source files need not be saved to
Run.

The first Run loads FB/FBI cooperatively and starts a persistent interpreter
Process. Later Run requests use that same Process and bank, attaching an
immutable snapshot until the request's completion reply. Values, strings,
arrays, modes and open channels survive END, Stop and recoverable errors.
Source is parsed again with stable bindings; a parse failure runs no partial
program. No source/COM/diagnostic scratch files or compiler Process are used.
Version, job/source generation and completion records must match before an
error location is selected.

Program → Restart interpreter closes channels and resets BASIC state in the
same Process. It leaves the source document and output contents in place.
Changing Integer mode shuts down the old session and selects a fresh engine for
the next Run. New/Open do not implicitly reset the interpreter. Quit keeps the
session through a canceled unsaved-document query; final application teardown
sends QUIT and collects it. Idle state retains a Task and one shared guest slot.
Check/Build can use the other guest slot. Their complete argument list and NIL
input let them compile without taking the idle interpreter's console keyboard. See the
[session contract](fastbasic.md#persistent-interpreter-sessions) for workspace,
DIM and type-change rules.

Check/Build copy an immutable ATASCII snapshot and exclusively reserve three RAM
scratch names. The eight-character stem encodes the full nonzero 32-bit identity,
using A–P for its high nibble so the name starts with a letter. Existing names
are preserved, including collisions after partial reservation. A successful
compiler Process, matching complete `FBD1` diagnostic, unchanged source generation
and freshly validated COM are all required. A failed or stopped job never runs
an earlier command. Compiler execution and Image references retire before the
program is loaded. One child runs at a time.

A source/parser or compiler error selects the reported byte and reveals its line, including
folded procedures. Other completions restore the retained caret, selection and
viewport. Native errors and both child results remain distinct; an earlier cause
survives cleanup failures. Ordinary BASIC handled ERR behavior is unchanged.
Runtime source locations require the later debugger slices.

The application creates one 64×20 output console on demand. Select it to enter
INPUT/GET/KEY; select the source to edit or use shortcuts. Stop, output close and
Quit request cancellation without releasing a live child's resources. Quit waits
for the active request to finish before asking about unsaved source. Closing output retains its
contents for Program → Output or the next job. Run completion uses the reply-port signal in the public combined AES/Exec wait,
without a child-poll timer.

Loading stages perform one DOS operation per turn, with reads bounded to 1 KiB,
through the public cooperative program loader. Build copies binary bytes through
the same checked Close, exclusive temporary and no-replace Rename protocol as
source Save. It does not mark the source saved. This replacement is not atomic;
retained temporary/backup names are recovery copies. Scratch cleanup warnings
also retain their paths. File → Recovery paths prints build recovery paths into
the output window. Only owned scratch is removed, after all its users retire.
