# Classic Exec list update

> Historical record: applies to the revisions and profiles described below.
> See the [current documentation](../architecture/overview.md) and [history index](README.md).

Status: implemented and qualified (14 list cases, 38 task integration cases).
This supersedes the representation and API choices in the
[original implementation plan](../plans/lists-implementation-plan.md). The
[contract](../reference/lists.md) describes the new implementation and its qualification.

## Design

Follow classic Exec's intrusive, doubly linked sentinel lists and public names.
Use `MinNode`/`MinList` for linkage-only storage, and `Node`/`List` for named,
typed and priority-ordered objects. Keep the original field names and ordering:

| Type | Fields | Native size |
| --- | --- | --- |
| `MinNode` | `mln_Succ`, `mln_Pred` | 6 bytes |
| `MinList` | `mlh_Head`, `mlh_Tail`, `mlh_TailPred` | 9 bytes |
| `Node` | `ln_Succ`, `ln_Pred`, `ln_Type`, `ln_Pri`, `ln_Name` | 11 bytes |
| `List` | `lh_Head`, `lh_Tail`, `lh_TailPred`, `lh_Type`, `lh_Pad` | 11 bytes |

Pointers are native 24-bit pointers. Metadata bytes retain their original
widths. `ln_Pri` is stored as a BYTE with signed two's-complement ordering
(-128 through 127); Action! has no signed byte type. No word-alignment padding
is needed. Preserve the explicit `lh_Pad` field for structural familiarity.
These are source-level conventions, not an Amiga binary ABI.

The head sentinel starts at the header and the tail sentinel at its second
pointer. Initialize head to the tail sentinel, tail to null, and tailPred to
the head sentinel. A zero-filled header is not initialized. Link operations
must never read node metadata from either sentinel.

Expose `NewList`, `NewMinList`, `IsListEmpty`, `IsMinListEmpty`, `AddHead`,
`AddTail`, `Insert(list,node,pred)`, `Remove(node)`, `RemHead`, `RemTail`,
`Enqueue`, and `FindName`. Common operations use List/Node pointer signatures;
minimal records use explicit typed casts, as in the original C API. Only
Enqueue and FindName inspect full Node metadata.

Insert accepts a null predecessor or the head sentinel for head insertion,
and the tail sentinel for tail insertion. RemHead/RemTail return null when
empty. Removal repairs neighbors but leaves the removed node's fields intact;
those stale links are not a membership test. Enqueue uses descending signed
priority with FIFO ties. FindName compares case-sensitive zero-terminated byte
strings, skips unnamed nodes, and supports continuing after a node cast to a
List pointer. NewList preserves list type/pad, which the caller initializes.

The synchronization and storage-lifetime contract is unchanged. Operations
remain trusted, non-atomic primitives. Fixed-position mutations are O(1);
Enqueue and FindName scan the list. No allocation, locking, scheduling or OS
calls belong in this module.

## Executable slices

1. Commit this design update before changing implementation.
2. Replace list structures and operations, migrate all fixtures and the task
   ready queue, and qualify emitted raw/optimized code. The task record keeps
   its six-byte MinNode prefix. Grow the ready header from six to nine bytes
   and move following bookkeeping within the existing reserved region using
   the machine-readable task ABI. Update guards and shutdown assertions for
   sentinel endpoints and retained removed-node links.
3. Commit the implementation with the updated public contract and qualification
   records. Preserve earlier records as historical evidence.

## Acceptance

- Independent ordered-node model checks every operation, sentinel endpoints,
  forward/backward traversal, stale removed links, reuse and two memberships.
- Native sizes/offsets and minimal/full interoperability are exercised through
  emitted code, including odd, far and bank-crossing records and pointers.
- Cover Insert's null/head/tail predecessor forms, empty removals, singleton
  transitions, and removal while iterating with a saved successor.
- Cover signed priority extremes, FIFO ties, named/unnamed nodes, duplicate
  names, case-sensitive misses, empty strings and continuing a name search.
- Retain raw/optimized private/shared queue tests, actual VBI between pointer
  writes, timer IRQs, nested locks, stack/domain guards and OS coexistence.
- Run the general-task matrix after ready-header relocation, including
  lifecycle, sleep, join/reap/detach, NMI transitions and register restoration.
- Record actual code/stack costs without claiming a speed improvement from
  source inspection. Keep compiler, ROM and emulator pins unchanged unless a
  separately fixed compiler defect requires a documented update.

Reference: [Amiga Exec lists and queues](https://wiki.amigaos.net/wiki/Exec_Lists_and_Queues).
