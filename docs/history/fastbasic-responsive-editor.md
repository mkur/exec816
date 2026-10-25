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
| RE3 | Settled identity and bounded translation preparation implemented; development checks pass. |
| RE4 | Four-direction movement implemented; 96 painter and 24 motion/failure checks pass. Loaded physical pilot running. |
| RE5 | Structural suffix/prefix mapping implemented; 100 painter, 44 structural and 30 key checks plus loaded pilot pass. |
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

## RE3 Presentation identity

The editor reserves 512 additional upper bytes for one translation, settled
source identity and per-visible-row source offsets/line mapping. Its full model
is 7,296 bytes; combined refresh reservations are 5,632 bytes including spare.
Compile-time bounds enforce the motion reservation. Existing model field offsets
remain unchanged. There are no per-key allocations, Tasks, signals or new VRAM.
Bank-zero reservation deltas remain zero fixed, root/kernel, each public Task
and idle, including guards, alignment and spare capacity.

Exposure, incomplete painting and changed source/geometry prevent reuse.
Preparation computes overlapping rows/columns while keeping old/new origins
separate. AES END_UPDATE now publishes the final paint epoch and PixelsReady,
so an application can retain the completed presentation identity. The optimized
painter passes 91 assertions; the live binding fixture checks the returned
identity after complete, deferred and repaired updates. Actual pixel movement
is connected in RE4.

The frozen physical baseline contains 281 samples with independent whole-client
pixels: twenty per ordinary cohort and one separate far-gap observation. Readiness
is separately derived from passive Task-owned event-dispatch entries. A parser
bug that truncated readiness at complete scanout was repaired using the retained
trace, without changing physical input or cadence. Top Return/join scanout p95
is 1,604/1,625 ms; scrolling p95 is 1,584–1,645 ms across the four directions.
The single far-gap sample is 401 ms scanout / 415 ms readiness, and does not
establish a distribution. All baseline timing gates remain as specified.

## RE4 Four-direction viewport movement

Eligible movements now copy text pixels and shift retained character/attribute
cells together. An old text caret is removed before copying; selection travels
with text and is compared at its new position. Copied pixels stay in one pending
presentation transaction through exposed-strip/overlay repair, with epoch and
visibility checked at each UPDATE. Only then can the grid be acknowledged.
New input, exposure or geometry changes retire the incomplete transaction and
retain bounded reconstruction. No-overlap/covered fallbacks keep status and
margins independent. Selection dragging shares the same four-direction path;
an active outside-edge gesture steps every 80 ms after the preceding repair.

The six-row/16-column emitted fixture draws 16–17 source cells per vertical
scroll and 6–7 per horizontal scroll, with one copy and no status drawing. The
horizontal fixture completes in two bounded paint turns; vertical scrolling in
one. The separate motion probe passes 24 assertions covering selection edge movement,
newer input, reversal during repair, stale/covered sources, copy and END failures,
final independent pixels and resource retirement. The painter passes 96 checks.
The raw/optimized snapshot-interface probes each pass 26 checks, and all 653
host tests pass. The unchanged per-operation drain bound is retained; the larger
independent case set runs in separate bounded probes. Loaded application checks
are in progress, and timing acceptance remains open.

The motion payload is 260 bytes within its 512-byte reservation, leaving 252
reserved spare bytes. The model remains 7,296 bytes; the actual APP span is
96,765 bytes, exactly 512 more than the frozen baseline. C import ABI 30 adds a
read-only window snapshot helper instead of exposing mutable binding internals.
All fixed/root/kernel/per-public-Task/idle bank-zero reservation deltas remain
zero, including guards, alignment and spare. QED consumes another 4 KiB of its
existing provider-code growth allowance, leaving 8 KiB inside the same three
provider code banks; no pool or bank is enlarged.

An optimized integration check caught Calypsi 5.18 reusing an uninitialized
local rectangle edge during dependent bounds arithmetic. Reusing the existing
independently computed bounds helper eliminates that form; emitted independent
pixel probes cover the resulting geometry. The pinned Action! compiler is
unchanged. This development record makes no platform qualification claim.

## RE5 Structural edits

Return, newline Backspace/Delete and complete-line range deletion/replacement
retain an explicit old/new line and byte-offset mapping. Each reused row is
checked against that mapping; equal newline counts do not imply reuse. An
unchanged prefix stays in place, the suffix moves, and the changed boundary
compares its old physical appearance. Empty trailing suffixes need no copy.
Undo/Redo, complex selections/folds and superseding input retain reconstruction.

The emitted painter passes 100 checks. Top and middle splits/joins each copy
once and draw eight source cells in the small fixture, with one changed saved
marker on insertion and no status drawing on join. The separate structural
probe passes 44 checks for middle splits, indentation/tabs, syntax, complete-line
ranges, trailing empty lines, panning, Undo/Redo, equal-count replacement and
new input before presentation. Thirty logical editing checks pass.

A loaded current-system pilot passes fifteen physical operations, independent
whole-client pixels, copy counts, heap/guard checks and OS restoration. On its
19-row/56-column viewport, top Return/join draw 8/55 source cells and complete
scanout in approximately 321/341 ms. Vertical scrolling is approximately
281–301 ms; horizontal scrolling still takes approximately one second. These
single samples establish correctness and guide RE6; none closes a timing gate.
The final matched twenty-sample distributions remain RE7.

Motion payload is 276 of 512 reserved bytes (236 spare), with no new reservation
relative to RE3. Model size remains 7,296 bytes. Fixed, root/kernel, each public
Task and idle bank-zero reservation deltas remain zero including guards,
alignment and unused capacity. The native system and import ABI remain unchanged.
