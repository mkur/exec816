# FastBasic editor repaint implementation plan

Status: implemented, ER0–ER4 complete, 24 October 2026.

[Development results](../history/fastbasic-editor-refresh.md) and
[machine-readable evidence](../development/fastbasic-editor-refresh.json) record
the executed scope, measured costs and final delivery identities.

[Design](fastbasic-editor-refresh-design.md) · [Plan index](README.md) ·
[Testing policy](../contributing/testing.md)

Deliver changed-cell editing in the native `BASIC.APP`, with independent
caret/status damage and correct publication of deferred or hidden changes.
Use the current public AES/VDI interfaces and preserve the interpreter, source
document, file transactions and Check/Run/Stop/Build behavior.

## ER0 Baseline and measurement

Freeze the current application and package identities. Measure physical append
and caret input through completed scanout on the pinned desktop, using the
same document, key sequence and observer for the final comparison. Retain the
baseline sources and emitted application for reproducing the comparison with
candidate drawing counts and pixels.
Record machine inputs and distinguish scanout from software completion.

Exit: reproducible baseline samples and checksums outside the distribution.
Additional reserved bank-zero bytes: zero fixed, root/kernel, per Task and idle.

## ER1 Retained appearance and damage

Append one 5,120-byte private upper-data reservation to `BasicEditor`, preserving
existing field offsets. Add a compile-time bound on the private state. Retain
character/attribute cells, per-row changed/forced intervals, composition flags,
status characters and publication state. Compose at most four rows per turn;
compare text, syntax colour, selection and caret before merging damage.

Route status setters to status composition. Keep pending intervals across newer
edits, including reversals. Detect viewport/document changes and retain a full
repair path for geometry and exposure.

Exit: emitted logical editing/composition checks cover tails, tabs, recolouring,
caret/selection changes, single-line deletion, equal-line-count replacement,
repeated status messages and the reserved size.
Additional reserved bank-zero bytes: zero fixed, root/kernel, per Task and idle.

## ER2 Incremental painting and publication

Replace clear-and-row painting with opaque text runs and restored selection/caret
marks. Bound turns to 96 cell reconstructions and four rows, counting fragments.
Keep initial/exposed margins and footer padding on an explicit repair path,
with at most eight fill fragments per turn.

Complete an ordinary visible edit in one window UPDATE. Publish an empty UPDATE
only when a new drawable change must cross a wait without complete presentation.
Keep forced repair independent of cache equality, acquire fresh visibility for
each quantum, report actual completed pixels and retain pending work on failure.
Covered windows publish changes without polling for hidden screen work.

Exit: emitted painter checks compare against independent complete pixels and
exercise partial visibility, multiple quanta, new input, exposure, journal
limits, failures and hidden idle. Simple append/caret updates have no full-row
clear, unchanged status drawing or empty publication.
Additional reserved bank-zero bytes: zero fixed, root/kernel, per Task and idle.

## ER3 Loaded interaction and performance

Run the real updated application with the same native system and observer as
ER0. Compare append/caret median and 95th-percentile key-to-scanout latency;
accept lower values with pointer response and bounded repair progress preserved.
Check selection, long lines, newline/Undo, status, occlusion/exposure, resizing
and source execution. Preserve guards, existing stack admission and final
resource collection. Run the host suite and the affected emitted editing/file
and assistance checks. Record actual scope without a release qualification claim.

Exit: pixel, lifecycle and performance evidence on pinned inputs, with actual
upper-data and stack costs. Additional reserved bank-zero bytes remain zero.

## ER4 Delivery and documentation

Update the workbench contract/guide and record development results. Refresh the
demo with `tools/build_demo.py`, retaining OF816 and its five-second autoboot,
the combined writable system ATR, separate QED ATR, ported SDX tools, ROM,
cartridge images, `licenses/` and checksums. Include the new sample source.
Verify the extracted final package and refresh corresponding source delivery.
Preserve user-written FujiNet media; install a fresh version separately if the
existing writable disk differs from its distributed template.

Exit: runnable, checked distribution and a recorded limitation for any gate
that remains unmet. Keep build/test output outside the ZIP. This plan does not
authorize changing compiler semantics or enlarging stack/bank-zero pools.


## Completed slices

| Slice | Result |
| --- | --- |
| ER0 | Frozen original sources/APP; matched 12-sample append and caret scanout cohorts on the same native system and observer. |
| ER1 | 5,120-byte upper reservation, independent source/caret/status damage, base-row recomposition and narrowed deletion ranges. |
| ER2 | Opaque changed spans, bounded composition/drawing/margins, exact completion, deferred/hidden publication and forced repair; 66 emitted painter checks pass. |
| ER3 | 30 logical and 512 assistance checks, 103 file-controller checks, 28 native physical assertions/11 scanout cases, loaded retained-interpreter session and 643 host checks pass. Typing/caret median and p95 improve; maximum-gap edit takes 33 of the allowed 120 PAL frames with peer progress. |
| ER4 | Final combined ATR/OF816 ZIP, separate QED, tools/sample, independent media/checksum audit, corresponding source and FujiNet installation refreshed. |

The unchanged 96-cell/four-row limits exposed an existing overbroad Backspace
nomination. Narrowing it reduced the maximum-gap fixture from 140 to 33 frames.
The original response bound was retained. Initial/exposed bulk repairs keep the
bounded path and current full-client deferred-publication fallback. Pointer
measurements cover the scripted idle motion/settling case; no busy-pointer
percentile or hardware qualification is claimed.
