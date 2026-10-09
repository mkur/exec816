# GEM text viewer

[GEM integration](README.md) · [Implementation plan](text-viewer-implementation-plan.md) ·
[Open roadmap](../../roadmap.md)

Status: TV1–TV2 pass development checks; TV3–TV4 are in progress.
See the [execution record](../../history/text-viewer.md).

Add a small loadable `C:TEXT.APP` that opens text through the standard file
selector and displays it in a resizable GEM window. This supplies a useful
application for the complete select → DOS read → VDI draw → scroll/resize
path, including exposure repair beside the shell and other applications.

Build the viewer first, then let Files open `.TXT` documents with it. Keep
document state and rendering in the application. Existing AES, VDI, DOS and
Process services provide the required mechanisms; no new GUI server operation,
worker Task, scheduler policy or timer mechanism is needed.

## Application and interaction

Use one Process, one application-owned model, one virtual workstation and one
`NAME|CLOSER|MOVER|SIZER|UPARROW|DNARROW|VSLIDE` window. Ship the application on
disk and launch it on demand; do not add another startup application or enlarge
the four-window desktop limit. Keep the normal shell, counter and Control Panel
startup behavior. A full desktop reports the existing capacity failure.

With no argument, open an empty viewer showing a brief Open instruction. Provide
a compiled File menu with Open, Cancel Load and Quit. Open uses
`fsel_exinput(path, file, &button, "Open text")`, initially `SYS:*.TXT`; retain
the last selector fields for the next use. Cancel Load is enabled only while
loading, and Open is disabled during that interval. The closer and Quit always
request application exit.

Use O for Open, Q for Quit, Up/Down for one line, Space/Shift-Space for one page
and Escape to cancel loading. Page actions are also available through the
vertical track. Keep shortcuts within the existing translated keyboard profile;
additional key mappings are not a prerequisite. Document scrolling has no
selection, editing, double-click action or button capture of its own.

The title identifies the committed filename. A small status row shows the
visible line range and total, or a loading/error message. Longer display labels
may be shortened to fit; stored paths and file contents must never be silently
truncated. Empty files are valid and show an empty-document status.

Keep the minimum work area at least 208×128 so that the borrowed file selector
fits even after resizing. Derive outer minimum dimensions with `wind_calc` and
the current window kind. Do not duplicate frame-inset constants in the viewer.

## Document representation and text rules

The first profile accepts regular disk files of at most **65,536 bytes** and
**4,096 logical lines**. These bounds cover demo documents and modest source or
log files while keeping one raw-data allocation inside a bank. Reject files
above either bound with a visible explanation; do not present an incomplete
prefix as a successfully loaded document. Larger-file streaming is later work.

Keep the raw bytes unchanged in upper RAM and build an array of 32-bit line
start offsets with a final end offset. Byte counts and offsets must represent
65,536; line counts and viewport rows fit in 16 bits. Parsing occurs only during
loading. Scrolling indexes directly into this array and performs no DOS I/O.

Use these explicit display rules:

| Input | Display behavior |
| --- | --- |
| LF, standalone CR, CRLF, ATASCII `$9B` | End a logical line; CRLF counts once, including across read boundaries. |
| Final unterminated content | One final line. A trailing terminator does not add another empty line. |
| Empty input | Zero logical lines and a blank document area. Consecutive terminators still represent blank lines. |
| Printable ASCII `$20–$7E` | Render using the existing fixed 8×8 font. |
| Tab | Spaces to the next eight-column stop, measured from the line start. |
| Other bytes, including NUL and high-bit characters | One visible dot; never treat them as a string terminator or an escape command. |

This is a bounded ASCII/ATASCII-line-ending text view, not full ATASCII or
Unicode decoding. It follows the useful byte-display convention of
[TYPE](../../guides/shell.md), with explicit standalone-CR and CRLF handling.

Do not wrap lines in this version. Clip at the right edge; making the window
wider reveals more columns. Resize changes the visible row/column count, not
the line index. Keep an upper-memory row buffer sized for the screen's maximum
80 columns plus NUL. Expand only the visible prefix and pad its remaining cells
with spaces; drawing a very long line must not scan its hidden suffix.

## Loading, cancellation and replacement

Use the current [DOS calls](../../reference/dos.md): `Lock`/`Examine` to reject
directories and obtain a size hint, then release the lock and `Open` with
`MODE_OLDFILE`. Metadata is a hint, not proof of a later successful read. No
current-directory mutation, writable Open or persistent directory lock is needed.

Load into a candidate document while retaining the committed document, its
filename and scroll position. Allocate the candidate's byte buffer and index
before reading. Read at most **1 KiB per work unit**, indexing that returned
chunk once and carrying CRLF state across chunks. At the byte limit, use a
one-byte EOF probe outside the full buffer to distinguish an exact fit from an
oversized file. The line-limit check also waits for actual next-line content
or a terminator rather than inventing an extra line after the final delimiter.

Check both the returned count and `IoErr`, following DOS partial-transfer rules.
Do not treat a short read with an error as EOF. Save the causal error before
cleanup. A read error, allocation failure, excessive size/line count or Cancel
discards only the candidate. Close the read handle before publishing success;
a terminal Close error also leaves the old document intact. Commit by replacing
the model and resetting the top line to zero, then free the old allocations.
No text buffer needs a terminator; all parsing uses the counted byte length.

Show Loading before the first filesystem operation. Between load units, service
window messages, keys and pending paints through the same event loop. While
work remains, use public `evnt_multi` with `MU_MESAG|MU_KEYBD|MU_TIMER` and zero
timer duration. The [existing event contract](../../reference/aes.md) makes this
an immediate readiness check without submitting an alarm; it still has binding
and clock-query cost, so poll once per bounded unit, not once per byte. When
idle, omit `MU_TIMER` and block normally. Do not call private selector polling
helpers from the application or introduce a periodic polling timer.

Escape and Cancel Load preserve the current document. Quit, the closer or an
owned Process Stop cancels the candidate and exits. Movement, resizing, focus
and redraw requests continue to be handled during loading; the old document
can still scroll. Cancellation takes effect between synchronous DOS operations:
an in-flight Open, metadata call, Read or Close must finish first. Other Tasks
continue running, but this design does not promise a millisecond bound on disk
request completion. Input loss discards stale input, cancels the candidate and
returns to the normal event loop. Avoid nested selectors or alerts during a load;
use the status row for recoverable errors.

## Selector return and application messages

The selector temporarily borrows this window's work area. A normal Cancel may
update its path/filename fields but must not change the loaded document. On OK,
replace the path's final filter with the selected leaf using a bounded path
join, then start loading. Keep selector fields separate from the committed
document path. Permit up to 127 path bytes plus NUL, and report an overlong
combination rather than truncating it.

Follow the [selector contract](../../reference/aes.md#file-selector) on
`AES_PENDING`: resume the event loop, handle the retained policy message first,
then reconstruct the viewer through the following repair request. Do not reopen
the selector automatically, begin loading from unchanged buffers, or repaint
ahead of that retained message. Keep the document model available throughout
the call so cancellation, movement and exposure can restore it without a saved
screen image. Normal selector failure leaves the document intact.

## Scrolling and painting

Handle `WM_MOVED`, `WM_SIZED`, `WM_TOPPED`, `WM_CLOSED`, `WM_VSLID`,
`WM_ARROWED`, `WM_REDRAW` and `MN_SELECTED` through the existing contracts.
Keep the top logical line on resize, clamped to
`max(0, line_count - visible_rows)`. Publish `WF_VSLIDE` and `WF_VSLSIZE` on
document, viewport or scroll changes. Use widened arithmetic for the 0–1000
mapping; calculate it once per state change, outside the row/glyph loop. A
document that fits has position zero and size 1000. Ignore scrolls that leave
the clamped position unchanged.

Use only resident `v_gtext`, `v_bar`, colour setters and `vs_clip` from the
[VDI profile](../../reference/gem-vdi.md#resident-application-workstations).
Draw baseline coordinates from that profile and obtain cell metrics through
`graf_handle`. Intersect damage with the work area and the current
`WF_FIRSTXYWH`/`WF_NEXTXYWH` visible rectangles under `BEG_UPDATE`. Respect
half-open rectangle geometry when converting to VDI inclusive corners.

Paint in bands of at most **four text rows** per UPDATE section, then release
ownership and service events. Enumerate visible rectangles anew for each band;
do not retain an iterator across UPDATE release, movement or resize. A small
application-local pending-damage rectangle and row cursor suffice. New damage
must merge with all unfinished damage; geometry, document or scroll changes
restart painting from the current model. Consume a band's damage even when it
is completely covered, because a later exposure produces another redraw.

Render padded text rows directly in replace mode and clear only uncovered
margins, blank rows and the status background. Avoid a whole-page white clear
followed by text, which lengthens visible blank intervals. Exposure draws only
intersecting rows; scrolling redraws the visible document from RAM. Update the
status only when its displayed content changes. Do not add screen-copy, offscreen
bitmap or retained VRAM caches in this slice. Record repaint time and visible
flicker before considering a new rendering primitive.

## Startup path and Files integration

The standalone viewer accepts zero or one filename through
`ExecGetArgStr()`, which already exposes the Process-owned argument tail.
Use a small bounded one-path parser: whitespace separators, optional surrounding
double quotes, no switches and no extra arguments. Preserve the spelling passed
to DOS; shell-relative paths use inherited current-directory semantics. Open
the window before loading the argument so early Stop and load errors follow
the normal event loop. Invalid arguments produce a visible error without
opening a file. Keep parsing local; no `argc`/`argv` framework is required.

Files integration follows the standalone viewer. Today
[`ExecStartProgram`](../../../c/include/exec816/program.h) accepts only a program
name and starts with empty arguments. Extend that one current entry point to
accept an argument pointer and explicit byte length, using the existing
[Process argument-copy contract](../../reference/process.md). Update all
callers together; empty launches pass null/zero. Advance the C component ABI
and rebuild GEMSYS and its applications. Keep native Process/kernel ABIs
unchanged if the existing argument path suffices; do not pass an application
pointer by an AES message after launch or keep an obsolete launcher profile.

On Open, Files navigates directories as before, launches `.TXT` files through
`C:TEXT.APP` with the selected path, and preserves existing program launch
behavior for other files. Match the extension without case sensitivity and
quote the path according to the viewer's one-path syntax. Apply the viewer's
path limit before launch. This is one explicit association, not a registry,
desktop icon system or generic plugin mechanism. Other text extensions remain
accessible through the viewer's selector or a shell launch.

Files retains its one-child limit and owns Stop, completion collection and
error reporting. Do not add a child-completion timer or change its existing
collection policy as part of this work. Test a missing `TEXT.APP`, unavailable
Task/window capacity and a child that exits during loading. The viewer owns
only its file handles and allocations; Process teardown continues to own the
DOS context, so the application must not call `ExecDOSDetach`.

## Resource budget and compatibility

One maximum document uses 65,536 raw bytes and 4,097 four-byte offsets: **81,924
payload bytes**, or **81,928 bytes** after eight-byte heap rounding with
`AllocMem`. Replacement peaks at **163,856 reserved upper bytes** for the old
and candidate allocations, plus the small application model. Allocate the
buffer and index separately with the normal upper-memory bank-contained mode;
no cross-bank buffer abstraction is necessary. The file selector adds its
existing temporary allocation while the committed document remains live, but
retires before candidate allocation. Record actual model, image, workstation,
selector and peak heap costs in the implementation evidence.

Target reserved bank-zero delta: **0 fixed bytes, 0 per public Task and 0 for
private idle**, including guards, alignment and unused pool capacity. Launching
uses an existing Task slot and DP. Keep the file/index, menus, message arrays,
path fields and row scratch in upper-memory application storage, not large
automatic locals. No VRAM reservation is added.

The [current platform budget](../../reference/platform.md#bank-zero-memory-budget)
has 1,312-byte ordinary stacks. The latest
[file-selector run](../../history/file-selector.md) leaves 139 bytes above the
ordinary interrupt floor against a 128-byte target; that is not evidence for
the viewer's new call chains. Measure its selector, load, redraw, error and
shutdown paths. A small justified stack increase remains an option if needed;
report its full reservation cost and placement rather than forcing a broad
refactor or reducing guards.

No new AES/VDI interface is planned. Keep correct pointers, handles and model
state as caller responsibilities. Check user-input bounds and ordinary resource
or filesystem failures once at their owning boundary, not repeatedly at each
draw. This remains rebuilt GEM source support over Exec DOS, not GEMDOS binary
compatibility.

## Evidence before acceptance

Use the [development tier](../../contributing/testing.md), with focused optimized
emitted-code tests and an exact packaged desktop walkthrough:

- Test empty input, all line endings, CRLF split between reads, tabs at viewport
  edges, embedded NUL/high bytes, long clipped lines and final unterminated text.
  Check both exact limits and one-byte/one-line overflow, with canaries around
  document/index/row storage and a pixel oracle independent of the parser.
- Exercise allocation, metadata, Open, Read and Close errors; partial transfers
  with errors; and cancellation between load units. Preserve the old document
  and scroll position on every failed replacement. Verify no writes and no file
  reads during scroll, resize or exposure.
- Use physical input for selector acceptance/Cancel/interruption, menu and
  keyboard scrolling, thumb endpoints, minimum/maximum resize and overlapping
  windows. Check damage arriving during a partial paint and model changes before
  paint completion. Observe input during disk reads as well as idle viewing.
- Run shell, counter and Control Panel alongside the viewer. For Files launch
  tests, close another application to respect the four-window limit. Cover
  launch arguments, capacity failures, Stop while loading, repeated launch/close,
  complete child collection, warmed heap return and existing OS restoration.
- Record ordinary-stack headroom, guards, resident/image/upper-memory costs,
  load completion and repaint latency. Raw/optimized tests are required for the
  changed launcher ABI and any compiler-facing layout, not duplicate desktop
  walkthroughs. Do not claim HY4/PI4 closure from these functional checks.
- Package with `tools/build_demo.py`, retaining OF816, the pinned ROM, notices,
  five-second shell/prime autoboot and the normal distribution contents. Include
  the viewer and suitable text fixtures; run the extracted exact ZIP.

These are requirements for future work, not executable results or hardware
qualification. Editing, Save/overwrite, search, selection/clipboard, wrapping,
horizontal scrolling, font choice, streaming large files and automatic reload
remain outside this first viewer.
