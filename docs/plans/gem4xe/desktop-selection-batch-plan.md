# Desktop multiple selection and batch file operations

Status: MS1–MS4 implemented and passing development checks; see the
[execution record](../../history/desktop-selection-batch.md).

[Roadmap](../../roadmap.md#colour-gem-desktop-roadmap) ·
[CG4 design](colour-launcher-design.md) ·
[CG4 plan](colour-launcher-plan.md) ·
[Copy throughput results](../../history/desktop-copy-performance.md)

Extend the existing folder selection and Copy/Delete commands. Keep one desktop
Task, one active file operation and sequential transfers through one 16 KiB
buffer. Throughput takes priority over short cancellation intervals. Selection
and job state belong to the application in upper RAM; no AES, VDI, DOS or kernel
ABI extension is needed.

The current copy-throughput changes are the starting point, committed separately as `1906104`, including source, fixtures and evidence. Do not repeat the buffer-size study.
Implement MS1–MS4 in order, with a commit after each passing slice.

## Scope and interaction

Multiple selection applies independently to each folder's existing snapshot of
at most 256 entries, in both icon and list views. The desktop background keeps
its existing single selection. Standalone `FILES.APP` shares folder selection
behavior; file-operation ownership stays in `DESKTOP.APP`.

| Action | Result |
| --- | --- |
| Plain click on an entry | Replace the selection with that entry. |
| Shift-click on an entry | Toggle that entry without changing the others. |
| Plain click on empty directory space | Clear the selection; toolbar, status and window gadgets are not empty directory space. |
| Arrow key | Move the lead entry using current grid/list geometry and select only it. |
| Shift-arrow | Move the lead and add the destination entry; no range reconstruction. |
| Select All / Ctrl+A | Select all cached entries, including entries outside the viewport. |
| Select None / Escape | Clear selection when no dialog is open; Escape retains its dialog cancellation meaning. |
| Return / Open / Rename | Operate only when exactly one entry is selected. |
| Unmodified double-click | Select and open the clicked entry using the existing completed press/release rule. Modified clicks never launch. |

Latch the click's modifiers with its press, alongside the existing armed object
and click count. Retain a lead index for keyboard navigation, separately from
membership. Toggling the lead off must not let Open/Rename act on an unselected
entry. A plain arrow with no lead starts at the first entry.

Show the selected count in the folder status strip, independently of the
directory byte/item totals in INFO. Do not request filesystem metadata to
compute selection totals. Select All means the cached entries only; keep the
existing truncation warning visible when the directory exceeds 256 entries.

Rubber-band selection, dragging, recursive operations, multi-open, trash/undo,
background-volume selection and a separate copy Process are later work.

## State, painting and refresh

Add a 32-byte membership bitmap and 16-bit selected/selected-directory counts
per `Browser`; reuse the existing selected index as the lead. Update counts
when membership changes so menu eligibility does not scan 256 entries on every
event. Use a few private browser helpers, not a reusable selection framework.
Keep `FileEntry` and the shared file selector representation unchanged.

Update visible OBJECT selection states from the bitmap. A selection change
draws only visible entries whose membership changed, under one existing UPDATE
transaction, plus the changed status strip. Offscreen entries require no
drawing. A repeated selection is a no-op. Select All/Clear may touch all
sixteen visible objects, but must not clear and reconstruct the entire window,
re-enumerate the directory or resend unchanged scrollbar settings. Keyboard
movement that leaves the viewport uses the existing clipped scrolling path.

Scrolling, resize, full/restore, exposure and switching icon/list views retain
membership. Refresh and Name/Disk order changes retain selection by filename,
never by the entry's previous index. Before replacing a same-directory snapshot,
save only selected names in one temporary upper-memory allocation, remap them after the
scan/sort, then free it. Reuse `savedName` for the lead. This cold operation is
bounded by 256 names of at most 108 bytes including terminators: 27,648 bytes in
the worst case, with no persistent name array. Do not allocate this scratch
when nothing is selected. Allocation failure leaves the old view intact and
reports no memory. A failed initial directory open also leaves it intact.
Implementation clarification: a later enumeration error retains the shared
`FileScanNext` policy of discarding the incomplete snapshot and reporting the
error, rather than changing that helper's semantics for one consumer.
Navigating to another directory clears selection and lead.

## Batch behavior and ownership

Evolve the existing `DesktopCopy` into one private desktop file-job record,
with an operation kind, pending-selection bitmap, current entry, original count,
completed/skipped counts, owner and the existing transfer/error fields. Rebuild
observers and callers together; do not retain an obsolete copy-job interface.
Keep the buffer as a separately allocated 16 KiB block, allocated once for a
copy batch and reused for every file. Delete needs only the small job record.
Use direct copy/delete routines and explicit states, not callbacks, a general
job queue or a new message protocol.

The source folder's snapshot and path remain fixed from operation admission
through completion. Its inline dialog prevents selection, refresh, sort,
navigation, rename and new-folder commands, including keyboard/menu routes.
Move, resize, exposure and focus switching still work. The job's bitmap is a
copy of the admitted selection; later focus changes cannot change its targets.
Read names from that pinned snapshot rather than copying 256 full paths.

Allow only one Copy or Delete batch across the desktop. Another folder can
still browse, launch and use its existing dialogs, but cannot start another
batch. Do not hold UPDATE, a directory enumeration lock or an extra scheduler
lock across DOS I/O or a confirmation. External filesystem changes are ordinary
DOS errors; do not add repeated preflight scans or an ownership service.

Process selected entries in snapshot order. Between files, return to the
existing event loop. During a file, retain one synchronous 16 KiB Read/Write
pair per turn. Delete performs one `DeleteFile` per turn. Wait for real events
at confirmations; an active job waiting for an answer must not cause a zero-time
timer spin. Running transfers retain the current timer/event mechanism.

### Copy

- Enable Copy only for a nonempty selection consisting entirely of regular
  files. Selecting any directory disables it; do not silently omit directories.
- For one file, preserve the current full destination-file path dialog and
  rename-on-copy behavior. For several files, request one destination directory
  (initially `WORK:`) and retain each source leaf name. Check that directory once
  at admission, then use existing DOS calls and bounded `FileJoin` results.
- Check each destination when that item is reached. An existing file offers
  **Replace / Skip / Cancel**, with Cancel the default. Replace applies to that
  item, Skip advances the batch, and Cancel stops the whole batch. No additional
  confirmation is needed for a new destination. Replace All is deferred.
- Reuse `EXECCOPY.TMP`, handle existing-temp conflicts, and close the completed
  transfer before publishing it as today. Check the joined path once when it is
  constructed and retain actual Open/Read/Write/Close/Delete/Rename errors.
  Cleanup may remove only a temporary file created by the current item; an
  admission failure must not remove a preexisting file. Allocate neither a new
  buffer nor a new Process for each file.
- Cancellation removes the current partial temporary file, preserves its old
  destination until replacement begins, and leaves completed copies intact.
  Final delete/rename remains non-atomic. Retain and report a complete temporary
  file if publication fails, as the current implementation does, then stop.

### Delete

- Enable Delete for a nonempty selection of files and/or directories. Present
  one default-Cancel confirmation with the entry count; retain the filename for
  a single entry. State that only empty directories can be deleted.
- After confirmation, delete entries sequentially with the same job ownership
  and cancellation rules. Let `DeleteFile` reject nonempty directories; do not
  enumerate descendants or add a speculative emptiness check.
- Completed deletions remain deleted. Clear their source selection bits as
  they succeed. Cancellation or failure leaves unprocessed entries selected;
  refresh remaps those names after the job retires.

### Completion, errors and shutdown

Stop on the first operational error, report the affected filename and DOS error,
and leave unprocessed entries untouched. Do not add retry/skip-error policy in
this slice. Overwrite Skip is an explicit successful decision, not an I/O error.
Report completed, skipped and remaining counts, distinguishing cancelled,
failed and completed batches, including an all-skipped batch.

Progress shows the current filename, item position/count and bytes actually
copied. `FileEntry` contains no sizes, so do not scan or Examine every source to
invent a total-byte percentage. Repaint the progress strip at most once per
completed chunk, and filenames/dialog controls at item or prompt transitions.
Do not rebuild the folder or allocate formatting buffers on each chunk.

Refresh affected open source/destination views once at batch completion,
cancellation or failure, not after every file. A sibling with an open dialog
defers its refresh until that dialog ends, preserving typed input. Copy retains
source selection by name; Delete retains surviving selected names. Use existing
path information and do not add a general alias/invalidation service.

Closing the owner or quitting the desktop requests cancellation of the entire
batch, including while an overwrite prompt is open. Close handles, finish the
existing temporary-file cleanup policy and retire the job before freeing its
owner/snapshot or buffer. Never schedule the next file after cancel, close or
quit. Other windows can close without cancelling the owner's batch. Surface
cleanup failures without losing the original operation error or claiming that
a leftover temporary file was removed.

Cancellation is observed between synchronous operations; neither Escape nor
owner close promises immediate interruption of a Read/Write or cleanup. Retain
the accepted throughput tradeoff and measure it without a small-buffer gate.

## Executable slices

### MS1 — folder selection

Update `examples/gem-browser/browser.h` and `browser.c`: bitmap/count, lead and
press modifiers, physical/keyboard input, incremental selection painting,
filename preservation and count display. Extend both folder menu variants with
Select All/None. Update `desktop.inc` dispatch explicitly: its current
`item >= DESK_COPY` test must not interpret new menu items as Delete. Update menu
capacity, identifiers and cached enable-state bits together.

Until MS2/MS3 land, keep Copy/Delete enabled for exactly one entry; Open/Rename
also require exactly one. Apply that rule to keyboard and popup paths as well
as menu visuals. Refresh the private layout probes and pixel expectations.

Development acceptance: emitted icon/list checks for toggle/all/clear, index
255 and a full/truncated snapshot, offscreen selection, keyboard navigation,
double-click, refresh/sort, resize/exposure and independent folder selections.
Verify unchanged single-selection launch/rename and standalone Files. Observe
that selection draws only changed visible objects and the status strip.

### MS2 — sequential batch Copy

Extend the existing desktop copy path and inline dialogs with the single job,
frozen pending set, multi-file destination directory, per-file overwrite choices,
progress/counts and explicit terminal cleanup. Make owner-close and desktop-quit
safe in this slice, including prompts before handles are open. Keep Delete
single-entry until MS3. Update the copy measurement observer to the new layout
without changing its timing definitions.

Development acceptance: copy several binary files including empty, short,
exactly 16 KiB and multi-chunk files with tails; independently extract and compare
bytes. Cover overwrite Replace/Skip/default-Cancel, all-skipped, existing temp,
unavailable/read-only destination, failed path join, partial disk-full failure,
cancel after an earlier file completes and close/quit during transfer or prompt.
Require unchanged sources/old targets where promised, accurate outcomes,
temporary cleanup or reported recovery file, and no work on remaining items.

### MS3 — batch Delete and affected-view refresh

Use the same private job ownership for sequential Delete with one confirmation.
Add/defer affected-view refresh after both operations and preserve any pending
sibling dialog. Keep DOS calls outside UPDATE and return to input between files.

Development acceptance: mixed files/empty directories, default-Cancel with no
mutation, nonempty-directory failure after an earlier deletion, read-only
failure and cancellation between deletions. Verify completed/remaining counts,
surviving selections, source snapshot lifetime, deferred sibling refresh and
second-batch rejection. Other applications and folder switching remain usable
at the existing I/O boundaries. Independently inspect final disk contents.

### MS4 — integration, measurements and demo

Extend the existing `tools/test_colour_desktop_session.py` walkthrough and
`tools/colour_file_check.py`; keep observers in `tools/colour_desktop_model.py`
and the emitted layout fixture synchronized. Reuse existing folder/pixel and
copy measurement tools rather than create a second test framework.

- Run host checks and focused optimized emitted-code cases for changed behavior.
  Use small raw/optimized layout/access probes where observer layouts change;
  do not repeat full raw system sessions or compiler qualification.
- Compare single-file throughput with the current 16 KiB baseline on matched
  fresh media, then measure a multi-file batch including small files. Record
  byte counts, timing boundaries and finalization separately. Investigate a
  repeatable single-file slowdown; extra chunk-level scans, allocations or full
  window redraws are not acceptable costs of batch support.
- Record median/p95 selection feedback for ordinary click and Shift-click in
  both views, with unchanged geometry/input phase. Check Select All's bounded
  repaint, and Panel feedback at idle and during a copy. Report cancellation
  samples and desktop-local stalls as tradeoffs, not throughput acceptance gates.
- Verify stack/domain guards, job/heap cleanup, a second batch after completion,
  owner/desktop shutdown and return to the OS. Record actual stack headroom,
  upper-memory allocations and reserved bank-zero deltas.
- Build using `tools/build_demo.py --gem-desktop` with OF816 and the existing
  five-second autoboot. Exercise the extracted `exec816-demo.zip`, retain license
  notices/checksums, and provide its launch command. Keep development evidence
  and intermediates outside the ZIP.
- Update the current desktop contract in `docs/reference/aes.md`, demo guide,
  roadmap and plan index. Reconcile stale 512-byte copy descriptions with the
  accepted 16 KiB default. Save results/hashes in development evidence and a
  history page; mark only passing slices complete.

## Memory and completion criteria

Planned reservation change in every slice: **0 bytes fixed bank zero, 0 bytes
per public Task, 0 bytes idle**, including guards, alignment and unused capacity.
No extra Task, stack, direct page, VRAM buffer or persistent directory snapshot.
Report actual emitted upper-memory sizes rather than assuming host C padding:
selection starts at 36 bytes per folder plus press state/menu objects; one job
has a 32-byte pending bitmap and small counters/path state; Copy retains one
16 KiB payload allocation. Refresh scratch is temporary and allocated only when
names must be preserved. Keep paths and name lists off the Task stack.

Completion means both folder views support independent multi-selection;
Copy/Delete obey the documented per-file results, cancellation and lifetime
rules; single-file copying retains the throughput-oriented path; and the exact
OF816 demo passes the focused development checks. This is development evidence,
not release or real-hardware qualification.
