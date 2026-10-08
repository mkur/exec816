# Process API

The DOS-owned Process sits above the existing Exec Task ABI. A Process runs a
registered resident `LONGINT FUNC()` or a retained loaded Image in a child Task. It uses
an existing stack/DP slot and does not allocate a new bank-zero execution domain.
The separate [program loader](program-loading.md) owns file validation,
placement and relocation.
The machine-readable contract is [abi/process.json](../../abi/process.json).

Use the `PROCESS` module:

| Call | Contract |
| --- | --- |
| `Start(entry, arguments, length)` | Copy 0–255 argument text bytes (length excludes NUL), append NUL, inherit Input/Output/current directory and start the command. Return a nonzero `LONGCARD` identity, or zero with `DOS.IoErr()` set. A null argument pointer is valid only for length zero. |
| `StartForeground(entry, arguments, length)` | As `Start`, also loan the caller's active foreground console binding to the child. The caller's DOS context is suspended until collection. |
| `StartLoaded(image, arguments, length, foreground)` | Start a validated Image through the resident dispatcher; retain it through kernel retirement and collection. A nonzero foreground byte requests the same console loan. |
| `StartBackground(entry, arguments, length)` | As Start with a private cancellation scope; no parent suspension or keyboard loan. |
| `StartBackgroundLoaded(image, arguments, length)` | The loaded-image form of StartBackground; retain execution ownership until collection. |
| `RequestBreak(identity)` | Request cooperative cancellation of an owned scoped child. Return one on acceptance or zero with IoErr. |
| `RequestStop(identity)` | Request native BREAK or, for an owned C/GEM child, cooperative `WM_CLOSED`. No forced removal. |
| `CompletionMask(identity)` | Borrow an owned child's completion signal until collection; zero with IoErr for an invalid identity. |
| `Wait(identity, @result)` | Wait for kernel-acknowledged retirement, collect the two `LONGINT` results, and release the completion record. Return -1 on success, zero on error. |
| `Collect(identity, @result)` | Collect an already retired child without waiting. Return -1 on success, zero on error. |
| `GetArgStr()` | Borrow this child's argument text as a read-only `CSTRING`. Empty arguments return a non-null empty string; outside a Process return `CSTRING(0)`. |

Argument payloads containing NUL are rejected with `ERROR_BAD_NUMBER` before
launch or foreground handoff; any temporary argument storage and Image retention
are released. `Start` keeps its explicit input length so copying remains bounded.
The Process retains that length privately for freeing storage. `GetArgStr()`
preserves `IoErr()`, performs no allocation or copy, and borrows text until the
Process retires. Use `STR.strlen()` (with `USE CSTRING AS STR`) when the caller
needs a length.

Only the starting Task can wait or collect. Collection succeeds once. Identities
are monotonically assigned for the boot session and never wrap; stale identities
cannot name a reused slot. Errors are 103 (capacity/storage/signal exhaustion),
115 (invalid arguments or unregistered entry), 202 (not yet collectable/admission
refused), and 305 (unknown, stale or foreign identity). A failed start publishes
no child identity and releases every acquired resource. Failed child setup skips
the command and returns primary 20 and the setup error through normal retirement
and collection. Foreground start requires an existing active CON binding; missing
or unsuitable bindings report 212, and busy contexts/bindings report 202.

Commands return a signed `LONGINT` primary status. `PROCESS.RETURN_OK`,
`RETURN_ERROR` and `RETURN_FAIL` name the conventional values 0, 10 and 20.
Every normal exit must return a value. Before entering the command, successful
setup clears its Task-local `IoErr()`. The resident `Run` trampoline saves the
returned primary and snapshots `IoErr()` immediately, including on success;
finalization cannot overwrite those saved results. `DOS.SetIoErr(error)` sets
that error slot and returns its previous value, without allocating a context.

Process callbacks are admitted through a separate exact-signature function list
in the existing upper-RAM DOS descriptor (one count byte and up to 36 three-byte
addresses). Task entry/finalizer admission remains procedure-only. Process
record keeps its 128-byte stride in Process ABI v7; its former four-byte tail
stores cancellation flags and a three-byte published scope pointer.

Commands return normally through a resident finalizer. Each child starts with an
independent DOS context and reply port. Its inherited handles and directory lock
are distinct objects owned by that context. A parent without a DOS context gives
the child empty selections.
Arguments and stack locals belong to each instance; resident module globals are
still shared between calls of that command.
The finalizer clears selections, closes every file/stream and unlocks every lock
in the child's DOS ownership list, then releases the context, request and port.
Commands must collect their own children before returning. Failed teardown retains
ownership and takes the existing system fault path; it cannot acknowledge removal.
Arbitrary Exec allocations still require explicit freeing. There is no forced
Process termination or isolation of corrupt commands.

## Inherited resources and foreground input

Inheritance retains detached copies before launch, then adopts them after the
child's context and reply port exist. Every failed preparation or child setup
releases those copies. Input and Output selecting one handle become one child
handle with both selections, so cleanup closes it once. Other parent DOS objects
are not inherited, except the bound console needed for foreground handoff.

File handles share a reference-counted open position; the filesystem worker
serializes Read and Seek. Directory locks copy their immutable cursor and cached
canonical name and retain the mount without resolving the path again. RAW shares
its console endpoint, CON shares both that endpoint and its cooked line/EOF state,
and NIL retains its null-stream behavior. Changing a child's selection or current
directory cannot change the parent's. Either side can close first.

A shared cooked session permits one Read at a time, including draining buffered
bytes. Another reader receives error 202. A nonfinal handle may close while another
Task reads; the last close refuses a busy endpoint/session and preserves ownership.
The filesystem worker never waits for console input. Each Task retains its own
IoErr, reply port and reusable transfer request.

`StartForeground` allocates the child's break signal and scope before transferring
the console binding. It retires queued physical input and publishes a fresh route,
while preserving cooked buffered bytes. A break already delivered to the parent's
scope follows the child; input still tagged with the retired route is discarded.
The parent can use Process Wait/Collect, Exec services and the Input/Output/IoErr
queries while suspended. DOS transfers, changing selections, another start and
releasing its context fail with 202. This prevents a concurrent prompt Read.
The child cannot end or replace its
loaned foreground scope through the public DOS API.

On return, synchronous DOS calls have already collected their exact I/O or packet
reply, including cooperative cancellation. Cleanup restores the parent's binding
with a fresh route after that collection. Stale captured breaks cannot cancel the
restored parent. Collection then lifts the parent's DOS suspension. A retained busy
operation or failed restoration keeps the Process in quiescing and faults; there
is no forced reclamation of an active request. Arbitrary Exec I/O and heap objects
are outside the DOS ledger and must be settled explicitly by the command.

The shell's state-changing built-ins remain local. Exact-path disk commands use
`PROGRAMFILE.Load`, `StartLoaded` with foreground ownership, and `Wait` before
reading the next prompt. A resident foreground caller uses `StartForeground`
followed by `Wait`.

## Background cancellation

Background starts retain the ordinary Input, Output and directory snapshots,
but allocate an independent DOS scope and signal after child adoption. They do
not bind that scope to a keyboard route or suspend the parent. Stream policy
belongs to the caller: the shell selects NIL by default and rejects interactive
background redirection. A background child can use BreakPending and normal
interruptible DOS I/O without sharing its parent's BREAK.

RequestBreak validates the identity through the existing kernel Process lookup.
Only the starting Task may request cancellation. Background children, foreground
loans and pipeline followers have scopes; plain Start without a scope reports
212. An early request is latched before adoption and delivered when the scope
is published. Repeated requests coalesce. Once quiescing is committed, acceptance
does not alter the saved result; stale and foreign identities report 305.

Task-side Forbid covers identity lookup, flags, scope publication and signaling.
IRQ/NMI handlers never follow the published pointer. Cleanup clears it before
freeing the scope. Background scope lifetime cannot be ended or replaced through
DOS Begin/EndForeground. It lasts until ordinary child finalization; there is no
forced termination or additional kernel job registry.

## Two-member foreground groups

The resident `PIPELINE.Run` coordinator accepts two loaded Images and their
separate argument tails. The caller keeps both Image references until it returns.
It retains both Process results. The first ERROR/FAIL in command order determines
the combined result, otherwise the first nonzero result is used. A left ERROR
with ERROR_BROKEN_PIPE is excluded from aggregation when the right returns OK or
WARN with zero secondary error: a successful consumer may intentionally finish
early. Other errors remain visible. See [shell results](../guides/shell.md#pipes).

`DOSGROUP.Begin` renews the parent's console route and retains an already delivered
BREAK. `PROCESS.PrepareLoaded(image,args,length,group)` leases a Task slot, retains
the Image, copies arguments and snapshots owned streams without launching a Task.
Both children must be prepared before `DOSGROUP.Seal` suspends parent DOS activity.
`StartPrepared(identity)` then launches each child; `DiscardPrepared(identity)`
releases a child that has not launched. These operations are for this bounded
resident coordinator, not general shell job control or loaded-command imports.
Process ABI version 7 keeps the 128-byte row and these group operations.

The coordinator restores its selections and closes both parent pipe wrappers
before sealing. Each child adopts its own DOS context and break signal, while
one parent console route fans cancellation out to both. A child that joins after
BREAK inherits the durable pending state. Child scope allocation can still fail
after launch; normal failed-setup retirement closes its inherited streams.

Each prepared child holds a group reference through final collection, including
failed setup and early exit. Ending the group or replacing its parent scope is
rejected while any reference remains. A partial launch cancels and collects all
launched members and discards unlaunched preparations. Only then does group End
renew the parent route, clear the notification and lift DOS suspension. Parent
Wait/Collect and Exec services remain available while suspended. Cleanup faults
retain ownership and use the existing fail-stop policy.

Neither an extra worker nor a new bank-zero reservation is required. The group
fields add eight upper-heap bytes to each foreground scope (48 to 56); the Process
row consumes three previously reserved upper bytes. An unrelated background
Process has no membership and does not receive the group's BREAK.

## Admission and retirement

The kernel reserves a slot in its guarded activation before argument allocation
or signal allocation. Every ordinary Task and service admission observes this
lease. The Process table's embedded Task records are registered writable extents,
but ordinary `AddTask` cannot claim them. The command, trampoline and finalizer
must be registered native zero-argument entries; immutable boot bindings identify
the trampoline, finalizer and loaded-image dispatcher. Public Task layout and
entry ABI are unchanged.

The states are preparing → running → quiescing → retired → collecting → free.
Preparation failures return directly to free. After DOS cleanup, the finalizer
requests self-removal. On the kernel stack, removal clears
the Task/context binding before publishing retired and signaling the parent.
The child can no longer execute when `Wait` or `Collect` releases its resources.
The slot remains leased until collection, even though the Task has already gone.
Removal of a managed child through any other path, or removal of a parent that
still owns preparation/live/completion records, is rejected by the Task fault
policy. Completion bits are private to the parent and must not be freed manually.

Lease/state publication uses the existing switching guard; IRQ/NMI paths do not
access the Process table. Argument/result writes belong to one Task at a time.
The completion signal handles both waiting before completion and checking after
completion without losing a wakeup. This is cooperative shared memory, not a
security boundary against arbitrary writes.

## Memory

Reserved bank-zero change: **0 fixed bytes, 0 bytes per Task**, including guards,
alignment and unused capacity. The existing stack and DP pools are reused.

Upper-RAM static storage is 128 bytes per configured slot plus a four-byte
identity counter: 1,028 bytes for eight slots, including the unused root row and
4 reserved bytes in every row. P2 uses 19 previously reserved row bytes; L2 uses
three more for the retained Image pointer. D4 uses three more for the retained
group scope, without changing the stride. Enabling
the console adds 12 bytes of alignment before its existing metadata reservation.
Each row contains the unchanged 62-byte public Task, association, lease and
completion results. The parent additionally owns
`length + 1` argument bytes and one completion signal until collection. A running
child owns the existing 88-byte DOS context and its reply port, plus allocator
overhead. No reaper Task, extra stack or dynamic entry registry is introduced.

P2/P3 add no static reservation to P1. The two context flags consume its existing
padding at offsets 86 and 87; a retired-route flag uses byte 13 of each existing
16-byte console route. Upper heap requests, before allocator rounding:

| Resource | Bytes |
| --- | ---: |
| File handle or directory-lock prefix | 116 (was 112) |
| Shared file-position backing, once per open file | 94 |
| Directory name trailer | name length + 3 |
| NIL/RAW inherited wrapper | 16 |
| CON inherited wrapper | 20 |
| Cooked session, shared by inherited CON handles | 402 (was 400) |
| Foreground child scope | 56, plus one child signal |

The file wrapper still reserves its inline 92-byte cursor for the common lock
layout; files use the separate backing cursor. That reserved capacity is included
in the 116 bytes above. Lock copies include the full name trailer and fresh ticket.
Inheritance allocates one wrapper per distinct selected handle, one current-directory
lock when selected, and at most one extra bound-console wrapper. It does not allocate
another cooked session or file-position backing.
