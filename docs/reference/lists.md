# Intrusive Lists

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

## Preemption and synchronization

List updates and three-byte pointer writes are not atomic. All scratch is
invocation-local, but sharing a list still requires serialized access, including
reads, traversal, name/priority changes and compound operations.

- Initialize before dispatch with exclusive access to the storage.
- Serialized kernel policy retains its existing stack/domain and transition
  protocol throughout the operation.
- In the current Task profile, sharing tasks call `EXEC.Forbid()` before access
  and `EXEC.Permit()` afterward. The outer Permit may immediately switch tasks.
- A private list needs no scheduling lock if no other task or interrupt can
  access its storage.
- IRQ/NMI calls to Lists, or interrupt access to a shared list, are unsupported.

Hardware interrupts continue while the scheduling lock is held. The VBI hook
records ticks and never traverses Lists; SEI alone does not mask NMI. Restore
invariants before releasing access or publishing a switch, and do not yield,
block, exit or call the OS during a partial update. Borrowed pointers retained
across unlock do not guarantee node lifetime or continued membership. See the
[preemption contract](../history/vbi-preemption.md).

## Further reading

See the [Task API](tasks.md) for Task record lifetime and the
[testing policy](../contributing/testing.md) for validation scope. The
[earlier list reference](../history/lists-reference.md) preserves migration notes,
old code-size measurements and the qualification record for its original build.
