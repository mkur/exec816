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
implementation writes through and retains no dirty sectors. Flush preserves
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
prefix. A unit consists of one payload sector and its required allocation,
link/map and length updates. BREAK before its first write changes nothing;
after submission, completion is collected and the unit finishes before BREAK
is honored. A final completed unit returns success even if BREAK has arrived.

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

A failed or uncertain mutation invalidates the mount and cached metadata.
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

Formatting, repair, write-back caching, atomic replacement, cross-directory
moves, recursive deletion, sparse creation, seek past EOF, SetFileSize,
SetProtection and SetFileDate remain unsupported. MODE_NEWFILE truncates during
Open, so a later command failure does not restore old redirected output.
