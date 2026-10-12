# Command loader refactor plan

[Implementation plans](README.md) · [Roadmap](../roadmap.md) ·
[Loading measurements](../history/list-command-loading.md) ·
[Program contract](../reference/program-loading.md) ·
[Testing policy](../contributing/testing.md)

Status: CL0–CL2 complete at the development tier; CL3 evidence pending.
[Implementation record](../history/command-loader-refactor.md).
[Baseline inventory](../development/command-loader-refactor-baseline.json).

Reduce command loading CPU time by replacing the executable payload byte loop
and the nested bytewise scalar readers. Keep loading, validation, binding,
placement and Process ownership semantics unchanged. The existing measurements
are sufficient for this bounded refactor; no separate design note is needed.

## Baseline and scope

The [LIST profile](../history/list-command-loading.md) measures warm loading at
1,029 ms on SIO and 1,041 ms on IDE. Both have zero physical reads. The loader
itself accounts for about 72% of this time. Copying 5,726 text bytes takes
134–136 ms, and one load makes 4,446 cursor bounds-check calls.

Change only [PROGRAMPLACE.Copy](../../lib/dos/programplace.act) and
[O65READ.U16/U32](../../lib/dos/o65read.act), plus focused fixtures and observers
needed to verify them. Reuse the pinned compiler's A816MEMORY.Move primitive.
Compiler/runtime primitives remain owned by actionc; fix any compiler defect
there with a minimal reproducer rather than a loader-specific workaround.

Keep the o65 format, compact descriptor, providers, signatures, public ABI,
record layouts, staging limits and 4 KiB DOS read chunks. Preserve text alignment,
private text/data/BSS allocations, BSS clearing, complete source staging and
the existing validation/relocation passes. Import resolution still parses the
provider manifest once. No new cache, worker, scratch buffer or service is needed.

DOS Open/Read overhead, LIST output batching, command retention, provider indexes,
relocation-pass consolidation and C-program loading are outside this refactor.
PROGRAM.Load calls PROGRAMPLACE.Copy for text and initialized data. CPROGRAM
already uses A816MEMORY.Move directly and needs no copy-path change.

## Reader behavior to preserve

Successful U16/U32 reads decode little-endian values, advance the cursor by
exactly two/four bytes and leave its error clear. Make the complete-width bounds
test once, then read bytes directly and advance once. U32 must not call U16 on
its successful path. Use subtraction-based bounds checks so invalid offsets
cannot pass through arithmetic wraparound.

Preserve the current failure semantics explicitly:

| Cursor condition | Result and state |
| --- | --- |
| Error already latched | Return zero, keep the error and cursor position. |
| Position beyond the limit | Return zero, latch BAD_FORMAT, leave position unchanged. |
| Fewer bytes remain than the requested width | Consume only available bytes, return those bytes in the low part of the value with missing high bytes zero, then latch BAD_FORMAT. |
| No bytes remain | Return zero and latch BAD_FORMAT without advancing. |

Use the existing bytewise U8 behavior only when the complete-width fast path
cannot run. Do not attempt a failing Take(width) first: it latches an error
before the available prefix can be consumed. Keep U8, Take and first-error
latching unchanged. This preserves parsing results and cursor state on malformed
input while removing the nested calls from ordinary successful reads.

## CL0 Freeze the comparison inputs

Reuse [the existing evidence](../development/list-command-loading.json) and
retained builds as the baseline; do not rerun the full directory-listing matrix.
Record the production revision, pinned compiler/ABI/ROM/emulator, optimized
image, exact LIST bytes, media, cache setting and observer definitions.

Confirm that PROGRAMPLACE.Copy's LONGCARD count can be represented by the
runtime's 24-bit SIZE: the admitted text/data limits are 131,072/65,536 bytes.
Record loader routine
sizes, reserved memory and current stack observations. Retain the source and
development artifacts needed for comparisons, without committing large traces.

Acceptance: frozen executable baseline, caller inventory and explicit reader
failure behavior, with no production change.

## CL1 Use the bulk memory primitive

Add the A816MEMORY dependency to PROGRAMPLACE and implement Copy as a call to
Move(destination,source,SIZE(bytes)). Retain the helper signature and both
text/data copy sites. Keep source ownership through validation/copy and publish
the image only after relocation succeeds. No zero fill is added to text/data or
the unused text-alignment reservation; BSS retains its current clear allocation.

Use a small optimized emitted fixture to compare exact output bytes and guards
for zero, odd and even lengths, unaligned pointers, source/destination bank
crossings, lengths around 65,535/65,536 bytes and the 131,072-byte text limit.
Cover initialized data as well
as text, then run the existing optimized o65 execution fixture for relocation,
provider failures, allocation rollback and retained image/Process lifetime.
Keep stack/domain guards, interruption safety and OS/context restoration.

Repeat the warm IDE LIST load profile with unchanged command/media bytes. The
copy phase must be materially below its 136 ms baseline; report its measured
cost, total loading time, emitted size and actual stack use. Do not infer the
end-to-end saving by subtracting the old phase time.

Acceptance: identical loaded bytes, cleanup and publication behavior, measured
copy improvement, and zero added reserved bank-zero bytes.

## CL2 Decode complete scalars directly

Add a small emitted O65READ fixture that records value, cursor position and
error before changing U16/U32. Use the failure table above as its independent
oracle. Implement complete-width fast paths with explicit little-endian byte
loads and widening, retaining the existing bytewise behavior for short input.
Avoid alignment assumptions and casts that could change bank-crossing accesses.

Cover zero/maximum/mixed-byte values, nonzero positions, unaligned starts,
exact-end reads and reads crossing a 64 KiB boundary. For both widths cover
every shorter remaining length, position beyond limit, a prelatched distinct
error, repeated reads after failure and offsets that would wrap an addition.
Check input/cursor/output guards and bounded completion.

Run this small fixture raw and optimized to check far-pointer arithmetic and
integer widening. Ordinary integration stays optimized: run the o65 validation
fixture with its truncation/mutation oracle and allocation-failure cleanup,
then the execution fixture for imports and relocated bytes. Reuse unchanged
emission within a slice rather than duplicating whole-system matrices.

Update the loader observer's acceptance conditions: its old 4,446 Take count
belongs to the baseline, not the new implementation. Continue recording nested
reader calls and checking complete phase accounting. For the same LIST image,
the successful U16/U32 paths should eliminate their nested U8/Take calls and
reduce reader/loader elapsed time without changing accepted/rejected inputs.

Acceptance: identical scalar success/failure semantics in both compiler modes,
unchanged format/provider/relocation results, measured reader improvement and
zero added reserved bank-zero bytes.

## CL3 Measure the combined refactor

Build fresh optimized standalone VBXE demos through tools/build_demo.py with
OF816, matching media, pinned ROM/notices and five-second autoboot. Preserve the
comparison's SIO/IDE settings, filesystem geometry and exact command payloads;
fail the comparison if LIST bytes differ. Recreate the matched SIO media from
the same payloads when necessary.

Repeat tools/measure_list_loading.py for both transports: one cold and three
warm `LIST >NIL:` invocations each. Keep cold and warm results distinct. Compare
search, DOS staging, validation, provider resolution, allocation, copy,
relocation and total loading times; nested reader costs remain nonadditive.
All warm cases must retain zero physical reads and cache misses.

Check one loaded LIST invocation with ordinary console output for directory
rows and pixel results, using the existing listing fixture rather than adding
another harness. Finish the host suite and affected emitted checks, with
per-invocation ownership, unchanged disk bytes, stack/domain guards and EXIT
restoration. No full release matrix or release publication belongs to this slice.

Update the history report and compact development evidence with matched inputs,
actual timing ranges, routine/code sizes, stack use and memory costs. Preserve
the original baseline record. Update the roadmap and plan status to describe
the completed behavior and any remaining performance limits. Keep a change only
when its focused correctness checks pass and its intended phase improves beyond
the baseline's observed timing spread; no fixed speedup is assumed in advance.

Acceptance: reproducible improvement in warm loading on both transports,
unchanged visible behavior and ownership, and complete development evidence.

## Memory and commit boundaries

Expected added reservations are fixed **0**, per-Task **0** and idle **0**
bank-zero bytes for every slice, including guards, alignment and unused capacity.
No additional upper-RAM buffer or persistent allocation is intended. Report
actual resident/upper code sizes and stack peaks separately from reservations.

Keep the copy change and reader change in separate implementation commits, each
with its focused checks and evidence. The final integration record follows in
its own commit. CL0 reuses the retained baseline and needs no executable change.
