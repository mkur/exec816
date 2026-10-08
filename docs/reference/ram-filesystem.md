# RAM filesystem

`RAM:` is a volatile filesystem using ordinary DOS files and directory locks.
The shell/demo configurations enable it. Custom builds opt in with
`{"alias": "RAM", "format": 3}` in their mount list. The generated
[filesystem IDs](../../abi/filesystems.json) define the format value. A RAM
descriptor has no drive, geometry or SIO profile; access is always read-write.
Eight physical disks and one RAM volume can be configured together.

RAM supports Open, Read, Write, Seek, Flush, Close, Lock, Examine, ExNext,
CreateDir, DeleteFile and same-directory Rename. Existing commands, redirection,
append, pipes and EXECUTE use these interfaces unchanged. Names follow the
current case-insensitive 8.3 rules, with at most sixteen directory levels.
Seeking past EOF and cross-directory rename remain unsupported.

Storage grows on demand from upper RAM, without a fixed disk image or a new
Task. File buffers start at 256 bytes and double when necessary; growth briefly
requires both the old and replacement buffers. Only written bytes are readable:
unused payload storage is not cleared. The maximum individual file size is
8 MiB, subject to available contiguous memory. The namespace permits 256 live
nodes including the root. Deleted identities are not reused during the mount;
after 65,534 creations, remount to obtain fresh identities.

An allocation failure reports `ERROR_NO_FREE_STORE`; namespace exhaustion
reports `ERROR_DISK_FULL`. A Write can return a committed prefix with an error.
Existing contents and the mount remain usable. Read and Write commit at most
4 KiB of payload per worker step; buffer growth copies the existing contents
before the next payload commit. Writer leases, ancestry protection and
enumeration invalidation follow the [DOS contract](dos.md).

Flush succeeds because completed writes already reside in RAM. Delete and
truncate release payload storage. Unmount, filesystem-service shutdown and
reboot discard all contents; unmount still rejects live files or locks.
RAM operations require no SIO and survive a later SIO bus failure. Initial
startup retains the existing rule that all configured mounts must succeed
before any are published; a RAM-only configuration needs no attached disk.

For implementation costs and selected native checks, see the
[development record](../history/ram-filesystem.md).
