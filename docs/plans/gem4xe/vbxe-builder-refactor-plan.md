# VBXE command builder refactor plan

[GEM plans](README.md) · [Implementation plans](../README.md) ·
[Drawing adapter](../../../ports/gem4xe/adapter/README.md)

Status: BR1–BR2 implemented; BR3–BR4 pending. Refactor the trusted GEM command builders to remove repeated
geometry validation and reduce construction cost in Control Panel redraws.
Use generated upper-memory lookup tables for chunk limits and work costs,
and advance a write pointer through sequential records. Keep clipping and
dependency ordering, and enforce list capacity at chunk or run boundaries.
The table budget is up to one 64 KiB bank, shared by the renderer. Implement in
executable slices, committing each after its selected development checks.

## Starting point

Use the existing [prepared-list measurements](../../development/vbxe-prepared-submit.json)
and [execution record](../../history/aes-hybrid.md#prepared-vbxe-lists) as the
baseline. That change already removes record decoding in `VbxeOwnerSubmit`.
Maximum measured widget-paint CPU is 33.319 ms; button-pixel p95 is
159.082/199.246/179.375 ms for idle/scroll/disk loads. HY4 remains open.
There is no separate baseline milestone. Retain the measured image and its
source hashes before implementation, including the currently uncommitted
prepared-submit changes.

The remaining generic `blit_mask` builder checks mode and both VRAM extents,
divides to choose a row limit, and performs wide work accounting. The dedicated
`blit_glyph` builder already trusts geometry but checks and accounts for batch
capacity on every glyph. Widget clipping and fixed screen/font/scratch layouts
establish much of this information before construction starts.

The [list-size analysis](../../development/vbxe-list-sizes.json) reuses the
same ten-gesture idle/scroll/disk trace. It reads the command count at
`VbxeOwnerSubmit` entry and separates callers and widget/console paint spans.

| Prepared lists | Lists sampled | Median commands | p95 | Maximum |
| --- | ---: | ---: | ---: | ---: |
| Control Panel drawing | 323 | 15 | 38 | 40 |
| Console drawing | 118 | 50 | 50 | 50 |
| Cursor updates | 613 | 3 | 4 | 4 |

Native text uploads and asynchronous scroll launches are outside this sample.
Size tables for the supported 64-command limit, not the observed maximum.
Each record occupies 21 bytes; a full list occupies 1,344 bytes inside the
existing 4 KiB command arena.

## Boundary and limits

The internal builders accept valid renderer-produced geometry. Their contract
is documented and exercised by emitted-code tests; it does not require runtime
revalidation at each primitive. Existing public drawing entry contracts and
public raw `VbxeSubmit` validation remain at their current boundary in this
refactor. Do not add replacement checks in intervening wrappers.

| Operation | Responsibility |
| --- | --- |
| Renderer clipping | Compute visible intersections, discard empty results and preserve partial packed-pixel edges. |
| Internal record construction | Encode known modes, strides and admitted screen, atlas or scratch coordinates. |
| Batch reservation | Ensure space for at most 64 records and at most 8,192 estimated bus accesses. |
| Dependency boundaries | Flush before CPU staging access, scratch reuse and operations requiring completed pixels. |
| Submission | Upload, chain, fence and recover from hardware faults using the existing owner path. |

The 8,192-work ceiling is software policy. Keep it and the existing general
builder's maximum sixteen-row records while reducing the cost of enforcing
them. Larger lists are not part of the proposed speedup. Cursor and outline
producers retain their separately established fixed bounds.

Capacity checks are required only where a variable amount of output enters a
finite batch. Once a run has reserved its records and work, its encoder can
write records without checking those limits again. No reservation spans a
public return, callback to arbitrary code, Yield or Wait.

## Generated lookup tables

Generate integer constants during the build, with a deterministic generator
and recorded input/output hashes. Load them with the image into upper RAM;
there is no startup calculation, per-Task copy or runtime validity scan.
Use the existing VBXE constants as inputs and reject unsupported dimensions
at build time. Correct internal geometry remains a producer obligation.

| Table | Layout and meaning | Payload bytes |
| --- | --- | ---: |
| Record offsets | 65 unsigned words: `21 * index`, including the end offset for 64 records | 130 |
| Chunk row limits | Two 512-byte tables: `min(16, floor(8192 / (width * factor)))`, factors two and three, widths 1–512 | 1,024 |
| Chunk work | Two tables of 16 × 512 unsigned words: `rows * width * factor`, rows 1–16 | 32,768 |
| Screen row offsets | 256 unsigned long values: `y * 320`; valid screen coordinates remain unchanged | 1,024 |
| Common stride increments | Four tables of 17 unsigned words: `rows * stride` for strides 320, 640, 1024 and 1280, rows 0–16 | 136 |
| Total before alignment | Shared renderer data | **35,082** |

Select the factor's row-limit/work table once per operation. The work table's
byte index is `((rows - 1) << 10) | ((width - 1) << 1)`; each table is 16 KiB.
Other indices use byte access or shifts by one/two. Do not use packed
three-byte pointer entries or a 513-column array that introduces multiplication
just to index a table. Keep each work table within one CPU bank and verify
actual far loads, index widths and boundary addresses in emitted code.

Use a sequential write cursor for queued commands and the small offset table
for indexed cursor/outline records. Reset the queue cursor with `commandCount`
at open/drain/reset boundaries; direct cursor/outline lists must not advance
it. Any drain before an append requires a fresh cursor. Reserve a run, write
records at successive 21-byte offsets, then publish its actual usage.

Use common-stride tables for the screen, stipple and font atlas. For a variable
raster stride of 1–512, the factor-two work table also supplies `rows * stride`
by shifting its value right once; a zero source stride has zero displacement.
Audit actual producer strides in BR1 and document any remaining generic
arithmetic outside these domains. Skip source/destination advancement after
the final chunk. Preserve wide VRAM addresses even when displacement fits in
an unsigned word.

The screen-row table is a measured candidate: some existing `y * 320` paths
already use shifts/additions. Keep a lookup only where emitted cost and focused
timing improve; table capacity is permission to spend memory, not a requirement
to replace already cheaper arithmetic. Signed label-centering divisions and
clipped-glyph coordinate rounding remain a separate follow-up.

## BR1 Trust internal geometry

Implemented with [development evidence](../../development/vbxe-builder-br1.json).

Audit every caller of `blit_mask` and its fill/AND/OR/XOR wrappers in the selected
renderer and adapter. Cover startup clears, widget strips and stipple,
clipped/zero-ink glyphs, raster staging, and scratch-to-screen publication.
Record which clipping or fixed layout establishes each producer's bounds,
including nonempty dimensions and exclusion of command storage.

Remove the mode-range test and both `VbxeBlitExtent` calls from this private
builder. Keep geometry calculations that determine actual pixels, strip
redirection, fault propagation and the existing queue/split behavior. A missing
producer invariant belongs at its clipping/setup boundary, not in a general
validator called by every primitive. No checked/unchecked runtime mode or
parallel legacy builder is introduced.

Run optimized rendering and widget pixel checks, including odd edges, clipped
glyphs, stipple, XOR, strip continuation and startup. Retain public malformed
argument tests at their existing API boundary. Check cursor coexistence and
selected timeout/reopen cases because these share the command arena. Compare
the same representative widget draw's CPU and list trace with the baseline.

Acceptance: exact pixels, unchanged list splitting/order, and no internal
extent-validation calls in the emitted hot builder.

## BR2 Use lookup tables and sequential record addressing

Implemented with [development evidence](../../development/vbxe-builder-br2.json).

Narrow internal work accounting to 16 bits: admitted list work is at most
8,192, and even a candidate chunk of 512 bytes by sixteen rows at factor three
costs only 24,576. Their sum also fits in an unsigned word. Keep VRAM address
arithmetic wide where required.

Add the generated tables and their build/image provenance. Place them in the
existing C data bank first, following the memory rules below. Replace the row
limit division and both chunk-work multiplications with direct lookups. Cap the
selected row count by remaining rows and preserve existing split/drain
decisions. Advance sequential record addresses by 21, replacing the current
per-record `_Mul16` call in both general and individual-glyph builders. Adopt
the common-stride and indexed-record tables, and measure screen-row lookup
against its current emitted calculation.

Check all generated values against an independent arithmetic oracle. Exercise
emitted loads at first/last entries, row boundaries and each row-limit
threshold; include width 512, sixteen-row candidates, total-operation height
256 and addresses with a low-word carry. Cover lists immediately below, at
and across count/work capacity, plus repeated drain/reset and cursor interleave
to catch stale write cursors. Observe actual hardware lists and rendered pixels.
If section placement or the C/native image bridge changes, add small raw and
optimized load/address probes for that compiler-facing boundary.

Acceptance: identical rectangle coverage and list boundaries, bounded work,
and lower measured construction CPU. Emitted construction must have no general
multiply/divide helper for row-limit selection, chunk work, sequential record
addressing or the covered stride increments. Table indexing must not introduce
such helpers. Retain the focused widget timing and affected fault checks.

## BR3 Reserve full glyph runs once

Add a private run encoder for the eligible full cells in `GemWidgetText`.
Admission requires all eight rows visible and the existing nonzero-ink stencil
mode. Split horizontal clipping into complete-cell runs and partial edge
glyphs; keep partial/vertically clipped and zero-ink cases on the trusted
general path. Preserve blank-glyph skipping and the existing atlas geometry.

A complete even-X glyph costs 96 work units; an odd-X glyph costs 120.
Parity is constant within an eight-pixel-spaced run. Consequently, 64 glyph
records alone cost at most 7,680. A preceding fill or edge operation still
consumes part of the same list's capacity: never apply the glyph-only bound to
a mixed batch without accounting for its existing work.

Reserve a fitting prefix against the current record and work availability,
then encode it directly and publish the actual count/work once. Do not flush
merely because the primitive type changes or reserve a whole label when only
a prefix fits. Blank glyphs must not produce uninitialized records or leave
unused reservations charged. Perform staging/dependency flushes before the
reservation; the encoder must not call another producer while filling it.
Re-evaluate availability only at the next chunk boundary.

Use the BR2 write cursor inside the reserved run. Fixed glyph work is 96 or
120 per emitted record; account once per chunk with constant shifts/additions
or existing table entries. Do not reintroduce per-glyph multiplication or a
general divide to calculate the number of glyphs that fit; use bounded lookup
or comparison against fixed-cost multiples at the reservation boundary.

Implement selected-renderer changes through the checked-in extraction patches
and adapter, leaving the upstream `~/atari/gem4xe` checkout untouched. Reuse
the established fast native text uploader where it already applies; changing
the console's clipped-text dispatch is a separate follow-up.

Run pixel and list checks for even/odd runs, blank runs, 63/64/65 glyphs,
partial edges, vertical clipping, zero ink, and mixed fill/glyph sequences
near both limits. Include a dependency flush and a submission fault between
chunks. Verify record order, scratch publication and cursor restoration.

Acceptance: no per-glyph capacity/extent validation in eligible run encoding,
bounded mixed lists, exact pixels, and lower widget label construction CPU
without extra launches caused solely by switching primitive types.

## BR4 Measure integrated responsiveness

Run host checks and the focused optimized display, renderer, cursor and widget
fixtures affected by BR1–BR3. Use the original active-client panel protocol:
ten gestures per idle/scroll/disk load, intermediate feedback observation,
final pixel checks, model updates, ownership, guards and cleanup.

Compare against the retained prepared-submit image with matching compiler,
ROM, emulator and observer definitions. Record builder CPU, complete widget
paint CPU, input-service gaps, consumption/model/visible-button latency,
list counts and size distributions, maximum list work and completed background
traffic. Track arithmetic and extent-helper calls to show where the savings
occurred, and record table payload, alignment, image growth and bank placement.
Separate any retained arithmetic from the operations eliminated by BR2/BR3.
Summarize nesting correctly; inclusive component times are not additive.

Accept the refactor only with correct pixels and lower construction CPU.
Investigate any visible-button or input-service regression before accepting a
slice; batching throughput alone is insufficient. Preserve failed samples and
explain completion-paced workload differences. These focused runs do not close
HY4: closing it requires the original full frozen/matched comparisons, including
the raw-pointer cohort. Existing feedback observation also cannot establish
whole-gesture flicker freedom.

Record results in development evidence and the AES execution history; update
the adapter/private-builder contract and plan status to match implemented work.

## Memory and execution scope

Target reserved bank-zero delta: **0 bytes fixed, 0 per public Task and 0 idle**,
including guards, alignment and unused capacity. Keep existing upper-RAM command
and staging arenas and VRAM layout; report code, data and measured stack changes
for each slice. Reservation state stays local to a run; any shared queue cursor
belongs in the renderer's existing upper-RAM state.

BR2 attempted placement in the existing C data bank `$0D`. The active panel
fits, but the instrumented renderer requires 28,505 BSS bytes and exceeds that
bank by 1,506 bytes. Preserve this failed link in the development record.
Tables therefore occupy a dedicated read-only `gemtables` section in bank
`$0F0000–$0FFFFF`. The linker and foreign-image validator admit exactly this
read-only bank; native code starts at `$100000` when it is populated. Image
ownership reserves its complete 65,536-byte extent, including unused capacity.
Raw and optimized table-load probes exercise this bridge, far addressing and
ownership. No runtime section, BSS bank or executable-range permission expands.

BR2 table payload is 35,082 bytes with no table padding; the queue pointer adds
four upper-RAM bytes and narrowing work removes two. No per-Task allocation,
bank-zero reservation or additional VRAM is needed. BR3 may add small bounded
glyph-capacity tables within the same reserved bank.

Validation uses the development tier. Reuse existing tests, adding meaningful
boundary cases for the changed batching. Run raw and optimized probes if an
ABI/compiler-facing change becomes necessary; do not expand routine functional
testing into a full qualification matrix. No demo refresh is required.

Presenter continuations, scene-token lifetime, kernel scheduling, priorities,
public API validation policy and broader arithmetic optimization are separate
work. A bounded blitter list does not bound the CPU time of an entire paint
operation or create an input-service opportunity by itself.
