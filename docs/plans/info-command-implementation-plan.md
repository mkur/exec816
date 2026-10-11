# INFO command implementation plan

Status: planned; implementation has not started. Follow the
[roadmap](../roadmap.md), [testing policy](../contributing/testing.md) and
[platform budget](../reference/platform.md#bank-zero-memory-budget).

## Outcome and scope

Add a small loadable `C:INFO`, inspired by AmigaDOS INFO. It reports mounted
volumes, filesystem labels, capacity, used/free space, sector size, backing
device/unit and effective read/write status. This complements the resident
`MOUNT` command, which lists mount identities and state.

Use existing allocation metadata, not directory traversal, bitmap counting or
fsck. Do not probe additional drives or call IDE Plus BIOS. Disk repair,
formatting and label changes remain separate operations. RAM is a dynamic volume,
not a fixed disk or a reservation of all free system memory.

## Command behavior

The ReadArgs template is `VOLUME`, with one optional volume or existing path:

```text
INFO
INFO SYS:
INFO WORK:
INFO C:
INFO .
```

With no argument, show each published filesystem mount once, in mount-slot
order, including RAM and offline mounts. Do not list assigns as extra volumes.
With an argument, use normal DOS Lock/assign/relative-path resolution and report
the containing volume. `INFO C:` therefore reports SYS when C: points to SYS:C.
An unknown name or missing path produces the normal DOS fault.

Use the same compact layout on the standard and VBXE consoles. For example,
with illustrative counts:

```text
SYS: (SYS)
  Size 720K Used 184K Free 536K RO
  SpartaDOS 512B ideplus.device/1
WORK: (WORK)
  Size 720K Used 8K Free 712K RW
  SpartaDOS 512B ideplus.device/2
```

K means KiB; displayed values are rounded down. Keep ordinary lines within
40 columns. Print a long label/identity on a separate line when necessary.
MyDOS has no filesystem label, so omit the parenthesized label rather than
invent one from its mount name. For RAM, show `Size dynamic`, measured used
memory, `Free -`, and `RAM, volatile`; sector size and device/unit do not apply.

Offline or unreadable rows show their status and DOS fault, with unavailable
counts represented by `-`. All-volume output continues to other mounts. An
offline row returns WARN with IoErr zero; a failed statistics query returns
ERROR and preserves the first causal error; ERROR takes precedence over WARN.
A named query failure returns
ERROR. BREAK stops promptly with ERROR_BREAK. No mounts is an empty successful
result with an explanatory line.

## I1: public volume queries

Introduce one copied `VolumeInfo` record in [abi/dos.json](../../abi/dos.json),
with bounded mount-name and label strings, filesystem and transport identifiers,
unit, effective access/state, sector bytes, total/free block counts and allocated
RAM bytes. Explicit flags distinguish valid block counts and valid RAM usage
from unavailable values. The record contains no internal pointers.

Expose two operations through DOS and the checked COMMAND imports:

- `GetVolume(index, info)` copies the published identity, geometry and status
  of a mount slot without I/O or starting the filesystem service. The generated
  slot bound is nine. An empty slot returns DOSFALSE with IoErr zero; invalid
  arguments return DOSFALSE with a DOS error. Statistics flags remain clear.
- `Info(lock, info)` queries the containing volume through the existing
  filesystem worker and fills the complete record. It accepts a valid owned
  filesystem lock, returns DOSTRUE/DOSFALSE and uses normal IoErr semantics.

Reuse the registry exclusion and reference rules in
[FSINSPECT](../../lib/fs/fsinspect.act) and
[DOSCALLS](../../lib/dos/doscalls.act). Copy only identity/status under Forbid;
perform no I/O or waiting there. Validate the output record before touching it,
retain the queried mount through the packet reply, and publish statistics only
after a successful query. A mount disappearing between enumeration and Lock is
an ordinary query failure, not permission to follow a stale pointer.

Add the volume-information packet action and generated constants. Update ABI
inputs, generators, current bindings and import/provider checks together;
advance the affected ABI versions and rebuild all commands. Do not keep an
older provider profile. Loaded commands must not import private FS modules.
Until I2 supplies statistics, the query dispatch returns
ERROR_ACTION_NOT_KNOWN explicitly; I1 still builds and exercises its ABI,
enumeration, argument and lifetime checks.

Acceptance: focused emitted-code checks cover record bounds, sparse slots,
owned/stale locks, assign resolution, shutdown/unmount lifetime and IoErr.
Check raw and optimized builds for the new caller-facing operations.

## I2: filesystem statistics

Implement a read-only handler using the existing block cache and resumable
worker I/O. Queries serialize with writes, so they observe completed metadata
updates without flushing or interfering with an active write batch.

| Filesystem | Statistics source | Work required |
| --- | --- | --- |
| MyDOS | VTOC sector 360; free count at bytes 3–4 | One metadata-sector read |
| SpartaDOS | Header sector 1; total/free at bytes 11–14, eight-byte label at 22–29 | One metadata-sector read |
| RAM | Resident volume state and live nodes | At most 256 nodes, in bounded worker steps |

For disks, total blocks are the mounted sector count, excluding sector zero;
used blocks are total minus the recorded free count. Reserved boot sectors,
filesystem metadata and file allocations therefore count as used. Capacity
in bytes is the nominal logical sector count times data-sector size; it is not
the ATR file length or an IDE drive's unpartitioned capacity. In particular,
the MyDOS VTOC's allocatable-total field must not be confused with the mounted
volume's full size. Reuse its existing header consistency checks.

Validate counts before subtraction and use LONGCARD arithmetic before byte
conversion. Invalid metadata returns ERROR_DISK_NOT_VALIDATED without repair.
Copy and terminate the SpartaDOS label, trim padding and replace nonprinting
bytes for display. The statistics handler reads no bitmap or directory sectors;
normal path resolution for a named query remains separate work.

For RAM, sum the volume state, live node records and file-buffer capacities.
This reports memory owned by RAM, including unused file-buffer capacity,
excluding allocator bookkeeping. It is not the sum of file lengths. Leave
total/free block counts unavailable; do not report Exec's global free heap as
RAM free space. Walk a bounded number of nodes per worker checkpoint, checking
BREAK. Add no persistent counters to file write/delete paths.

Acceptance: real emitted filesystem queries match independent fixture metadata
for supported MyDOS 128/256-byte and SpartaDOS 128/256/512-byte geometries.
Exercise allocation, overwrite, deletion and directory creation; RAM growth,
truncate/delete; malformed counts; BREAK; and injected transport failure.
Verify zero disk writes, at most one cold metadata read per statistics query, and
zero physical reads when that header is already cached.

## I3: loadable INFO

Add `examples/commands/info.act`, using ReadArgs/help, selected Output,
WriteAll, standard fault reporting and existing decimal helpers. Enumerate
one slot at a time with a single result record. For online mounts, Lock the
published root name, call Info, then release the lock before printing. The
named form follows the same path with the supplied argument. Preserve errors
across cleanup and stop on output failure or BREAK.

Build each output line in a small caller-owned buffer and write once per line.
Do not print character by character or add a new formatting library. Apply the
[style guide](../contributing/style.md) to new and changed Action! routines.

Acceptance: emitted command checks cover no-argument and named forms, assigns,
relative paths, long/empty labels, offline and mixed-success listings, help,
redirection, short/output failures and cancellation. Verify cleanup and both
raw/optimized command bodies, then one focused real loaded-command session.

## I4: demo integration and documentation

Include C:INFO in normal and IDE-only demo command sets. Give demo SpartaDOS
SYS and WORK volumes distinct on-disk labels, `SYS` and `WORK`; these are
separate from mount aliases and APT partition names. Add an optional label
argument to the independent producer, preserving its existing default for
unrelated fixtures. Pass labels explicitly from the demo builders.

Update [DOS reference](../reference/dos.md),
[toolbox guide](../guides/toolbox.md) and the source of the packaged story.txt.
Document RAM accounting, nominal disk capacity, rounding and failure behavior.
Record completed slices and evidence in docs/history and update the plan index.

Acceptance: host checks verify generated bindings, command packaging and
independent label read-back. Refresh through tools/build_demo.py with OF816 and
the existing five-second autoboot; verify matching command imports and
cartridge fit. Exercise one pinned standard-console and one VBXE session,
covering an IDE-only 512-byte volume and a SIO volume across those sessions.
These are development checks, not a full release qualification matrix.

## Memory and execution rules

Implement and commit I1–I4 as small executable slices. Keep the existing
filesystem worker, cache and mount/object ownership; no new Task, sector cache,
per-file buffer or kernel gateway service is needed. The two queries are public
DOS services built on existing packet primitives.

Target zero additional reserved bank-zero bytes, fixed, per Task and idle,
including guards, alignment and unused reserved capacity. Put the record,
formatting buffer and any resumable query state in upper RAM. Measure resident
code, loaded INFO size, scratch storage and worker/command stack bounds after
each slice. If an existing reservation would need enlargement, record the
actual cost and justification before proceeding. Use the pinned compiler;
compiler defects belong in actionc with focused regressions.

Preparing this plan requires only content and local-link checks. System builds
and the focused behavior checks above belong to implementation.
