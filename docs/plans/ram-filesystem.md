# RAM filesystem implementation

Add a volatile `RAM:` volume for temporary files, redirection and scripts.
Reuse the ordinary DOS interface, file leases and the single filesystem worker.
The mount is explicit in build configuration and enabled in demo builds. It
does not open a device or depend on SIO availability.

Keep existing case-insensitive 8.3 names, sixteen-directory depth, seek bounds,
same-directory rename and enumeration invalidation. Allocate nodes and file
storage from upper RAM. Limit the namespace to 256 live nodes, with monotonically
assigned identities. Grow each file's contiguous buffer geometrically from
256 bytes; allocate the replacement before releasing the old buffer. Copy and
commit at most 4 KiB per read/write worker step. Do not clear unused file storage.
Allocation failure preserves existing contents and leaves the volume usable.
Contents disappear on unmount, filesystem-service shutdown or reboot.

1. **R1 — backend and ownership.** Add a generated format ID, explicit RAM mount
   descriptor, metadata/file operations and write dispatch. Allow eight physical
   disks plus RAM. Test public DOS behavior on a RAM-only machine, including
   cross-bank binary data, exhaustion, leases, enumeration and restart cleanup.
2. **R2 — command integration and documentation.** Enable RAM in shell/demo
   configuration, display it in startup diagnostics, update the user story and
   current filesystem contract. Exercise actual loaded commands, redirection,
   append and EXECUTE against RAM and disk. Record development evidence and costs.

Commit each executable slice. Reserved bank-zero delta is zero fixed and zero
per Task; no new Task, stack, signal protocol or public DOS ABI is needed.
Measure emitted code, rounded upper allocations and invocation-stack usage.
Run host checks and focused optimized emitted-code tests, not release matrices.
