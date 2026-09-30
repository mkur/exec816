# Byte-level memory allocation (superseded proposal)

> Historical record: applies to the revisions and profiles described below.
> See the [current documentation](../architecture/overview.md) and [history index](README.md).

Status: superseded by the [classic Exec allocation design](../reference/memory.md).
This document records the earlier status-returning Alloc/Free prototype, its
live-block headers and ABI probes. Those probes are implemented; allocation/free
services are not. The API, flags, size limits, invalid-free guarantees, ownership
policy and IRQ-masking choices below are historical, not the current design.
The [current implementation plan](../plans/memory-allocation-implementation-plan.md)
replaces the prototype plan for allocator policy work in
[roadmap milestone 6](roadmap-chronology.md#6-allocation-and-synchronization).

The implemented [Task migration](tasks-exec-update.md#version-and-gateway-migration)
preserved this prototype's selectors and call shapes. Its generated profile
metadata still targets `$0201`, following the `$0200` Task core. The earlier
`$0103` probe records remain evidence for that prototype, not the revised API.
The Task core requires an empty tc_MemEntry; it does not change shared
allocation lifetime.

## Scope

Provide a shared heap in verified native upper RAM, backed exclusively by the
[bank manager](bank-manager.md). Applications allocate byte-sized blocks and
explicitly free them. The initial public service targets the
[general-task profile](../guides/tasks.md) and the pinned
[AltirraOS upper-RAM configuration](../../toolchain/altirra-1m.json).

Two modes share the same allocation/free API:

| Mode | Address guarantee | Intended use |
| --- | --- | --- |
| Ordinary (default) | Every payload byte lies in the same 64 KiB bank. | Objects and buffers whose consumers require bank-contained storage. |
| `LINEAR` | One contiguous native address interval, which may cross bank boundaries. | Large buffers and arrays accessed with full 24-bit addressing. |

Ordinary allocations share subdivided banks. The first linear implementation
reserves a dedicated run of consecutive banks per allocation. Both acquire
storage from the same physical inventory; they cannot overlap. Image and
system reservations remain pinned. The heap does not reclaim unused bytes
inside image banks or discover RAM by probing it.

Bank zero remains outside this heap. Existing task stack/direct-page pools,
kernel storage and OS-facing buffers retain their current layout and lifetime.
Heap pointers cannot be passed directly to the current near-only console
adapter; callers copy through a permitted bank-zero buffer. Dynamic stack/DP
allocation and a bank-zero buffer pool require separate contracts.

## Proposed public API

Add module `EXECALLOC`, keeping `EXECMEMORY` as the trusted internal whole-bank
interface. The following declarations are proposed native Action! imports:

```action
PUBLIC EXTERNAL CARD FUNC Alloc(SIZE bytes CARD flags ADDRESS POINTER result)
PUBLIC EXTERNAL CARD FUNC Free(BYTE POINTER data)
```

Both calls return a CARD status. `Alloc` writes a complete 24-bit address to
`result^` only on success; it preserves the output cell on every returned
error. The ordinary native wrapper performs this output store after the COP
service returns. The kernel receives size and flags, not an application output
pointer. There is no shared last-error variable.

`SIZE` is 24 bits on the pinned native ABI. Select linear mode with
`EXECALLOC.LINEAR`; combine it with clearing using
`EXECALLOC.LINEAR OR EXECALLOC.CLEAR`. A request never silently changes mode.
Ordinary requests larger than their limit fail even when a linear run exists.

The caller must supply a writable ADDRESS cell whose lifetime covers the call,
including any preemption before the wrapper returns. This is an ordinary
native pointer precondition, not a checked memory-protection boundary. The
cell can be in bank zero or upper RAM. A null, dangling or unwritable result
cell is caller misuse. Callers convert a successful address to the required
typed pointer, retaining all 24 bits.

| Operation | Defined behavior |
| --- | --- |
| `Alloc(bytes, 0, result)` | Ordinary allocation of 1 through `MAX_BANK_SIZE = 65,512` bytes, inclusive. Return an even, nonnull address. Payload contents are unspecified. |
| `Alloc(bytes, LINEAR, result)` | Allocate one contiguous interval of 1 through `MAX_LINEAR_SIZE = $FEFFF0` bytes, subject to available consecutive banks. `LINEAR = 2`. |
| Either mode with `CLEAR` | Zero exactly the requested bytes before publishing success. `CLEAR = 1` is independent of allocation mode. |
| Zero or excessive size | Return `ERROR_SIZE`; no allocation or output change. |
| Unsupported flag bits | Return `ERROR_FLAGS`; no allocation or output change. |
| No suitable storage | Return `ERROR_NOMEM`; no heap, bank-table or output change. Linear mode requires a consecutive run, even when scattered free banks total enough bytes. |
| `Free(data)` | Release the exact start of a live allocation of either mode. Coalesce ordinary blocks or release the entire linear run. No size or mode argument is required. |
| `Free(BYTE POINTER(0))` | Successful no-op in a valid calling context. |
| Invalid nonnull free | Return `ERROR_POINTER` without mutation. This includes bank-zero, unavailable, image-owned, interior, misaligned and currently freed addresses. |

The ordinary maximum leaves 16 bytes of bank metadata and an eight-byte block
header in a 64 KiB bank. Linear mode keeps a 16-byte header only at the start
of its first bank; the payload starts at offset 16 and continues uninterrupted
through subsequent banks. It reserves `ceil((bytes + 16) / 65536)` banks.
Consequently an exact 64 KiB request is supported in linear mode and initially
occupies two banks. Unused tail space stays with that run until Free; it is
not allocated to another caller.

The linear size limit is an address-space ceiling (255 upper banks minus its
header), not a promise of installed or free capacity. For the 16-bank profile
the ceiling before image/system claims is `$0EFFF0` bytes; actual capacity is
smaller and depends on the longest free run. A valid request exceeding current
capacity returns ERROR_NOMEM. A run may end at the exclusive address `$1000000`
but cannot wrap to bank zero. Consumers must propagate address carries when
accessing a linear buffer; the flag does not change CPU addressing semantics.

Both modes provide at least two-byte alignment. Only the requested payload
belongs to the caller; rounding, tail bytes and allocator metadata are not
additional usable capacity.

Use zero for success and proposed codes `$FF30` through `$FF33` for SIZE, FLAGS,
NOMEM and POINTER respectively. Reuse the gateway's `ERROR_CONTEXT = $FF11`.
The generator must reject collisions with other service/error definitions.
Validate calling context first, then flags, then the selected mode's size
limit, then availability. Reject excessive SIZE values before any narrowing.
Corrupt allocator metadata is a terminal launch fault, not a recoverable
allocation failure; the implementation must detect it before dependent writes.

## Ownership and lifetime

The heap is one kernel resource with fixed owner identities for the complete
launch. Add `HEAP = 5` for ordinary banks and `HEAP_LINEAR = 6` for linear runs,
without renumbering SYSTEM, IMAGE, CLIENT_A or CLIENT_B. Heap storage is OWNED;
it is never task-owned or image-reserved. Neither identity is recycled during
the launch, so they do not need task-generation schemes. Free identifies the
mode from checked ownership and metadata, never from a caller-supplied flag.

All tasks share allocations. A task may free a block allocated by another
task after the application has arranged that nobody will use it again. Task
exit, Join, Reap, Detach and slot reuse do not release heap blocks. In
particular, a root may allocate a block, pass it to a child and exit while the
child continues to use it. Forgotten allocations consume capacity until
explicitly freed or the launch terminates.

The final normal shutdown, after no user task can resume, releases all
remaining HEAP and HEAP_LINEAR banks before restoring the host environment.
Image/system claims remain intact. This shutdown discards any remaining allocation contents;
it is not a task-exit reclamation policy or a DOS-return guarantee.

Free invalidates all aliases immediately. A repeated free is rejected while
the address is not a live allocation, but an old pointer can equal the start
of a later allocation. Raw pointers cannot distinguish those lifetimes. There
is no stale-pointer detection after address reuse, reference counting, owner
authorization or protection against writes through dangling pointers.

## Calling context and synchronization

Public allocation services are available to live user tasks in the general-task
profile. They run to completion on the existing serialized kernel stack/domain
and do not block waiting for memory. A scheduling lock or an interrupted I=1
does not prevent allocation; neither operation changes lock depth. Pending
preemption follows the established safe-return, Unlock and Poll rules.

IRQ, NMI, idle, OS callback and reentrant kernel callers cannot invoke the
public services. Trusted kernel initialization/shutdown use separate internal
helpers in the serialized context. The NMI hook never traverses heap metadata.
`SEI` alone is not the serialization protocol: retain the adapter's complete
save, switching flag, stack/domain transition and restore protocol.

Allocator serialization protects its metadata. Applications must separately
synchronize shared payloads, pointer publication and the decision to free.
Holding an alias across a scheduling boundary does not extend its lifetime.

The current COP dispatcher keeps IRQ masked while running kernel policy; VBI
NMI can still occur. Scanning, clearing and coalescing therefore add both
scheduling and IRQ latency. The first allocator offers bounded work, not a
hard real-time latency guarantee. Qualification must measure the largest
supported clear and fragmented scan, prove continued VBI work, and verify
pending IRQ/preemption delivery afterward. It must not claim continuous IRQ
dispatch during the protected operation.

## Proposed gateway extension

Use the existing `COP #$50` signature. Preserve COP `$00` and all other routing.
Define allocation selectors and layouts in `abi/heap-v1.json`, generate
shared definitions, and raise the general-task profile version from `$0200`
to `$0201` when the services are implemented. Existing selectors retain their
semantics; compatibility launch profiles retain their existing versions.

| Selector | Inputs | Success result | Returned error |
| --- | --- | --- | --- |
| `$0F` ALLOC | A high byte = size bits 16..23, X = size bits 0..15, Y = flags | A = 0, X = address low 16 bits, Y = bank with upper byte zero | A = status; preserve input X/Y |
| `$10` FREE | X = address low 16 bits, Y = bank with upper byte zero | A = 0; preserve X/Y | A = status; preserve X/Y |

A's low byte remains the service selector. In particular a 65,536-byte
allocation enters with A=`$010F`, X=0; zero in X is not a zero-sized request.
The ordinary native import lays out SIZE at argument offset 0, CARD flags at
offset 4 and the three-byte result pointer at offset 6: nine outgoing bytes.

These two new raw services require saved M=0 and X=0; narrower entry widths
return ERROR_CONTEXT before mutation. This makes the full X/Y allocation
result unambiguous across RTI. Existing services continue to support their
documented width combinations. A FREE bank argument with a nonzero Y high
byte is ERROR_POINTER; do not silently truncate it.

Except for the stated results, preserve the complete native context, including
P, DBR, D, S and PBR. Saved decimal mode and either I state are allowed; the
adapter runs policy with its ordinary native arithmetic conventions. The
Action! wrappers enter in the compiler ABI's standard widths and return CARD
status in A. ALLOC's X/Y result is a raw gateway convention, not a change to
the compiler's ordinary pointer-result ABI.

Imports from EXECALLOC in unsupported launch profiles are build errors. No
new COP signature, compiler runtime allocator, or implicit allocation in Lists
is introduced.

## Deferred work

This contract does not provide bank-zero allocation, scattered/virtual linear
storage, custom alignment, realloc, allocation-size queries, quotas, per-task heaps,
ownership transfer handles, automatic task-exit reclamation, memory protection,
interrupt allocation, executable storage, compaction, image unloading or
mapped-memory expansions or suballocation of linear-run tail space. Signals,
semaphores and message ports remain separate parts of milestone 6.

## ABI slice validation

The [original slice 1 qualification](../qualification/memory-allocation-abi.json)
retains the initial CARD-size prototype's results. The revised ABI uses SIZE
and the LINEAR flag; its [qualification](../qualification/memory-allocation-modes-abi.json)
covers raw/optimized calls at generated limits 1, 16 and 256. Probes check both
header layouts, sizes below/at/above 64 KiB, full 24-bit counts and outputs,
bank boundaries, guards, ownership preservation and OS cleanup. Upper-limit
and bank-255 checks are arithmetic only; physical execution uses the pinned
16-bank platform. Allocator policy and COP services remain unimplemented.
The general-task gateway remains at version `$0200`.

```sh
python3 tools/generate_heap.py --check
python3 -m unittest discover -s tests -p 'test_*.py'
python3 tools/test_heap.py --compiler-dir build/actionc \
  --bridge-dir /path/to/AltirraBridge-nightly-macos-arm64
```

`--case abi-16-raw` selects one bounded case. Generated files and reports live
under `build/heap-tests/` by default; `--output` selects a separate directory.
Measured probe frame/code costs are in the qualification record; they are not
estimates for the future allocator. No compiler change was needed.
