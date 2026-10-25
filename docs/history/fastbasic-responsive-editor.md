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
| RE2 | Implemented; 22 independent graphics pixel scenes and ownership checks pass. |
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

## RE2 Owned graphics copies

The public copy helper uses existing delegated display access, fresh visibility
and settled-pixel admission. It supports even horizontal displacements at both
packed-pixel parities, four directions and diagonal overlap. Parity-changing
horizontal displacement returns reconstruction-required before mutation.

All source edge bytes are captured before any interior or edge write. Copies
then run in overlap-safe strips, each fenced and with pointer/outline restoration
before physical access is released. The 32-byte descriptor and 480-byte edge
staging area add exactly 512 upper workstation bytes (894 payload / 896 allocated).
Existing transient CICON scratch is reused; no persistent VRAM or bank-zero
reservation changes. The C import ABI is 29, the private VDI layout version 3.

The packed-edge host oracle exercises thousands of overlapping translations,
one-pixel edges, screen-height moves and transfer failures. Small raw/optimized
loaded probes cover generated layouts and public-call preservation. The live graphics fixture passes 705 assertions and 22 independent whole-screen
pixel comparisons. It includes pointer pixels in the source and then moves the
pointer away, proving overlay removal/restoration. All guards, ownership and
cleanup checks pass. Small copy admission/error probes pass 23 checks in each
raw/optimized mode; current host suite passes 652 tests.

The live fixture touches 932 bytes in each 1,312-byte renderer caller pool,
leaving 124 bytes above its 256-byte floor; its 2,560-byte caller touches 722
bytes. Kernel peak is 285 of 1,536 bytes. Pools and floors are unchanged.
These are development checks; reset-required fault injection and coexistence
measurement remain in RE7.
