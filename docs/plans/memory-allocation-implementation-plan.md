# Memory allocation implementation plan

Status: all six slices complete, 2026-09-18. The
[implementation record](../history/memory-allocation-implementation.md) summarizes the
result, qualification scope and remaining limits. Message ports are next.
The [classic Exec allocation design](../reference/memory.md) is the public
contract; this plan defines implementation boundaries and acceptance. It
replaces the earlier Alloc/Free plan in this file. Existing prototype probes
are historical evidence and do not complete any slice of this plan.

Deliver a usable upper-RAM heap before message ports, queued SIO and DOS.
Eight-task concurrent serial timing qualification remains **deferred**. It is
not an entry condition for this work and is not silently included in its exit
criteria. The eventual eight-task SIO/DOS system still needs that qualification.

## Scope and working rules

Implement the six system calls in `EXEC`: AllocMem, FreeMem, AllocVec, FreeVec,
AvailMem and TypeOfMem. Also provide the caller-owned pool operations Allocate
and Deallocate. Preserve classic names, argument roles, numeric flag values,
pointer-or-null allocation results and void free calls. Use the design's
MemHeader/MemChunk representation and shared ordinary/LINEAR free extents.

Keep Task records and stack/DP pools under their current admission rules.
MEMF_BANK0 is recognized but cannot succeed without a registered bank-zero
region; this plan registers none. Dynamic stacks, heap-backed Task admission,
AllocEntry/FreeEntry, tc_MemEntry cleanup, public AddMemList, AllocAbs, memory
pools, MEMF_REVERSE and expunge callbacks remain separate work. Do not add a
heap worker, message-port dependency or general semaphore service.

Implement policy in Action!, with native wrappers for the compiler ABI and
platform boundary. Follow the [platform contract](../reference/platform.md) and
[IRQ/scheduler protocol](../history/kernel-critical-sections.md) from the first integrated
slice. When entered with I=0, no intermediate public allocator may mask IRQs
throughout a scan. No public allocator may return before MEMF_CLEAR is complete.

Use the compiler revision in [actionc.json](../../toolchain/actionc.json), currently
`e7266982c22527040dfc2a46508be8475581fe8f`. Compiler defects belong in actionc,
with focused regressions and a separately recorded pin update. Preserve one
current Task implementation and `COP #$50`; rebuild callers when the ABI changes.
Do not retain the prototype as a compatibility mode.

Each slice must execute its changed behavior as emitted raw and optimized code,
pass the relevant checks below, publish its qualification record and be committed
before the next major slice. Host-only models and interface metadata supplement
execution; they do not replace it. Run targeted checks per slice and the wider
integration matrix at the end, without repeatedly rerunning unchanged suites.

## Slice sequence

| Slice | Executable result | Commit boundary |
| --- | --- | --- |
| 1. Native API and layouts | New declarations, records, flags and argument/result probes | `Define classic Exec memory ABI and qualify native layouts` |
| 2. Private free-list engine | Allocate/Deallocate operate on caller-owned upper-RAM pools | `Implement MemHeader and MemChunk allocation engine` |
| 3. Heap registration | Bootstrap claims and publishes checked upper-RAM regions; shutdown releases them | `Register upper RAM with the Exec heap` |
| 4. System allocation policy | Shared ordinary/LINEAR selection, free and queries execute through an internal harness | `Implement Exec heap placement and memory queries` |
| 5. Public services | All eight APIs work in the current Task build, including vector allocation and CLEAR | `Expose Exec memory services with preemptible clearing` |
| 6. Integrated qualification | Lifetime, faults, interrupt races and four-task serial timing are qualified | `Qualify concurrent Exec memory allocation` |

The commit subjects are proposed. Update completion status and evidence as the
work lands; publishing this plan does not mark a slice complete.

## Repository integration

| Existing location | Planned change |
| --- | --- |
| [heap-v1.json](../../abi/heap-v1.json), [generate_heap.py](../../tools/generate_heap.py) | Replace prototype definitions with the current heap schema, records, flags and call shapes. Keep one active schema; the inherited filename does not create a compatibility profile. |
| [exec-memory-types.inc](../../lib/exec/exec-memory-types.inc) | Generated current types/constants; the Task builder adds native declarations to EXEC. Obsolete EXECALLOC files were removed in slice 1. |
| [generate_tasks.py](../../tools/generate_tasks.py), [tasks.json](../../abi/tasks.json) | Integrate the generated API, collision checks and current ABI tag. Exclude heap helpers from task-entry discovery and kernel metadata from application writable ranges. |
| [memory-v1.json](../../abi/memory-v1.json), [execmemory.act](../../lib/exec/execmemory.act), [generate_memory.py](../../tools/generate_memory.py) | Add one HEAP owner, validate it in the bank manager and include descriptor reservations in the resolved memory map. Preserve existing bank-record and boot-manifest layouts unless a separate change is justified. |
| [taskpolicy.act](../../lib/exec/taskpolicy.act), [cooperative.s](../../platform/altirraos/cooperative.s), [tasks.s](../../platform/altirraos/tasks.s) | Initialize after memory adoption, dispatch under the existing guard, preserve pending-wake processing and integrate controlled faults/shutdown. |
| [native_program.py](../../tools/native_program.py), [banked_image.py](../../tools/banked_image.py) | Bind native wrappers, check import layouts/stack costs, reject overlaps and record all generated and source inputs. |
| [test_heap.py](../../tools/test_heap.py), [test_heap_package.py](../../tests/test_heap_package.py), existing `heap_*` fixtures | Replace prototype expectations; grow the runner with the executable slices below. |

The implementation uses `lib/exec/heapcore.act` for free-list mechanics,
`lib/exec/heappolicy.act` for system-region policy and `platform/altirraos/heap.s`
for native mechanisms. The independent interval model is `tools/heap_model.py`,
with target fixtures under `tests/programs/heap_*.act`. The runners reuse common
build, guard and emulator helpers.

The Task builder generates its own EXEC module; editing only `lib/exec/exec.act`
would not expose the new API to current Task programs. Integrate at that actual
generation point and keep declarations generated from one definition.

## Slice 1: native API, flags and records

Completed: [ABI qualification](../qualification/memory-exec-abi.json) passes six
raw/optimized emitted probes, two current Task-core regressions and 50 host
checks. MemHeader is 28 bytes; MemChunk and the private vector prefix are eight
bytes each. Unimplemented public imports still reject. Reserved bank-zero delta:
zero fixed and per-task bytes, during loading and steady runtime.

Replace the prototype ABI and its probes together. Generate:

- Full MemHeader and eight-byte MemChunk layouts using the existing Node/List
  types, native 24-bit pointers and LONGCARD lengths/counts. `mh_Upper` is a
  LONGCARD exclusive endpoint, including `$01000000`.
- The eight-byte private AllocVec prefix: backing size and requested size.
- All supported flags from the design, the unchanged classic values for
  unsupported requirements, and the native BANK0/UPPER/LINEAR extensions.
- Native declarations/import layouts for all eight calls, with 32-bit size
  and flag arguments, 24-bit pointer results, 32-bit query results and void frees.
- Collision-checked service selectors and private argument records for the
  gateway. Check against core, Task, signal and private adapter selectors;
  service selectors in A are distinct from COP signatures.

Replace the old two-byte alignment, per-live-block headers, HEAP_LINEAR owner,
status/output-pointer API and `$0201` profile assumptions. Retain historical
qualification JSON unchanged. Do not bind an unfinished service to a successful
stub: unsupported production imports remain rejected until their slice lands.
ABI probes use explicitly test-only routines and do not enable public services.
Assign the current kernel's new reported ABI tag when production bindings land;
this is an update to one kernel, not a second selectable version.

**Acceptance:** interface checks and emitted calls agree on every argument,
result, field offset, record size and array stride. Exercise pointer values with
nonzero banks, 32-bit values with nonzero high words and bit 31, void results,
field access near bank boundaries and guards around records. Verify no writes
to bank ownership. Host tests reject stale generated files, collisions, narrowed
sizes/results and malformed layouts. Normalize host text line endings only.

**Evidence:** `docs/qualification/memory-exec-abi.json` with raw/optimized
results, compiler/native-ABI identity and generated-file hashes. Keep final-bank
arithmetic probes distinct from physical RAM tests.

## Slice 2: private MemHeader/MemChunk engine

Completed: [core qualification](../qualification/memory-exec-core.json) passes
183-operation interval-model traces in raw and optimized code, 18 isolated
corruption/invalid-free cases and 54 host tests. Payload/region/stack/DP guards
and OS restoration pass. Reserved bank-zero delta is zero, fixed and per task;
the fault thunk uses six bytes inside the existing FAULT reservation.

Implement address-ordered, singly linked free chunks under a caller-owned
MemHeader. A live AllocMem-style block has no allocator header. Implement checked
eight-byte rounding, first-fit selection, exact removal, splitting, sorted
insertion, and coalescing with either or both neighbours. Maintain `mh_Free`.
The mechanics should accept a checked subrange selected by system policy, so
ordinary and LINEAR will use the same split/free engine.

Implement private Allocate without a bank-boundary restriction and private
Deallocate with the design's rounding, valid subrange returns and declared-pool
containment. These calls do not acquire the system heap guard. The caller owns
synchronization and cannot use them on live system MemHeaders.

Validate a chunk's address/range before dereferencing it; validate length,
alignment, forward links, overlap and affected counts before mutation. Empty
lists are valid. Zero, rounding overflow and exhaustion must leave the pool
unchanged. Detected corruption takes the controlled fault path, with bounded
traversal rather than following a cycle indefinitely.

**Acceptance:** drive both an independent interval model and emitted code from
the same deterministic operation traces. The model represents free intervals,
not MemChunk links. Compare returned addresses, free totals and normalized
extents after each operation. Cover exact fit, one/two-piece splits, all
coalescing cases, odd requests, zero, exhaustion/reuse and allocations larger
than 64 KiB from a private linear pool. Check payload patterns and surrounding
guards. Run malformed links, cycles, overlaps, lengths and count cases as
isolated bounded fault fixtures. Do not claim detection of every wrong-size or
interior free without a live-allocation ledger.

**Evidence:** `docs/qualification/memory-exec-core.json`, including trace seeds
and operation counts. This slice qualifies private pools, not the system heap.

## Slice 3: upper-RAM registration and ownership

Completed: [registration qualification](../qualification/memory-exec-registration.json)
passes ten raw/optimized map, rollback, restart and corrupt-list shutdown cases,
four simultaneous eight-task cases (kernel banks 1 and 3), two four-task core
regressions and 57 host tests. Metadata occupies 512 upper bytes at 16 banks.
Complete fixed/per-task bank-zero reservations remain unchanged in loading and
runtime; the record includes the full before/after budgets.

After validated bank-manager adoption and before application task admission,
compute eligible free upper-bank runs and required descriptor storage. Reserve
the region List, MemHeaders and trusted heap-ownership bookkeeping in upper RAM,
preferably in the configured kernel bank, without recursive heap allocation.
Use the resolved image extents; code may occupy more than one bank.

Claim the eligible banks for one HEAP owner, initialize one header per contiguous
run with matching attributes, then publish the completed list. Sort regions by
descending priority and then address. Exclude image, OS, Task metadata, signal
code, descriptors and all other reservations. An empty heap is a valid state
with zero available bytes. Capacity failures must not publish a partial heap.

Rollback releases only claims made by the failed initialization. Freeing every
block later leaves the registered banks owned by the heap. At final launch
shutdown, quiesce users/producers and release the heap's trusted claims without
traversing potentially corrupt free chunks. Do not reclaim image-owned bank
fragments or expose bank-zero task pools in this slice.

**Acceptance:** compare resolved reservations, bank ownership and region extents
before initialization, after publication, after rollback and after shutdown.
Test empty, single-run and separated-run maps, descriptor exhaustion, unavailable
banks, image/metadata conflicts and repeated startup/shutdown. Use injected
initialization failures to prove no leaked claims or double ownership. Execute
raw/optimized builds with kernel banks 1 and 3; check the existing four- and
eight-task layouts functionally, including bank-table placement. This does not
run the deferred eight-task concurrent serial timing experiment.

**Evidence:** `docs/qualification/memory-exec-registration.json`, with final
image/maps, all reservation sizes and bank-zero deltas.

## Slice 4: system placement, free and queries

Completed: [policy qualification](../qualification/memory-exec-policy.json) passes
143-operation raw/optimized interval-model traces, eight system fault cases,
two private-pool trace regressions and 61 host checks. Real timer IRQs and NMI
remain active during the guarded task-context harness. Allocation/query traces
preserve bank ownership. Default/TOTAL queries use header counts; LARGEST
validates and measures chunks in one traversal. Full bank-zero budgets remain
unchanged. Production COP bindings and caller-side clearing remain slice 5.

Add internal system policy over the registered regions. Select the first
eligible region by priority, then the first fitting address. Ordinary requests
must keep the complete backing allocation in one bank; if necessary, skip to
the next bank boundary inside a free chunk and retain the skipped prefix.
LINEAR may cross banks but never reserved holes or separate region boundaries.
Both consume and return the same free extents and the same HEAP ownership.

Implement flag validation before mutation. CHIP, FAST, LOCAL, 24BITDMA and KICK
retain their classic numbers but cannot be satisfied. REVERSE, unknown bits,
query-only allocation flags and conflicting placement flags fail as specified.
ANY selects upper RAM; BANK0 returns no allocation while no region is registered.
Never reinterpret Amiga hardware flags as native placement flags.

Implement FreeMem's checked region lookup, rounding, bounds and overlap checks.
Do not add a global allocation-error variable or a mandatory live-block ledger.
Implement AvailMem's sum, LARGEST and TOTAL modes, using the allocation placement
calculation for LARGEST. TypeOfMem returns only registered region attributes,
for allocated and free addresses alike. None of these queries mutates ownership.

For now, execute through an internal task-context harness under the existing
kernel guard, with IRQs allowed. The public reserve/clear wrapper is slice 5;
do not expose an incomplete AllocMem that accepts CLEAR without clearing.

**Acceptance:** extend the independent model with priorities, attributes and
bank-aware placement. Exercise ordinary 65,536-byte allocations, rejection of
65,537 bytes, rounded LINEAR sizes, reusable linear tails, skipped prefixes,
fragmentation and mixed-mode free/coalescing. Query totals must agree with the
model and exclude all reservations, without counting both bank inventory and
heap capacity. Check invalid flags and overflow leave lists/ownership unchanged.
Test `$01000000` endpoint arithmetic using synthetic maps where necessary,
without accessing nonexistent banks on the pinned 1 MiB machine.

**Evidence:** `docs/qualification/memory-exec-policy.json`, with model/target
comparisons and the precise supported region/flag matrix.

## Slice 5: public services, vectors and preemptible clearing

Completed: [public API qualification](../qualification/memory-exec-api.json) passes
38 raw/optimized cases through all eight native imports, including controlled
faults, context preservation, vector boundaries and multi-bank clearing. Each
large-clear case verifies all 262,145 requested bytes, poisoned padding and
neighbours while another task allocates and frees. The single current Task ABI
is `$0400`. Wrappers use twelve caller-stack bytes within existing reservations;
complete fixed/per-task bank-zero budgets remain unchanged. There are 61 passing
host checks. Concurrent serial qualification is recorded separately in slice 6.

Bind all eight APIs into the single current Task build and update its reported
ABI tag, callers and tests together. System metadata operations enter through
COP `$50` and run under `E816_SWITCHING`. The private-pool pair uses ordinary
calls with caller-owned synchronization; it need not acquire the system guard.
Use generated argument/result layouts, preserve native context and reject
invalid service-entry contexts before accessing caller data.

The public allocation wrapper retains its arguments and result in the caller's
invocation storage. Reserve the complete backing block under heap serialization,
return to the caller's stack/DP, initialize a vector prefix if applicable, and
perform CLEAR before returning the pointer to application code. No continuation
or clearing cursor may remain on the shared kernel stack across preemption.
The block is already absent from the free list while clearing, so another task
may allocate safely. Preserve incoming Forbid nesting and the processor I flag.

AllocVec reserves `8 + round_up_8(requested)` and returns the aligned payload.
Its entire ordinary backing allocation must fit in one bank. FreeVec validates
region membership and prefix extent before reading the prefix, checks backing
and requested-size consistency, then frees through the same engine. Null is a
no-op. Detected invalid frees and invalid contexts fault; exhaustion and unsupported
requirements return null. FreeMem(pointer, 0) remains a no-op.

Native imports must declare and check their actual stack requirements and
interrupt effects. Verify result writeback remains correct if a pending wake or
VBI selects another task before the wrapper resumes. Keep the final pending-wake
recheck in native return. Initialization/fault shutdown must not call a checked
normal wrapper from an invalid compiler domain or processor-width state.

**Acceptance:** call every public API through emitted application code. Verify
full 32-bit inputs/results, native pointer returns, saved registers, widths,
DBR/D/S, guards and retained OS COP `$00` behaviour. Test vector payloads at
65,528/65,529-byte ordinary boundaries and larger LINEAR requests, zero/null
rules, prefix validation and allocation failure rollback. Clear a multi-bank
block prefilled with nonzero bytes, observe another task allocate/free during
that clear, and verify the requested payload is zero on public return without
damaging neighbours. Confirm I=1 and nested Forbid are preserved in separate
functional tests; they are not normal preemptible-clear timing workloads.

**Evidence:** `docs/qualification/memory-exec-api.json` and a small public-API
example. Public allocation is usable at this point; serial coexistence under
allocator load still requires slice 6.

## Slice 6: lifetime, interrupt races and timing

Completed: [concurrent qualification](../qualification/memory-exec-concurrency.json)
passes eight raw/optimized lifetime, forced IRQ/NMI race and eight-task allocation
cases, including kernel banks 1 and 3. Four-task timing passes 22 observed
transfers and 22 identical uninstrumented replays: 458,724 refills, zero deadline
misses or gaps, and a worst refill of 72.176 µs against 78.942 µs. The longest
observed completion-post-to-worker delay is 30.842 ms; an RX/turnaround buffer
budget remains separate work. The [integration record](../qualification/memory-exec-regressions.json)
passes the named 66-case regression selection and 61 host checks. Fixed and
per-task bank-zero reservations remain unchanged. Eight-task baud qualification
remains deferred; its functional allocation baseline passes.

Exercise multiple tasks allocating, publishing buffers through a fixture-owned
handoff, signalling, using and freeing each other's memory. This fixture needs
no production message ports. Prove allocations survive creator removal and task
slot reuse, and unrelated RemTask calls do not reclaim shared data. Removing a
task mid-allocation/clear does not introduce automatic memory reclamation; any
reserved storage remains allocated until explicit valid free or heap shutdown.
Keep requests/buffers alive until the simulated IRQ consumer is quiescent.

Inject IRQ signal posts and NMI ticks at allocation split, free/coalesce, query,
gateway return and task-side clear boundaries. Check that IRQ/NMI never traverses
heap metadata, no second policy activation enters, pending wakes are delivered,
and all non-result context survives. Corruption and invalid-free cases run
separately and reach controlled termination without following corrupt lists at
shutdown. Validate OS reservation/vector/serial-ownership restoration.

Add allocator workloads to the existing four-task serial concurrency harness:
ordinary allocation/free, mixed ordinary/LINEAR fragmentation, LARGEST scans,
vector operations and multi-bank CLEAR. Use preconstructed fragmentation plus
sustained churn, a compute control, and progress counters for every enabled
worker. Record fragment/region counts and operation sizes so a timing result
states what was actually stressed.

Use the pinned 8× PAL timing profile for 4,096-byte runs, then 65,535-byte runs
of the allocation, fragmentation/query and CLEAR workloads, in raw and optimized
builds. Require zero hardware refill-deadline misses, zero byte gaps, intact
guards, correct completion and worker progress. Replay the identical XEX and
workload on the uninstrumented emulator and compare functional outcomes. Preserve
the existing Yield/Signal/Wait/Sleep timing regression checks after integration.

Measure three different quantities: hardware-ready-to-refill latency against
the pinned deadline (about 78.94 µs), maximum IRQ masking, and signal-post-to-worker
resumption delay. Long scans may keep IRQs flowing while postponing a worker.
Report the latter delay for the future driver's buffer budget; a passing TX
pump does not establish an RX/turnaround budget that has not yet been specified.
Repair any deadline regression before declaring this slice complete. If long
scans require resumable traversal, specify and validate revalidation rules;
do not release serialization while retaining unvalidated free-chunk pointers.

**Acceptance:** targeted faults/races plus the relevant Task, signal, Lists,
banked-loading, native/cooperative/preemptive and existing eight-task functional
regression suites pass. Do not extend this slice into the deferred eight-task
concurrent baud qualification, RX driver, message ports or DOS.

**Evidence:** `docs/qualification/memory-exec-concurrency.json` and
`docs/qualification/memory-exec-regressions.json`, recording functional and timing
verdicts separately. A timing failure must remain visible even if functional
checks pass.

## Qualification and completion records

Use the [1 MiB functional pin](../../toolchain/altirra-1m.json) for normal hosted
checks and the [8× serial pin](../../toolchain/altirra-signals-1m.json) for timing.
Use the [passive observer pin](../../toolchain/altirra-concurrency-observer.json)
only for observed runs, with identical uninstrumented replays. Record actual
ROM/emulator hashes, compiler revision, optimization mode, kernel bank, task
capacity, source/generated/image hashes, cases, bounded timeout and results.
Keep raw bridge logs out of committed evidence; publish parsed measurements
and hashes without bridge authentication data.

Expand `tools/test_heap.py` with named cases for these slices. Run the affected
host package/generation/model tests and raw/optimized target cases before each
commit. Pin reports to the code they measured; do not overwrite the historical
prototype or critical-section records. A compiler fix, reservation change or
new native wrapper requires its own relevant regressions before proceeding.

For every slice, report complete fixed and per-task bank-zero reservations,
for loading and steady runtime, including guards, alignment and unused capacity.
The intended additional bank-zero reservation is zero; measure it from final
maps instead of assuming it from upper-RAM metadata placement. Added call depth
must fit existing stack/IRQ headroom or be budgeted and requalified explicitly.
This plan itself changes no reservations and has a **zero-byte bank-zero delta**.

The milestone is complete when slices 1–6 have committed executable evidence,
the current design and public examples match the implementation, and the
roadmap lists message ports next. Deferred bank-zero allocation, dynamic Task
storage and eight-task serial timing remain explicit follow-up work. This
milestone does not claim complete SIO or DOS support.
