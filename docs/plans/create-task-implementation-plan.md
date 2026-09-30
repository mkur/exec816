# CreateTask implementation plan

Status: **C1–C5 complete**.
[Same-source build guide](../guides/amiga-c.md). Development evidence: [CreateTask results](../development/create-task.json).
Implements the [CreateTask design](../architecture/create-task.md) for Action!
and C. Each slice ends with an executable result, focused checks and a separate
commit. This document does not authorize or record release qualification.

## Scope and baseline

Deliver one public CreateTask operation through COP #$50, automatic selection
from existing worker stack/DP pools, and managed Task records that become reusable
on removal. Keep AddTask for caller-owned records and custom finalizers. Remove
public ExecPrepareTask when its C callers migrate. There is no new allocator,
reaper Task, join API, scheduling policy or Process inheritance in this work.

Use the [recorded actionc revision](../../toolchain/actionc.json), existing native
ABI and pinned ROM/emulator profiles. No actionc changes or compiler-pin update
are expected. Record the actual source state and hashes for measurements; preserve
the separate documentation reorganization already in progress.

Before C1, capture matching checked four- and eight-slot build maps and emitted
Task-policy size, reusing artifacts only when their inputs match. Keep a small
scenario-driven Task fixture for C1/C2 so additional cases can reuse compiled
images. Follow the [testing policy](../contributing/testing.md): checks after a
coherent slice, not after every edit, and no automatic release matrices.

| Slice | Deliverable |
| --- | --- |
| C1 | Working shared service and Action! binding, including safe retirement. |
| C2 | Admission, ownership and reuse checks across the supported pool layouts. |
| C3 | C binding using the same service; retire ExecPrepareTask. |
| C4 | Ordinary examples use CreateTask and portable synchronization. |
| C5 | The identical C source builds and runs on Exec816 and classic Amiga. |

## C1 — Shared service and Action! binding

Extend [tasks.json](../../abi/tasks.json) with the public selector, argument/result
contract and managed-record stride. Check selector uniqueness against all public
ABI files. Derive native packet offsets from emitted declarations; do not guess
padding. Keep signed 32-bit priority, unsigned 32-bit stack size, CSTRING name and
a registered zero-argument PROC entry. Advance the feature version when the
service becomes callable; preserve existing call layouts and public Task size.

Update [generate_tasks.py](../../tools/generate_tasks.py), native gateway/import
binding in [native_program.py](../../tools/native_program.py), and the platform
dispatcher. Include selector bounds and packet extent validation in this change.
Update the existing ABI fixture to actually call the new import so declaration
checks and emitted argument/result checks remain meaningful.

Generate one 64-byte managed record for each non-root public pool, aligned to two
bytes. Prefer the existing upper Task metadata arena; account for the enlarged
metadata and its rounded end, and enforce the boundary before the SIO descriptor
at arena offset `$800`. Include the table in loader initialization, overlap
checks and memory reports. Do not enlarge bank-zero pools or expose the table as
general caller-writable Task storage.

In [taskpolicy.act](../../lib/exec/taskpolicy.act):

- Validate priority and size at full width, including even-rounding overflow,
  and validate the registered entry before publishing anything.
- Select the smallest fitting pool using resolved pool sizes and the existing
  `SlotFree` predicate. That predicate includes Process reservations and
  incarnation exhaustion; checking only the execution-context state is insufficient.
- Initialize the selected managed record, borrowed name, priority, stack bounds
  and empty memory list; use the existing admission/context machinery.
- Preserve the kernel transition protocol, caller Forbid nesting and scheduling
  behavior. Failed creation leaves capacity and live state unchanged.
- Use common removal for return, self-removal and permitted external removal.
  Managed records become reusable only after safe retirement. Preserve all
  existing ownership gates and borrowed-record semantics.

Keep this slice complete: no creation-only entry that relies on a later cleanup
patch, and no second pool-ownership bitmap. AddTask must reject caller records
overlapping the managed table without weakening ordinary storage validation.

**Validation:** affected host/generator checks; raw and optimized emitted Action!
creation, named lookup, normal return, explicit self-removal and repeated reuse.
Observe default-finalizer behavior, context/DP restoration, guards and unchanged
public capacity. Run a focused existing AddTask admission/finalizer case.

**Commit:** `Add public CreateTask with managed Task records`.

## C2 — Admission and lifetime boundaries

Extend the C1 fixture and existing lifetime coverage; keep instrumentation out of
production policy. Resolve any failures in the shared implementation.

| Area | Required cases |
| --- | --- |
| Arguments | Priorities -128/127 accepted and -129/128 rejected; zero, odd, exact-fit, oversized and rounding-overflow stack requests; NULL/unregistered entry; unnamed Task. |
| Pool selection | Root/idle excluded; four/eight layouts; a supported nondefault worker-stack size; deterministic selection among fitting pools. |
| Shared capacity | Mixed AddTask/CreateTask occupancy; live service worker; Process-reserved and retired-but-uncollected slots; exhausted incarnation; all usable slots full. |
| Failure | No ready-queue insertion, live-count change, pool loss or mutation of another Task after rejection; a following valid creation succeeds. |
| Retirement | Return, self-removal, permitted external removal and reuse; borrowed AddTask records survive; managed records cannot be passed back as caller-owned AddTask storage. |
| Protection | Existing lease/producer/DOS ownership rejection and nonempty-memory-list handling remain effective. Use the existing fault harness for diagnosed misuse. |
| Scheduling | Nested Forbid, competing creators, and a child that finishes before its creator resumes; no wrapper dereferences a retired result. |

Use a mixed-size synthetic map for host selection checks if useful; do not claim
that it qualifies a new native configuration. Native runs use valid generated
layouts. Check membership and cleanup under actual VBI, including reuse after
self-removal, rather than relying solely on host assertions.

**Validation:** raw/optimized boundary and lifetime scenarios, one focused worker
coexistence run, native guards and bounded completion. Reuse C1's unchanged images
where possible. Full serial timing/profile matrices remain release work.

**Commit:** `Cover CreateTask admission and retirement boundaries`.

## C3 — C binding and removal of ExecPrepareTask

Add `<clib/alib_protos.h>` with the classic CreateTask signature and our calling
annotation. Extend [the C generator](../../tools/generate_calypsi.py) and
[shim](../../c/calypsi/exec.c) to marshal the same public request. Generate or
check packet field layout against the native definition, using target-emitted
sizeof/offsetof probes rather than frontend static assertions alone.

Check huge name/entry pointers before conversion to 24 bits, retain all 32 bits
of priority/size, and widen the returned pointer correctly. Reject unrepresentable
pointer values without submitting a truncated request. Add no C-side pool scan,
Task allocator or call into Action! with the C calling convention.

Update the C message and context fixtures to call CreateTask, replacing their
static worker records and post-removal state polling with startup/completion
signals. Allocate notifications before admission and handle every failed-creation
path without waiting for a nonexistent child. The final notification follows the
design's protected signal/self-removal protocol.

Remove ExecPrepareTask from the shim and public header, its old tests, and the
generated C pool tables/`platform.h` build step once unused. Retain unrelated
public extensions used by genuine low-level tests. Continue explicit registration
of C Task entries in [build_calypsi.py](../../tools/build_calypsi.py); no arbitrary
entry admission or wider C runtime is introduced.

**Validation:** generated C ABI/layout checks and focused raw/optimized C runs;
pointer-representability failures, signed/unsigned argument boundaries, NULL
failure returns, native guards and existing callee-saved lower-DP/VBI checks.
Action! and C results must exhibit the same allocation and lifetime behavior.

**Commit:** `Expose CreateTask in the Calypsi binding`.

## C4 — Examples and current documentation

Migrate ordinary Action! worker/message examples to CreateTask; retain explicit
AddTask preparation where the example demonstrates caller-owned storage or custom
finalizers. Use named stack-size constants and signals/messages for synchronization.
Do not poll managed Task records after removal. Keep code, names and shared state
alive until the worker has actually retired.

Make [messages.c](../../c/examples/messages.c) suitable for the same-source demo:
standard Amiga includes/calls, no Exec816 header or platform conditionals, no
ExecYield loop and no global free-memory equality assertion. Verify the `(10,20)`
request and `(60,70)` reply in the program and return a success/failure status.
Handle startup allocation failure and retire ports/signals/messages on all paths.
The existing Exec816 bootstrap may display exported results; adding stdio/DOS C
bindings is separate work.

Update the Task reference, Task/message guides, C binding guide and C README to
the implemented API and its limits. Document borrowed results, stack-size meaning,
FIFO priority behavior and resource cleanup. Link the measured development record;
mark design/plan status only as each slice actually completes.

**Validation:** focused Action! example and C message runs, with output/status,
completion ordering and resource checks. Repeat lower-level tests only if the
implementation changes. No standard demo refresh is required for documentation
or source-only example cleanup; any requested demo refresh must use the OF816
distribution builder.

**Commit:** `Use CreateTask in ordinary Task examples`.

## C5 — Demonstrate unchanged C source on Amiga

Freeze an available classic 68k compiler, SDK, startup/link options and Amiga
runtime profile. Keep target build recipes and startup adapters outside
`messages.c`. Use the normal classic Exec/amiga.lib declarations, not OS4-only
interfaces. Select a compiler model that supports ordinary subtask entry without
uninitialized per-task global-base registers.

Build the exact same source bytes for Calypsi/Exec816 and Amiga. Run both,
recording the source hash, toolchain/runtime inputs, message/result assertions,
successful shutdown and repeatability. The Amiga test must observe success, not
merely produce a linkable executable. Use its program exit status or external
observation for results while output-library work remains out of scope.

If the Amiga tools/runtime are unavailable, finish C1–C4 and report C5 as pending;
do not infer compatibility from the Exec816 run or a host C compile. Document the
missing inputs rather than changing the shared source to hide a target difference.

**Commit:** `Add reproducible Amiga and Exec816 message example builds`.

## Completion and cost report

Report the two milestones separately: the shared API is delivered after C4;
the unchanged-source compatibility demonstration requires C5.

For each implementation slice, record full fixed and per-Task bank-zero deltas,
including guards, alignment and unused capacity. Both must remain **zero**.
The managed table occupies 192/448 bytes for four/eight slots, including stride
padding, plus any alignment/metadata rounding. Distinguish active storage growth
inside an existing arena from growth of the arena's full reservation.

Compare total emitted Task-policy/gateway/shim code and observed stack use against
matching baseline builds. Include support code added and obsolete C preparation
code removed; moving work between modules is not a size saving. Retain the compiler
pin and checked settings for comparison, and do not enlarge stacks to hide a
regression. Save focused results under one CreateTask development record with
source/profile hashes. Full release qualification remains separate.


## Delivered results

All five slices are complete. The Action! and C bindings share public selector
61 through COP #$50; Task feature version is `$0800`. The compiler pin is unchanged.
Ordinary examples use managed records and signals; the explicit-stack/custom-
finalizer example retains AddTask.

| Cost | Before | After | Change |
| --- | ---: | ---: | ---: |
| Optimized Task policy, matching checked fixture | 56,255 B | 58,381 B | +2,126 B |
| Upper gateway/support segment | 7,511 B | 7,526 B | +15 B |
| Fixed bootstrap segment reservation | 4,096 B | 4,096 B | 0 B |
| Entire compiled optimized C shim | 1,506 B | 1,429 B | −77 B |
| Active Task metadata, four slots | 512 B | 704 B | +192 B |
| Active Task metadata, eight slots | 768 B | 1,216 B | +448 B |
| Full upper arena reservation | unchanged | unchanged | 0 B |
| Fixed / per-Task bank-zero reservation | unchanged | unchanged | 0 / 0 B |

The managed-table strides and metadata rounding are included above. The new
context-rejection branch occupies five bytes inside the existing fixed bootstrap
reservation. The C shim includes the 179-byte CreateTask wrapper and removes the
216-byte preparation helper plus its pool-table support. These are separate
package components, not a claim that every executable links the entire C shim.

The unchanged AddTask fixture's kernel stack fill scan stayed at 157 bytes; the
CreateTask scenarios reached 183 bytes. No stack or DP reservation was enlarged.
All guards remained intact. The development runs cover 238 host checks, raw and
optimized native ABI/lifecycle cases, four/eight-slot layouts, nondefault worker
stacks, C VBI/DP preservation and the migrated examples.

The identical C source ran on Exec816 twice and on the pinned classic Amiga setup
in two cold boots, with three successful invocations per Amiga boot. Both targets
verified `(10,20)` → `(60,70)` and message identity. The
[build guide](../guides/amiga-c.md) and [evidence](../development/create-task.json)
record scope, source hashes and inputs. Release qualification remains separate.
