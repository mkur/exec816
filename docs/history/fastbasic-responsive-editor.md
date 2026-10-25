# FastBasic responsive editor development

[Implementation plan](../plans/fastbasic-responsive-editor-implementation-plan.md) ·
[Frozen baseline](../development/fastbasic-responsive-editor-baseline.json) ·
[Workbench contract](../reference/fastbasic-workbench.md)

The implementation proceeds through RE0 to RE8. The source baseline is
`de7dfce9`; its combined demo, BASIC.APP, native image and editor sources are
preserved under `build/fastbasic-responsive-editor/` with recorded hashes.

## RE0 Baseline and observers

The permanent emitted painter probe passes 83 assertions, including top and
middle line splits/joins, all four scrolling directions, direction reversals,
blank suffixes, independent final pixels and resource retirement. A six-row,
16-column scroll redraws 96 source and 16 status cells and uses one empty
publication scope followed by two paint turns. The original diagnostic record
is preserved separately from these permanent probes.

The 649 existing host checks pass. These are development checks; physical
latency cohorts and later copy/ownership slices remain pending. The physical
observer uses a separately recorded additive PLUS matrix-key alias so leftward
input can be measured without replacing the pinned emulator binaries or
changing emulated timing.

No production code or memory reservation changes in this preparation.
Additional reserved bank-zero bytes are zero fixed, root/kernel, per each of
twelve public Tasks and idle, including guards, alignment and unused capacity.

| Slice | State |
| --- | --- |
| RE0 | Source/package frozen and permanent drawing-work probes pass; physical observer and matched cohorts in progress. |
| RE1 | Pending |
| RE2 | Pending |
| RE3 | Pending |
| RE4 | Pending |
| RE5 | Pending |
| RE6 | Pending |
| RE7 | Pending |
| RE8 | Pending |
