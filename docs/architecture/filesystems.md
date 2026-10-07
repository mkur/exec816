# Filesystems and disk I/O

**Exec816 uses one shared filesystem Task for all mounted filesystems and open
disk files.**

- **Filesystem Task:** `dos.filesystem` handles requests for both MyDOS and
  SpartaDOS mounts.
- **Each mount:** has its own request port and volume state.
- **Each independent file open:** allocates a handle and cursor/backing state,
  with no Task, stack or direct page of its own.
- **Disk transport:** runs through the separate SIO worker.

The filesystem service is part of the resident system, executing in its worker
Task's context. It uses the kernel for scheduling, allocation, messages and
device I/O. See the [runtime model](runtime.md) for that distinction.

## Who owns what?

| Scope | State and responsibility |
| --- | --- |
| One filesystem service | Worker, mount table, management port, shared parsing/operation workspace, block adapter, transfer buffer and sector cache. |
| One mount | Effective name and geometry, filesystem-specific volume state, block volume/device-open request, request port and generation. |
| One calling Task | DOS error slot and a lazily allocated client context with a reusable packet, reply port and owned-object list. |
| One independent open file | Owned handle wrapper and reference-counted backing containing its cursor, position and length state. |
| One lock | Metadata, ancestry, canonical name and enumeration identity; no file backing. |
| SIO service | Serial request queue, active transaction, bus state and hardware completion. |

Mount ports all signal the same filesystem Task. The shared workspace is used
by the active operation; it is not duplicated for every open file. Mount state
and file cursors retain the information needed between operations.

Independent opens have independent positions. Process inheritance creates a new
owned handle wrapper sharing the parent's backing and position. Closing either
wrapper releases one reference; the last writer close finalizes its native entry
before freeing the backing. Locks instead
carry their own metadata and name. See [file and lock storage](../history/filesystem-objects.md).

## Following a disk Read

```mermaid
sequenceDiagram
    participant A as Application Task
    participant F as Filesystem Task
    participant S as SIO worker
    participant H as Native IRQ / disk
    A->>F: DOS packet to the mount's port
    Note over A: Wait for this packet's reply
    F->>F: Validate handle; use its cursor
    F->>F: Ask backend for sector; check shared cache
    alt Sector cache miss
        F->>S: Submit device request
        Note over F: Wait for I/O; pump cancellation
        S->>H: Start serial transaction
        H-->>S: Transfer completion
        S-->>F: I/O reply
    end
    F->>F: Copy bytes; update cursor; repeat as needed
    F-->>A: Packet reply with result and error
```

1. Caller-side DOS code resolves the handle and prepares the Task's reusable
   packet. It sends the packet to that file's mount port and waits for its reply.
2. The filesystem worker checks ownership and mount identity, selects the
   MyDOS or SpartaDOS backend, and uses the file's retained cursor.
3. The backend interprets disk structures and requests sectors through the
   block adapter. A cache hit needs no SIO request.
4. A miss uses the adapter's shared transfer request. The SIO worker owns the
   bus transaction; native IRQ code handles byte timing. Completion lets the
   filesystem worker continue parsing or copying.
5. The worker updates file state and replies. DOS collects the exact packet and
   exposes the operation's result and Task-local `IoErr()` to the caller.

Buffers and requests remain owned until completion, including on BREAK. A
cancellation request is cooperative: queued work can be removed, active work
stops at supported checkpoints, and outstanding I/O must be collected before
its storage can be reused.

## Concurrency and its limits

Applications, console work and computation can run while a disk caller waits.
The filesystem service itself processes **one active operation at a time**,
across all mounts. It selects among mount and management queues between
operations. A long Read can therefore delay a request to another volume.

The worker's bounded steps allow cancellation and lifecycle checks. They do not
give each queued file operation its own execution context or make the worker
start a second ordinary Read while the first is waiting for disk. The shared
workspace and single transfer request rely on that serialization.

The SIO worker is independently scheduled and serializes the physical bus.
Adding mounts or open files therefore increases state and queued work, rather
than adding filesystem workers or serial buses.

Console and pipe operations take other paths. Caller-side DOS stream adapters
use the console worker or pipe buffer directly. A shell waiting for a key does
not hold the filesystem worker, and a pipe has no filesystem mount or worker.

## Mounting, stopping and media identity

Mount descriptors are supplied with the image: names, SIO units, geometry,
profiles, filesystem formats and access policy. The first disk operation starts the shared
service if necessary. An empty mount configuration creates no filesystem Task.

Startup validates the complete descriptor set, allocates shared and per-mount
resources, opens devices and recognizes volumes. It publishes the initial set
only after every mount succeeds. Failure retires the partial service. Later
mount/unmount operations use the management port; a failed remount cleans up
its own unpublished resources while other mounted volumes remain usable.

Open files and locks retain their mount. An unmount with live references is
rejected. Successful remount gives the volume a fresh generation so old
identities cannot silently refer to replacement state. Explicit service stop
requires ownership to be settled; the resident service also participates in
shutdown after the last ordinary application Task exits.

`SYS:` is an alias for the explicitly selected system mount. It shares that
mount's port, generation, cache and references. It is not another mount or Task,
and does not mean the drive from which the kernel XEX was loaded. See
[system-volume selection](../reference/sys-volume.md).

Both filesystems support opt-in write access. Keep media unchanged externally while mounted;
there is no automatic disk-change detection. Unmount/remount establishes a new
volume identity. An uncertain transport failure can mark the bus and affected
mounts offline rather than continuing to return cached bytes.

## The cache belongs to the service

The sector cache is shared by both backends, every mount and all open files.
The default is **64 KiB of sector payload**, with additional tag/replacement
storage. It resides in upper RAM and needs no Task of its own.

Closing a file or exiting a command preserves retained sectors while the
service remains alive. Detaching a volume invalidates its entries; stopping
the service releases the cache. Offline bus handling invalidates retained data
as well. Capacity is configurable at build time or through OF816 before boot;
allocation failure falls back to the existing scratch-sector buffer.

A warm cache avoids serial reads, but the loader still validates and relocates
commands, and the filesystem still performs ordinary CPU work. Cached sectors
are not a cache of running Processes or loaded executable images. See the
[cache contract and measurements](sector-cache.md).

## Mutations

A writable service allocates one shared upper-RAM workspace: three 256-byte
sector buffers, one private 256-byte bitmap, one 23-byte record, ten sector
reservations and bounded scalar/cursor-snapshot state. Mounts without write
access need no mutation workspace. Each mount keeps
a list of live and detached inherited wrappers for writer exclusion. No per-file
sector buffer, additional Task, direct page or bank-zero reservation is added.

MyDOS writes publish bounded payload groups. SDFS retains private bitmap, free
count and current map changes across the four-sector work groups of one Write,
then publishes their dependencies before reply or dirty-buffer replacement.
BREAK stops additional payload groups and drains accepted staged data. There is
no cross-request dirty queue or general write-back sector cache. See the
[implementation and measurements](../history/spartados-write-buffering.md).
The iterative helper frames remain
live while BLOCKWIRE waits for SIO; the measured worker stack budget includes
that depth. This keeps the mutation ordering explicit without an additional
continuation state for every dependent metadata write. Reads retain their
existing resumable callbacks. Every transport wait pumps control messages; no
Forbid or interrupt mask spans I/O. Stop drains retained handles and packets.

The block layer invalidates a target before submitting verified WRITE and caches
replacement bytes only after confirmed completion. An uncertain mutation makes
the mount unvalidated; retirement remains available. Mounting performs bounded
header checks, with no ownership scan or resident fsck. The full
[write contract](../reference/filesystem-writes.md) documents consistency
assumptions, cancellation, native incomplete entries and recovery limits.

## Source map

| Responsibility | Start here |
| --- | --- |
| Public DOS calls and caller packets | [DOSCALLS](../../lib/dos/doscalls.act), [DOSCLIENT](../../lib/dos/dosclient.act) |
| Service startup and partial teardown | [FSBOOT](../../lib/fs/fsboot.act), [FSINIT](../../lib/fs/fsinit.act) |
| Worker, queue selection and operation dispatch | [FSWORKER](../../lib/fs/fsworker.act), [FSMUX](../../lib/fs/fsmux.act), [FSHANDLER](../../lib/fs/fshandler.act) |
| Records, files and locks | [FSTYPES](../../lib/fs/fstypes.act), [FSFILES](../../lib/fs/fsfiles.act), [FSLOCKS](../../lib/fs/fslocks.act) |
| Backend selection and on-disk formats | [FSBACKEND](../../lib/fs/fsbackend.act), [MyDOS](../../lib/mydos/), [SpartaDOS](../../lib/spartados/) |
| Sector fetching, caching and transport | [FSIO](../../lib/fs/fsio.act), [BLOCKIO](../../lib/io/blockio.act), [BLOCKCACHE](../../lib/io/blockcache.act), [BLOCKWIRE](../../lib/io/blockwire.act), [SIODRIVER](../../lib/io/siodriver.act) |

The [FSINIT simplification record](../history/fsinit-simplification.md) explains the current
startup flow and its validation. The [progress vocabulary](filesystem-progress.md)
describes the results used between worker steps and backends.
