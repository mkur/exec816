# QED practical coexistence

[History](README.md) · [Design](../plans/gem4xe/qed-coexistence-design.md) ·
[Implementation plan](../plans/gem4xe/qed-coexistence-implementation-plan.md) ·
[Saving handoff](qed-saving.md#qw8-saving-gate-and-coexistence-handoff)

Strategy step 6 is in progress. The production baseline, Counter/shell cohorts
and repeated lifetime gate will establish the selected development scope.

## QC1a Incremental edit damage

The first physical-input baseline exposed a second-character delay above the
design's insertion limit. `qed_replace` marked every edit as `TOTAL_CHANGE`,
including replacements contained in one row. The editor finished repainting
the rest of the viewport before handling the following key.

Patch 0018 marks same-row replacements as `LINE_CHANGE`. Splits, joins and Undo
retain full damage. If shortening the longest line clamps the viewport origin,
`restore_edit` requests a complete redraw so other rows cannot retain the old
horizontal position. The existing scroll owner still performs cursor-revelation
redraws. No renderer, scheduler, driver or public ABI changes are required.

The [QC1a record](../development/qed-coexistence-qc1a.json) binds the measured
failure, correction, current production image and source-frame ledger. The
actual-source core passes two loaded lifetimes, including explicit damage-kind
checks and the existing clipboard/Undo, allocation rollback and multi-bank
cases. Six production insertions pass the unchanged response limit. The broader
workflow and concurrent cohorts remain separate gates. The record also
distinguishes the core's retained compiled sources from its earlier preparation
ledger and the low-word-only diagnostic callgraph.

QED stack admission and the conditional source bound remain unchanged.
Production costs and upper-image backing deltas are in the record. Reserved
bank-zero growth is **0 fixed / 0 per-public-Task / 0 private idle bytes**,
including guards, alignment and unused capacity. The native desktop and its
provider remain byte-identical to the interactive cursor-paint preview.
