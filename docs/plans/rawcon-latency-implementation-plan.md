# RAWCON cell access and console batching implementation plan

Status: implemented development delivery, 25 October 2026; RC5's visual latency
acceptance remains open. This addresses the remaining
interaction work from [RS6](sdx-resident-stack-implementation-plan.md#rs6-bound-rawcon-dispatch-and-meet-the-interaction-target),
without changing EDX's editing algorithm or the one-active-guest policy.

[Plan index](README.md) · [Measured diagnosis](../history/edx-key-latency.json) ·
[Resident guest contract](../reference/sdx-runtime.md) ·
[Console contract](../reference/console.md) ·
[Platform budget](../reference/platform.md#bank-zero-memory-budget) ·
[Testing policy](../contributing/testing.md)

Keep RAWCON get/put inside the bridge's existing complete-frame transition,
then submit all changed text/caret/status spans through one public console
request. Native Tasks retain preemption; BASIC keeps its parked Process/state.
Use the existing Exec request, message, cancellation and completion primitives.
Driver queue and presentation policy stay in console.device. No new private
kernel service or console-backing access is needed.

The [execution record](../history/rawcon-latency.md) covers RC0–RC4, passing RC5
functional/interrupt checks and the RC6 distribution. Matched p95 input readiness
is about 80 ms for all three cohorts; complete target scanout is about 120 ms.
The plan's overall performance gate is not closed. The remaining measured work
is backing-to-screen presentation after request completion.

## Baseline and acceptance

The diagnostic uses the pinned 8× 65816 PAL desktop, 64×20 cells, ST mouse on
port 2, the dedicated AltirraOS 65816 ROM and three-frame physical key holds.
Each operation has 20 samples. Full target scanout is independently compared
with the expected ATASCII pixels, including captures before input readiness.

| Operation | Current p95 input ready | Current p95 complete target scanout |
| --- | ---: | ---: |
| Insertion | 140.391 ms | 140.391 ms |
| Horizontal caret | 120.336 ms | 120.336 ms |
| Vertical caret | 160.447 ms | 160.447 ms |

One insertion makes 74 cell calls and 75 guest/bridge returns. Its two console
requests take about 55 ms elapsed, including about 52 ms in transfer/wait.
Presenter intervals total about 8 ms. Inclusive routine intervals can overlap
across Tasks and must not be added as exclusive CPU time. The final interval
still combines input rearming and scanout; isolate it before changing policy.

Acceptance is p95 **≤100 ms for both input readiness and complete target
scanout**, for all three ordinary editing cohorts. The pinned PAL frame is
about 20.056 ms: the current frame observer therefore needs at most four
frames, about 80.22 ms. Five frames, about 100.28 ms, do not pass by rounding.
Keep the key hold, observation cadence, geometry and loading exclusion fixed.
Time to the first model change or first glyph is separate evidence.

Correctness, cancellation, device deadlines and resource retirement are hard
gates. If latency remains above the target, record the remaining measured cost
and keep this plan open. Do not relax guards, shorten the acceptance key hold,
raise Task priorities globally or substitute model completion for scanout.

## Implementation decisions

### Bound cell access inside the resident bridge

Bind the active EDX screen when RAWCON Open succeeds. Publish one generated
upper-memory record containing owner slot, screen pointer, width/height,
first/end damage pointers, foreground BREAK pending pointer and a 30-entry
row-offset table. Reserve 96 bytes inside the existing 64 KiB bridge bank,
including alignment and scratch/spare capacity. Build row offsets at binding,
so a cell call needs no general multiplication helper. Publish ownership last;
clear it before console restoration, buffer release or lease release. A parked
BASIC reset or another retained Image must not clear the active owner's record.

Recognize only EDX's bound get/put events after the common veneer has saved the
13-byte frame and the bridge has corrected its JSR return PC. Check the physical
stack domain, all 32 DP guard bytes and foreground BREAK at every boundary.
Perform one bounded caller-owned cell read/write and damage update, then return
through the common guest restore. Get changes A's low byte and N/Z; put preserves
the existing register/flag contract. Preserve hidden B, X/Y, D, DBR and E/M/X.
An unchanged put creates no damage. Invalid coordinates retain SDX error 156
and ordinary trap semantics. Guard/domain failures keep their existing fatal
semantics. BREAK follows the native cancellation path before cell mutation.

The leaf may use a documented four-byte scratch area in the already-owned
native Task DP, saving and restoring those bytes below the physical frame.
It must not borrow another Task's DP, add bank-zero scratch, or call a native
Task-stack checker while S is in page one. Generate the scratch/frame contract
from the pinned ABI inputs and account for every temporary push and NMI entry.

Keep the leaf short under the existing transition protocol. IRQ masking does
not mask NMI: a distinct fast-cell phase and the gate must make asynchronous
entry acknowledge/defer safely. No ROM call, allocation, DOS call, rendering,
wait or Task dispatch occurs inside it. Complete a successful cell exactly once,
retire its event, and drain pending VBI/owned work before another guest
instruction. Restore all temporary bytes and the complete-frame S before ROM
borrowing or scheduling becomes possible again; a lower transient S must never
be published as that anchor. Refactor the restore tail so this route never reads
native-call arguments from the physical guest stack. Retain partial-pop
reconstruction.

The engineering budget is at most 50 µs for the full masked cell transition at
the pinned 8× clock, including guard and restore work. Establish an emitted
instruction bound and measure bus/interrupt effects. Actual serial service and
pointer-gap limits remain authoritative; the budget cannot justify a deadline
regression. Rework the leaf if it cannot fit those limits.

Move successful get/put semantics into this single bridge implementation.
Remove the previous Action! cell dispatch once callers/tests migrate. Other
RAWCON operations keep the ordinary service route; errors and cancellation
detach to native handling. Do not retain a selectable old cell runtime or
silently suppress asynchronous work to obtain a faster measurement.

### Add one public request for cell spans

Add `CONCMD_WRITE_CELL_SPANS=15` to [abi/console.json](../../abi/console.json),
with generated constants and this public `CellSpan` layout:

| Field | Type | Byte offset |
| --- | --- | ---: |
| column | CARD | 0 |
| row | CARD | 2 |
| data | far BYTE POINTER | 4 |
| length | CARD | 8 |

The record is 10 bytes, alignment two; byte 7 is padding. `io_Data` points to
0–30 records, `io_Length` is descriptor bytes, and `io_Offset` is zero.
A nonempty length must be a multiple of 10 and at most 300 bytes. Each span
contains 1–80 exact cell bytes and stays within its row. Descriptors apply in
array order; overlaps are allowed and later cells win. Neither the stream
cursor nor console mode changes. A zero-length request completes with zero.

Use the ordinary output FIFO and `DOS.ConsoleIO`; the operation is reusable by
native Tasks. Validate descriptor structure and geometry once when the worker
claims the request, before its first model edit. Live descriptors, nested data
buffers and their lifetime are caller responsibilities. Keep existing endpoint
ownership admission and avoid another layer of repeated mapping/handle checks.

`io_Actual` counts descriptor bytes for fully consumed spans. A partial span
can have changed a cell prefix but contributes zero descriptor bytes until
complete. On success Actual equals Length. Cancellation and quiesced errors
return that completed prefix and one terminal reply; they need not roll back
accepted cells. The caller retains the array and all source buffers until
completion collection. The device retains nothing from them after reply.

This is one FIFO request, not an atomic full-screen paint. Keep at most 64 source
cells per worker quantum and the existing presenter/fragment limits, with input,
controls and instance rotation between quanta. Preserve one bounded presentation
pass at terminal model acceptance and existing live-fragment retirement rules.
Completion still means accepted model data and retired caller pointers; it is
not a scanout fence. Later writes cannot pass the vector. Geometry changes,
hide/destroy and Stop use the driver's existing drain/cancel/retirement protocol;
no geometry-changing control may invalidate an active vector's admission.

Track vector index and intra-span offset in two new CARD fields per console
Instance. Grow Instance 202→206 bytes, move the default Presentation offset
362→366 and Routes 416→420, and retain Windows at 688 and the 896-byte static
reservation. This consumes four bytes of existing padding before Windows.
Generate all layouts and rebuild consumers together. Dynamic Instance heap
allocations remain 208 bytes with eight-byte rounding. Do not use the existing
bulk-scroll Batch context as a second request owner.

### Flush EDX damage with one vector

Allocate the 300-byte descriptor capacity once at screen Open, from upper heap,
and release it at retirement after all requests settle. Keep a pointer in the
SDX Session; do not put this array on a native Task stack or allocate per key.
The screen remains the sole application-owned ATASCII buffer.

Flush gathers nonempty first/end spans in row order, points descriptors into
that stable screen and makes one synchronous `DOS.ConsoleIO` call. Unchanged
status rows and idle waits issue no request. The software inverse caret is
ordinary cell damage. Do not widen spans or add a second full-screen copy.

Keep the existing DOS completion convention: a successful return supplies the
descriptor-byte count; BREAK can return a positive prefix with IoErr still set,
whereas other errors return -1 and hide the device's Actual from this wrapper.
Capture IoErr immediately. A nonzero cause remains a failure even if the returned
count equals the full vector length. Clear only whole spans covered by a valid
nonnegative returned prefix. On -1, conservatively retain every submitted span;
replaying exact positioned cells is safe. Never inspect private DOS request
state to recover a hidden prefix or change completion rules for other commands.
Retain the partial span and remaining damage, preserve the original cause and
follow existing console cleanup rules. No guest resumes or mutates the lent
screen while Flush waits. A zero-damage Flush is a no-op; a new key remains
behind Flush's accepted output boundary.

## Executable slices

Each slice leaves a runnable build, records source/artifact identities and
reports reserved memory changes. Keep historical evidence unchanged. RC1
prepares the one implementation; RC2 cuts over its get/put handling together.

| Slice | Result | Depends on |
| --- | --- | --- |
| RC0 | Freeze baseline and separate remaining pipeline costs | Current tree |
| RC1 | Bind/unbind record, row offsets and focused frame probes | RC0 |
| RC2 | Get/put leaf, common restore and asynchronous-entry gates | RC1 |
| RC3 | Public span-vector request and bounded console execution | RC0 |
| RC4 | One-request RAWCON Flush and damage/error retirement | RC2, RC3 |
| RC5 | Matched latency, fairness and application acceptance | RC4 |
| RC6 | Current contracts and rebuilt checked distribution | RC5 |

### RC0 Freeze measurements and isolate the pipeline

Preserve the diagnostic observer, committed base `2db74777`, actual worktree
inputs, native image, guest/tool binaries, ROM/emulator hashes and compiler pin.
The current observer/diagnostic changes are uncommitted preparation; record
them explicitly rather than treating the base commit as their source identity.
Use [actionc.json](../../toolchain/actionc.json) without an undocumented override.

Extend passive markers for cell events, native detach/restore, request publication,
worker acceptance/reply, READ_KEYS readiness and presenter completion. Separate
queue/scheduling delay from model-copy/render work and the final rearm/scanout
interval. Establish per-event counts for get, put and keyboard/checkpoint returns.
Any detailed timing partition must distinguish exclusive Task time from nested
elapsed spans. Preserve the original 20-sample records and independent pixels.

Exit: reproducible unchanged-runtime baseline and explicit accounting boundaries.

### RC1 Bind screen state without changing cell execution

Define binding/phase/scratch constants in [abi/sdx.json](../../abi/sdx.json)
and generate Action!/assembly definitions. Add internal bind/unbind entry points
to [SDXRUNTIME](../../lib/dos/sdxruntime.act) and wire screen Open/Retire.
Register their native ABI/stack shapes in
[native_program.py](../../tools/native_program.py).
Publish only while the caller owns the active lease. Failure rollback, Close,
lease Release, Image reuse and a new invocation must leave no stale binding.

Add a focused `tools/test_sdx_rawcon.py` runner with planned selectors
`--group binding|cells|transitions --case raw|opt --output DIR`. The binding
fixture checks exact far pointers, all row offsets, two retained Images,
allocation failure, repeated Open/Close, parked BASIC and slot reuse. Raw/opt
cases cover only changed ABI/frame access. Audit the leaf's proposed temporary
stack and asynchronous paths before enabling it.

Exit: bind/unbind and emitted layout checks pass; production cells still use
the existing path and all reservations remain within the declared budget.

### RC2 Cut get/put over to the bridge leaf

Change [sdx-runtime-probe.s](../../platform/altirraos/sdx-runtime-probe.s),
native bindings and [SDXSERVICE](../../lib/dos/sdxservice.act) together. Reuse
the complete frame and restore path without detaching for successful cells.
Do not increment the saved JSR PC twice, replay a consumed put after an NMI,
lose get's N/Z, or leave native DP scratch altered. Preserve ROM borrowing and
native S/D when the bridge next returns an ordinary event.

Migrate the emitted screen fixture to the same production cell implementation.
Cover all 256 cell values, inverse caret, unchanged writes, coordinates and
geometry edges, first/end damage, traps, BREAK and native cause preservation.
Keep focused raw/optimized frame cases and run maximum geometry optimized.

Force real NMI at binding publication, complete-frame capture, scratch borrow,
cell/damage commit, scratch restoration and handoff to the common restore.
Retain the existing partial-pop/early-emulation cases. Add canaries proving
insufficient headroom fails before scratch/guard corruption, and recompute the
source-derived stack bound including the four temporary bytes and ack NMI in
[audit_sdx_stack.py](../../tools/audit_sdx_stack.py).
Run a selected `generic56k` IRQ trace/replay with pointer activity immediately:
the leaf is a new masked interval and cannot wait until packaging for this check.

Exit: exact cell/frame/error behavior, bounded interrupts and native restoration
pass. Record cell-only latency and verify ordinary cell events no longer return
through the Action! service loop. Preserve EDX's original call sequence.

### RC3 Implement the public cell-span request

Generate the command, `CellSpan` and Instance layouts. Verify that generic
`DOS.ConsoleIO` forwards the operation without a new wrapper or validation
layer. Update the console driver's request classification, write quantum,
cancellation and terminal cleanup. Keep FIFO and active-request ownership in
the driver using existing public Exec operations. Do not change Task priorities,
the public kernel ABI or the bulk-scroll batching policy.
Publish the implemented command's public contract with this slice.

Add `tools/test_console_spans.py --case raw|opt --output DIR` as a planned
runner. Small raw/optimized cases prove record offsets, far pointers and counts.
Optimized cases cover empty/one/max vectors, ordering and overlaps, row bounds,
all byte values, rejection before first mutation, partial-span cancellation,
completed-prefix errors, later queued writes/mode operations and one exact reply.
Test hidden/clipped views, multiple instances, exposure/resize retirement,
device Stop and allocation failure. A native Task that is not an SDX guest must
use the same public operation successfully.

Exit: public semantics and existing console cell/input tests pass; worker
quanta, pointer retention and old request types remain correct.

### RC4 Submit RAWCON damage as one request

Integrate the descriptor allocation and vector Flush into
[SDXSCREEN](../../lib/dos/sdxscreen.act). Update error-injection fixtures to
return descriptor-byte prefixes, including failure in a partially copied span.
Cover a negative error after partial model acceptance, a positive BREAK prefix,
and a full returned count with a late error. The first retains all submitted
damage; the latter two retire only acknowledged damage and report the original
error cause.
Verify exact full cell models and pixels after each accepted prefix and retry.
No dirty span may disappear after a short write, cancellation or renderer fault.

Exercise EDX typing/movement, inverse/Caps qualifiers, all four scrolls,
save/reopen and physical BREAK on text and bitmap consoles. A normal edit with
damage in text and status must issue one vector request; the idle case issues
zero. Native peers and other instances continue progressing during a large Flush.
Remove per-row Flush submission; no compatibility switch remains.

Exit: one-request damage delivery, error cleanup and unchanged saved bytes pass.
Record combined measurements and isolate vector benefit from RC2's cell-only
result. Keep a vector-only comparison on the frozen pre-leaf build if needed to
attribute performance; do not ship that comparison as another runtime profile.

### RC5 Meet latency with fairness and state intact

Repeat at least 20 insertions, horizontal moves and vertical moves on the exact
64×20 pinned desktop. Preserve readiness and complete-target scanout as separate
metrics, capture during held-key frames and compare the entire client image.
Record baseline, cell-only, vector-only diagnostic if used, and combined
median/p95/max, request counts, get/put counts, native returns and IRQ intervals.

Check maximum geometry and scrolling separately for bounded completion, input
service and peer progress. Reuse the console fairness fixture when worker-turn
behavior changes. Exercise real stock-810 and `generic56k` sector bytes with
port-2 pointer IRQs and trace/untraced agreement; retain existing serial deadlines,
sample-gap and BREAK bounds. Retest ROM minimum-anchor borrowing and the changed
return/NMI phases without expanding unrelated qualification axes.

Run parked BASIC → EDX/MD5/ARC/FBCI → BASIC Run, busy Run during EDX's input wait,
Restart/Quit under another owner and final collection. MD5 verification/BREAK
and ARC no-argument help/overlay use are optimized regression cases. Preserve
the two retained Images, twelve public Tasks, zero lease/borrow after cleanup,
exact frame restoration and guard checks. Do not run full scenarios twice in
raw and optimized modes.

Exit: functional/fairness gates pass and both latency metrics meet the target.
If the target fails, identify the remaining measured interval and keep RC5 and
the plan's performance acceptance open. Do not infer gains by subtracting
overlapping routine totals.

### RC6 Document and deliver the matching system

Publish the implemented console operation, byte-count/error rules, binding
lifetime, scratch/phase protocol and actual stack/memory bounds in current
references. Link a new execution record from the history and plan indexes;
retain prior results and the open/closed status of each latency gate accurately.

Build a fresh graphical native system through `tools/build_demo.py`, rebuilding
all changed generated-layout consumers. Do not refresh new media around the old
kernel. Keep OF816/five-second autoboot, combined writable D1 SYS/WORK, bundled
SDX tools, separate QED ATR, port-2 mouse, pinned ROM, notices and checksums.

Test the extracted final ZIP through combined-ATR cold boot/save, matching XEX,
supported cartridge launch/return and the BASIC/tool/Run workflow. Record exact
artifact hashes and checkpoint use separately from actual cold boot. Preserve
user-written FujiNet disks when installing. Keep test output and build manifests
outside the distribution ZIP. This is development delivery; full hosted release
qualification remains a separate requested tier.

## Memory budget and validation entry points

| Storage | Planned change |
| --- | --- |
| Fixed bank-zero reservation | 0 bytes |
| Root/kernel bank-zero reservation | 0 bytes |
| Each of twelve public Task reservations | 0 bytes |
| Idle bank-zero reservation | 0 bytes |
| Existing native Task DP scratch | Four borrowed/restored bytes; 0 reserved growth |
| Upper bridge binding | 96 used/reserved within the existing 65,536-byte bank |
| Console Instance | +4 payload bytes; dynamic allocation stays 208 bytes |
| Fixed console metadata | 896 bytes unchanged; four bytes of spare padding consumed |
| SDX Session packet pointer | +4 aligned bytes; allocation 2,320→2,328 bytes |
| Embedded BASIC Session | +4 aligned bytes; allocation 2,344→2,352 bytes |
| EDX descriptor array | 300 payload bytes; 304-byte upper allocation per open screen |

Count guards, alignment and unused reserved capacity in every slice's emitted
report. Confirm these projections against `memory.json` and emitted record
sizes; explain any difference before enlarging a reservation. Native call-stack
headroom and page-one transient pushes are separate from reserved-size changes.

Existing development commands include:

```sh
python3 -m unittest discover -s tests -p 'test_*.py'
python3 tools/generate_sdx.py --check
python3 tools/generate_console.py --check
python3 tools/test_sdx_service_shape.py --case raw --output build/rawcon-latency/shape-raw
python3 tools/test_sdx_service_shape.py --case opt --output build/rawcon-latency/shape-opt
python3 tools/test_console_cells.py --case opt --output build/rawcon-latency/console
python3 tools/test_sdx_edx.py --bitmap --output build/rawcon-latency/edx
python3 tools/test_sdx_tasks.py --sio --trace --profile generic56k --output build/rawcon-latency/sio
python3 tools/measure_sdx_editor.py --bundle build/rawcon-latency/demo --output build/rawcon-latency/measure --samples 20 --trace --early-scanout
python3 tools/build_demo.py --desktop --basic-workbench --fastbasic --sdx --qed --release-compiler --output build/rawcon-latency/demo
```

Build the bundle before measuring it. New runner names/selectors above are
deliverables, not commands already available in the current tree. Documentation
preparation requires content/link checks; implementation uses host checks and
focused emitted development tests for the affected behavior. Fix any demonstrated
compiler defect in actionc with its own regression, rather than adding an Exec
routine special case or silently changing the toolchain pin.
