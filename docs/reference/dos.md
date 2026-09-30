# DOS files, directories and errors

[Reference index](README.md) · [Filesystem architecture](../architecture/filesystems.md)

`DOS` provides file handles, locks, standard streams and per-Task error state.
These are native pointers, not Amiga BPTRs. Names are NUL-terminated byte strings;
I/O remains counted binary data. Exact signatures and constants come from
[dos.act](../../lib/dos/dos.act) and [dos.json](../../abi/dos.json).

## Files and directories

| Call | Contract |
| --- | --- |
| `Open(name, mode)` | Open an existing disk file with an independent cursor at zero; return a handle or `NULL`. Device names have their own mode rules. |
| `Read(file, buffer, length)` | Return a byte count, zero at EOF, or -1 on failure. |
| `Write(file, buffer, length)` | Write to a supported stream; mounted filesystems reject nonempty writes. |
| `Seek(file, offset, origin)` | Return the **old** position or -1. A failed seek preserves the original position. |
| `Close(file)` | Release the owned handle; return DOS true or false. |
| `Lock(name, mode)` / `UnLock(lock)` | Acquire/release a shared file or directory reference. UnLock(NULL) is harmless. |
| `Examine(lock, info)` | Return object metadata and initialize directory enumeration. |
| `ExNext(lock, info)` | Return the next entry; false with ERROR_NO_MORE_ENTRIES ends enumeration. |
| `CurrentDir(lock)` | Select an owned directory lock and return the previous selection; the returned lock is not automatically unlocked. |
| `NameFromLock(lock, buffer, length)` | Copy the canonical absolute path into caller-owned storage. |

Sizes, positions, modes and primary results use `LONGINT`. Boolean results are
`DOSFALSE=0` and `DOSTRUE=-1`. Use named constants rather than numeric arguments.
`MODE_OLDFILE` opens an existing disk file. `MODE_NEWFILE` and `MODE_READWRITE`
retain their usual meanings but are rejected by the read-only disk handlers.

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

Both [MyDOS](mydos.md) and [SpartaDOS](spartados.md) are read-only. Mounts are
explicitly configured; geometry is validated when binding the mount, not
rediscovered on each ordinary request. Keep media unchanged while mounted.
There is no automatic disk-change detection, filesystem repair or writable RAM:
filesystem.

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
