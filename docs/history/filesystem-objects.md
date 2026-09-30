# Separate file handles and locks

> Historical record: applies to the revisions and profiles described below.
> See the [current documentation](../architecture/filesystems.md) and [history index](README.md).

File handles now allocate a small wrapper and shared read/seek backing. Locks
allocate their metadata, ancestry, enumeration ticket and canonical name in one
record. The common prefix contains only DOS ownership, mount identity and mount
generation. Public DOS calls and opaque handle identities are unchanged.

`FSFILES` owns file allocation and backing references. `FSLOCKS` owns lock and
name allocation. `FSOBJECTS.Free` dispatches storage teardown by kind; callers
still release mount references. Ownership, kind, backend and generation are
checked before exposing a payload. An unpublished object has its kind set before
any failure can reach cleanup.

Inherited file wrappers retain the same backing and position. Inherited locks
copy metadata, ancestry and the name, then receive a fresh enumeration ticket.
Only locks consume tickets. Independent opens retain independent backing.
Failed allocation, reference retention or ticket assignment unwinds the resources
already acquired. Both parent/child close orders remain supported.

`FSBTYPES.LockState` contains an `Entry`, 17 ancestors and depth. Active file and
measurement cursors retain their position and backend traversal storage. Relative
path validators accept `LockState` directly and preserve their parent, cycle and
overlap checks. Enumeration progress stays in the caller's FIB cookie. The name
trailer starts after `SIZEOF(FSTYPES.LockObject)` everywhere.

## Memory and code cost

Against the length-cleanup baseline `7a2e1fa`, the pinned compiler emits:

| Record or allocation | Before | After |
| --- | ---: | ---: |
| Common prefix, active bytes | Within combined object | 16 |
| File wrapper, active bytes | 134 | 20 |
| File wrapper, rounded heap bytes | 136 | 24 |
| Independent file, wrapper + backing heap bytes | 248 | 136 |
| Lock record before name trailer, active bytes | 134 | 98 |
| Lock metadata/ancestry, active bytes | Within 110-byte cursor | 78 |
| Shared file backing, active and heap bytes | 112 | 112 |

Each file wrapper saves **112 heap bytes**, including inherited wrappers. An
independent file still uses two allocations; an inherited wrapper uses one and
shares the existing backing. A lock still uses one allocation, with its name
length, bytes and terminator following the record. Eight-byte heap rounding gives:

| Canonical name length | Lock heap bytes before | After | Saved |
| --- | ---: | ---: | ---: |
| 0 | 144 | 104 | 40 |
| 3 (`D1:`) | 144 | 104 | 40 |
| 12 | 152 | 120 | 32 |
| 23 | 160 | 128 | 32 |
| 255 | 392 | 360 | 32 |

Resident/library Action! routines in the optimized mixed-volume fixture grow
from **312,372 to 313,310 bytes: +938 bytes (0.30%)**. This includes `FSOBJECTS`
and excludes the fixture module. The increase is accounted for: separate clones
add 599 bytes, file allocation 150, handler setup 358, teardown dispatch 279 and
registry validation 75; smaller lock helpers and directory/packet code offset
531 bytes, while relative lookup adds 8. This change reduces live object storage;
it does not reduce resident code size.

The compiler pin, binary, ABI, guards, mount geometry and platform inputs match
the baseline. The complete generated memory map is identical. Reserved bank-zero
delta is **0 fixed bytes and 0 bytes per Task**, including guards, alignment and
unused capacity. Fixed upper-memory reservations, workers and signals are also
unchanged.

In the matching mixed-volume run, the largest observed Task stack use stays at
291 bytes; kernel stack use is 260 bytes versus 270 before. No interrupt reserve
was touched. These touched-byte observations are lower bounds, not worst-case
stack proofs.

## Development validation

Both code slices passed the 236-test host suite. O1 also passed optimized name
and allocation checks, raw object routing/layout, inheritance failure injection
and open/lock cancellation. The allocation checks fail each of the lock, file
wrapper and file backing allocations; inheritance checks include saturated
references, ticket exhaustion and both close orders.

Final-source validation covers nine builds and 17 native scenarios:

- Raw lock layouts/names, including empty and maximum names, source and output
  bank boundaries, wrong-kind handles and trailer guards: 58 assertions.
- Raw inheritance, current-directory snapshots, shared positions and rollback:
  395 assertions.
- Optimized relative lookup, maximum depth and corrupt ancestry: 82, 14 and
  10 assertions.
- Optimized mixed MyDOS/SpartaDOS public DOS operations: 124 assertions.
- Optimized MyDOS metadata, independent enumeration and stale cookies:
  1,532 assertions.
- Five cancellation checkpoints on each backend: file/lock allocation,
  file/lock publication and FIB publication.

Native guards, bounded completion, ownership cleanup and the fixtures' OS
restoration checks pass. Two stale fixture assumptions were corrected: an initial
bank-crossing test placement overlapped platform assembly, and the directory
fixture still expected the older 524-byte Service record instead of 454 bytes.
Production memory reservations were not changed.

The [development record](../development/filesystem-objects.json) includes source,
image and result hashes, allocation costs, module deltas and stack observations.
Artifacts are under `build/development/fs-objects/`. The
[implementation plan](../plans/filesystem-objects-implementation-plan.md) is complete.
Full release matrices, physical hardware qualification and a refreshed demo
remain separate work.
