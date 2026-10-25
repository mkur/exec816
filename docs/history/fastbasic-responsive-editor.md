# FastBasic responsive editor development

[Implementation plan](../plans/fastbasic-responsive-editor-implementation-plan.md) ·
[Frozen baseline](../development/fastbasic-responsive-editor-baseline.json) ·
[Execution record](../development/fastbasic-responsive-editor.json) ·
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
| RE1 | Explicit invalidation and bounded source/status/margin publication implemented; development checks pass. |
| RE2 | Pending |
| RE3 | Pending |
| RE4 | Pending |
| RE5 | Pending |
| RE6 | Pending |
| RE7 | Pending |
| RE8 | Pending |

## RE1 Explicit damage publication

Public `ExecAESInvalidate` uses a separate eight-rectangle invalidation journal.
Declarations retain hidden and deferred obligations without acknowledging paint.
New logical damage retires overlapping earlier completion reports; drawing
outside declarations retains conservative invalidation. Explicit empty updates
preserve a settled cache and leave older outstanding damage intact.

The editor publishes text, status and margin repairs separately. A Return in
an empty six-row/16-column fixture now draws two source cells and one saved-state
cell in one nonempty UPDATE, compared with 112 glyphs over three scopes. A
populated top split draws 96 source cells and only the changed saved-state cell;
its join redraws no status cells. Pixel copies follow in RE2 onward.

The emitted painter passes 83 checks. Raw and optimized API/record probes each
pass 25 checks, exchanging the generated journal record between Action! and C.
The live AES binding fixture passes 359 assertions, including explicit empty
updates, delayed invalidation, exact repair and conservative unreported changes.
All 651 host tests and the affected generators pass. These are development
checks; matched candidate latency and packaged application rebuilds follow.

AES wire version 19 has a 340-byte request. The C context grows 482 to 596
payload bytes, or 488 to 600 allocated bytes, within the per-client allowance.
C application import version is 28. Editor, VDI, fixed upper metadata and VRAM
reservations do not grow. Additional bank-zero reservations remain zero fixed,
root/kernel, per each public Task and idle, including guards/alignment/spare.
