# DOS simplification

Status: D1–D4 completed in separate commits. See the
[implementation and measurements](../history/dos-simplification-implementation.md). Validation
uses focused native development checks, following [the testing policy](../contributing/testing.md).

## Baseline and scope

The standard optimized shell image from Exec816 `2bca1c8`, compiler `5f62c9fd`,
contains 68,835 bytes of DOS Action! routines including DOS-specific Task policy.
That excludes filesystem modules, Process management and the executable loader.
The whole image contains 480,792 Action! routine bytes and 493,778 loaded-segment
bytes. Preserve the existing compiler pin and public DOS/command ABI.

Keep handle ownership, exact reply collection, partial-transfer/BREAK behavior,
inherited references, startup rollback and removal guards. No generic dispatch
framework, additional worker or allocation is needed. Target zero change in
fixed and per-Task bank-zero reservations, counting guards and unused capacity.

## Executable slices

### D1 — Close only according to the real device contract

Remove the always-successful RAW CloseDevice wrapper and its impossible device
error rollback. Preserve rejection while an endpoint is active and keep CLOSING
published until resources are released. Cooked close can use the result directly
instead of searching the object list after freeing the wrapper. Replace tests
that invent a failing procedure with real busy-close/retained-ownership coverage;
keep pauses at actual close/free boundaries. Run focused stream lifetime checks.
That fixture must also preserve first-opener exit with another shared handle
alive. An independent PA_IGNORE endpoint cannot retain its first caller; ordinary
Task-owned console opens retain their existing removal guard.

### D2 — Reuse resolved context and remove simple private gateway calls

Pass the caller's already resolved DOS slot through context admission, object
lookup and packet delivery. Update all internal callers and fixture hooks together;
do not add a second context representation or a compatibility path. Resolve a
console unit and relative base directory once per open/lock. Preserve error
precedence and the distinction between configured names and published mounts.

Use the existing TASKMEMORY writable-range helper for RAW bank-zero validation,
and generated storage bindings for the fixed registry address. Remove their
private Control selectors. Preserve the public DOS context service and current
filesystem worker admission. Check packet/reentrancy and relative-name behavior.

### D3 — Reuse native copies

Replace the inheritance copy helper and cooked-line drain loop with A816MEMORY.
Copy pipe data in contiguous spans bounded by the ring end, the existing 64-byte
quantum and the remaining transfer. Keep ring metadata and copies under the same
Forbid, with unchanged wakeups and partial-transfer semantics. Check patterned
ring wrap/odd lengths, blocked readers/writers, cancellation, inheritance and
cooked input in raw/optimized emitted code where affected.

### D4 — Remove an unnecessary command forwarding hop

Dispatch command providers directly to the shared DOS implementation. Keep the
checked opaque-handle entries: typed DOS pointers have different native signature
hashes even where the physical layout matches. Keep adapters that transform data
or combine operations. Preserve symbol names, signatures, provider extents and
stack checks; rebuild disk commands. Validate generated contracts and the loaded
HELLO/CAT/WC pipeline on the standard image.

## Completion

Commit each executable slice with its development results and bank-zero delta.
Run the host checks once after the related edits, then build and smoke-test the
standard play image. Publish the final whole-image and DOS size comparison,
including shared code and bindings. Reuse unchanged binaries where practical;
the full media/placement/release matrix remains separate.

Filesystem worker admission/removal migration is a separate lifecycle project.
Moving its routines out of Task policy alone is not a size reduction. Also retain
configured-name screening before lazy mount startup: rejecting an unknown name
must not start disk I/O simply to avoid a second registry lookup.
