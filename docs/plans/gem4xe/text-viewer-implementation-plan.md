# GEM text viewer implementation plan

[Design note](text-viewer-design.md) · [GEM integration](README.md) ·
[Open roadmap](../../roadmap.md)

Status: TV1 passes development checks; TV2–TV4 are in progress.
See the [execution record](../../history/text-viewer.md).

Implement the design in four executable slices. Keep document storage and
painting application-owned, use the existing AES/VDI/DOS calls, and leave the
normal desktop startup set unchanged. The standalone viewer must work before
Files gains argument-bearing launches. Commit each slice after its development
gate passes, recording the actual tests and resource costs.

## Sequence

| Slice | Executable result | Development gate |
| --- | --- | --- |
| TV1 | Bounded document loader, line index and row formatting exercised by an emitted fixture | Text boundaries, real DOS reads, failed replacement/cancellation and allocation return |
| TV2 | Loadable `TEXT.APP` with Open, startup path, resize/scroll and incremental drawing | Physical interaction, pixels, selector interruption, loaded coexistence and stack headroom |
| TV3 | Files opens `.TXT` through the current launcher with copied arguments | C/native ABI probe, argument lifetime, unchanged program launches and child collection |
| TV4 | Documented viewer and Files workflow in the normal OF816 demo ZIP | Exact-package walkthrough, resource return, guards and recorded repaint behavior |

TV1 uses the real application document code in a test fixture. TV2 publishes a
complete standalone application; do not install menu stubs or require the
launcher change before it can open a file. No separate baseline project or full
latency campaign is needed before starting these slices.

## TV1 Bounded document storage and loading

Add the small application module under `examples/gem-text`, with a private
header and a document implementation separate from the window loop. Use a
concrete document record and begin/step/cancel/dispose routines. Avoid a generic
document interface, stream cache, callback framework or reusable job scheduler.

1. Store a counted raw byte buffer, a 32-bit line-offset array with end sentinel,
   byte/line counts and the few incremental parsing fields. Use the design's
   65,536-byte and 4,096-line limits. Allocate byte and index storage separately
   in upper RAM; retain original sizes for freeing. Keep the one-byte EOF probe
   and 81-byte display-row scratch outside the full raw buffer.
2. Implement LF, CR, CRLF and ATASCII `$9B` line boundaries, including split CRLF,
   empty input, consecutive delimiters and an unterminated last line. A trailing
   delimiter must not manufacture a further line. Use counted bytes throughout;
   a NUL byte is content. Check the limits when admitting additional content,
   not repeatedly while drawing.
3. Format only a requested visible row prefix: printable ASCII, eight-column
   tab stops, dots for other bytes, space padding and a final NUL. Stop at the
   viewport width without walking a long line's hidden suffix. Keep file offsets
   wide enough for 65,536 and avoid division in the byte/glyph loop.
4. Implement metadata/type admission, read-only Open and reads of at most 1 KiB
   per step. Index each returned chunk once and probe EOF at the exact byte
   limit. Follow the current DOS count/`IoErr` rules, including positive prefixes
   with errors and buffer contents modified by a failed read. Metadata is only
   a hint; success depends on the reads and final Close.
5. Keep a candidate separate from the committed document. Failure or cancellation
   closes owned resources and frees the candidate; success closes first, then
   swaps the model and frees the old allocations. Retain causal errors through
   cleanup, preserve the old filename/top line on failure, and reset top line
   only after a successful replacement. Close handles according to their actual
   consumption contract; never retry a consumed terminal-error handle.

Add an optimized emitted fixture using the same document source, with real DOS
files plus focused injected operation/allocation failures. No GUI is required
for this first gate. Test empty/one-line files, each delimiter, CRLF split at
the read boundary, tabs, embedded NUL/high bytes, long clipped lines and exact
limits followed by one-byte/one-line overflow. Verify the end offset at 65,536,
unchanged raw bytes, independently expected rows and no out-of-bounds writes.

Exercise failure at each acquired resource, a read error after a successful
prefix, Close failure, cancellation before/after a chunk and repeated successful
replacement. Require old-document preservation, no writes, no reads from row
formatting and complete owned-resource return. Preserve exact binary/ATASCII
fixtures rather than normalizing their bytes. Add a small raw/optimized layout
probe only where a host observer or language bridge relies on record layout.

Resource record: one maximum document reserves **81,928 upper bytes**, and old
plus candidate reserve **163,856**, before model/scratch and DOS setup. Report
actual rounded allocations and code/data sizes. Reserved bank-zero target is
**0 fixed, 0 per public Task and 0 private idle**; no VRAM change.

## TV2 Standalone GEM viewer

Add `main.c`, the application model and window loop under `examples/gem-text`.
Build through [the existing APP packer](../../../tools/build_c_program.py),
including its relocation verification. Keep the document implementation in
`TEXT.APP`, not GEMSYS. Use compiled menu objects; no new RSC file or AES/VDI
export is needed.

Open one resizable, vertically scrollable window and one private workstation.
Derive outer minimum geometry through `wind_calc` so the work area remains at
least 208×128. Obtain cell metrics from `graf_handle`; keep title, status, menu,
message, path and row storage in the upper-memory model. An empty launch shows
the Open instruction. Parse zero or one startup path from `ExecGetArgStr`,
including the design's quoted form and 127-byte path bound; open the window
before starting I/O. Invalid arguments leave a usable window with an error.

Implement the complete application workflow:

- File menu Open, Cancel Load and Quit, plus O/Q, Up/Down, Space/Shift-Space and
  Escape. Reflect loading state in menu enablement. Handle the existing window,
  scroll and menu messages, including `menu_tnormal` after accepted menu policy.
- `fsel_exinput` with separate retained selector fields and committed document
  path. Reuse the small existing path helper source where useful without adding
  public exports or copying the browser. On normal Cancel preserve the document;
  on OK join the directory and leaf once and schedule loading. On `AES_PENDING`,
  resume policy delivery before repair and never reopen or load automatically.
- Show Loading before filesystem work. Between at most one load step or one
  paint band, use zero-duration `evnt_multi` to service messages/keys. While both
  loading and painting need progress, alternate their work units so neither
  starves the other; process cancellation before starting the next unit. When
  there is no pending work, omit `MU_TIMER` and block normally. Reuse the public
  binding, accepting its clock-query cost; add no private polling API or alarm.
- Continue move, resize, focus, old-document scrolling and exposure during
  loading. Escape/Cancel Load or input loss discards the candidate. Quit,
  `WM_CLOSED` and cooperative Process Stop close the application after owned
  I/O settles. No draw lock, MCTRL or Forbid may span DOS I/O, allocation or an
  event wait. Cancellation cannot interrupt a synchronous DOS call in progress.
- Clamp top line after scrolling/resizing, preserve logical position on resize,
  and set the 0–1000 slider values only when their model changes. Use widened
  arithmetic once per viewport change. Fitting and empty documents have a full
  thumb at zero; a no-op scroll should not trigger a content repaint.

Implement the design's pending-damage rectangle and paint cursor directly in
the viewer. Each UPDATE section draws at most four text rows, using fresh
visible rectangles and clipping against damage/work bounds. Merge new damage
with unfinished work; restart from the current model after move, resize,
scroll or document replacement. Covered bands retire normally and later
exposure repairs them. Release UPDATE on every path, including draw failure.

Draw padded text in replace mode; clear only necessary margins, blank rows and
status background. Handle bottom partial-row pixels and an empty document.
Do not clear the whole page before drawing its text or add a backing bitmap,
VRAM cache or screen-copy primitive. Repaint the status only when it changes.

Finish application-owned resources through the established window/workstation/
menu lifetime. Keep referenced menu/model storage valid through AES retirement;
the existing Process wrapper retains the image if teardown cannot complete.
Free document allocations and close file handles on startup failure and normal
exit. Do not detach the Process-owned DOS context.

Development gate: run a loadable viewer from the shell with no path, a literal
path and a quoted path. Use real keyboard/pointer input for Open/Cancel,
selector policy interruption, line/page/thumb scrolling, resize limits and
closing. Compare initial, scrolled, resized, overlapped and selector-repaired
pixels against independent fixture expectations. Inject new damage and model
changes between paint bands; check that no stale row or uncovered margin remains.

Check Stop/input loss during loading, missing files, failed replacement and
startup/window/workstation capacity failures. Verify keyboard delivery during
DOS work, peer shell/counter progress, no I/O on repaint/scroll, no timer alarm
for zero-duration polls and no idle busy loop. Record maximum read-unit bytes
and rows per UPDATE, ordinary-stack margins, guards and warmed resource return.
Use checked observation offsets and a focused raw/optimized layout probe if
the harness reads the application model. Ordinary interaction/pixel/failure
scenarios run optimized.

Resource record: include model, loaded image backing/alignment, workstation,
selector peak and the TV1 document allocations. Bank-zero target remains
**0 fixed, 0 per public Task and 0 private idle**, with no VRAM increase. Resolve
any measured stack shortage here, before the final packaging slice.

## TV3 Copied launch arguments and Files association

Extend the current C launcher signature in
[`program.h`](../../../c/include/exec816/program.h) to:

```c
ULONG EXEC_CALL ExecStartProgram(CONST_STRPTR name,
                                CONST_STRPTR arguments, UWORD length);
```

Length excludes NUL and follows the existing Process limit of 255 bytes;
null/zero denotes an empty tail. In `c/calypsi/dos.c`, use the existing three
bridge argument slots. In `c/calypsi/dos-bridge.inc`, pass them to
`PROCESS.StartBackgroundLoaded` instead of supplying null/zero. Preserve the
current program-load, NIL input, shell output, error and Image ownership paths.
The Process copies arguments before launch returns; no caller buffer is lent
to the child. Keep validation at the owning argument-admission boundary.

Advance [the C component ABI](../../../abi/c-program.json) from 10 to 11,
regenerate its outputs and rebuild all consumers. Update every source and
fixture call, including `examples/gem-desktop/resident.c`, to the new signature.
Do not retain an empty-argument compatibility entry or duplicate the launch
implementation. No new import ordinal, kernel gateway, AES wire message or
native Process ABI is required for this existing argument-copy path.

Update Files' Open handling in `examples/gem-browser/browser.c`: directories
still navigate; a case-insensitive `.TXT` suffix launches `C:TEXT.APP` with the
selected path; other files retain normal program launching with empty arguments.
Use the existing target scratch if it fits the quoted path. Enforce the viewer's
path bound only for this association, without shrinking other Files paths.
Keep this one explicit association and the current one-child policy.

Retain Files' Stop and completion collection, including its existing wait/poll
policy. Report missing viewer, load failure and capacity errors in the existing
status UI. Preserve the selected directory entry after launch. A launched
viewer may choose a different document through Open without changing Files'
ownership of that Process.

Development gate: use small raw/optimized C/native argument probes for empty,
nonempty and maximum-length tails, normal invalid-length/NUL admission, and
mutating or freeing the caller buffer after successful launch. Verify the child
receives its own copy and start failures release temporary storage/Image holds.
Run optimized Files launches for uppercase/lowercase `.TXT`, a quoted selected
path, directory navigation and an ordinary native/GEM program. Cover one-child
refusal, unavailable viewer/Task/window, Stop during read and selector waits,
completion, relaunch and Files exit while its child is alive. Verify collection
before parent retirement and restoration of the warmed ownership/heap baseline.

Update current launcher documentation only with implemented behavior. Record
changed browser observation offsets if its model grows, shared code/import
sizes and per-launch argument allocation. Bank-zero target is **0 fixed,
0 per public Task and 0 private idle**; guards, Task count and VRAM stay unchanged.

## TV4 OF816 package and desktop evidence

Add the viewer source list to `tools/build_gem_desktop.py`, then include
`C/TEXT.APP` in `tools/build_demo.py` media assembly, expected-file checks and
source hashing. Preserve the initial application set; the viewer is launched
on demand. Add small useful text fixtures to the demo disk. Generate large,
mixed-ending and failure fixtures for development runners, keeping test
intermediates out of the distribution.

Build with `tools/build_demo.py --gem-desktop`. Retain OF816, the matching
system disk, pinned ROM, license notices/checksums and the five-second standard
shell/prime autoboot. Update the generated disk README, distribution guide and
[application guide](../../guides/aes-applications.md) for Open, scrolling,
cancellation, Files association, limits and the need for a free window slot.

Extend the existing exact-ZIP walkthrough machinery, reusing
`tools/test_file_selector_demo.py` and its menu/input/ownership helpers without
duplicating a second desktop driver. Add an independent viewer pixel oracle
and checked model observer only where needed. Run the extracted final package:

1. Close Files and launch the viewer from the shell beside Control Panel and
   counter. Open through the selector, scroll/resize, change focus and expose
   covered areas while the shell does disk work. Verify Cancel and failed Open
   preserve the document; interrupt the selector with application policy.
2. Close the viewer, restore Files and close another application to free the
   fourth window slot. Open a `.TXT` from Files, stop while loading, collect and
   relaunch. Retain smoke coverage for other program launches and the existing
   panel, Files editing, calculator and standard-dialog consumers after the ABI
   rebuild; do not enlarge capacity to show them all simultaneously.
3. Repeat launch/Open/Cancel/close and end with shell EXIT. Require owned-resource
   return after collection, guard integrity and OS display/input restoration.
   Separate warmed baselines from first-use DOS/cache allocation.

Record package/source/compiler/ROM/emulator hashes, exact executed cases, stack
headroom by physical slot, image/upper-memory growth and bank-zero deltas. Measure
load completion and event-to-paint completion for representative scroll/resize
and overlap cases, keeping disk waiting separate from application work. Record
visible flicker and any regression without claiming a new latency gate passed.

Add `docs/history/text-viewer.md` and its development evidence record, and update
the relevant history index. Mark actual completed slices in this plan, link the
record from the design, and update the roadmap and plan indexes. Keep current
contracts/guides separate from the execution history. Publish only the normal
`exec816-demo.zip` contents; manifests, captures and build output stay in the
development directory. This slice is complete only when the exact shipped
payload passes, including checksums and the recorded source list.

## Common acceptance and resource rules

Follow the [development testing tier](../../contributing/testing.md): host suite,
affected generator checks, focused optimized emitted behavior and small
raw/optimized probes for changed compiler-facing interfaces/layouts. Use the
current pins and record overrides. Do not duplicate full walkthroughs in raw
mode or run release matrices merely because another slice is ready to commit.

Count guards, alignment and unused reserved capacity when reporting bank-zero
changes, including zero. Every slice targets **0 fixed, 0 per public Task and
0 private idle**. Report upper-memory and loaded-image costs separately;
allocating from existing upper RAM is not a new bank-zero reservation.

Retain the **128-byte ordinary-stack headroom target** above the interrupt floor.
The current 1,312-byte pools and 139-byte file-selector minimum do not establish
headroom for the new viewer. If evidence requires a small pool increase, allow
it as part of the affected slice: read the platform contract, account for each
changed physical slot and all boot-phase placement, regenerate the layout and
repeat affected stack/guard tests. Do not reduce guards or force a broad
refactor solely to preserve a nominal zero delta.

Keep validation minimal in runtime code: caller-owned pointers/handles are
trusted, user-input bounds and operational failures belong at their owning
boundary, and synchronization remains required. Add no editor, Save path,
wrapping, horizontal gadgets, streaming cache or general file-association
framework. Development evidence does not qualify hardware or close HY4/PI4.
This document alone changes no executable behavior or memory reservations.
