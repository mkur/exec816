# Intrusive Lists

> Historical record: applies to the revisions and profiles described below.
> See the [current documentation](../reference/lists.md) and [history index](README.md).

`USE EXECLISTS` provides classic Exec-style intrusive doubly linked lists,
implemented in [Action!](../../lib/exec/execlists.act). The task scheduler uses a minimal
list for its FIFO ready queue. Storage belongs to the caller; the library
allocates no memory and performs no locking, scheduling or OS calls.

## Types and storage

| Public type | Fields in order | Native size |
| --- | --- | --- |
| `MinNode` | `MinNode POINTER mln_Succ, mln_Pred` | 6 bytes |
| `MinList` | `MinNode POINTER mlh_Head, mlh_Tail, mlh_TailPred` | 9 bytes |
| `Node` | `Node POINTER ln_Succ, ln_Pred`; `BYTE ln_Type, ln_Pri`; `BYTE POINTER ln_Name` | 11 bytes |
| `List` | `Node POINTER lh_Head, lh_Tail, lh_TailPred`; `BYTE lh_Type, lh_Pad` | 11 bytes |

Pointers occupy three bytes, aligned to one byte, under
`action65816.native.v2`. The two node links are at offsets 0/3; the three header
links at 0/3/6. Full-node metadata is at 6/7/8 and full-header metadata at 9/10.
There is no implicit padding. `lh_Pad` is retained as an explicit field to follow
Exec's structure. These native layouts are not an Amiga binary ABI.

`ln_Pri` stores a signed priority from -128 to 127 in a BYTE: `$80` represents
-128, `$FF` represents -1, and `$7F` represents 127. Action! has no signed byte
type; Enqueue interprets the representation with signed ordering. Names are
borrowed pointers to case-sensitive, zero-terminated byte strings. A null name
marks an unnamed node. The caller owns name storage and its lifetime.

Use minimal records when only links are needed. Common routines take List/Node
pointers and touch only their minimal prefixes; explicit typed casts allow the
same operations on MinList/MinNode. Enqueue and FindName require full Nodes.
The public types are the layout source of truth; assembly does not inspect
these fields. Task bookkeeping reserves its header through the
[machine-readable task ABI](../../abi/tasks.json).

## Sentinels and traversal

The header contains two overlapping sentinel nodes. For a header at address H,
the head sentinel begins at H and the tail sentinel at H+3. Initialization sets:

- `head = H+3`
- `tail = 0` (this field always remains null)
- `tailPred = H`

A nonempty list's first predecessor is the head sentinel, and its last
successor is the tail sentinel. Sentinel nodes contain linkage only: never
read their name, priority, type or payload. A zero-filled header is **not** an
initialized empty list.

Forward traversal starts at `lh_Head` and ends when `node.ln_Succ` is null;
backward traversal starts at `lh_TailPred` and ends when `node.ln_Pred` is null.
The node tested at termination is a sentinel and must not be processed.
Save the successor before removing the current node while iterating.

Headers and nodes may occupy different banks, odd addresses, or cross a bank
boundary. All bytes must be valid contiguous RAM owned by the caller, without
wrapping the 24-bit address space. Bank zero's reservations still apply.

Embed a node in a containing task/message record and pass its address. Separate
embedded nodes support independent simultaneous memberships. A node at offset
zero can be explicitly cast back to its containing record; the library provides
no automatic container-offset recovery. Do not copy or move an initialized
header or a linked node: the sentinel and neighbor addresses refer to its
original storage. Keep storage alive while linked or borrowed.

## Operations

All calls use the ordinary native Action! ABI. Unless specified otherwise,
`list` is a List pointer and `node`/`pred` are Node pointers.

| Call | Result | Behavior |
| --- | --- | --- |
| `NewList(list)` | none | Initialize three header links; preserve `lh_Type` and `lh_Pad`. Caller initializes metadata. |
| `NewMinList(minList)` | none | Initialize a MinList through its typed pointer. |
| `IsListEmpty(list)` | BYTE | Exactly 1 when empty, otherwise 0; no writes. |
| `IsMinListEmpty(minList)` | BYTE | Same query for a MinList pointer. |
| `AddHead(list, node)` | none | Insert at the front. |
| `AddTail(list, node)` | none | Insert at the back. |
| `Insert(list, node, pred)` | none | Insert after pred. Null or head sentinel means front; tail sentinel means back. |
| `Remove(node)` | none | Repair the two neighbors. No header argument; leave removed-node fields intact. |
| `RemHead(list)` | Node pointer | Remove and return the first node; null when empty. |
| `RemTail(list)` | Node pointer | Remove and return the last node; null when empty. |
| `Enqueue(list, node)` | none | Insert in descending signed priority order, after existing equal-priority nodes (FIFO ties). |
| `FindName(list, name)` | Node pointer | First exact name match, or null; skip unnamed nodes. |

FindName's `name` argument is a nonnull BYTE pointer to a zero-terminated string.
To continue after a match, cast that Node pointer to a List pointer and pass it
as the next search start. The search begins at its successor. Never resume from
a null result or from a sentinel. Names may cross banks when the storage is
contiguous and valid. The search does not modify names or list memory.

Enqueue requires an already priority-ordered list. Change the priority of a
linked node only by removing it, changing the priority, and enqueuing again.
Fixed-position mutations, initialization and empty checks are O(1). Enqueue is
O(number of nodes); FindName also depends on the compared string lengths.

These are trusted primitives. Insert only nonnull nodes that are not currently
linked, remove only real linked nodes, and supply a predecessor belonging to
the specified list (or one of its permitted sentinel/null forms). Empty removals
perform no writes. Removed nodes retain stale links; those links are not a
membership or lifetime test. Reinsertion overwrites both links.

There are no membership scans or recovery guarantees for double insertion,
double removal, wrong-list predecessors, stale pointers or corrupted chains.
Reinitializing a live list does not detach its nodes.

## Migration from the initial Exec816 API

- The old six-byte Node becomes MinNode; full Node now includes metadata.
- The old two-pointer List becomes a three-pointer MinList or a full List.
- Replace Init/IsEmpty with NewList/IsListEmpty (or their minimal variants).
- Replace `InsertAfter(list,pred,node)` with `Insert(list,node,pred)`.
- Replace `Remove(list,node)` with `Remove(node)`.
- Replace next/prev and head/tail access with the corresponding Exec fields.
  In particular, the last node is `lh_TailPred`; `lh_Tail` is always null.
- Update traversal for sentinels and stop assuming removal clears the links.

No aliases retain the old representation or removal contract. Source callers
must migrate and recompile. The later [Task API migration](tasks-exec-update.md)
uses a full Node in each public Task, separate from its private execution context.

## Preemption and synchronization

List updates and three-byte pointer writes are not atomic. All scratch is
invocation-local, but sharing a list still requires serialized access, including
reads, traversal, name/priority changes and compound operations.

- Initialize before dispatch with exclusive access to the storage.
- Serialized kernel policy retains its existing stack/domain and transition
  protocol throughout the operation.
- In the current Task profile, sharing tasks call `EXEC.Forbid()` before access
  and `EXEC.Permit()` afterward. The outer Permit may immediately switch tasks.
  Earlier two-task profiles use their checked `EXEC.Lock()`/`EXEC.Unlock()` calls.
- A private list needs no scheduling lock if no other task or interrupt can
  access its storage.
- IRQ/NMI calls to Lists, or interrupt access to a shared list, are unsupported.

Hardware interrupts continue while the scheduling lock is held. The VBI hook
records ticks and never traverses Lists; SEI alone does not mask NMI. Restore
invariants before releasing access or publishing a switch, and do not yield,
block, exit or call the OS during a partial update. Borrowed pointers retained
across unlock do not guarantee node lifetime or continued membership. See the
[preemption contract](vbi-preemption.md).

## Qualification

Prepare the pinned compiler, ROM and emulator using
[banked loading](banked-loading.md) and the
[current emulator pin](emulator-native-irq-fix.md), then run:

```sh
python3 -m unittest discover -s tests -p 'test_*.py'
python3 tools/test_lists.py --compiler-dir build/actionc \
  --bridge-dir build/altirra-irq-bridge
python3 tools/test_tasks.py --compiler-dir build/actionc \
  --bridge-dir build/altirra-irq-bridge
```

The list matrix has 14 cases: four sequential, eight private/shared preemptive,
and two full-node priority/name cases. Each category covers raw and optimized
NIR. Sequential traces use an independent ordered-node model with bounded
forward/backward validation and byte snapshots, including retained removed
links, metadata, sentinels and guards. Fixtures exercise minimal/full layout,
odd and crossing-bank storage, nonzero-bank pointers, equal low address words
in different banks, and two independent embedded memberships.

Priority/name cases cover signed extremes, FIFO ties, duplicate names,
case-sensitive misses, unnamed nodes, empty names, prefix mismatches, continued
searches and bank-crossing names. Names and metadata must remain unchanged.

Preemptive cases include production builds and test-only checkpoints after all
17 scalar link-write sites. Checkpoints wait for actual VBI, with timer IRQs,
private invocation overlap, nested shared locks and pending delivery. Production
code has no probe dependency. Instrumentation normalizes LF/CRLF line endings.
All cases check bounded completion, stack/domain guards, OS coexistence and
unchanged bank ownership. Tests reserve all upper-bank fixture storage before
writing it. Test bounds are 1,200 frames/60 seconds after native startup, in
addition to the loader's separate 1,800-frame/60-second bound.

The [sentinel-list qualification](../qualification/lists-exec.json) records all 14
passing cases and their input/image hashes. Each sequential case executes 117
operations; each shared probe task reaches 51 checkpoints covering all 17 write
sites. The final 30 host tests and both ABI generator checks pass.

| Library measurement | Raw | Optimized |
| --- | --- | --- |
| Emitted code, all twelve public routines | 6,911 bytes | 6,659 bytes |
| Largest fixed routine frame | 110 bytes | 96 bytes |
| Largest normal call path | 244 bytes | 234 bytes |

The largest call path is Enqueue -> Insert -> AddHead/AddTail. It includes
incoming arguments and JSL return addresses, and excludes the caller's frame,
test instrumentation and platform interrupt headroom. These are storage costs,
not cycle benchmarks. The full library now includes priority/name operations
and typed minimal-header helpers absent from the previous implementation.

The historical [task integration qualification](../qualification/lists-exec-tasks.json) records
38 passing raw/optimized cases: lifecycle, sleep, join/reap/detach, NMI
transitions and register restoration. Qualification exposed a runner issue:
its PC16 polling could mistake an upper-bank instruction for the bank-zero
completion point. The runner now also checks published completion status; the
record preserves each run's exact harness inputs. This fix changes no target
code. Earlier [list qualification](../qualification/lists.json) and
[regressions](../qualification/lists-regressions.json) describe the historical
null-terminated representation. See the [update plan](lists-exec-update.md).
The current Task migration has separate
[Task](../qualification/tasks-exec.json) and
[compatibility/Lists](../qualification/tasks-exec-regressions.json) qualification.

Reference: [Amiga Exec lists and queues](https://wiki.amigaos.net/wiki/Exec_Lists_and_Queues).
