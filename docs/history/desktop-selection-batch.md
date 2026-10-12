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
