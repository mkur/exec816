# DOS files, directories and errors

[Reference index](README.md) · [Filesystem architecture](../architecture/filesystems.md)

`DOS` provides file handles, locks, standard streams and per-Task error state.
These are native pointers, not Amiga BPTRs. Names are NUL-terminated byte strings;
I/O remains counted binary data. Exact signatures and constants come from
[dos.act](../../lib/dos/dos.act) and [dos.json](../../abi/dos.json).
The current native DOS ABI is revision 10; the loaded COMMAND ABI is version 17.

## Transfer ownership

Read/Write buffers and handles must remain live for the entire call. This
single-user system has no memory protection: correct pointers, available
buffer capacity and valid handles are caller responsibilities. DOS resolves
its owned object and retains the mount once before queuing a file transfer;
the filesystem handler uses that resolved object. It does not repeat ownership
or RAM-map walks. Negative counts, read-only/offline volumes, file-size bounds,
short transfers and physical errors remain operational errors. Mount references,
writer leases, cancellation, exact reply collection and stack/domain guards
still protect state transitions.

## Volume information

`GetVolume(index, info)` copies a published mount identity into a caller-owned
62-byte `VolumeInfo`. Iterate `0..VOLUME_SLOTS-1`; empty slots return DOSFALSE
with IoErr zero and a cleared record. Enumeration does not start the filesystem
service or perform I/O. Records contain terminated names, format/transport IDs,
unit, sector bytes and effective access/state, with no internal pointers.

`Info(lock, info)` uses an owned filesystem lock to request statistics through
the normal worker packet. Failed queries leave the caller's record unchanged.
`VOLUME_BLOCKS_VALID` and `VOLUME_RAM_VALID` distinguish available measurements
from unknown values; GetVolume clears both.

MyDOS reads VTOC sector 360; SpartaDOS reads header sector 1. The shared cache
serves warm queries without physical reads. Queries perform no disk writes or
directory/bitmap scans. Total blocks are the mounted sector count, including
boot sectors and metadata; free blocks are the recorded allocation count.
Invalid counts return ERROR_DISK_NOT_VALIDATED. Nominal capacity is total blocks
times sectorBytes, rather than the ATR container length. SpartaDOS labels are
trimmed to eight printable bytes; nonprinting bytes become dots. MyDOS has no
label.

RAM leaves total/free blocks unavailable. With VOLUME_RAM_VALID, allocatedBytes
counts its volume state, live node records and allocated file-buffer capacities,
excluding allocator bookkeeping. It does not report file lengths or global free
memory. The worker walks at most sixteen nodes between cancellation checkpoints,
within RAM's existing 256-node limit. Queries retain normal BREAK and transport
errors without publishing partial statistics.

DOS and COMMAND export the same record layout. The C header also publishes the
record and constants; C query-call wrappers are not yet provided.

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
| `Examine(lock, info)` | Return directory metadata for the object and initialize enumeration. |
| `ExNext(lock, info)` | Return the next entry; false with ERROR_NO_MORE_ENTRIES ends enumeration. |
| `ExamineExact(lock, info)` | Measure the selected object's exact byte length and allocated sectors; initialize enumeration. |
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

### Metadata availability

Ordinary Examine/ExNext use directory metadata without measuring the selected
file's payload or sector-map chain. Check `fib_InfoFlags` before interpreting
`fib_Size` or `fib_NumBlocks`:

| Flag | Value | Meaning |
| --- | ---: | --- |
| `FIB_SIZE_EXACT` | 1 | Exact byte length. |
| `FIB_SIZE_BOUND` | 2 | Byte upper bound; it is not EOF. |
| `FIB_BLOCKS_EXACT` | 4 | Exact allocated disk-sector count. |

The size flags are mutually exclusive. An unavailable quantity is -1 with its
flag clear. A valid empty size is zero with `FIB_SIZE_EXACT`. Directory byte
size is zero and exact; allocated sectors describe its storage separately.

| Backend | Ordinary size | Ordinary allocated sectors |
| --- | --- | --- |
| MyDOS file | Directory count × (sector bytes − 3), a bound; an admitted live writer may already supply an exact length | Directory sector count, exact |
| MyDOS directory | 0, exact | 8, exact |
| SpartaDOS file/directory | Stored file length / directory zero, exact | -1, unavailable |
| RAM file/directory | Known file length / directory zero, exact | 0, exact; RAM has no disk sectors |

MyDOS's accepted legacy zero-count/zero-start empty entry has exact size and
sector count zero. An ordinary one-sector file still has a bound. Bounds never
replace the internal exact EOF used by Read, Seek or Write.

`ExamineExact` is an Exec816 extension to the Amiga-shaped DOS API. It uses the
existing bounded measurement path and owned-lock packet rules. To measure one
listed file, lock that file and use a separate FIB. Subsequent ExNext calls
still return ordinary metadata; there is no persistent exact-enumeration mode.
SpartaDOS exact sector counts include occupied data and map sectors, excluding
sparse holes. Exact queries on RAM require no disk I/O.

The FIB remains 260 bytes: `fib_Reserved(30)` begins at 228 and the two-byte
`fib_InfoFlags` begins at 258. The private 22-byte enumeration cookie fits in
the reserved area and remains tied to its lock, FIB, object ticket and mutation
epoch. Rebuild native, COMMAND and C callers together for this ABI change.
Failed or canceled queries preserve the prior FIB, subject to the existing
end-of-enumeration cookie rule. Live-object, mount, lease, initial-reference,
ancestry and directory-read checks remain. Later file-chain corruption may be
discovered by Read, Seek, ExamineExact or mutation preflight after a cheap
listing succeeds. Listing does not certify file integrity.

## Paths and mounts

Paths support physical mount names such as `D1:`, the selected `SYS:` alias,
bounded [ASSIGN logical directories](assigns.md), and
current-directory resolution. Components use `/`, not host separators. The
[shell guide](../guides/shell.md) describes relative paths and parent/root forms;
[SYS:](sys-volume.md) describes stable system paths. Paths are bounded and are
never silently truncated.

Both [MyDOS](mydos.md) and [SpartaDOS](spartados.md) support explicitly
[writable mounts](filesystem-writes.md); read-only remains the default. Geometry
and bounded header checks run at mount, without a filesystem scan. Keep media
unchanged externally while mounted. There is no automatic disk-change detection,
filesystem repair. [RAM:](ram-filesystem.md) supplies volatile files through
the same DOS interface, without disk I/O.

### User SIO mounts

`MountVolume(name, spec)` and `UnmountVolume(name)` return DOSTRUE/DOSFALSE
and set the calling Task's IoErr. Native DOS, loaded COMMAND and C export both
operations. Names are case-insensitive, 1–31 legal bytes, without a colon.
Keep caller name/spec storage live until the synchronous call returns.

`SioMountSpec` is eight bytes: four CARD fields, drive at offset 0, format at
2, profile at 4 and access at 6. Drive is 1–8. Format is `MOUNT_MYDOS` or
`MOUNT_SPARTA`; access is `MOUNT_READONLY` or `MOUNT_READWRITE`. Profiles are
Exec's STOCK810, FASTEST125 and GENERIC57600 constants. Geometry is not an input.
Read-only acquisition discovers READ-sector-1 → STATUS → PERCOM geometry and
runs only the selected format's bounded admission. Only clean unsupported
PERCOM permits conventional 720/1,040 × 128 STATUS fallback. Double-density
capacity requires usable PERCOM. Stock-XF551 density ambiguity remains
unsupported; no probe negotiates speed or writes the media.

Null spec remounts a detached saved SIO boot definition with its configured
geometry and access. New definitions cannot replace SYS, RAM, streams, active
mounts or ASSIGN names. A Dn name must agree with spec.drive. Active/pending
physical units cannot be mounted twice. The nine slots include boot IDE/RAM
volumes; detached boot definitions retain their slots and names. A failed
replacement preserves the saved boot definition; a successful replacement
becomes a user definition. Successful unmount discards user definitions, while
boot definitions remain saved but disabled. Boot-selected SYS never changes.

Unmount rejects live files, locks/current directories, inherited backings and
accepted operations with ERROR_OBJECT_IN_USE. Idle detachment retires the cache,
binding and mount before reply. Mount publication and unmount detachment each
win over late BREAK; earlier BREAK cleans up an unpublished candidate. These
calls can start an empty control service after failed automatic startup. They
cannot create IDE/RAM mounts or bypass an offline SIO bus. Builds without
sio.device return ERROR_ACTION_NOT_KNOWN. Observational queries never start
workers or probe disks. See the [implementation record](../history/user-sio-mounts.md).

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

DOS and COMMAND publish shared English error formatting since DOS ABI revision 5
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

## Console history

Native DOS ABI revision 6 added `SetConsoleHistory(file, enabled)`; the loaded
COMMAND ABI introduced it in version 10. This returns DOSTRUE and clears IoErr on success,
or DOSFALSE with IoErr on failure. Zero disables history; any nonzero BYTE enables
it. Only a live CON handle owned by the calling Task is accepted. Invalid handles
report ERROR_BAD_STREAM_NAME (206), other backends ERROR_OBJECT_WRONG_TYPE (212),
and active/suspended clients or a busy session ERROR_OBJECT_IN_USE (202).
Allocation failure reports ERROR_NO_FREE_STORE (103), releases the session lease
and leaves history disabled.

The setting applies to the shared cooked session. Disabling retains stored history
and pending input state, but resets browsing. Final session release frees storage.
The [cooked console contract](cooked-console.md#optional-history) defines recording,
browsing and ownership; the shell enables history only at its prompt. This small
Exec816 extension requires no kernel operation or additional Task.

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

OpenConsole requires a console-bound foreground scope. An unbound background
cancellation scope reports ERROR_OBJECT_WRONG_TYPE rather than selecting unit zero.

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
