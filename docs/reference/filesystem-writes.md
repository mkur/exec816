# Writable MyDOS and SpartaDOS mounts

[Reference index](README.md) · [DOS API](dos.md) · [Filesystem architecture](../architecture/filesystems.md)

Mount descriptors accept `"access": "readonly"` (the default) or
`"access": "readwrite"`. Access belongs to the mount, including its SYS: alias.
Both formats support the existing 128/256-byte geometries and transport
profiles; STOCK810 remains limited to 128 bytes. Mount diagnostics report
requested access, effective read-only state and offline state separately.

Mounting reads the format header and checks geometry, metadata extents and
declared ranges. It does **not** scan directories, files, allocation ownership
or free-space totals. Writable admission assumes consistent allocation metadata
and exclusive external ownership of the medium. Keep the disk mounted and do
not modify it from another system while Exec816 owns it.

## Operations and ownership

`MODE_OLDFILE` opens an existing read-only handle. `MODE_READWRITE` preserves an
existing file or creates a missing one; `MODE_NEWFILE` creates or immediately
truncates it. All start at position zero. A writable backing has an exclusive
writer lease: independent readers, writers and locks on that file conflict in
either order with `ERROR_OBJECT_IN_USE`. Inherited handles share the backing,
position, rights and lease. Only their last Close finalizes the native entry.

Write overwrites at the current position, preserves an unwritten suffix and
extends at EOF. Seek still cannot pass EOF; append by seeking to EOF and writing.
Bytes, including ATASCII, are unchanged. A valid zero-length Write returns zero
without I/O. A nonempty Write through a read-only handle returns
`ERROR_WRITE_PROTECTED`; a read-only mount rejects mutation with
`ERROR_DISK_WRITE_PROTECTED`.

`Flush(handle)` succeeds once that handle's confirmed writes are settled. The
implementation settles all required writes before each Write reply; no dirty
metadata survives between requests. SDFS coalesces private metadata within one
Write; it does not make the general sector cache dirty. Flush preserves
position and ownership and leaves a live writer's native incomplete flag set.
Valid read-only disk, NIL, console and pipe handles also succeed without a
filesystem write. Ownership validation still applies.

`CreateDir` creates one directory under an existing parent and returns an owned
shared lock. `DeleteFile` removes a file or empty directory. `Rename` changes a
name within one parent without replacing another object. SYS: and its physical
alias compare by mount identity. Cross-volume rename returns
`ERROR_RENAME_ACROSS_DEVICES`; cross-directory moves are unsupported. New names
are uppercase 8.3. Existing timestamps and unrelated flags are preserved; new
SDFS timestamps use the native unspecified (zero) representation.

Directory locks can coexist with child mutations. They prevent deleting or
renaming that directory; retained descendants also prevent changes to their
ancestor's identity. Root cannot be deleted or renamed. File protection,
collisions, nonempty directories, disk/directory exhaustion and unsupported
structures produce explicit errors before mutation when discovered in preflight.

Completed mutations advance a mount-wide metadata epoch. An older ExNext cookie
returns `ERROR_OBJECT_IN_USE`, including after a change elsewhere on that mount;
restart with Examine. Examine refreshes directory metadata through the retained
lock, including its extent after child creation. The cookie occupies 22 of the
existing 32 reserved FIB bytes. Enumeration sees a live writer's last committed
metadata. An unexplained
native incomplete entry does not grant permission to resume writing it.

## Completion, cancellation and errors

Write returns the confirmed byte count, or -1 when no bytes completed. Short
positive results retain their causal IoErr. Position advances only by this
prefix. MyDOS sequential extension commits at most four new payload sectors
with their VTOC, link and length updates; groups stop at a VTOC page. Existing
sectors, overwrites and SDFS map transitions retain the single-payload path.

SDFS sequential extension writes payloads in groups of up to four sectors while
retaining one private bitmap page, free count and current file map across groups
of the same Write request. Metadata publication follows completed payloads:
bitmap, sector 1 free count, file map, then directory length. Only a complete
publication confirms the staged prefix. It occurs at request end, before dirty
bitmap/map replacement or an immediate write path, and when BREAK or logical
disk exhaustion stops further payloads. The native incomplete flag stays set
until terminal Close. No additional zero-fill write precedes a new file payload.

BREAK before a group's first payload submission leaves its unused reservations
free. Once submitted, that group finishes before BREAK stops further payloads;
SDFS then drains all accepted staged data before replying. Control messages
continue to be pumped during I/O. If all requested bytes are accepted and drained,
a late BREAK permits full success. Logical exhaustion or BREAK after a successful
drain leaves the mount usable and reports the confirmed prefix with its causal
IoErr. A failed SDFS publication can cover more than four payload sectors: only
an earlier confirmed prefix is returned, and the cursor is restored to its
confirmed position. A physical error takes precedence over pending BREAK.

Create, truncate, delete and rename finish their operation once mutation starts.
Reclaiming a large file therefore delays cancellation for a volume-bounded walk.
Close also drains finalization with BREAK pending. No scheduler exclusion or
interrupt mask spans disk I/O. Stop rejects new admission and keeps servicing
retained objects until their ownership and outstanding packets retire.

Close consumes a handle after its terminal reply, including when finalization
fails. Success preserves entry IoErr; failure returns false with the causal
error. Never retry using that handle. Process and shell cleanup continue after
terminal close errors; they turn an otherwise successful command into FAIL and
preserve an earlier command failure. Unresolved ownership remains an invariant
failure, distinct from an ordinary disk error.

A physical mutation failure or uncertain completion invalidates the mount and
cached metadata. Detected metadata inconsistency after mutation starts does too.
Ordinary operations then fail; Close and UnLock can still retire ownership.
Additional physical bytes may have changed beyond a returned prefix: no rollback
is promised. Before explicitly mounting writable again, restore a known-good
image or check/repair it externally. A lightweight remount does not establish
recovery. There is no resident fsck or repair code.

The host-only [allocation audit](../../tools/filesystem_audit.py) reconstructs
whole-volume ownership for development. Runtime validation examines touched
metadata and the selected chain/map; it cannot prove that unrelated files are
not cross-linked or that a falsely free sector has no owner. Neither format is
journaled. Power loss, torn sectors and uncertain multi-sector completion can
leave incomplete entries, lost allocation or inconsistent counts. Verified SIO
WRITE completion does not establish power-loss durability.

The earlier [write-performance development record](../history/write-performance.md)
includes a repeatable Generic 57600 timeout when a 16 KiB COPY writes to
accurately timed 256-byte MyDOS media. The verified write transmits its payload
but exceeds the existing one-second transport deadline, leaving the bus offline
and requiring reset. This occurs with the frozen filesystem too. Fast-media
binary checks and that record's bundled 128-byte WORK disk pass; they do not qualify that
accurate 256-byte timing case. This slice leaves transport deadlines unchanged.
The current SDFS demo uses 720 KiB WORK media with 256-byte sectors; its buffered
Write checks and emulator measurements are recorded in the
[SpartaDOS buffering record](../history/spartados-write-buffering.md).

## Format limits

MyDOS uses 125/253-byte payloads. New files have sixteen-bit links and one
canonical empty sector. Existing ten-bit links retain their directory ordinal
and cannot allocate above sector 1023. An empty directory needs eight contiguous
sectors; aggregate free space alone is insufficient. Truncate/delete validate
the selected chain before detaching and reclaiming it.

SDFS allocates map pages as well as data. Empty files retain one empty map;
directories grow as mapped files and preserve record zero's authoritative
length. Writers reject sparse files, while existing sparse reads remain
supported. Lengths remain limited to 24 bits and actual disk capacity.

Formatting, repair, cross-request write-back caching, atomic replacement, cross-directory
moves, recursive deletion, sparse creation, seek past EOF, SetFileSize,
SetProtection and SetFileDate remain unsupported. MODE_NEWFILE truncates during
Open, so a later command failure does not restore old redirected output.
