# DOS files, directories and errors

[Reference index](README.md) · [Filesystem architecture](../architecture/filesystems.md)

`DOS` provides file handles, locks, standard streams and per-Task error state.
These are native pointers, not Amiga BPTRs. Names are NUL-terminated byte strings;
I/O remains counted binary data. Exact signatures and constants come from
[dos.act](../../lib/dos/dos.act) and [dos.json](../../abi/dos.json).

## Files and directories

| Call | Contract |
| --- | --- |
| `Open(name, mode)` | Open a disk file in the selected mode with an independent cursor at zero; return a handle or `NULL`. Device names have their own mode rules. |
| `Read(file, buffer, length)` | Return a byte count, zero at EOF, or -1 on failure. |
| `Write(file, buffer, length)` | Write bytes; disk writers overwrite/extend and return a confirmed prefix or -1. |
| `Seek(file, offset, origin)` | Return the **old** position or -1. A failed seek preserves the original position. |
| `Close(file)` | Finalize the last writer and consume the owned handle, including on a terminal disk error. |
| `Flush(file)` | Settle confirmed output without closing or changing position. |
| `CreateDir(path)` | Create one directory and return an owned shared lock. |
| `DeleteFile(path)` | Delete a file or empty directory. |
| `Rename(old, new)` | Rename within the same parent without replacement. |
| `Lock(name, mode)` / `UnLock(lock)` | Acquire/release a shared file or directory reference. UnLock(NULL) is harmless. |
| `Examine(lock, info)` | Return object metadata and initialize directory enumeration. |
| `ExNext(lock, info)` | Return the next entry; false with ERROR_NO_MORE_ENTRIES ends enumeration. |
| `CurrentDir(lock)` | Select an owned directory lock and return the previous selection; the returned lock is not automatically unlocked. |
| `NameFromLock(lock, buffer, length)` | Copy the canonical absolute path into caller-owned storage. |

Sizes, positions, modes and primary results use `LONGINT`. Boolean results are
`DOSFALSE=0` and `DOSTRUE=-1`. Use named constants rather than numeric arguments.
`MODE_OLDFILE` opens an existing read-only handle. On writable mounts,
`MODE_READWRITE` preserves or creates a file and `MODE_NEWFILE` creates or
immediately truncates it. See [filesystem writes](filesystem-writes.md) for
writer leases, inherited ownership, cancellation and finalization.

Seek origins are `OFFSET_BEGINNING`, `OFFSET_CURRENT` and `OFFSET_END`. Positions
must stay between zero and exact EOF; overflow and extension past EOF fail.
Negative transfer lengths or invalid buffer ranges fail. Zero-length transfers
do not wait or consume input.

## Paths and mounts

Paths support physical mount names such as `D1:`, the selected `SYS:` alias and
current-directory resolution. Components use `/`, not host separators. The
[shell guide](../guides/shell.md) describes relative paths and parent/root forms;
[SYS:](sys-volume.md) describes stable system paths. Paths are bounded and are
never silently truncated.

Both [MyDOS](mydos.md) and [SpartaDOS](spartados.md) support explicitly
[writable mounts](filesystem-writes.md); read-only remains the default. Geometry
and bounded header checks run at mount, without a filesystem scan. Keep media
unchanged externally while mounted. There is no automatic disk-change detection,
filesystem repair or RAM: filesystem.

## Errors and partial transfers

`IoErr()` reads the caller's secondary DOS result; `SetIoErr(error)` replaces it
and returns the previous value. Error storage exists independently of the lazy
DOS context. Save a causal error before cleanup calls that may replace it.

For an ordinary disk-read transport or filesystem error, the call returns -1
and retains the starting logical position. Earlier copying may have changed the
buffer, so discard that call's contents. Normal EOF may return a short count.
Foreground cancellation has a separate contract: a committed prefix can be
returned with ERROR_BREAK. Console and pipe transfers can also return a positive
prefix with a secondary error. A short count alone must not be treated as proof
of EOF across all handle types.

See [foreground cancellation](foreground-break.md), [console/NIL streams](streams.md)
and [pipes](pipes.md) for their precise behavior. Close preserves the prior error
on success and clears any standard-stream selection referring to that handle.

## Fault text

DOS and COMMAND publish shared English error formatting in DOS ABI revision 5
and program ABI version 9. Message definitions come from the DOS and program ABI
JSON files; one generated resident table covers all defined DOS/loader errors.

| Call | Contract |
| --- | --- |
| `Fault(code, header, buffer, capacity)` | Return the formatted payload length excluding NUL, or -1 for invalid storage/header or insufficient capacity. |
| `PrintFault(handle, code, header, buffer, capacity)` | Completely write the formatted message plus LF to the explicit borrowed handle; return DOSTRUE or DOSFALSE. |

Known errors format as `HEAD: Object not found (205)`. Null/empty header omits
the prefix. Unknown signed codes format as `Error code n`, optionally prefixed.
Code zero produces an empty string and PrintFault writes nothing. Fault adds no
newline. Neither service opens, selects or closes streams, allocates memory, or
uses mutable global scratch.

Both preserve entry IoErr on success and failure. Their return value reports
diagnostic failure; it must not replace the operation's original cause. To retain
a write error itself, call Fault followed by ordinary WriteAll. This adapts the
Amiga fault services to explicit stream/scratch ownership and preserved IoErr;
the signatures and error-state behavior are not Amiga-compatible.

Header text is bounded to 255 bytes and descriptions to 80. The generated
`FAULT_BUFFER_BYTES=384` covers a maximal message, signed number, LF and NUL.
Capacity includes the terminator; PrintFault also needs room for LF. Storage
must be writable upper RAM satisfying the DOS transfer-range rule, and must not
overlap the readable header. A valid nonempty destination is NUL-terminated on
format failure; there is no truncated successful message. PrintFault can commit
a prefix before a transport failure and makes no recursive diagnostic attempt.

## Task-local state and ownership

Each Task has an error slot and lazily allocated DOS context. That context owns
its handles, locks, current directory and reusable filesystem packet/reply port.
The [shared filesystem worker](../architecture/filesystems.md) serves all these
clients; an open file does not allocate a Task, stack or direct page.

Handles and locks belong to their Task. Do not pass raw handle pointers to another
Task. Process inheritance creates new wrappers referring to shared backing; for
disk files those inherited wrappers share position. Separate Opens have independent
positions. A lock retains metadata and enumeration state, not a file cursor.

`Input()` and `Output()` return current selections without allocating a context
or changing IoErr. `SelectInput(file)` and `SelectOutput(file)` accept an owned
handle or NULL and return the previous selection; they do not close it. A NULL
return can be a successful previous selection, so use IoErr to distinguish failure.
`IsInteractive(file)` identifies interactive streams.

`ReleaseContext()` releases an otherwise empty DOS context; close handles and
unlock remaining locks first. [Process cleanup](process.md) retires inherited and
owned DOS resources before result collection. Ordinary raw Tasks remain responsible
for their own DOS cleanup.

The [block adapter](block-io.md) documents sector-level rules. Earlier packet
layouts, milestones and measurements are retained in the
[historical storage design](../history/block-io-dos-design.md).

## Foreground console access

`OpenConsole()` returns a new caller-owned RAW FileHandle for the active
foreground scope's console. It works independently of redirected Input/Output.
It fails with ERROR_OBJECT_WRONG_TYPE without an active scope and never falls
back to console unit zero. Ordinary busy/suspended DOS context checks apply.
Close the returned handle; opening it adds no Task, stack, direct page or window.

`ConsoleInfo(file, buffer)` writes two CARD values (width, height) to four writable
bytes for an owned interactive handle. It returns DOS true or false with IoErr.
The handle's retained endpoint protects the instance, and the dimensions are
copied under the existing task-switch exclusion. A wrong/stale handle or invalid
buffer fails; no private pointer is returned. Current console geometry is fixed
for the lifetime of an instance.

These operations and IsInteractive are also published through COMMAND for loaded
programs. `COMMAND.ConsoleSize` names the four-byte output layout. A pager should
query its Output geometry and open its foreground console for keys; selected
Input remains the data stream.
