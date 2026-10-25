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

## RE6 Bounded document and composition work

Gap movement retains its 1,024-byte work quantum and yields only when more
movement remains. Zero-width gaps move logically without copying, and an edit
with unchanged newline count avoids a redundant index memmove. Offset adjustment
uses a pointer walk. The document, undo and saved-generation contracts remain.

Composition reads each line once, using the existing scratch storage for bytes
and then colours. Eligible uniform, tab-free rows reuse retained syntax and
compose only incoming horizontal bytes. Mixed syntax or any tab keeps the full
composition path. Independent pixels cover tabs inside strings/comments, offscreen
tabs, syntax, reversal, odd geometry and a copy whose exposed pixels already
match: that transaction still publishes its final acknowledgement.

Twenty isolated native component samples give p95 tiny movement/edit 3.38 ms
(previously 13.88), index work 2.18 ms (12.05), and 19-row full composition
260.27 ms (273.09). A real 32 KiB gap move/edit still costs 256.64 ms, with
253.68 ms in movement; its 200 ms target remains OPEN. These are attribution
measurements, separate from loaded physical input/scanout.

Optimized emitted checks pass: painter 100, motion 24, structural edits 44,
edge cases 24, assistance 512, document 130, mock file controller 45,346 and
SDFS file controller 45,245. The motion payload is 374 of 512 reserved bytes,
leaving 138 spare. Total refresh reservation remains 5,632 bytes, with 146
spare, inside the unchanged 7,296-byte model. No persistent VRAM is added.

The compiled application crosses a code-bank boundary: its loaded span is
133,294 bytes, rounded allocation 133,296, including a 34,311-byte address-space
hole, code, data and zero-fill. This is 36,528 reserved upper bytes more than
RE5 and 37,040 more than baseline, despite no model reservation increase. File
size is 92,812 bytes. Bank-zero reservation deltas remain zero for fixed,
root/kernel, each of twelve public Tasks and idle, including guards, alignment
and unused capacity. The final loaded run touches 997 of BASIC's 1,312 stack
bytes, leaving 59 above its 256-byte observation floor; guards remain intact.

## RE7 Loaded interaction and remaining timing gates

The frozen baseline and final candidate each have 281 physical samples: twenty
per ordinary cohort and one separate far-gap sample. Both use the same pinned
ROM, 19-row/56-column viewport, document, three-frame key hold and per-frame
whole-client independent pixel comparison. The final APP hash is
`057b82bc2f8df83474b38588ac91459a88ac446c9b52237e49978ab480600796`.
All target pixels match. The candidate's p95 results are:

| Operation | Input ready (ms) | Complete scanout (ms) | Frozen gate |
| --- | ---: | ---: | --- |
| Append / Backspace / insertion / deletion | 110.8–111.3 | 100.28 | OPEN, 100 ms |
| Horizontal caret movement | 91.2 | 80.22 | Pass, 100 ms |
| Top Return / join | 348.1 / 372.5 | 320.9 / 340.9 | OPEN, 100 ms |
| Middle Return / join | 339.6 / 362.6 | 300.8 / 320.9 | OPEN, 100 ms |
| Content up / down | 372.6 / 312.3 | 340.9 / 300.8 | OPEN, 100 ms |
| Content left / right | 282.2 / 261.9 | 782.2 / 782.2 | OPEN, 100 ms |

Top Return/join scanout improves from baseline p95 1,604/1,625 ms; baseline
four-direction scrolling is 1,584–1,645 ms. Five PAL frames are still 100.28 ms
and fail the 100 ms target. The physical far-gap sample remains 411.6 ms ready /
401.1 ms scanout; one sample is not a p95 distribution. The separate twenty-edit
component attribution also misses 200 ms. No threshold, key hold, budget, Task
priority or ordinary measurement geometry was relaxed. Functional delivery and
performance acceptance remain separate; vertical caret-only latency is not
independently distributed by this observer.

Loaded pixels pass for selection replacement, Undo/Redo, menu actions, focus and
coverage/exposure, long panning, partial-row resize, minimum 288×128 client and
maximum desktop client 616×205 at (8,24). The maximum-document accepted deletion
completes in 31 PAL frames while the native peer advances 65 times, preserving
the existing 120-frame bound. New input and reversal during partial repair,
odd positions, stale/hidden pixels and drawing failures have their focused emitted
independent-pixel probes. Passive CPU traces show no repeated BASIC dispatch
in twenty settled idle frames, independently of diagnostic paint counters.

The loaded file/assistance cohort passes 23 cases. AES cache/snapshot ownership,
EDX physical typing and both cursor directions pass. The two-sample EDX smoke
check is functional evidence, not a new latency distribution. The actual packaged
persistent-interpreter test passes integer/float state, arrays, parse failure,
Stop, Restart within the same Process, mode replacement, output-close cancellation,
Check beside parked BASIC and canceled Quit.

The renderer-borrower regression and both original fault cases pass. New copy
injections complete a real packed-edge screen strip before forcing BUSY. Both
quiescent and reset-required cases pass: STOP occurs once, quiescent grants retire,
and unsafe ownership remains retained through reset-required recovery. No fixture
hook enters production. These are development checks, not platform qualification.

Check/Build exposed a stack-budget regression before delivery: the modal Build
selector retained the transfer state machine's 86-byte local frame, touching
30 bytes of the 256-byte interrupt observation floor. Separating modal admission
from transfer work reduces that live frame to fourteen bytes. The same two-run
fixture now passes all 67 native assertions, executes the standalone commands
after editor exit, and reclaims equal heaps. Its peak is 1,020 of 1,312 bytes,
leaving 36 above the floor. Stack pools, guards and bank-zero reservations do
not grow. The final APP span is 133,216 bytes (rounded allocation 133,216),
36,960 more than baseline, including the unchanged 34,311-byte placement hole.
File size is 92,858 bytes; model and refresh reservations remain unchanged.

The selected release cohort explicitly exercises Save As twice, Check, Build,
quit, execution without the IDE and cleanup across two application loads.
Persistent Run has its separate current-system regression; the earlier broad
compiler-era relative-directory transcript expectation is not used to claim
interpreter-session qualification. Physical selector helpers now wait for
directory-scan completion and focus changes before typing into the next field.

The final serial/pointer stress cohort uses the delivered APP and a concurrent
128 KiB native CAT read while offering physical pointer motion during every
repair. All 29 key targets match independent whole-client pixels; every RAM output
byte matches the host fixture after CAT retires. During input/repair, 22,335 real
SIO receive bytes are serviced without overwrite or a missed byte deadline;
maximum service delay is 0.1055 ms. Maximum pointer capture gap is 0.5136 ms,
below its existing 1 ms envelope. GUI pointer delivery p95 is 140.4 ms; that
separate value is not presented as a new latency pass. Pointer observation
continues through delivery even when target text pixels complete sooner.

All 653 host tests and affected generated definitions pass. The final package
also passes two-shell/pipeline coexistence, unsaved floating-point Run, Stop,
finite Run, editor quit and resource retirement. This is selected development
validation; no full hosted-system qualification is claimed.

## RE8 Matching distribution and corresponding source

The final `exec816-demo.zip` is generated with `tools/build_demo.py`, retaining
OF816's five-second autoboot, the matching pinned ROM, XEX and Atarimax cartridges,
writable combined D1 SYS/WORK, port-2 mouse, separate QED ATR, and MD5/ARC/EDX
with ARC overlays and notices. Only boot files, the guide, checksums and license
notices appear in the ZIP. Corresponding source has its own archive; development
intermediates and observations stay under `build/fastbasic-responsive-editor/`.

The delivered APP is the exact 281-sample candidate and 29-sample coexistence
candidate. Original-package cold ATR boot/save checks and the final-package cold
smoke are recorded separately from pre-native checkpoint replay. Packaged editor
Run/Stop and native peer/guard/ownership/OS-return checks pass. Source delivery
uses the clean offline rebuild checker, comparing the rebuilt BASIC.APP, four
FastBasic tools and a compiled sample byte for byte. Artifact receipts in the
execution record follow the archived source snapshot; they do not change its
production source. These are development checks, not release qualification.

The FujiNet installation uses a fresh versioned directory. Hash comparison
found the user's existing `SD/EXEC816/exec816.atr` modified from its template;
that installation and its work are preserved in place. The final directory and
all installed checksums are recorded in the execution record. The repository's
`exec816-demo.zip` contains the same final distribution.

Refresh reservation is 5,632 bytes within the 7,296-byte model; copy storage is
512 bytes per VDI workstation and AES metadata grows 112 rounded bytes per
client, with no new shared metadata reservation. Final APP allocation is 133,216
upper bytes including alignment, zero-fill and the 34,311-byte placement hole.
Fixed, root/kernel, each of twelve public Tasks and idle reserve zero additional
bank-zero bytes, including guards and unused capacity. No persistent VRAM grows.
The recorded stack peaks retain their existing interrupt floors.

Functional RE0–RE8 delivery is complete. The 100 ms local edit, scroll and
structural-edit targets and physical 200 ms far-gap target remain OPEN. Horizontal
caret movement meets its matched 100 ms gate; broader vertical-caret-only and
far-gap distributions and hardware/platform qualification remain separate.
