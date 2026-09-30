# Memory allocation: classic Exec design

> Historical record: applies to the revisions and profiles described below.
> See the [current documentation](../reference/memory.md) and [history index](README.md).

Status: implemented and qualified within the scope below, 2026-09-18. The
[private free-list engine](../qualification/memory-exec-core.json),
[upper-RAM registration](../qualification/memory-exec-registration.json) and
[system allocation policy](../qualification/memory-exec-policy.json) are implemented
and qualified. [Public API qualification](../qualification/memory-exec-api.json)
covers all eight native imports, vectors and caller-side CLEAR. The
[implementation record](memory-allocation-implementation.md) reports shared
lifetime, eight-task functional tests and four-task serial qualification under
allocator load, with links to the measured evidence.
This note supersedes the public API, block representation and synchronization
choices in the [earlier proposal](memory-allocation.md). The
[implementation plan](../plans/memory-allocation-implementation-plan.md) follows this
design. [Native ABI probes](../qualification/memory-exec-abi.json) qualify declarations,
flags and layouts. Earlier prototype records are historical. The single current
Task kernel reports `$0600`.

The reference is classic Amiga Exec, including the V36 AllocVec/FreeVec pair,
rather than AmigaOS 4 virtual-memory APIs. Preserve familiar names, argument
roles, failure conventions, memory lists and explicit lifetime management.
Change behavior where native banking, platform ownership or the
[eight-task minimum and 12–16-task target](platform-contract.md#task-capacity-requirement)
require it. Every intentional difference is classified below.

## Scope and ordering

The upper-RAM allocation milestone is complete; message ports are next. Eight-task
concurrent serial timing qualification is **deferred**, not a prerequisite
for designing or implementing the heap. It remains required before claiming
the complete eight-task asynchronous SIO/DOS configuration is qualified.

The first allocator provides the six system calls below and the private-pool
Allocate/Deallocate pair. It uses the existing Lists, Task kernel, bank manager
and interrupt-entry protocol. It requires neither message ports nor a dedicated
allocator task. Keep static Task stack/DP pools during initial heap integration.

The dependency order is **allocation → message ports → queued device I/O and
SIO → DOS/filesystems**. A static-buffer TX/RX experiment can precede those
services, but does not provide their ownership or request/reply contracts.
Dynamic Task storage, allocation groups and public pool-management APIs are
separate extensions, not requirements for the first usable upper-RAM heap.

## Public interface

The core calls are exposed through `EXEC`. These are the current native
declarations; their emitted layouts and public calls are qualified:

```action
PUBLIC EXTERNAL BYTE POINTER FUNC AllocMem(LONGCARD byteSize LONGCARD attributes)
PUBLIC EXTERNAL PROC FreeMem(BYTE POINTER memoryBlock LONGCARD byteSize)
PUBLIC EXTERNAL BYTE POINTER FUNC AllocVec(LONGCARD byteSize LONGCARD attributes)
PUBLIC EXTERNAL PROC FreeVec(BYTE POINTER memoryBlock)
PUBLIC EXTERNAL LONGCARD FUNC AvailMem(LONGCARD attributes)
PUBLIC EXTERNAL LONGCARD FUNC TypeOfMem(BYTE POINTER address)
```

The low-level pair uses the same generated native MemHeader type:

```action
PUBLIC EXTERNAL BYTE POINTER FUNC Allocate(MemHeader POINTER memHeader LONGCARD byteSize)
PUBLIC EXTERNAL PROC Deallocate(MemHeader POINTER memHeader BYTE POINTER memoryBlock LONGCARD byteSize)
```

`LONGCARD` preserves the unsigned 32-bit size and flag arguments of Exec's
`ULONG`; pointers use the native 24-bit representation. A 16-bit CARD is not a
size argument. Keep values wide through validation, rounding and endpoint
arithmetic; reject overflow or unaddressable requests before narrowing. The
[pinned compiler](../../toolchain/actionc.json) defines the native calling ABI.

Applications call the generated native imports, as in the
[memory example](../../examples/memory.act). Allocation COP packets perform the
serialized reservation phase; the native wrapper then initializes any vector
prefix and completes CLEAR on the caller's stack before returning. Sending an
allocation packet directly bypasses that completion protocol and is not a
supported substitute for AllocMem or AllocVec. The private-pool pair tail-calls
the compiled free-list engine with the caller's synchronization in force.

| Call | Contract |
| --- | --- |
| `AllocMem(bytes, flags)` | Return a pointer or null. The caller retains the requested size for FreeMem. |
| `FreeMem(pointer, bytes)` | Return the allocation to its region; no status result. Use the original pointer and requested size. |
| `AllocVec(bytes, flags)` | Return a pointer or null; Exec retains the size needed to free it. |
| `FreeVec(pointer)` | Release only an AllocVec allocation. Null is a no-op. |
| `AvailMem(flags)` | Report matching free bytes, largest possible AllocMem payload, or total managed capacity, as selected below. It is a snapshot, not a reservation. |
| `TypeOfMem(address)` | Report attributes of a registered allocatable RAM region, or zero outside such regions. It does not establish whether an allocation is live. |

The allocation/free pairing and null-on-allocation-failure convention follow
[AllocMem](https://developer.amigaos3.net/autodocs/exec.library/AllocMem.html),
[FreeMem](https://developer.amigaos3.net/autodocs/exec.library/FreeMem.html),
[AllocVec](https://developer.amigaos3.net/autodocs/exec.library/AllocVec.html) and
[FreeVec](https://developer.amigaos3.net/autodocs/exec.library/FreeVec.html).
There is no status-plus-output-pointer replacement or global allocation error.
A future DOS wrapper can translate null into its own process-local error.

For Exec816, zero-byte allocation returns null without mutation. Allocation
failure, including unsupported requirements, leaves ownership and free lists
unchanged. `FreeMem(pointer, 0)` is a no-op; a null pointer with a nonzero size
is misuse. Invalid calling contexts and detected invalid frees take a controlled
kernel fault; void calls must not silently discard an error status.

Preserve eight-byte block alignment and size granularity. Round a positive
request up to a multiple of eight, checking overflow first. Only the requested
bytes are caller payload. `MEMF_CLEAR` clears those bytes before returning the
pointer. There is no mandatory header on a live AllocMem block.

AllocVec adds one private eight-byte prefix containing the backing allocation
size and the requested payload size as LONGCARD values. Its payload remains
eight-byte aligned. Allocate the prefix and rounded payload together; FreeVec
recovers the backing size and uses the same free engine. This prefix is not
application storage, and the two allocation/free pairs are not interchangeable.
Its format is private: the public Exec contract promises size tracking, not a
particular negative offset or a header that clients may inspect. The requested
size permits prefix consistency checks without introducing a live-block table.
Validate region membership and prefix extent before reading it in FreeVec.

With `R(n) = (n + 7) & ~7`, checked in 32 bits, AllocMem reserves `R(n)` bytes
and AllocVec reserves `8 + R(n)`. Reject an overflow in either operation, or a
range whose exclusive end exceeds `$01000000`, before any free-list mutation.
On failure, vector allocation must not leave a prefix or a partial reservation.

## Requirements and the two allocation modes

Preserve classic flag values where their meanings apply. The
[classic memory header](https://developer.amigaos3.net/autodocs/include_h/exec/memory.h)
defines the reference values. Native extensions below occupy unused bits in
that classic namespace. The current ABI generates and collision-checks them.

| Flag | Value | Exec816 meaning |
| --- | --- | --- |
| `MEMF_ANY` | `$00000000` | Default ordinary allocation from upper RAM. No implicit bank-zero fallback. |
| `MEMF_PUBLIC` | `$00000001` | Accepted. All managed memory is shared and resident in this address space. |
| `MEMF_CLEAR` | `$00010000` | Clear the requested payload before returning. |
| `MEMF_LARGEST` | `$00020000` | AvailMem query for the largest payload meeting the selected placement/mode. |
| `MEMF_TOTAL` | `$00080000` | AvailMem query for managed capacity, including live allocations. |
| `MEMF_NO_EXPUNGE` | `$80000000` | Accepted; the initial allocator has no expunge or low-memory callbacks. |
| `MEMF_BANK0` | `$00000008` | Native requirement: use explicitly registered bank-zero byte-allocation regions. |
| `MEMF_UPPER` | `$00000010` | Native requirement: use upper RAM; also the default class. |
| `MEMF_LINEAR` | `$00100000` | Native option: allow a contiguous upper-RAM allocation to cross banks. |

`MEMF_BANK0 | MEMF_UPPER` and `MEMF_BANK0 | MEMF_LINEAR` are invalid.
`MEMF_CHIP`, `MEMF_FAST`, `MEMF_LOCAL`, `MEMF_24BITDMA` and `MEMF_KICK` retain
their classic numeric identities but are unsupported requirements here. Do not
alias CHIP to bank zero, FAST to upper RAM, or infer DMA capability from address
width. `MEMF_REVERSE` is deferred. Unknown or unsupported allocation bits return
null; query-only bits are invalid for allocation.

| Mode | Guarantee | Boundary behavior |
| --- | --- | --- |
| Ordinary, including explicit BANK0 | The complete backing allocation stays in one 64 KiB bank. | AllocMem can request up to 65,536 bytes if a whole eligible bank is free. AllocVec can request at most 65,528 bytes with its eight-byte prefix. |
| LINEAR | One uninterrupted native address interval; banks may change inside it. | Limited by the largest contiguous free extent and the platform map. It can also satisfy small requests. |

There is no automatic promotion of an oversized ordinary request to LINEAR.
Allocation never stitches together discontiguous banks. The LINEAR flag does
not change addressing instructions: the consumer must propagate carries when
accessing successive banks. Bank-contained storage in an upper bank is still
a far address, not an OS-compatible 16-bit pointer.

For a candidate base `p` and complete rounded backing size `r`, ordinary
placement requires `(p & $FFFF) + r <= $10000`, using wide arithmetic. Test
the prefix as well as the payload for AllocVec. If a free chunk's first bank
has too little room, try the next bank boundary inside that same chunk before
discarding the chunk. Skipped bytes remain available to smaller allocations.

Both modes share the same free space. For example, AllocMem of exactly 64 KiB
can use one whole free bank; a 65,537-byte LINEAR request occupies 65,544 bytes
after rounding, leaving the rest of its free extent reusable. This replaces
the old design's dedicated whole-bank run per linear allocation and its
65,512-byte ordinary limit.

AvailMem uses the same region filters as allocation. Its default result sums
free bytes; LARGEST applies the ordinary bank-boundary restriction unless
LINEAR is set. TOTAL reports registered usable capacity after permanent
reservations, regardless of current allocations; allocation mode does not
change that total. LARGEST and TOTAL together are rejected with zero. CLEAR
and NO_EXPUNGE have no effect on queries. Other unsupported bits return zero.
An AllocVec caller must allow for its prefix rather than treating LARGEST as
its maximum payload. This retains the purpose of
[AvailMem](https://developer.amigaos3.net/autodocs/exec.library/AvailMem.html).
The default free-byte sum may exceed 64 KiB even though an ordinary single
allocation cannot. Default and TOTAL queries use checked MemHeader counts;
they do not scan free chunks. LARGEST validates and measures the chunks in one
traversal. Run the same placement calculation for LARGEST and AllocMem;
do not report a cross-bank free chunk as an ordinary allocatable block.

TypeOfMem returns region properties such as PUBLIC and BANK0/UPPER, not CLEAR
or LINEAR options. Free and allocated portions of a registered region have the
same attributes; querying an interior address is not a valid-free check. Image,
OS, allocator-descriptor and otherwise unregistered ranges return zero in this
initial implementation. See the classic
[TypeOfMem contract](https://developer.amigaos3.net/autodocs/exec.library/TypeOfMem.html).

## MemHeaders and free chunks

Use actual Exec-style **MemHeader and MemChunk records**. A MemHeader describes
one registered region, not one allocation. Its full Node participates in the
kernel's doubly linked memory-region list. Free chunks within that region form
an address-ordered, singly linked list; MemChunk is not an Exec Node.

| Record field | Native role |
| --- | --- |
| `mh_Node` | Full Exec Node; type NT_MEMORY, optional persistent name, and region preference priority. |
| `mh_Attributes` | CARD region attributes; allocation/query option bits are not stored here. |
| `mh_First` | Native pointer to the first free MemChunk, or null. |
| `mh_Lower` | Native pointer to the inclusive usable lower bound. |
| `mh_Upper` | LONGCARD exclusive endpoint, able to represent `$01000000`. It is not a dereferenceable pointer. |
| `mh_Free` | LONGCARD count of free bytes. |
| `mc_Next` | Native pointer to the next free chunk, or null. |
| `mc_Bytes` | LONGCARD size of this free extent, including its chunk record. |

Keep the field names and region/free-list model of
[exec/memory.h](https://developer.amigaos3.net/autodocs/include_h/exec/memory.h).
Use generated native offsets and sizes, not 68k structure offsets. The native
MemChunk needs three link bytes, one padding byte and four length bytes, fitting
the retained eight-byte allocation unit. Reuse the current full Node and List
definitions; do not introduce heap-specific substitutes for the region list.
The first implementation slice qualifies packing and array strides through
emitted code: MemHeader is 28 bytes and MemChunk is eight bytes. The eight-byte unit follows Exec's free-chunk representation;
it is not a claim that the 65816 requires eight-byte-aligned accesses.

The region list follows descending `mh_Node.ln_Pri`; use deterministic address
order for equal priorities. This memory preference is independent of Task
priority scheduling. Search each eligible region's free chunks in address
order. Ordinary selection must find a fitting eight-byte-aligned subrange
within a bank, leaving any skipped prefix and remaining suffix free. LINEAR
selection can use a chunk across banks. All nonempty split pieces remain at
least eight bytes. Free inserts by address and coalesces both adjacent chunks
within the same region. Never coalesce across a reserved hole or incompatible
region attributes.

Region bounds are eight-byte aligned; address zero is never allocatable.
Bounds and counts use checked arithmetic through `$01000000`. Every
free chunk must be eight-byte aligned, have a positive multiple-of-eight length,
and lie wholly within its region. Links must advance strictly in address order;
chunks cannot overlap and adjacent chunks must already be coalesced. Their
lengths must sum to `mh_Free`. Validate a chunk before following its link or
using its length, and prevalidate affected ranges before changing links. These
invariants bound traversal and detect cycles without a live-allocation ledger.

Allocated bytes contain no free-list node. This is why FreeMem requires a size
and why freeing a block can overwrite its first eight bytes. A whole free bank
can become a whole AllocMem allocation because its MemHeader is stored outside
the managed range.

Also retain the low-level private-pool operations:

| Call | Contract |
| --- | --- |
| `Allocate(memHeader, byteSize)` | First-fit allocation within the supplied private region; pointer or null. No implicit system-list lookup or lock. |
| `Deallocate(memHeader, pointer, byteSize)` | Return storage to that private free list and coalesce; no result. Caller owns synchronization. |

These follow [Allocate](https://developer.amigaos3.net/autodocs/exec.library/Allocate.html)
and [Deallocate](https://developer.amigaos3.net/autodocs/exec.library/Deallocate.html).
A private Allocate has no implicit bank-boundary guarantee: the caller chose
the region. The system allocator uses a constrained form of the same engine
for ordinary allocations. Private Deallocate retains classic rounding of the
start down and size up to eight-byte boundaries, and may return subranges.
For a nonzero size, release `[align_down(pointer, 8), align_up(pointer + size, 8))`,
checking the sum before rounding so the entire supplied interval is included.
The resulting extent must stay inside the declared private region. Adding
out-of-region storage through Deallocate is deferred; explicit region setup
must establish those bounds first. A client must not call these helpers on the
kernel's live MemHeaders.

## Physical ownership and descriptor placement

The [bank manager](bank-manager.md) remains the authority for physical
availability and ownership. After validated image loading and adoption, heap
initialization claims the eligible unclaimed upper banks for a fixed HEAP owner.
Create one MemHeader for each contiguous run with the same attributes; exclude
all image/system reservations. A bank must not be both FREE in the bank table
and exposed through a heap MemHeader.

Pre-reserve the descriptor storage using the resolved image/platform map.
MemHeaders, the region-list header and bank inventory belong in upper RAM,
preferably the [configured kernel bank](platform-contract.md#kernel-bank-build-parameter).
They must not depend on allocating from the heap they initialize. Size the
descriptor budget for the configured regions, and validate capacity and all
claims before publishing the heap. Additional metadata does not consume native
stack/direct-page capacity.

The current registration implementation reserves a 32-byte-aligned prefix in
the selected kernel bank, after its ownership table when that table is upper.
It includes the 14-byte list/state header, one trusted claim byte per configured
bank, padding to 32 bytes, and `MAX_BANKS - 1` descriptor slots of 32 bytes
(28-byte MemHeaders plus four padding bytes). This conservative bound supports
any separated-run map without recursive allocation: 512 bytes at 16 banks,
8,448 bytes at 256 banks. Only published slots describe allocatable memory;
unused slots remain reserved. No bank-zero reservation grows.

Bootstrap computes the candidate runs and descriptor count before claiming
banks, builds the headers and free chunks while the heap is unpublished, then
publishes the completed region list. On failure, release only claims made by
that attempt and leave the heap unavailable. Neither a partially built region
list nor descriptor-storage banks may become allocatable. Initial registration
uses whole unclaimed upper banks; reclaiming unused portions of image-owned
banks requires a later explicit ownership refinement.

The initial policy retains these registered banks until heap shutdown. FreeMem
returns bytes to the shared free lists; it does not hand every newly empty bank
back to a competing bank allocator. Ordinary and LINEAR use the same HEAP owner;
a separate HEAP_LINEAR ownership class is unnecessary. Whole-bank clients must
use this allocator or have their banks excluded before registration. Demand
growth, bank hand-back and independent image loading need a later coordinated
ownership transition; they must never create overlapping allocation authorities.
This deliberately replaces the earlier grow/return-per-bank policy.

## Bank zero and task storage

Bank zero is an explicit allocation class with a separate capacity budget, not
a fallback when upper RAM is exhausted. Register only platform-approved ranges
whose lifetimes permit reuse. OS memory, kernel/interrupt storage, guards,
boot data still in use and reserved task pools remain excluded. Initially
BANK0 requests fail until such regions are implemented and qualified; they
must never silently return upper RAM.

Generic byte allocation provides eight-byte alignment. It does not promise
256-byte DP alignment or construct a valid task stack. Task setup needs an
internal aligned range allocator for DP storage and guarded stack allocations,
using the same ownership/reservation information. Keep the capacity required
for at least eight live tasks reserved against unrelated BANK0 buffer requests.
Smaller per-workload stacks and further reclamation support the 12–16 target;
the upper heap alone cannot supply that capacity.

SIO requests, filesystem state, cache blocks, public Task records and ordinary
I/O payloads should use upper RAM. A driver needing a bank-zero staging buffer
must state why and budget it explicitly. Current Task admission checks accept
image-backed public records and fixed stack pools; accepting heap-backed Task
records or dynamic stacks requires a separate validation/lifetime integration
slice. AllocMem alone does not make those objects admissible.

## Lifetime, misuse and task removal

AllocMem and AllocVec storage is shared and explicitly freed. It is not
implicitly attached to the allocating Task. Another task may free it after all
users have finished. Removing the creator does not release shared buffers.
For asynchronous I/O, retain the request and buffer until the driver reports
completion; requesting cancellation is not itself permission to free them.

Free validates known region membership, alignment, checked extent arithmetic,
containment and overlap with existing free chunks before writing. Corrupt lists
or detected double frees fault. With no live-allocation ledger, these checks
cannot prove that an aligned pointer and size describe the original allocation:
an interior free, wrong size or stale pointer after address reuse may be
undetectable. Such calls remain misuse, as does mixing FreeMem and FreeVec.
Do not preserve the old proposal's promise to reject every invalid pointer
without mutation. Optional debug tracking can improve diagnosis, not define
the production API or justify mandatory live-block overhead.

AllocEntry/FreeEntry and nonempty `tc_MemEntry` are deferred. The intended model
is explicit groups of allocations, optionally enrolled for RemTask cleanup,
following [AllocEntry](https://developer.amigaos3.net/autodocs/exec.library/AllocEntry.html)
and [FreeEntry](https://developer.amigaos3.net/autodocs/exec.library/FreeEntry.html).
Their later design must address classic AllocEntry's bit-31 failure encoding:
that value cannot be carried by a native 24-bit pointer, and bit 23 is a valid
address bit, not an error tag. Do not publish a guessed replacement now.
Self-removal must abandon its stack/DP before reclaiming them. The current
requirement for an empty tc_MemEntry remains until that integration is qualified.

At launch shutdown, stop admission and quiesce tasks and outstanding I/O before
returning heap-owned banks. Do not traverse corrupt free lists for fault cleanup;
use trusted ownership/reservation state. Image and OS reservations remain intact.

## Synchronization and asynchronous SIO

Allocation, free and memory queries are task-context services, never IRQ/NMI
services. Drivers preallocate their interrupt-visible state; completion handlers
signal or enqueue work without calling the allocator. This is consistent with
the task-context restriction in the classic memory autodocs.

Use the implemented [critical-section protocol](kernel-critical-sections.md).
`E816_SWITCHING` excludes scheduler/policy reentry during a kernel activation;
it does not require masking IRQs throughout that activation. The old
whole-policy IRQ blackout has been removed. Heap integration must preserve
this property, including for scans, coalescing and queries.

The initial system-heap serialization is:

1. Enter through the existing native gateway. Validate arguments, select a
   region, scan and update its free list under the kernel's scheduler guard.
   IRQs remain enabled when the caller entered with I=0. Another Task cannot
   enter heap policy until this activation returns. No additional heap task,
   message exchange or semaphore is needed for this first implementation.
2. IRQ/NMI handlers never traverse or mutate MemHeaders, free chunks or bank
   ownership. They use already-owned buffers, record ticks and post completion
   signals through the existing delivery protocol. Multi-instruction heap-link
   updates are therefore protected by scheduler exclusion; they do not need a
   new IRQ-masked transaction.
3. Complete all metadata updates before releasing the guard. A newly allocated
   block is already absent from the free list, and its pointer belongs only to
   the allocating invocation until public return or explicit publication.
4. Initialize an AllocVec prefix and perform MEMF_CLEAR in the native public
   wrapper on the **caller's task stack/DP**, outside heap serialization.
   Clearing uses full native addressing across banks. The caller may be
   preempted and other tasks may allocate while its private block is cleared.
   Return to the application only after all requested payload bytes are zero.

The internal reserve operation is not a second public AllocMem with weaker
CLEAR semantics. Its result and clearing state remain in per-invocation task
storage; no kernel-stack continuation or shared scratch survives a task switch.
Do not call task-switching services or block midway through heap metadata
updates. Private Allocate/Deallocate do not acquire the system guard: their
caller owns the pool and must serialize any access shared with other tasks.

Preserve incoming Forbid nesting and processor interrupt state. Normally,
clearing is preemptible; a caller already inside Forbid remains nonpreemptible,
while IRQs can still run. Never enable IRQs that the caller had disabled. Calls
made with I=1 are outside the asynchronous-SIO latency guarantee. Bootstrap
initialization runs before ordinary task access under its separate ownership
rules. Allocation failure or controlled faults must not leave a held guard or
partially published heap.

IRQs staying enabled does not by itself bound task wake latency: a long heap
scan still postpones scheduling until the kernel activation ends. Measure the
worst fragmented-list traversal, free/coalesce and LARGEST query as well as
clearing. If scheduling delay exceeds the device buffer budget, shorten those
paths or design a resumable traversal with explicit revalidation before
qualifying the integrated driver. Do not unlock mid-scan and retain unvalidated
free-chunk pointers.

The current four-task diagnostic pump meets the 125 kbaud target under the
tested kernel workloads; it has not exercised this allocator. Before SIO
qualification, measure hardware-ready-to-refill latency against the pinned
byte deadline (about 78.94 µs), IRQ masking and completion-to-worker delay
during allocation/free/query/clearing. Include fragmentation and retained
OS/VBI activity. The deferred eight-task concurrent run remains part of that
system acceptance; eventual IRQ delivery alone does not prove lossless I/O.

## Deviations and reasons

| Difference from classic Exec | Classification and reason |
| --- | --- |
| Native 24-bit pointers, little-endian records and native call/gateway layouts | Required by the CPU/compiler ABI. Preserve source-level roles, not 68k binary offsets or register conventions. |
| `mh_Upper` is a 32-bit integer endpoint | Required to represent the exclusive end of bank `$FF` without wrapping a 24-bit pointer to zero. Sizes/counts remain 32-bit as in Exec. |
| Ordinary allocations cannot cross a bank; LINEAR explicitly permits it | Target requirement: consumers using bank-relative access need the guarantee, while large buffers need full native addressing. |
| ANY excludes bank zero; BANK0 and UPPER are explicit native classes | Resource policy required to conserve stack/DP capacity for eight tasks and eventual 12–16. This is stricter than choosing any suitable classic region. |
| Amiga hardware-specific requirements are unsupported, rather than aliases | Target requirement: the Atari map and adapters cannot promise Amiga custom-chip, reset or Zorro DMA properties. |
| System MemHeaders live outside their managed spans in upper RAM | Placement choice justified by scarce bank zero and whole-bank allocations. Classic AddMemList consumes the start of the added region for its header; private Allocate already accepts a separate header. |
| Private Deallocate does not add storage outside its declared region | Initial scope: maintain checked region bounds and require explicit setup for additional storage. Classic pointer/size rounding and private subrange returns remain supported. |
| System FreeMem requires the original pointer and requested size | Deliberately excludes partial system-block frees, which classic Exec discourages. Keeps system ownership and validation predictable; private Deallocate retains documented subrange frees. |
| TypeOfMem covers registered allocator regions, not all platform RAM | Initial scope: image/OS reservations are managed separately and are not advertised as heap regions. It is not a general platform memory-map query. |
| Explicit zero-size, invalid-flag and conflicting-query rules | Defined Exec816 edge cases for deterministic failure; do not depend on undocumented behavior of particular ROM versions. |
| Fixed registered heap banks, with no automatic return to the bank manager | Target integration policy: a byte heap and whole-bank loader must not claim the same physical RAM. Ordinary and LINEAR share one owner and free-space model. |
| No expunge callbacks, REVERSE, AllocAbs, public AddMemList or memory pools initially | Staging, not hardware limitations. Add familiar APIs when lifecycle, ownership and synchronization are specified and tested. |
| AllocEntry/FreeEntry and tc_MemEntry reclamation are deferred | Staging plus a required decision about pointer/error encoding and safe stack reclamation. No implicit change to raw allocation lifetime. |
| No AmigaDOS process error side effect yet | DOS Process state is not implemented. Preserve the pointer result; add DOS-specific error translation with DOS. |

The out-of-region header distinction is documented by classic
[AddMemList](https://developer.amigaos3.net/autodocs/exec.library/AddMemList.html).
Eight-byte granularity, MemHeader priority, singly linked free chunks, null
allocation failure, explicit free-by-size, optional vector prefixes and shared
allocation lifetime are retained choices, not target deviations.

## Migration and acceptance

The old `EXECALLOC.Alloc/Free`, CLEAR=1/LINEAR=2 flags, per-live-block headers,
separate linear-bank owner and raw `$0F/$10` probe layouts are not this API.
Do not reinterpret those imports or their flags silently. Follow the current
[implementation plan](../plans/memory-allocation-implementation-plan.md) to replace the
prototype definitions and probes. Add the qualified services to the **single
current Task kernel** and generate selectors, flags and layouts from
machine-readable ABI definitions.
Keep `COP #$50` and the existing native calling convention; assign service
selectors and update the reported ABI tag when their emitted call shapes are
qualified. Rebuild callers and update tests together. Do not keep a second
heap/Task profile or compatibility dispatch for the old proposal. Its `$0201`
metadata is historical prototype state, not a version to preserve. Retain
historical qualification records as evidence for the revisions they measured.

The implementation plan separates these executable slices, with a validated
commit after each:

1. Generate and qualify the API, flags, MemHeader/MemChunk layouts and vector
   prefix using the pinned compiler, in raw and optimized code.
2. Implement private free-list allocation/deallocation against an independent
   interval model: exact fit, splitting, two-sided coalescing and corruption.
3. Register upper-RAM regions with the bank manager, including bootstrap
   rollback and shutdown ownership.
4. Implement shared ordinary/linear system policy, explicit free and queries.
5. Enable the public services, vector allocation and preemptible clearing
   through the current gateway/native wrappers.
6. Qualify shared lifetime, interrupt races, four-task serial timing under
   allocator load and integration regressions.

Bank-zero range allocation and dynamic Task storage follow separately, enforcing
the eight-task reservation and qualified stack/DP requirements. Eight-task
concurrent serial timing remains deferred.

Acceptance includes zero and odd sizes, eight-byte rounding, 65,528/65,536/
65,537-byte boundaries, values above 24 bits, arithmetic overflow, a last-bank
endpoint of `$01000000`, free-list fragments on both sides of a bank boundary,
mixed ordinary/linear allocations, reusable linear tails, vector overhead,
unsupported flags and metadata corruption. Queries must agree with the
independent model without double-counting bank inventory and heap capacity.
Check failed allocation rollback, CLEAR publication, cross-task ownership,
creator removal, register/stack/domain preservation and bounded completion.
Cover concurrent allocation/free while another task clears a multi-bank block,
IRQ signal posting during split/coalesce, NMI entry during metadata updates,
preserved Forbid/I state and the final bank of the native address space. Use
synthetic maps for boundary cases beyond the pinned machine's installed RAM;
do not advertise that RAM as physically available. Preserve OS reservations
through successful shutdown, initialization rollback and controlled faults.
The eventual SIO/DOS profile must exercise concurrent allocation and I/O with
at least eight live tasks; tests using the default four-task configuration do not
establish that system capacity or its interrupt-latency budget.

Report full fixed and per-task bank-zero costs, including guards and reserved
slack. Metadata goes in upper RAM unless a measured requirement says otherwise.
The implemented allocator adds **zero bank-zero reservation bytes**, fixed or
per task, during loading and runtime. Qualification records include complete
before/after budgets. The implementation record separates observed TX refill
latency, IRQ masking and worker-resumption delay; it does not establish a global
latency bound or the future driver's RX/turnaround budget.
