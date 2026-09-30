# Lists implementation plan

Status: historical implementation plan. The [classic Exec update](../history/lists-exec-update.md)
supersedes its representation and API choices. See the [Lists contract](../reference/lists.md) for the actual API,
commands and qualification. Lists are the first slice of milestone 5 in the
[roadmap](../roadmap.md), after [banked loading and ownership](../history/banked-loading.md).

## Outcome and scope

Implement an intrusive doubly linked list library in Action!, module
`EXECLISTS`. Callers supply the list header and nodes, so the library needs no
allocator, bank-manager calls or global workspace. It will support ready
queues, wait queues and message queues as those services are introduced.

This slice delivers list operations and executable qualification. Adopting
Lists in the scheduler, expanding task records or bank-zero pools, dynamic task
creation, priority ordering, sorted insertion, list splicing, name lookup and
allocation remain separate work. Keep the current two-task scheduler and COP
service ABI intact.

Use the [pinned compiler](../../toolchain/actionc.json), `wdc-65816-native` and
`action65816.native.v1`. The pin defines three-byte data pointers with byte
alignment, ordinary JSL/RTL calls and pointer results in A plus X's low byte.
Its source supports self-referential record pointers. Stage 1 must qualify the
exact exported record and call shapes used here; those existing capabilities
alone do not establish Lists correctness.

## Representation and invariants

Use null-terminated links and explicit first/last pointers:

```action
MODULE EXECLISTS
PUBLIC TYPE Node=[Node POINTER next,prev]
PUBLIC TYPE List=[Node POINTER head,tail]
; Public routines follow.
ENDMODULE
```

| Record | Field | Offset | Size |
| --- | --- | --- | --- |
| `Node` | `next` | 0 | 3 |
| `Node` | `prev` | 3 | 3 |
| `List` | `head` | 0 | 3 |
| `List` | `tail` | 3 | 3 |

Both records occupy six bytes under the selected ABI. Use typed null pointers
for `$000000`; never store links or pointer results in `CARD`. This layout
avoids sentinel nodes and header-to-node casts. It is an Exec-inspired API,
with its own representation rather than Amiga binary compatibility.

The contract is:

- An empty list has both `head` and `tail` null. A nonempty list has both nonnull,
  `head.prev` null and `tail.next` null.
- Each interior link is reciprocal: `node.next.prev = node` and
  `node.prev.next = node` wherever the adjacent pointer is nonnull. Traversal
  reaches the opposite endpoint without cycles or duplicate nodes.
- One embedded `Node` belongs to at most one list. A containing task or message
  may embed separate nodes for separate memberships.
- Removal clears both links in the removed node. This supports reuse, but two
  null links do not prove nonmembership: a linked singleton has the same links.
  Membership and node lifetime remain the caller's responsibility.
- List operations modify only header/link fields. Payload bytes and other
  embedded nodes remain untouched. Live headers and nodes occupy disjoint
  storage; callers do not copy active structures to create a second list.
- Headers and nodes may reside in different native RAM banks. Individual
  records, including a three-byte pointer field, may cross a bank boundary if
  every byte lies in contiguous RAM owned by the caller. All address arithmetic
  retains 24 bits; crossing the end of the 24-bit address space is unsupported.

The library imposes no bank-zero residency requirement. Future task management
will choose storage within its validated region map. OS addresses, stack/DP
reservations, absent RAM and another owner's banks do not become usable merely
because a pointer can represent them.

Callers pass `@object.link` for an embedded node. For initial task integration,
placing a link first in its containing record permits an explicit typed pointer
cast back to that record. Generic container-offset recovery is outside this
slice. Test both a first-field node and a node after payload fields, preserving
the surrounding payload in each case.

## API and operation semantics

All routines are public ordinary native calls in `EXECLISTS`. They follow the
compiler calling convention, not the raw-register preservation contract of COP.
In this table, `list` is `List POINTER`; `node` and `after` are `Node POINTER`.

| Routine | Result | Behavior |
| --- | --- | --- |
| `Init(list)` | none | Set both endpoints to null. Storage must be new or already empty; this does not detach an existing chain. |
| `IsEmpty(list)` | `BYTE` | Return exactly 1 for empty, otherwise 0. |
| `AddHead(list, node)` | none | Insert a detached node before the current head. |
| `AddTail(list, node)` | none | Insert a detached node after the current tail. |
| `InsertAfter(list, after, node)` | none | Insert after a member; null `after` means add at the head. Insertion after the tail updates the tail. |
| `Remove(list, node)` | none | Unlink this member, repair both neighbors/endpoints and clear its links. |
| `RemHead(list)` | `Node POINTER` | Remove and return the head; return null without writes when empty. |
| `RemTail(list)` | `Node POINTER` | Remove and return the tail; return null without writes when empty. |

Every operation has bounded O(1) work and O(1) invocation storage. Use direct
`head`, `tail`, `next` and `prev` reads for traversal under the same synchronization
rules as the routines. Save the next pointer before removing the current node
during traversal.

These are trusted primitives. `list` must point to a valid initialized header
except on first `Init`; insertion requires a valid nonnull detached node;
`Remove` requires a nonnull member of that exact list; nonnull `after` must be
a member and distinct from the inserted node. Double insertion, wrong-list or
double removal, null dereferences and stale pointers violate preconditions.
Do not add membership scans, owner fields or a misleading error guarantee for
these cases. A bounded validator in the test harness detects structural errors;
it is not part of the runtime API.

## Synchronization and lifetime

The primitives are reentrant through invocation-owned locals and the caller's
compiler domain. They contain no scheduling, OS calls, locks or mutable module
scratch. Neither a three-byte pointer store nor a multi-link update is atomic.
Invariants need hold at operation boundaries while the caller owns access;
interrupts may arrive between individual stores.

Use the existing [platform protocol](../reference/platform.md) and
[preemption contract](../history/vbi-preemption.md):

| Caller | Required protection |
| --- | --- |
| Initialization before task dispatch | No task or interrupt consumer may access the list yet. |
| Serialized kernel policy | Keep the existing kernel stack/domain and transition protocol active for the whole operation. Interrupt handlers must not inspect or mutate these lists. |
| Tasks sharing a list | Check successful `EXEC.Lock()` before any shared access; hold it across traversal and compound updates; finish with a checked `EXEC.Unlock()`. The outer unlock may immediately switch tasks. |
| Task-private list | No scheduling lock is needed when no other task/handler can access its header or nodes. |
| IRQ/NMI handler | Calling Lists or accessing a shared list is unsupported in this slice. |

Hardware interrupts continue under a task scheduling lock. The existing VBI
hook only records tick state and must not traverse Lists. `SEI` alone is not
the NMI protection strategy. Do not yield, block, exit or call the OS while
holding access to an inconsistent list. A future scheduler must restore queue
invariants before publishing a task switch.

Protection includes reads and object lifetime, not just writes. A caller cannot
retain a borrowed pointer across unlock and assume another task has kept the
node alive or on the same list. Removing a node may transfer its ownership to
the caller according to the containing service's rules; the library itself
never frees a node or releases its bank.

## Implementation sequence

### 1. Establish the source and layout contract

Add `lib/exec/execlists.act` with exported types, `Init` and `IsEmpty`, and document
the interface in a new `docs/reference/lists.md`. Keep type definitions in that module as
the single source of truth. No assembly consumes this layout yet, so do not
duplicate offsets in the COP ABI or introduce a separate ABI generator. Add
generated shared definitions before any later assembly consumer needs them.

Create an external-module fixture that uses the qualified public types, embeds
nodes in records and passes/returns node pointers through actual calls. Inspect
compiler record facts and emitted image interfaces; assert six-byte sizes,
offsets 0/3, pointer arguments/results and array stride through target execution.
Use typed pointer casts for fixed upper-bank test addresses; wide bare
declaration-address aliases are outside the pinned compiler's supported subset.

Acceptance: raw and optimized emitted code imports the module, initializes
guarded headers, preserves neighboring bytes and round-trips a nonzero-bank
pointer with all 24 bits intact. Any compiler blocker is fixed in actionc with
focused regressions and an explicit pin update, not an Exec-specific workaround.

### 2. Implement and qualify sequential operations

Implement end insertion/removal, arbitrary removal and `InsertAfter`, reusing
small helpers where useful. Store neighbor pointers in invocation locals before
rewiring; keep stack usage bounded and avoid recursion or whole-record copies.

Add `tests/programs/lists.act` and a bounded `tools/test_lists.py` runner using
the existing compiler, build, emulator and guard-check helpers. Exercise actual
emitted operations and compare them with an independent host model consisting
of ordered node IDs. Check full-width endpoint/link values, forward and backward
order, unique membership, detached links, payloads and guards after each step.
Bound the validator by the fixture's node count so a cycle produces a failure
instead of hanging the test.

Include a deterministic mixed-operation trace over two lists and a fixed node
pool. Generate only operations that meet the API preconditions, record the seed
and trace, and cover transfer between lists, draining and repeated reuse. The
host model supplies expected semantics; executing a Python imitation of the
implementation is not target qualification.

Acceptance: every API operation passes empty, singleton and multi-node cases
in raw and optimized code, including all endpoint transitions and full-pointer
returns. Only the permitted link/header bytes change.

### 3. Qualify banked placement and preemption

Extend the runner with the [pinned upper-RAM profile](../../toolchain/altirra-1m.json)
and the existing INITAD packaging path. Reserve test storage before writing it:
either include validated fixture extents in the image's reservations or reserve
whole test banks during serialized kernel initialization through `EXECMEMORY`.
Record the chosen ranges and verify they do not overlap code, near data or
platform reservations. Tests must not silently use unclaimed upper RAM.

Cover a bank-zero header with upper-bank nodes, an upper-bank header, identical
low-16-bit node addresses in different banks, and records/pointer fields spanning
a bank boundary. Test odd byte addresses as well as naturally aligned storage.
Keep bank-zero shadow locations guarded to detect truncated pointer writes.
Use the existing test-only far-memory helpers when inspection needs them; the
bridge exposes only near memory and a 16-bit PC. Rendezvous in bank zero and
prove upper-bank behavior through emitted execution and full-width memory data.

Use the current two tasks for two distinct cases:

- Private lists: both tasks call the same routines on separate lists while VBI
  preempts them, checking invocation-local isolation and continued progress.
- Shared list: both tasks transfer nodes under scheduling locks. Use nested
  locks and test-only checkpoints between link writes. Wait for an actual VBI
  at each checkpoint, verify no peer mutation occurs while locked, and verify
  deferred progress after the outer unlock. Also exercise a list operation on
  the serialized kernel initialization path.

Checkpoint code must be absent from production builds and must not add an OS
call or voluntary switch inside the mutation. Normalize host source text before
instrumentation and test both LF and CRLF through that actual path. Include
uninstrumented executions; do not infer production correctness only from builds
whose extra calls may change optimization.

Acceptance: all cases terminate within explicit frame/time bounds, preserve
stack/DP/payload guards and domain metadata, retain image bank reservations,
and maintain OS VBI/clock and console operation. Check native context restoration
where interruption is introduced, using the existing platform checks. This
qualifies ordinary ABI callers; it does not promise arbitrary raw M/X widths
at entry to an Action! routine.

### 4. Record qualification and hand off to task management

Write `docs/qualification/lists.json` with compiler/ABI, ROM and emulator pins,
source and fixture hashes, memory ranges, optimization mode, image/XEX hashes,
trace seeds, case results and bounds. Record measured code size and compiler
stack costs, including helper call depth; verify them against the existing
domain floors and interrupt headroom.

Update `docs/reference/lists.md`, README and the roadmap with the actual API, build/test
commands and limitations. The new runner should follow existing
`--compiler-dir`, `--bridge-dir`, `--rom` and `--case` conventions, placing
artifacts in `build/lists-tests/`. The [Lists contract](../reference/lists.md) documents the
implemented commands.

Run the new target matrix in raw and optimized modes and the affected host
tests. With library/fixture-only changes, run existing banked demo and lock
regressions as integration checks. If shared build, startup or interrupt code
changes, broaden to its hosted/cooperative/preemptive/banked consumers. Run
generator checks when their inputs or consumers change. Compiler-wide checks
are required only if compiler contracts change, following actionc's instructions.
Repeat passing suites only after a relevant change or unresolved failure.

## Acceptance matrix

| Area | Required cases |
| --- | --- |
| Layout and ABI | Exported recursive types; six-byte records/stride; embedded nodes at zero and nonzero offsets; native pointer arguments and returns; null and nonzero bank bytes. |
| Empty and singleton | Initialization/reinitialization of an empty header; read-only `IsEmpty`; empty removals return null without writes; every insert/remove path into and out of a singleton. |
| Ordering and removal | Head/middle/tail insertion and removal; null `InsertAfter`; insert after last; forward/backward traversal; draining from both ends; remove while iterating with saved next. |
| Reuse and independence | Repeated reuse; transfers between two lists; separate embedded memberships; payload preservation; deterministic mixed-operation trace checked after every step. |
| Native addresses | Near/far headers; nodes in multiple banks; equal low words with distinct bank bytes; odd addresses; boundary-crossing records and pointer fields; no shadow or guard writes. |
| Synchronization | Serialized kernel initialization; preempted private lists; shared-list nested locks; actual VBI during partial updates; no peer access until unlock; pending delivery and bounded peer progress. |
| Hosted integration | Raw/optimized production and checkpoint builds; stack/DP guards and context checks; OS clock/console; cleanup restores vectors/MEMLO; reservations remain owned. |
| Reproducibility | Pinned inputs; validated storage ranges; bounded validators/execution; recorded hashes/traces; LF/CRLF instrumentation if introduced. |

Completion requires the documented API and this matrix to pass through emitted
code with a committed qualification record. The next slice can then replace
fixed two-task selection with a ready list and design the expanded task,
stack and direct-page pools within the checked bank-zero layout.

## Implementation decisions

The typed record-pointer conversions required a compiler correction: explicit
named pointer conversions now parse as casts and validate their destination
types before NIR. Exec pins that separately tested correction; see the
[compiler qualification](../qualification/compiler-lists-fix.json).

Sequential tests capture guarded memory after each trace step and compare it
with an independent ordered-node model, with bounded forward/backward walks.
The test image includes all fixture regions in its INITAD reservations.
Checkpoint builds insert test-only calls after each of the 23 scalar link-write
sites. Shared-list startup uses a gate published under the first task's lock,
so the pending-delivery check does not depend on which task first receives VBI.
The complete matrix also executes uninstrumented raw and optimized library code.
