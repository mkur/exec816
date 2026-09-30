# Memory allocation

[Reference index](README.md)

Exec manages explicitly registered RAM regions. The bank manager supplies usable
upper RAM; the heap allocates bytes within it. Bank zero is available only through
its explicit platform reservations, never as an implicitly free whole bank.
There is no allocator Task.

## Public interface

Calls belong to `EXEC`. Sizes and attributes are unsigned `LONGCARD`; data
pointers are native 24-bit pointers. Exact declarations and constants are in
[exec-memory-types.inc](../../lib/exec/exec-memory-types.inc) and
[heap-v1.json](../../abi/heap-v1.json).

| Call | Contract |
| --- | --- |
| `AllocMem(bytes, flags)` | Return a pointer or `NULL`. Retain the requested size for freeing. |
| `FreeMem(pointer, bytes)` | Release an AllocMem block using its original pointer and requested size. |
| `AllocVec(bytes, flags)` | Allocate with private size tracking; return a pointer or `NULL`. |
| `FreeVec(pointer)` | Release an AllocVec block. `NULL` is a no-op. |
| `AvailMem(flags)` | Snapshot matching free bytes, largest allocation, or total registered capacity. |
| `TypeOfMem(address)` | Return registered region attributes, or zero. This does not prove that an allocation is live. |
| `Allocate(header, bytes)` / `Deallocate(header, pointer, bytes)` | Manage a caller-owned MemHeader pool, under caller-owned synchronization. |

The two allocation/free pairs are not interchangeable. Zero-byte allocation
returns `NULL`; `FreeMem(pointer, 0)` does nothing. A null pointer with a nonzero
FreeMem size is misuse. Unsupported requirements or allocation failure leave
ownership unchanged. Detected invalid frees and invalid calling contexts fault;
there is no DOS-style allocation error slot.

## Allocation modes and attributes

Blocks have eight-byte alignment and rounded storage, but only the requested
bytes are payload. `MEMF_CLEAR` clears the requested bytes before return.
AllocVec additionally reserves a private eight-byte prefix, which is not caller
storage.

By default an upper-RAM allocation fits within one 64 KiB bank. The largest
possible AllocMem payload is 65,536 bytes, subject to available space; AllocVec's
prefix reduces its maximum payload to 65,528. `MEMF_LINEAR` permits one physically
contiguous allocation across adjacent banks. It does not join discontiguous
memory or make the CPU's bank-sensitive instructions transparent.

| Attribute | Meaning |
| --- | --- |
| `MEMF_PUBLIC` | Shared address-space memory. |
| `MEMF_UPPER` | Select upper RAM; the default allocation region. |
| `MEMF_BANK0` | Explicitly select registered bank-zero heap memory. |
| `MEMF_CLEAR` | Clear payload before returning. |
| `MEMF_LINEAR` | Permit a contiguous cross-bank upper allocation. |
| `MEMF_NO_EXPUNGE` | Accepted compatibility flag; no library expunge mechanism exists. |

BANK0 combined with UPPER or LINEAR is invalid. CHIP, FAST, LOCAL, 24BITDMA, KICK
and REVERSE requirements are unsupported. Unknown flags and requests whose
rounding or extent overflows are rejected before mutation.

`AvailMem` normally sums matching free bytes. `MEMF_LARGEST` asks for the largest
possible AllocMem payload under the selected mode; `MEMF_TOTAL` asks for total
registered capacity. Combining LARGEST and TOTAL is invalid and returns zero.
The result is a snapshot, not a reservation.

## Ownership and execution

The caller releases ordinary allocations explicitly. Removing a raw Task does
not reclaim arbitrary heap blocks. Process cleanup handles its documented DOS
resources; it is not general heap ownership tracking. Dynamic Task stack/DP
allocation and allocation groups remain outside this API.

Free-list mutations are serialized in short kernel operations with interrupts
permitted under the platform protocol. Allocation wrappers complete vector
initialization and CLEAR on the caller's stack. Call the native wrappers rather
than sending allocation packets directly, which bypasses that completion work.
Private-pool Allocate/Deallocate do not acquire system-pool synchronization for
the caller.

See the [memory example](../../examples/memory.act),
[bank-zero budget](platform.md#bank-zero-memory-budget) and
[historical design](../history/memory-allocation-design.md) for implementation
rationale and earlier validation records.
