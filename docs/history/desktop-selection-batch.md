# Desktop selection and batch file operations

[Implementation plan](../plans/gem4xe/desktop-selection-batch-plan.md) ·
[Desktop contract](../reference/aes.md#small-gem-desktop)

Implementation is in progress. This record reports development checks, not
release or real-hardware qualification.

## MS1 — selection

Folder selection uses a 32-byte bitmap, selected/selected-directory counts and
press-time modifiers. Both views expose Select All/None and keyboard controls.
Open/Rename require one selected member, even when the keyboard lead was toggled
out of the set. Refresh and sort remap selected filenames using temporary upper
memory. Visible selection changes retain the existing object painting path.

The emitted Browser record grows from 3,861 to 3,947 bytes: 38 bytes of state
and 48 bytes for two menu OBJECTs. The desktop record grows from 2,128 to 2,176
bytes for its menu. The directory snapshot and shared file-selector records do
not change. Each folder allocates refresh-name scratch only when needed, bounded
by 27,648 bytes and freed after remapping.

Raw and optimized emitted Browser/Desktop layout probes pass. A focused
548-check machine-code probe passes in both modes for every bitmap position,
counts, the last remaining member and adjacent state. It caught a Calypsi 5.18
signed-index shift narrowing above entry 31; bitmap helpers now use unsigned
indices, matching their nonnegative domain. Host checks pass 451 tests with
four historical-source checks skipped. The physical-input walkthrough passes icon/list toggling, Select All/None,
Ctrl+A/Escape, sole-member command gates, refresh/sort remapping, independent
folders, a truncated 256-entry snapshot and entry 255. Full-scene pixel checks
and orderly shell/OS exit pass. The desktop Task used 757 stack bytes with
1,547 bytes remaining above its checked floor. These checks use the explicitly
recorded development disk, not the earlier packaged application bytes.
Exact image inputs and results are in the [evidence](../development/desktop-selection-batch.json).

Bank-zero reservation changes: **0 bytes fixed, 0 bytes for every public Task,
0 bytes idle**, including guards, alignment and unused capacity. The generated
budget remains 10,528 fixed runtime bytes, public reservations
`[1824,1600,1600,1600,1600,1600,2848,2848]`, and 800 idle bytes.


## MS2 — sequential batch Copy

One 974-byte private job owns a frozen pending bitmap and source snapshot.
Copy allocates one separate 16,384-byte buffer for the whole batch (17,358 bytes
combined); an extra Skip button increases each Browser to 3,971 bytes.
The destination directory is checked once. Each existing target offers
Replace/Skip/default-Cancel; transfers and temporary publication remain sequential.
Progress updates only the status strip on each chunk. Terminal results report
done/skipped/remaining counts, and cancellation removes only the current owned
temporary file. Owner close and desktop quit retire the job before its folder.

The physical development walkthrough passes empty, short, exactly 16 KiB and
multi-chunk binary copies with a tail; Replace/Skip/default-Cancel; all-skipped;
cancellation after an earlier completed file; preexisting temporary conflict;
read-only failure; and owner close/desktop quit at overwrite prompts. Independent
ATR extraction verifies all bytes, retained old targets and temporary cleanup.
A second batch and shell HELLO/EXIT pass. Raw/optimized layout probes and the
451 passing host checks (four skips) pass. The final integration slice also
covers the inherited partial-disk-full/single-copy walkthrough and measurements.
Bank-zero reservation delta remains **0 fixed, 0 per public Task, 0 idle bytes**.


## MS3 — sequential Delete and folder refresh

Delete uses the same 974-byte job without a payload allocation. One confirmation
covers the selection; each event turn deletes one entry. Nonempty-directory and
read-only errors stop the batch. Completed deletions clear membership, while
refresh remaps pending filenames. Each Browser adds a two-byte refresh flag
(3,973 bytes total). Affected paths match case-insensitively; volume aliases are
not resolved. Copy leaves its unmodified source snapshot in place and refreshes
open destination views. Sibling dialogs defer refresh until they end.

Physical checks pass mixed files/empty directories, default Cancel, a nonempty
directory after an earlier successful deletion, read-only failure, cancellation
between entries, surviving selection, second-batch exclusion and deferred refresh
with typed input preserved. The refresh case uses lowercase destination spelling.
Independent extraction verifies completed changes and untouched remaining files;
shell HELLO/EXIT, stack/domain guards and raw/optimized layout probes pass.
The pixel oracle now applies the existing OBJECT extent to folder G_STRINGs,
including clipped long error summaries; target rendering semantics are unchanged.
Host checks pass 451 tests with four skips. Bank-zero reservation change remains
**0 fixed, 0 per public Task, 0 idle bytes**.
