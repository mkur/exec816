# FastBasic responsive editor implementation plan

Status: implementation started, 25 October 2026. RE0 is in progress; RE1 through
RE8 are pending. See the [development record](../history/fastbasic-responsive-editor.md).

[Plan index](README.md) · [Workbench contract](../reference/fastbasic-workbench.md) ·
[Earlier refresh](../history/fastbasic-editor-refresh.md) ·
[AES contract](../reference/aes.md) · [VDI contract](../reference/gem-vdi.md) ·
[Display ownership](../reference/display.md) ·
[Platform budget](../reference/platform.md#bank-zero-memory-budget) ·
[Testing policy](../contributing/testing.md)

Make BASIC.APP responsive during typing, insertion and deletion of lines, and
scrolling up, down, left and right. Preserve usable pixels with the blitter,
move their retained character and attribute state consistently, and reconstruct
only the newly exposed or otherwise changed cells. Publish deferred damage
without invalidating unrelated source rows, status text or margins.

Deliver reusable public AES and graphics operations through the existing
application bindings. Exec continues to own Tasks, signals and I/O lifetime;
the display adapter owns hardware admission, completion and recovery. Rendering
and editor changes need no private kernel operation or scheduling exception.
Keep the interpreter Process, BASIC state, Restart interpreter, file transactions
and Check/Run/Stop/Build semantics intact.

## Current behavior

The [key handler](../../examples/gem-basic/editor.c) nominates the visible suffix
when an edit changes the line count. The
[painter](../../examples/gem-basic/editor-paint.c) compares retained cells but
forces the whole client dirty when a published change cannot finish in one
turn. That includes the status strip and margins. Changing the first visible
line or horizontal offset also invalidates the whole cached geometry.

A build-local diagnostic at source revision `de7dfce9` ran the emitted editor
and painter against independent pixels. Its 16-column, six-row viewport gives:

| Operation | Source cells drawn | Status cells drawn | UPDATE scopes | Empty scopes |
| --- | ---: | ---: | ---: | ---: |
| Insert a newline at the top | 96 | 16 | 3 | 1 |
| Join that newline | 96 | 16 | 3 | 1 |
| Insert a newline at row four | 18 | 1 | 1 | 0 |
| Scroll vertically by one row | 96 | 16 | 3 | 1 |

The diagnostic passes 77 assertions; these counts describe drawing work, not
hardware latency. Its runner, generated fixture and results are under
`build/fastbasic-scroll-audit/`. RE0 must preserve this evidence and its source
hashes before implementation. The earlier matched append/caret measurements
remain in the linked refresh record; new scroll and structural-edit cohorts
must use the current complete system.

Glyph drawing already uses the accelerated renderer. BASIC has no operation
for copying existing rows or columns. The native console's backing-scroll
protocol is private to that renderer; it cannot be borrowed by BASIC. Current
Layers screen-copy admission also rejects externally painted GEM layers.
Implement an owned graphics operation instead of bypassing either policy.

## Required behavior

Define movement by signed pixel offsets. The editor uses multiples of its
eight-pixel cell size, while the public graphics operation accepts pixels.
Direction names below describe pixel movement; navigation commands translate
their viewport movement into the corresponding content displacement.

| Editor action | Preserved movement | Reconstruction |
| --- | --- | --- |
| Scroll up | Existing content moves upward | Bottom rows |
| Scroll down | Existing content moves downward | Top rows |
| Scroll left | Existing content moves leftward | Right columns |
| Scroll right | Existing content moves rightward | Left columns |
| Insert a line | Unchanged suffix moves downward | Split/new line, caret and any exposed strip |
| Delete or join a line | Unchanged suffix moves upward | Joined line, caret and bottom strip |

Move only the text grid or its affected subrectangle. Keep status, footer
padding, margins, title and gadgets independent. Support a split in the middle
of a line, indentation, tabs, syntax colours, selection and a trailing empty
line. A one-line edit must not acquire whole-window damage just because it
needs several turns.

Scrolling must work through existing caret navigation, horizontal reveal,
vertical arrows, thumb movement and mouse selection at the viewport edge.
Adjacent movements with reusable overlap take the copy path in all four
directions. Page jumps without overlap reconstruct the viewport. Existing
geometry, fold and document-replacement operations keep a correct bounded
reconstruction path. Horizontal scrollbar widgets are outside this delivery;
horizontal panning itself is required.

## Acceptance and measurement

RE0 freezes the current application, native system, test sources, documents,
ROM, emulator binary/configuration, geometry and observation protocol. Use the
dedicated AltirraOS 3.44 65816 ROM selected by the
[platform pin](../../toolchain/altirra-shell-paced.json), with SHA-256
`85a6e927038f401f05f0056fd41a062986cbf7e104c1ac135c248764c132c9a7`.
Use the current demo's 800XL/PAL, 8x CPU, 63 high banks, shadow ROM, VBXE FX 1.26
at $D600, and port-2 ST mouse. Record the actual renderer and emulator inputs
from the selected build; a nominal configuration alone is insufficient.

Measure at least twenty physical-key samples per ordinary cohort. Observe
every PAL frame from the first offered key edge, including frames while the
key remains held. Use the same three-frame hold, release sequence, setup,
geometry and documents for baseline and candidate. Compare the complete
visible text grid and status with independently generated pixels, including
the caret, colours and selection. Do not stop at the first changed glyph.

| Cohort | Required gate on the pinned default viewport |
| --- | --- |
| Append, insertion within a line, Backspace/Delete, horizontal and vertical caret movement | p95 input readiness and complete target scanout each at most 100 ms |
| One-cell viewport scrolling in each of four directions | Same 100 ms gates, with preserved pixels and no unchanged status/margin drawing |
| Return and newline join at the top and middle of a populated viewport | Same 100 ms gates when the document gap is already local |
| First edit after a far caret move in a 32 KiB document | Separate p95 readiness and scanout target of 200 ms; report gap movement and index costs |
| Page/slider jumps without overlap, resize, exposure, document replacement | Correct bounded completion; no regression against the frozen baseline |
| Repeated input, direction reversal and an edit during repair | Every accepted edit survives; final independent pixels match after input stops |

About five PAL frames are 100.28 ms and fail the 100 ms gate. About ten are
200.56 ms and fail the 200 ms gate. Keep model acceptance, input rearming,
paint completion and complete scanout as separate timestamps.
Input readiness means return to an event-dispatch boundary where the next
ordinary edit can be accepted; pending bounded paint need not be finished.
The far-gap fixture must leave insertion capacity or use an accepted deletion
or length-preserving replacement, rather than timing a rejected capacity check.

Also exercise minimum and maximum supported work areas, odd window positions,
long horizontally panned lines and the maximum document. Record their separate
latency distributions and preserve the existing 120-frame maximum-document
fixture bound. They must not be substituted for the frozen default cohort.
Measure pointer delivery and native peer progress while scrolling; retain the
existing pointer and serial deadlines. Idle or completely hidden editors must
not poll solely to repair invisible pixels.

Missed timing gates keep their slice and overall performance acceptance open.
Do not change key holds, observer cadence, Task priorities, geometry or damage
limits to obtain a nominal pass. Functional delivery and performance acceptance
are distinct entries in the final execution record.

## Shared interfaces

### Explicit AES invalidation

Add a public `ExecAESInvalidate(window,x,y,width,height)` helper. It requires
the caller's UPDATE scope and declares logical damage in screen coordinates
clipped to that window's work area. Logical invalidation includes covered
pixels and is independent of the VDI user clip. It reports no paint completion.
An explicit empty declaration means no additional logical damage; malformed
dimensions remain errors.

Generate any declaration flag or record extension from
[aes-server.json](../../abi/aes-server.json). At outer END_UPDATE, consume
declared damage and actual drawing changes, retaining older unsatisfied paint
obligations. An update with an explicit declaration must not acquire the
implicit whole-client invalidation solely because it drew nothing. An ordinary
unreported update retains conservative invalidation semantics.

The existing eight-entry paint journal remains a completion journal. Do not
turn invalidation into an acknowledgement, reuse an old paint epoch, or claim
that hidden pixels were drawn. A conservative declared rectangle may require
reconstruction of unchanged cells inside it; it must not spread into status or
margins. A wholly completed copy plus exposed-strip repair can acknowledge the
affected rectangle only after every pixel in it is known current.

Use the existing local binding and presenter handoff. If new wire/view fields
are needed, update the generated layout, C import version and all applications
together. Retain one current ABI and implementation. Rebuild the complete
application set when that ABI changes.

### Owned graphics copies

Add a reusable public graphics helper with this contract:

```c
WORD ExecVDICopyRect(WORD workstation, WORD x, WORD y,
                    WORD width, WORD height, WORD deltaX, WORD deltaY);
```

It copies the source rectangle to its translation by the signed offsets.
Source coordinates and dimension arithmetic use wide intermediates. Return
distinct generated results for completed copy, reconstruction required before
any mutation, and operational error. Empty or identical copies complete
without hardware work. This extension does not advertise the full GEM MFDB or
raster-operation family.

Require a live caller-owned workstation and the owning window's UPDATE scope.
Use the existing display grant, physical-access protocol and adapter. Before
copying, establish that both source and destination are inside the work area,
the user clip and one fresh visible work rectangle. A covered source, stale
presentation or changed geometry returns reconstruction-required without
changing pixels. The application must also hold the matching settled source
generation; a character cache alone does not prove valid screen pixels.

Support overlap in both axes with the required memory-copy direction. Include
odd-X packed-pixel edges; use an aligned interior and bounded edge handling
where the existing hardware copy requires even pixels. Freeze the edge staging
and ordering in RE2 so no earlier write destroys a later source pixel. Read
source pixels with pointer/caret overlays excluded, and preserve the display
adapter's overlay restoration and fault handling.
Even horizontal displacements, including every editor cell step, are required
accelerated cases at both X parities. A displacement that changes pixel parity
may return reconstruction-required before mutation in this delivery; expose
and test that limit explicitly.

The adapter owns any asynchronous copy and completion signal. Retain operation
records and edge storage until completion or proven quiescence. The caller
sees completion only after dependent pixels are safe to use; no pending DMA
may outlive UPDATE release or workstation storage. A fault after partial
mutation is an error, not a harmless request to redraw. Invalidate the affected
area, retain unsafe resources through reset-required recovery, and follow the
existing display failure route.

Keep existing physical drawing/work bounds. Split larger copies in an
overlap-safe order when necessary, without a new busy-wait, global Forbid,
Task, priority rule or driver-specific kernel service. Mouse sampling, serial
service and other native Tasks remain live. Externally painted layer policy
is not weakened to make BASIC eligible for a private copy operation.

Define constants and any layouts in [vdi-client.json](../../abi/vdi-client.json)
and the relevant binding manifests; generate declarations and assembly inputs.
Measure direct calls through emitted code in addition to editor integration.

## Editor state and lifetime

Separate viewport geometry from the first visible source row and column.
Keep a settled presentation identity: document, source generation, visible
mapping, geometry and paint epoch. Describe pending movement with one bounded
translation record and affected row/column intervals. Do not allocate during
a keystroke or retain pointers into temporary event storage.

Before a copy, remove caret and selection marks that cannot move with the
underlying text. Repair them from retained source appearance without reporting
premature completion. After the copy, shift retained text, base syntax colours,
validity and damage consistently, then compose new overlays at their final
positions. Commit the screen identity and consume pending movement only after
the copy, exposed repair and END_UPDATE succeed. Failed or incomplete work
remains pending and ineligible as a later copy source.

Document edits need an explicit old-to-new row mapping. A source generation
change alone must not forbid reuse of an unchanged suffix, and equal newline
counts do not prove an unchanged mapping. Preserve source offsets/line identity
for reusable rows; invalidate the split/join boundary, changed syntax and
selection ranges. Account for tab expansion and horizontal offsets.

Coalesce successive movement only while its source identity remains valid.
New input may replace a prepared translation with a bounded reconstruction
job; it must never apply an obsolete copy to newer pixels. Direction reversals,
Undo/Redo, folds, scrolling during repair, resize and document replacement all
need explicit state transitions. Initial delivery may reconstruct complex
folded/selected edits, while ordinary four-direction scrolling and unselected
line splits/joins must take the copy path when eligible.

Keep four-row composition, 96 reconstructed cells and eight margin fragments
per paint turn. Copied pixels use a separate bounded adapter-work budget; do
not charge them as regenerated glyphs or treat copy completion as complete
scanout. Release UPDATE between independent paint quanta and obtain fresh
visibility on reacquisition. New exposure always forces repair independently
of character-cache equality.

For large documents, profile gap movement, line-offset maintenance, syntax
composition and procedure indexing separately from display work. Use bounded
CPU-memory movement and yield when its work budget is exhausted; avoid a yield
after an already completed tiny move. Keep background indexing behind accepted
edits. Preserve document, undo, saved-generation and file-transaction semantics.
Any compiler defect belongs in actionc with a focused regression.

## Memory budget

The existing editor keeps a 5,120-byte appearance reservation inside its
6,784-byte application model. Reuse it for text and attributes. Allow at most
1,024 additional reserved upper bytes per editor for translation, row mapping
and presentation identity: at most 6,144 reserved refresh bytes in total.
Enforce the reservation with a compile-time bound, including spare capacity.

Allow at most 1,024 additional upper bytes per VDI workstation for copy records,
packed-edge staging and completion state. Allocate this once at workstation
creation. New AES declaration metadata has a budget of 128 additional upper
bytes per client, including its owned views, and 128 shared upper bytes.
Report actual payloads, allocation rounding, static-arena alignment/spare and
loaded image extents for every slice; these are ceilings, not automatic
allocation requests.

Additional reserved bank-zero bytes must remain zero for fixed storage,
root/kernel, each of the twelve public Tasks and idle, including guards,
alignment and unused reserved capacity. Keep existing DP ownership and stack
pools. Report emitted stack peaks and headroom; do not silently enlarge a pool
or its declared minimum. No new persistent VRAM bitmap or backing reservation
is required. Covered content uses the reconstruction path.

## Executable slices

Each slice ends with runnable code and its focused development checks. Update
the evidence and actual memory costs before advancing. Keep independent
implementation slices reviewable.

### RE0 Freeze the baseline and observers

Preserve the current package, application, native source and the diagnostic
fixture/results described above. Add permanent focused probes for top and
middle Return/join, blank suffixes, all four scroll directions and direction
reversals. Extend [the measurement runner](../../tools/measure_fastbasic_editor.py)
to load a deterministic populated document and long lines through normal UI
flows. Observe the whole visible grid/status and collect the separate timestamps,
glyph counts, UPDATE scopes, invalidation regions, copy counts and copied area.
Record gap distance, affected line count and background-index activity.

Exit: reproducible current-system baseline and independent pixel oracles, with
all performance cohorts and thresholds frozen before optimization. Archive
artifacts under `build/fastbasic-responsive-editor/`; retain the compact evidence
record under the repository's development/history organization.

### RE1 Publish bounded damage through AES

Implement explicit invalidation, generated ABI changes and current callers.
Replace the editor's unconditional full-client deferred fallback with declared
text/status/margin regions and matching local obligations. Preserve unsatisfied
damage across turns, visibility changes and publication failures. In a blank
suffix, nominate only rows whose appearance or caret can change.

Extend [the painter oracle](../../tests/programs/basic_paint.c) and direct AES
tests for empty declarations, hidden changes, partial coverage, journal rollover,
untouched sibling windows, saved snapshots and END_UPDATE failures.

Exit: a multi-turn source repair causes no unrelated status or margin drawing;
ordinary append/caret remains a single nonempty UPDATE. All exposure and hidden
publication checks still pass.

### RE2 Implement four direction graphics copies

Implement the public copy helper and its adapter path, with generated result
constants/layouts and all four displacement signs. Exercise native callers
independently of BASIC. Test overlap direction, diagonal displacement, odd/even
edges, clipping, zero/identical areas, unsupported source visibility, overlays,
busy completion, timeout/quiesced/reset-required failure and ownership retirement.
Use focused raw/optimized probes for changed ABI layouts and call preservation;
run broader pixels, lifetime and device coexistence optimized.

Exit: independent source-pattern pixels prove every supported copy, and
reconstruction-required results precede mutation. Driver completion and error
paths preserve their existing deadlines and resource lifetime.

### RE3 Retain movement and presentation identity

Add bounded pending translation and row/column mapping to the editor. Separate
content origin from physical geometry, and establish eligibility from settled
pixels plus the fresh UPDATE view. Move character, attribute and damage state
with correct overlap ordering. Keep old/new caret and selection repair explicit.

Exit: emitted tests distinguish reusable movement from pending, stale or exposed
source pixels. Newer input, failed UPDATE and generation changes cannot retire
or reuse an incomplete operation. Report the reserved upper-byte deltas.

### RE4 Connect scrolling in all four directions

Route vertical arrows, horizontal/vertical caret reveal, overlapping thumb
movement and selection auto-scroll through the shared movement path. Repair
only exposed rows or columns and necessary overlays. Cover multi-cell deltas,
direction reversals, long tabbed lines, mixed syntax runs and viewport limits.
No-overlap jumps and covered/stale sources take bounded reconstruction.

Exit: real loaded BASIC.APP produces independent expected pixels after physical
input in every direction. Eligible scrolls issue copies and draw no unchanged
status text or margins. Collect the four latency cohorts without declaring a
pass before both readiness and complete scanout meet the frozen thresholds.

### RE5 Reuse unchanged rows after structural edits

Apply the mapping to Return, Backspace/Delete at newlines, and ordinary
multi-line insertion/deletion. Copy the preserved suffix of the viewport and
repair the changed boundary, exposed strip and overlays. Preserve indentation,
tabs, syntax, trailing empty lines and undo groups. Give complex selection/fold
edits a correct fallback rather than assuming all source rows translate.

Exit: top and middle splits/joins use copies when eligible; saved/reopened
source, Undo/Redo, equal-line-count replacements and pending-input cases match
the logical model and independent pixels. The status strip changes only for
its actual text or saved-state marker.

### RE6 Bound edit and input work

Use RE0 attribution to reduce expensive gap moves, line-index work or repeated
composition. Keep byte/time-bounded CPU work and remove unnecessary completed
move yields without hiding partial edits from the owning editor. Share row
composition with translation state and keep procedure indexing behind paint.
Service input between paint turns and coalesce obsolete presentation work while
preserving the order of accepted document edits.

Exit: local edits meet their target and the separate far-gap cohort meets its
200 ms target, or the exact remaining cost stays recorded as open. Maximum
document, undo capacity, file controllers and assistance checks pass. Settled
idle/hidden behavior and guards remain intact.

### RE7 Validate interaction and responsiveness

Run the frozen matched measurements on the final current-system candidate,
including repeated keys, reverse scrolling and input during a partial repair.
Validate default, minimum and maximum geometry, odd placement, partial and full
coverage, menu/dialog overlays, expose/move/resize, focus changes, hidden idle,
allocation/drawing/copy failures and cleanup. Check native peers, pointer input
and actual serial service during sustained scrolling and a large edit.

Run the host suite, affected generated-definition checks, optimized painter,
logical/file/assistance tests and selected graphics/AES ownership/fault checks.
Exercise retained integer/float interpreter state, Run/Stop, Restart, Check/Build
and cancel/quit while repair is pending. Include a native shell/EDX regression
because UPDATE and display access are shared.

Exit: independent pixels, bounded completion, resource retirement and actual
latency distributions are recorded together. Every unmet gate remains explicit.
This is the development tier; release/platform qualification is separate.

### RE8 Deliver the matching system and applications

Update the workbench, AES, VDI and display references to describe implemented
contracts and limits; record results in history with machine-readable evidence
and source/artifact hashes. Update the guide and plan/roadmap status to the
actual final state.

Build with [tools/build_demo.py](../../tools/build_demo.py). Rebuild all affected
applications against the current imports. Keep OF816's five-second autoboot,
combined writable D1 SYS/WORK, matching XEX/cartridges, port-2 mouse, separate
QED ATR and ported MD5/ARC/EDX with overlays and notices. Verify extracted ZIP
checksums/CRCs, cold ATR boot and the loaded editor's copy/edit/Run workflow.
Use the packaged current image for a final physical interaction check.

Refresh the corresponding source delivery. Keep intermediates, observers,
manifests and test output outside `exec816-demo.zip`. When installing into
FujiNet SD, compare writable media with the installed template and preserve
modified user media in place, using a fresh versioned installation as needed.

Exit: matching runnable distribution and source delivery, recorded development
scope and memory costs, and an accurate list of remaining performance gates.

## Completion record

Record RE0 through RE8 individually, with measured glyph/copy work, independent
pixel results, input-ready and scanout p95 values, serial/pointer bounds, stack
headroom and allocation/reservation changes. Distinguish the aligned/odd-edge
copy paths, covered-source fallback and no-overlap reconstruction in those
results. A faster model update or a lower glyph count cannot close the visual
latency gate.
