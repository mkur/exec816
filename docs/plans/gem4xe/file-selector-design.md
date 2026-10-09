# Standard GEM file selector

[GEM integration](README.md) · [Implementation plan](file-selector-implementation-plan.md)

Status: FSEL1 shared helpers pass development checks. FSEL2–FSEL4 remain
pending; see the [execution record](../../history/file-selector.md).

Add `fsel_input` and `fsel_exinput` as synchronous, caller-local AES routines.
Reuse Files' bounded directory snapshot, viewport and path handling, and the
existing standard-dialog host and editable TEDINFO support. Applications gain
a conventional file chooser without embedding Files or running another Task.

The selector returns a directory/filter and a filename. It does not open,
create, truncate, rename or launch anything. Open and Save use the same call;
the application supplies the title, interprets the selection, checks existence
and confirms overwrites where appropriate. A successful selection is not a
promise that a subsequent filesystem operation will succeed.

## Public interface

Provide the named bindings and equivalent AES parameter-block dispatch:

```c
WORD fsel_input(char *path, char *file, WORD *button);
WORD fsel_exinput(char *path, char *file, WORD *button, const char *title);
```

| Call | Opcode | Counts: integer in/out, address in/out |
| --- | --- | --- |
| `fsel_input` | 90 | 0/2/2/0 |
| `fsel_exinput` | 91 | 0/2/3/0 |

`intout[0]` is the function result; `intout[1]` is the button. The input address
slots hold path, filename and, for opcode 91, title. There are no output address
slots. Use the donor signatures/counts and `FSEL_CANCEL=0`, `FSEL_OK=1`.

The caller supplies a writable 128-byte path buffer and a writable 13-byte
filename buffer, including their terminators. `path` includes the directory
and final filename filter; `file` contains only the selected leaf name.
`fsel_input` uses the caption File selector; `fsel_exinput` displays up to 30
characters of its supplied title. Copy these inputs into private session storage
before drawing or entering nested AES calls.

| Completion | Function result | Button | Diagnostic and outputs |
| --- | --- | --- | --- |
| OK | 1 | 1 | `AES_OK`; directory/filter and literal filename |
| Cancel, Escape or temporary-host closer | 1 | 0 | `AES_OK`; current bounded path and filename fields |
| Application-policy event interrupts the call | 0 | 0 | `AES_PENDING`; original caller buffers unchanged |
| Admission or operational failure | 0 | 0 | Existing AES error diagnostic; original caller buffers unchanged |

Set the button to Cancel at entry. Publish path/filename changes only after
successful host cleanup. Returning edited fields on normal Cancel follows the
donor; the application must inspect the button before using them as a selection.
Cancel does not require those fields to describe an existing directory or a
valid filename. Failure is distinct from normal cancellation.

Correct pointer lifetimes and buffer capacities are caller responsibilities.
Check lengths, path composition and resource availability at admission or when
the user commits an edit. Keep normal filesystem errors and synchronization;
do not repeat tree, pointer or request validation through each wrapper and draw.

## Paths, filters and selection

Use the current [Exec DOS namespace](../../reference/dos.md): for example
`SYS:*.TXT`, `SYS:DOCS/*.*` or an existing assign such as `WORK:*.C`. Separate
components with `/`. An empty initial path becomes `SYS:*.*`; a prefix root or
path ending in `/` acquires `*.*`. Otherwise the final component is the filter.
Only that component may contain wildcards. Keep the directory and filter
separate internally, and recombine them within the 127-character output limit.

Do not introduce an `A:` through `P:` drive mapping or translate GEMDOS
backslashes in this slice. Exec already gives prefixes their own meaning,
including the `C:` command assign. Ports retain the conventional AES call and
buffer contract but must supply Exec paths. This is rebuilt source support,
not GEMDOS or GEM binary compatibility.

Use GEM-style 8.3 `*`/`?` matching, with separate basename/extension matching
and ASCII case folding. Base the small matcher on the pinned donor's
`dos_wildcmp`, including trailing wildcard behavior; `*.*` must include names
without an extension. Directories remain visible regardless of the filter.
The filter limits the list, not which literal filename may be typed for Save.
Do not append an extension automatically or accept wildcards in the final
selected filename.

The first profile uses the filesystem's existing 8.3 leaf-name rules. OK requires
a successfully enumerated directory and a nonempty, representable literal leaf;
that leaf need not exist. A selected directory navigates instead of completing
the call. Overlong paths or names produce a visible error, never a silently
truncated selection. The application combines the returned directory and leaf
when it performs its own Open or Save.

Up stops at the current logical prefix root, retaining the filter. Editing the
prefix provides access to other mounted devices or assigns; there is no new
drive registry or drive-button grid. Navigation never changes the Task's
current directory. A namespace change after enumeration is an ordinary race
for the later filesystem operation to report.

## Reuse and directory lifetime

Extract small project-internal routines from
[Files](../../../examples/gem-browser/browser.c): directory enumeration,
path joining/parent handling, viewport clamping and selection visibility.
Files and the binding share those routines and the entry representation.
Keep Files' event loop, menus, launcher, child collection and mutation dialogs
in Files. Do not introduce a generic browser framework, a public utility ABI
or a dependency on `DESKTOP.RSC` for the selector.

Retain the [Files snapshot](files-scrolling-design.md) limit of 256 raw directory
entries and at most sixteen reusable row objects. Store a small array of
matching entry indices rather than copying the snapshot for each filter.
Enumerate with `Lock`, `Examine` and `ExNext`, then `UnLock`; retain no directory
lock while waiting for user input. Open, navigation and Refresh perform I/O.
Scrolling, selecting and changing only the filter use the existing snapshot.

Keep enumeration order initially. Read at most one entry beyond the capacity
to detect truncation, and report that only the first 256 directory entries were
searched. Do not scan an unbounded directory to find 256 matching files. Refresh
preserves selection by exact filename when it remains present; changing
directories clears row selection but may retain the typed Save filename.

Use one entry allocation. If opening or examining a proposed directory fails,
retain the previous valid view and show the error. If enumeration fails after
overwriting that array, clear the list, mark it unavailable and allow retry,
path editing or Cancel. Never display a partial read as a complete directory,
or an old list under a newly committed path. Initial path errors leave the
selector open for correction. Capture `IoErr` before other DOS calls overwrite
it and show a bounded status message.

Draw a loading status before enumeration, without holding UPDATE over disk I/O.
Other Tasks continue running, but the selector cannot cancel an in-flight
synchronous DOS request. Between entries, service already-pending interruption
or cancellation using the existing event readiness path; release the directory
lock before any wait for fresh input. There is no new worker or polling timer.

## Dialog and interaction

Build one private compiled OBJECT tree using existing boxes, strings, buttons
and two editable TEDINFO fields. Provide a caption, Path/filter, Filename, Up,
Refresh, directory rows, a status line, line/page scrolling and OK/Cancel.
Keep the tree within the current 32-object limit. Adapt the row count and field
viewports to the host; target a compact 208-by-128-pixel work area
as the minimum useful layout. Larger hosts expose more rows and path text.

Reuse the [standard-dialog host](standard-dialogs-design.md). Borrow a shown
application window, or create a temporary NAME/CLOSER/MOVER window when the
application has no allocated window. Preserve the borrowed window's geometry,
kind, title, menu, workstation attributes and frame scrollbar state. A closed
allocated window, existing form/editor session or caller-held UPDATE/MCTRL
returns `AES_BUSY`; insufficient space or a full four-window desktop returns
`AES_RESOURCE` before painting. The selector cannot be nested in `form_do`.
As with the other caller-local dialogs, ports must remove classic wrappers
that hold MCTRL across the entire call; input routing already identifies the
owning application, and a desktop-wide lock would prevent useful concurrency.

Put line/page scroll buttons inside the selector, using Files' viewport math.
Its content controls do not take ownership of a borrowed window's frame
scrollbar. Thumb dragging, double-click activation, hold-to-repeat, resizing
the temporary host, folder creation and rename are deferred. This keeps the
first chooser within the existing OBJECT/input contract.

Clicking a file fills the filename field; clicking a directory enters it.
Keyboard selection exposes the selected row; Return on a directory enters it,
and Return on a file accepts it. Tab/Shift-Tab moves through fields, list and
buttons. Return in Path applies the directory/filter edit; Return in Filename
or on OK accepts the candidate. Before acceptance, apply any uncommitted path
edit. Escape first cancels an active press, otherwise dismisses the selector.
Buttons activate on release inside; outside release or input loss cancels the
press. Page buttons remain keyboard-accessible through focus and activation.

Use a small selector-specific loop over the existing key/button/message wait
and editing routines. Share private host-message and press/edit helpers where
needed; do not add a callback framework or restart `form_do` on every row click.
Initial paint and exposure repair draw the work area; ordinary edits and
selection changes redraw affected fields/rows, and scrolling redraws the list.
All drawing uses existing visible rectangles and short UPDATE sections. Keep
disk scans, allocation and wildcard matching outside the drawing path.

## Messages and cleanup

Follow the existing dialog interruption contract. Service live host redraw and
focus events internally. Handle movement of a temporary host locally and its
closer as Cancel. Borrowed-window move/size/scroll/close requests, menu commands
and ordinary application messages belong to the application: retain the exact
message and existing epoch metadata, unwind the selector, and return
`AES_PENDING`. An ordinary message resembling `WM_REDRAW` is still opaque.

Use the existing deferred-message slot and borrowed-content repair fact. The
retained application message is returned first, repair follows, and later
queued messages retain their order. Do not send a self-message to request
repair or add a second event queue. The application's event loop handles the
interruption and may invoke the selector again.

Attach private selector storage to the existing upper-memory form session so
that cleanup retry and `appl_exit` can retire it. End editing and presses, release
owned DOS locks, finish the host and free storage in the established order.
If retirement fails, retain referenced tree/text storage until retry or exit;
do not leave pointers into automatic locals. Close only an internally opened
workstation and window. Never detach the caller's DOS context or close its
pre-existing file handles and locks.

## Cost and compatibility boundaries

The existing 112-byte entry representation costs 28,672 bytes for 256 entries;
a WORD index per entry adds 512 bytes. Tree, fields, labels, FileInfoBlock and
session bookkeeping also live in upper RAM. Measure the final per-selector
allocation, shared component growth and cleanup baseline during implementation.
Two applications may run independent selectors subject to existing heap/window
capacity; there is no shared mutable selection state.

Target bank-zero reservation delta: **0 fixed, 0 per public Task and 0 private
idle**, including guards, alignment and unused capacity. Avoid large automatic
arrays. Measure emitted-code stack use against the existing ordinary-task
headroom target; a justified small stack increase is preferable to a major
refactor solely to save stack. Report any resulting reservation change rather
than silently consuming the remaining headroom.

Add the exports through the existing generated C component interface and
advance its ABI revision, rebuilding consumers together. Record donor API
inputs in the binding manifest. No AES server wire operation, Exec gateway
operation, priority change or timer extension is needed. Preserve the donor
and third-party notices for any adapted matcher or UI code.

## Evidence required before claiming support

Use development checks with focused emitted-code and packaged-desktop cases:

- Named calls and AESPB agree on counts, buffers and outcomes. Cover normal
  Cancel versus failure/interruption, maximum lengths, buffer canaries, literal
  Save candidates and unchanged outputs after failed cleanup. Use focused raw
  and optimized probes for new ABI/bridge behavior.
- Exercise empty, missing, multi-page, filtered and truncated directories,
  extensionless names, case folding, navigation limits, refresh/removal and
  read errors. Verify scrolling/filter-only changes cause no disk enumeration
  and the selector performs no filesystem writes.
- Test keyboard and physical pointer editing/selection, line/page scrolling,
  outside release, input loss, overlap repair, borrowed and temporary hosts,
  fit/capacity failure and two independent callers. Keep shell/counter activity
  running during disk work; record the selector's cancellation limits.
- Check policy interruption and exact message ordering, including an ordinary
  WM-shaped message and a full application queue. Exercise cooperative Stop,
  cleanup retry, relaunch and `appl_exit`; preserve caller-owned DOS resources.
  Compare warmed-call heap baselines separately from first-use DOS setup, and
  check complete process retirement and ordinary-stack margins.
- Keep Files navigation, scrolling, editing and launching working after helper
  extraction. Extend a small loadable example to demonstrate Open and Save
  selection without requiring a full editor. Validate the exact OF816 demo ZIP
  with its pinned ROM and five-second shell/prime autoboot.

These are acceptance requirements for the future implementation, not test
results or hardware qualification. Update the public AES reference, application
guide and execution record only when the corresponding behavior exists.

## Sources

The API shape and Cancel behavior come from GEM4XE's pinned
[binding](https://github.com/slaapliedje/gem4xe/blob/e413c39d2f8e1bec8fe16596f610b923de4a0ae9/src/app/gemlib.c)
and [selector](https://github.com/slaapliedje/gem4xe/blob/e413c39d2f8e1bec8fe16596f610b923de4a0ae9/src/aes/fsel.c).
Use its small
[wildcard routine](https://github.com/slaapliedje/gem4xe/blob/e413c39d2f8e1bec8fe16596f610b923de4a0ae9/src/sys/dos.c)
as the matching reference, not the donor's global CIO/browser lifecycle.
The [GEM file-selector reference](https://freemint.github.io/tos.hyp/en/fsel.html)
documents classic buffer capacities, title length and call results. Exec path,
host and interruption rules above are explicit adaptations to the current
multitasking profile.
