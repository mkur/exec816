# Native pointer loops: implementation plan

Status: implemented. See [measured results and validation limits](../history/compiler-pointer-loops-results.md).
Compiler slices were committed separately in actionc; Exec816 owns the
integration and compiler-pin update.

Improve allocation and emission for ordinary pointer traversal and string loops.
Keep the [FindName source](../../lib/exec/execlists.act) as a representative consumer.
Eligibility must use typed operations, lifetimes and effects, with no recognition
of routine names or particular record layouts. No emitted-byte peephole pass.

## Baseline and existing machinery

The optimized demo built with [compiler pin](../../toolchain/actionc.json)
`52747ef69234e7d30f4f6b7cc57ec28226ac7e29`, stack checks enabled, contains:

| FindName measure | Baseline |
| --- | ---: |
| Routine code | 381 bytes |
| Fixed frame / local stack peak | 26 bytes |
| Calls | 0 |
| Instructions per matching, nonzero character | 67 |
| Stack-relative instructions on that path | 35 |
| REP/SEP instructions on that path | 13 |
| String-byte reads on that path | 3 |

The loop counts are static path counts, not cycle measurements. The entry guard
and frame allocation occupy 28 bytes. Reproduce the baseline through the current
compiler and save code, maps and measured cycles before changing allocation.

Relevant actionc code is under `src/mir65816/emit/`:

- `allocation.rs` already has tagged stack/DP homes. Its pointer strategy admits
  a single block, pointer/address temporaries and a void return, with three DP
  slots. FindName's nested loops, byte operations and pointer return fall outside
  that strategy.
- `coalescing.rs` coalesces word edges; `pointer_coalescing.rs` handles selected
  pointer casts but deliberately anchors block parameters and edge arguments.
- `scalar.rs` already allocates loop-carried word values in the upper 32 bytes
  of compiler scratch. Reuse its ownership and frame-compaction approach.
- `pointer_values.rs` supports direct three-byte arithmetic and scheduled
  pointer edge copies. Edges currently preserve the fallback's complete A and
  final N/Z, generating some of the observed saves, restores and dead bank loads.
- `liveness.rs`, `analysis/machine_liveness.rs`, `tracked.rs` and the selected
  emission/proof machinery provide the starting point for legality checks.

## Boundaries

- Keep SSA values in IR; stable mutable homes are a physical allocation choice.
- Preserve exact three-byte pointers, native ABI v2, checked calls and returns,
  stack-fault behavior, interrupt headroom and truthful frame/location maps.
- Use only the existing [compiler DP reservation](../reference/platform.md):
  `$80–$BF`. Preserve the caller's `$00–$7F`, metadata and reserved-zero bytes.
- Start with call-free routines containing supported pointer/byte operations,
  branches, nested loops and pointer returns. Calls, helpers, machine operations,
  volatile/address-escaping storage and unmodelled scratch effects retain the
  established stack strategy. No call-crossing spills in this work.
- Memory effects remain explicit. Coalescing pointer values does not authorize
  eliminating or reordering reads through those pointers. Indirect stores need
  a proved safe effect contract before admission.
- Reserved bank-zero delta for every slice: **0 fixed / 0 per Task bytes**,
  including guards, alignment and unused capacity. Reduced invocation frames
  do not shrink the reserved Task stack pools.

## P1 — Stable pointer homes and copy coalescing

Extend pointer affinities across block parameters, loop backedges and nested
joins using the existing CFG liveness. Combine representation-preserving
three-byte copy/cast chains into compatible home classes. An affinity expresses
a preference; interference still prevents destructive merges.

Keep incoming parameter storage authoritative. Require exact whole-home overlap
or disjoint storage; retain simultaneous-copy semantics for swaps, repeated
sources and genuine cycles. Recompute staging, frame extent, argument offsets
and stack peaks after adopting a plan, then verify the complete routine.

Initially use stack homes so the effect of coalescing is independently reviewable.
Avoid adding shared NIR transformations when the needed values are already
promoted; this baseline's frame consists of temporaries, not source objects.

Completion: loop-carried pointers retain consistent homes wherever liveness
permits; the entry swap and copy chains in the baseline are reduced. Genuine
cycles and live old values remain correct. Save the before/after allocation map.

## P2 — DP residence across pointer loops

Add a bounded CFG pointer strategy to the existing allocator. Admit ordinary
pointer loads, byte loads/comparisons, NULL tests, same-width casts, supported
constant pointer steps, branches and pointer returns. Audit the selector scratch
effects of every admitted operation, including generic fallback sequences.

Use the existing resident pool at `DP_SCRATCH_OFFSET+32 .. +63` (`$A0–$BF` with
the current ABI), separate from transient pointer/arithmetic scratch. Allocate
complete three-byte homes, reuse disjoint lifetimes deterministically and share
the pool's ownership rules with scalar allocation. Never allocate overlapping
scalar and pointer residents. Four live pointer values require 12 bytes; the
32-byte pool has room for ten complete pointer slots when used exclusively.

Address through resident DP slots directly instead of copying each pointer into
`$80` before a dereference. Support pointer results and mixed byte/Boolean
temporaries without assuming a pointer-only routine. Derive frame maps from
the actual remaining storage. Preserve the existing proven straight-line path.
Capacity or eligibility failure uses the verified stack plan for the routine;
mixed spill/reload scheduling is deferred.

Completion: FindName's current node and string cursors remain in DP across both
loops. Successor temporaries receive homes according to their actual lifetimes.
The steady character loop has no stack traffic to reload those pointer values.
Allocation verification rejects live overlaps and transient scratch collisions.

## P3 — Compute pointer updates directly into their final homes

Give dying input/result pairs safe same-home affinities for supported constant
pointer arithmetic. Reuse `pointer_constant_arithmetic` and its 16-bit low-word
plus 8-bit carry sequence. Write each component directly to the destination;
avoid an arithmetic temporary followed by copies into the loop-carried home.

Preserve carry across low-word stores and M-width changes. If the old value has
another live use, retain separate storage. For a loaded successor replacing its
own base, capture all three source bytes before changing the address used by the
load; reuse the existing dying-base reload contract. Reject partial overlaps.

Completion: both FindName cursor increments update their stable homes directly,
with no temporary pointer round trips. Constant steps across `$xxFFFF` and
subtraction across `$xx0000` retain exact 24-bit behavior, including wrap.

## P4 — Emit only demanded loads, register repair and width changes

Use the existing register-lane/flag liveness and typed selection evidence to
authorize omissions before final encoding. Extend the edge contract to state
which results are demanded; do not preserve incidental fallback A/N/Z when no
successor observes them. Keep the conservative path when proof is unavailable.

Remove unnecessary A staging, final bank-byte reloads and identity-copy repairs.
Plan M-width requests from actual consumers and proved predecessor modes,
including backedges. Preserve hidden A-high, live N/Z/C/V, index width and all
protected execution state. Revalidate maps/staging and refresh analysis evidence
after any selection or frame change; stale liveness cannot authorize emission.

Completion: the identified overwritten private loads and redundant mode changes
disappear without changing live results or flags. This slice concerns private
copies and register repair. Reusing the repeated `left^` read requires a separate
nonvolatile memory-effect proof and is not a prerequisite for these four
optimizations.

## P5 — Integrate and measure Exec816

Use a clean actionc branch/worktree, preserving unrelated work. First validate
the candidate as a recorded local override. Then update the compiler pin and
rebuild the kernel and disk commands together; retain stack checks and the
checked o65 provider contract. No ABI or image-format change is expected.

Run the existing named-list cases in raw and optimized modes through
`tools/test_lists.py --case named-raw` / `--case named-opt`, with its required
compiler/ROM/bridge arguments. Add only missing semantic cases. Exercise the
rebuilt shell and commands through one OF816 demo smoke run, then regenerate the
standard distribution with XEX, system disk, ROM, guide and notices.

Record FindName code/frame size, DP allocation, matching-character instruction
and traffic counts, and same-input VM cycles. Also report the whole Exec image
and representative list/string routines to expose regressions outside FindName.
Acceptance requires smaller FindName code/frame and lower matched-character
cost, stable DP cursors and no pointer copy chains on the steady path. Establish
durable measured budgets from the first complete implementation; do not invent
cycle savings from static counts or hide a regression by changing the workload.

## Validation scope

Each compiler slice gets affected unit tests and focused emitted-code execution
in raw/optimized modes. Reuse the native runner and existing pointer allocation,
coalescing, edge, value, state-tracking and preemption fixtures. Batch these cases:

- Empty/single/multiple-node lists, unnamed nodes, equal and unequal names,
  empty names, prefix mismatches, long common prefixes and resumed searches.
- Nested-loop entry/backedges, early returns, pointer copy chains, true swaps,
  repeated sources, live old values, enough DP capacity and pressure fallback.
- Distinct banks, unaligned fields, bank-crossing strings/pointers, exact
  three-byte accesses, aliased read-only names and checked arithmetic boundaries.
- Calls/helpers that clobber scratch and unsupported effects exercise fallback.
  Negative allocation/proof cases check overlaps, stale facts and live flags.
- Two Task domains and targeted IRQ/NMI injection while pointers are resident,
  including halfway through an update; check full context, DP ownership, stack
  guards, ABI return lanes and bounded completion. Run the changed residence
  probe in P2; repeat affected cases when P3/P4 change its instruction paths.

Use generic traversal and two-cursor fixtures as well as FindName. Keep the
shared NIR pipeline unchanged unless evidence requires a separate scoped change;
if changed, run actionc's required shared-contract checks. Run the affected
native backend suite once at completion, including relevant fixed-image/o65 and
fixture-normalization coverage. Full Exec release qualification remains a
separate gate under the [testing policy](../contributing/testing.md), not a per-slice task.

Implementation and integration are complete. The refreshed demo includes OF816,
the system disk and the pinned ROM. Existing full-backend test failures are
recorded in the results document and remain a separate release gate.
