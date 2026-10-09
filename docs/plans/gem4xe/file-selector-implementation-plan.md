# Standard GEM file selector implementation plan

[Design note](file-selector-design.md) · [GEM integration](README.md)

Status: FSEL1/FSEL2 pass development checks. FSEL3/FSEL4 are pending; see the
[execution record](../../history/file-selector.md).

Implement the design's caller-local `fsel_input`/`fsel_exinput` profile in four
executable slices. Reuse Files and the standard-dialog lifecycle, keeping the
actual Open/Save operation in the application. Each implementation slice ends
with its development checks and a separate commit. No new baseline measurement
project is needed.

## Slices

| Slice | Working result | Development gate |
| --- | --- | --- |
| FSEL1 | Shared directory/path/viewport helpers used by Files, plus bounded filtering | Emitted snapshot/path/filter cases and Files regression; no I/O during scrolling/filtering |
| FSEL2 | Private hosted selector with real directory navigation, editing and pointer/keyboard interaction | Physical input, pixels, interruption during enumeration, host lifetime and independent callers |
| FSEL3 | Named and AESPB file-selector calls in the shared C component | ABI/counts, output semantics, boundary/failure cases and rebuilt callers |
| FSEL4 | Open/Save selection in the loadable dialog example and refreshed OF816 package | Exact ZIP walkthrough, resource return, stack margins and current documentation |

FSEL2 is exercised through a development fixture calling the private selector
entry. Publish the standard API only in FSEL3, once that implementation works;
do not install public stubs or claim a partly working `fsel_input`.

## FSEL1 Shared directory and viewport helpers

Extract the small reusable parts of
[Files](../../../examples/gem-browser/browser.c) into a private C source/header,
for example `c/calypsi/file-list.c` and `file-list.h`. Compile the same source
into Files and the selector component; no new public helper exports are needed.
Keep rendering, menus, window messages, launching, child collection and New
Folder/Rename interaction in Files.

1. Move the entry representation, bounded snapshot enumeration, path joining,
   parent calculation, viewport clamping and selection visibility into the
   helper. Use a concrete begin/next/end scan state so the caller can inspect
   input between directory entries; avoid callbacks and a generic iterator
   framework. Files can drive the same scan to completion in its current loop.
2. Keep one 256-entry allocation and enumeration order. Read at most one extra
   entry for truncation. Capture DOS errors before cleanup, release locks on
   every completed/abandoned scan, and preserve exact-name selection on Refresh.
   Apply the design's error policy: preserve a view on pre-scan open/examine
   failure, or clear it if a later read has overwritten the snapshot.
3. Add the 256-WORD filtered index and the pinned donor's small 8.3 matcher,
   with ASCII case folding and directories always visible. Filter rebuilding
   operates only on the bounded snapshot. Files uses an unfiltered view;
   do not add a filter UI or otherwise change its normal workflow.
4. Add selector path split/join/default and leaf-length handling at the input
   boundary. Preserve Files' existing operation-specific path capacities;
   the selector's 128/13-byte contract must not silently shrink unrelated DOS
   or Files buffers. Keep prefixes and `/` separators exactly as designed.
5. Update Files' private observation offsets/layout probes when its structure
   changes. Use the existing `tools/browser_model.py` mechanism rather than
   adding unchecked offsets to tests. Keep any adapted donor source and notices
   reproducible through the existing pin/extraction process.

Development gate: run host checks and optimized emitted cases for zero, one,
256 and 257 entries; empty and multi-page views; truncation before later matching
files; read/open/examine errors; refresh/removal; root/parent/path bounds; and
case/extensionless/wildcard matching. Verify no enumeration on viewport/filter
changes and no filesystem writes. Exercise actual Files navigation, scrolling,
path editing and launch/child collection after the extraction. Use a focused
raw/optimized probe only for changed record layouts or bridge behavior.

## FSEL2 Hosted selector and interaction

Add a private `aes-fsel.c` implementation and bounded selector state attached
to the existing form session. Tree, TEDINFOs, text, directory scratch and snapshot
allocations belong in upper RAM. Extend the existing form cleanup directly;
do not introduce a second host manager or a generic controller interface.

Build the compact compiled tree with Path/filter, Filename, caption, status,
Up/Refresh, rows, line/page buttons and OK/Cancel. Stay within 32 objects and
sixteen rows, adapting to available work space with the design's 208-by-128
minimum layout target. Borrow the application's shown work area or create the
existing temporary host. Enforce fit once before painting and preserve borrowed
geometry, frame sliders, menu and workstation attributes.

Implement the complete interaction loop through the private entry:

- Path and filename editing, Tab/Shift-Tab traversal, list Up/Down, Return/Space,
  Escape, directory entry/Up, Refresh and line/page scrolling. Commit pending
  path edits before OK. A file click fills the candidate; a directory click
  navigates. A literal nonexistent leaf can be accepted for Save.
- Release-inside button activation and cancellation on outside release or
  input loss, including a button already held at entry. Disabled loading
  controls and hidden rows cannot activate. Do not restart `form_do` for every
  click or add double-clicks, dragging or hold-to-repeat.
- Full initial/exposure repair and bounded redraw of changed fields/rows or
  the list. Use current visible rectangles and short UPDATE sections, with
  no DOS scan, allocation or wildcard work inside painting.
- Existing host redraw/focus/move/close handling and exact application-message
  interruption. Share small private helpers with `aes-form.c` where useful,
  preserving the deferred-message/epoch and borrowed-content repair contract.
  Once interrupted, do not accept a simultaneous input action.

Enumeration needs a private nonblocking event pass. Refactor only enough of
`aes-events.c` to reuse its current selection, epoch/loss checks and payload
commit path without reaching `Wait` or submitting a timer. Preserve public
`evnt_multi` behavior. Keep input interest armed across the scan so Cancel can
actually be routed during a DOS request; balance arm/disarm on every exit.
Do not clear wake signals or hold Forbid, UPDATE or MCTRL over disk I/O.

Draw Loading before starting a scan. Between `ExNext` calls, make one bounded
ready-event pass: service host events, cancellation or a policy interruption.
Keep path/list/navigation actions inactive during Loading, so an old row click
cannot apply to the new directory or recursively start another scan. An empty
ready pass proceeds to the next read; it does not become a polling loop.
Release the scan lock before any wait for fresh input. Cancellation may wait
for the current synchronous DOS call to finish; do not claim SIO cancellation.

Complete ownership handling in this slice. End editing/presses, release owned
directory locks, retire the host and preserve storage on retirement failure
for retry or `appl_exit`. Keep result storage alive until host retirement
succeeds, allowing FSEL3 to publish outputs before freeing it. Close only owned
resources and never detach the caller's DOS context. No result path may leave
a live tree pointing at automatic storage.

Development gate: add an emitted selector fixture using the existing AES/form
harness and actual DOS enumeration. Cover keyboard and physical pointer input,
compact/larger layouts, independent pixel expectations for changed/exposed
areas, minimum fit and one-pixel-too-small rejection. Test two independent
callers, full window capacity, closed hosts, nesting/lock rejection, temporary
move/close, borrowed frame-policy interruption and exact message/repair order.
Include WM-shaped ordinary messages and a full receive queue.

Inject resource failures at the new allocations and host retirement boundaries;
check retry, Stop/exit and caller-owned DOS resources. Schedule input/message
arrival around the ready-pass decision and scan completion, including loss and
no-event cases. Verify public blocking waits still work, no wakeup is lost,
and no new timer request is made for enumeration. Measure peer progress and
ordinary-stack margins on the selector's deepest paths.

## FSEL3 Standard bindings and output contract

Publish `fsel_input` and `fsel_exinput` through the existing public GEM headers,
named bindings, AESPB dispatch and component exports. Both wrappers call the
FSEL2 implementation. Add `FSEL_CANCEL`/`FSEL_OK` and record the pinned donor
signatures/counts in the binding inputs.

Use opcode 90 with counts 0/2/2/0 and opcode 91 with counts 0/2/3/0.
Preserve outer AESPB input pointers/title before nested calls reuse context
arrays. Initialize the button to Cancel. Keep the design's 128-byte path,
13-byte filename and bounded title handling at this boundary; do not introduce
new per-layer validation.

Publish outputs only after successful host retirement, then free private result
storage. Normal OK and Cancel return one with the appropriate button and current
fields. Policy interruption returns zero/Cancel with `AES_PENDING`; failures
return zero/Cancel with their error. Both leave the caller's original strings
unchanged. Preserve the original completion diagnostic unless cleanup fails.
Path errors that the user can correct remain visible within the selector.

Advance the current [C component ABI](../../../abi/c-program.json) revision
(currently 9), regenerate its interfaces and rebuild GEMSYS and all applications
together. Keep one current ABI, with no legacy profile. Update the source lists
in the shared-component and loadable-Files builders; do not add an AES server
wire operation. Any changed context/observer layout must be generated or checked
through the existing layout mechanism.

Development gate: compare named and AESPB results for both calls, default and
custom titles, OK, edited Cancel, Escape, temporary close, policy interruption
and injected cleanup failure. Check buffer canaries and exact boundary lengths,
empty/default paths, directory selection, literal Save names, unsupported path
syntax and output preservation on failure. Use small raw/optimized ABI/count/
layout probes and optimized functional cases. Rebuild consumers and run focused
existing form/alert/event regressions where shared helpers changed. Update the
current AES reference and application guide to describe only support now proven.

## FSEL4 Loadable example and packaged desktop

Extend `examples/gem-dialog` with Open and Save selection commands. Exercise
both standard calls and display the accepted directory/filename or Cancel result.
Save demonstrates choosing a new filename; no actual write or editor is needed.
Branch explicitly on function result and button. On `AES_PENDING`, resume the
application event loop and process the retained message before borrowed-content
repair; do not blindly reopen the selector and swallow application policy.

Retain the existing edit/alert demonstrations. Include a temporary pre-window
selector path and a normal borrowed-window path in the example or its packaged
test scenario. Add read-only fixture directories covering multiple pages,
filters and navigation to the demo disk. Use existing window/Task capacity;
close a demo application when necessary instead of enlarging the pools simply
to display every example together.

Build with `tools/build_demo.py --gem-desktop`, always including OF816, the
five-second shell/prime autoboot, matching disks, pinned ROM, notices and guide.
Extend the exact-ZIP walkthrough based on `tools/test_standard_dialog_demo.py`.
Exercise selecting, typed Save names, Cancel, path correction, scrolling and
overlap repair beside shell disk work and a progressing counter. Cover menu and
borrowed-window interruption, temporary move/close, cooperative Stop while
waiting, repeated launch/close and final EXIT. Keep Files/calculator/panel
smoke coverage after the shared binding and helper changes.

Record package/source/configuration hashes, actual executed cases, resource
return and stack margins per physical slot. Separate warmed selector heap
baselines from first-use DOS context allocation, and verify full process
retirement. Add the implementation history/evidence record and update this
plan, the design status, current reference/guide, roadmap and both plan indexes.
The distributed ZIP contains only the usual boot files, guide, notices and
checksums; development manifests, captures and intermediates stay outside it.

## Common acceptance and resource rules

Follow the [two-tier testing policy](../../contributing/testing.md): host suite
and affected generator checks for code slices, focused optimized emitted
behavior, and raw/optimized probes for changed compiler-facing boundaries.
Reuse the current pins and record intentional overrides. Full release matrices
and a new latency campaign are not part of this plan; observe repaint/input
behavior during the focused scenarios and investigate concrete regressions.

For each slice report the target reserved bank-zero delta as **0 fixed,
0 per public Task and 0 private idle**, counting guards, alignment and unused
capacity. Keep large arrays on the upper heap. Report exact upper-memory code,
data and allocation growth, including the 28,672-byte snapshot and 512-byte
filtered index when allocated, and any change in image bank extents.

Retain the 128-byte ordinary-stack headroom target. If emitted evidence shows a
shortage, a measured small stack-pool increase is allowed: report its bank-zero
cost and check guard/boot-memory placement. Do not force a broad refactor to
avoid that change. VRAM reservations should remain unchanged.

Commit each slice only after its behavior and cleanup gates pass, recording
the actual validation scope. Development checks do not qualify real hardware
or close the historical HY4/PI4 latency gates. This plan itself changes no
executable behavior or memory reservations.
