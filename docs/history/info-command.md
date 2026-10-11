# INFO implementation record

[Implementation plan](../plans/info-command-implementation-plan.md) ·
[Current DOS contract](../reference/dos.md)

## I1 public queries

DOS ABI 8 and COMMAND ABI 15 introduce GetVolume and Info with a copied
62-byte VolumeInfo. Enumeration follows the published registry under Forbid,
starts no service and borrows no mount pointer. Info retains the existing owned
lock/mount through the ordinary packet reply; its statistics action is explicitly
unsupported until I2. C record declarations and layout probes follow the same
machine-readable input.

Development checks: the host suite, generated definition checks, raw/optimized
emitted ABI probes and the focused RAM mount enumeration/lifetime fixture.
Builds and detailed results are under build/info; this does not qualify a release.
The host suite passes 444 checks and the public-query fixture passes 21
assertions, including empty slots before startup, unmount refusal with a live
lock, stale-lock rejection, stopped-service enumeration and complete heap
retirement. The ABI probes include guarded fields across a native bank boundary.

The complete provider manifest is 1,586 bytes within its unchanged 1,664-byte
reservation. No persistent query storage, new Task or sector buffer is added.
Reserved bank-zero deltas are zero fixed, zero per Task and zero idle, including
guards, alignment and spare capacity. Record and ABI probe storage are upper RAM.
