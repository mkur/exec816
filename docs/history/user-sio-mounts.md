# User mounted SIO filesystems development

[History index](README.md#filesystems-and-dos) ·
[Design](../plans/user-sio-mounts-design.md) ·
[Implementation plan](../plans/user-sio-mounts-implementation-plan.md) ·
[Compact evidence](../development/user-sio-mounts.json)

Status: UM0–UM2 implemented at the development tier; UM3–UM5 pending. Public user
mount commands are not available yet.

## UM0 registry and saved definitions

The upper DOS registry owns nine stable definition slots and defined, boot and
enabled masks. Disabled volumes remain detached across worker restart. Empty
slots are skipped during startup, lookup and inspection, while SYS keeps its
boot-selected slot. Unmount leaves boot definitions saved; remount reenables
them. Failure identity and geometry are copied before mount cleanup, independent
of a later slot's contents.

The registry reservation grows from 114 to 576 bytes: 414 bytes for nine 46-byte
specs, eight for masks/control state and 40 for copied failure identity. This
kernel-owned reservation lasts until the kernel image retires, avoiding heap
allocations that need separate teardown when workers stop. Bank-zero reservation
changes are fixed 0, per Task 0 and private idle 0, including padding and guards.

Development checks: 469 host cases; 28 optimized emitted volume-query/lifecycle
assertions on RAM; 17 optimized emitted SIO/MyDOS registry and remount
assertions with unchanged media; seven optimized native IDE mount diagnostics (valid media,
wrong count, protection, missing slot, wrong filesystem header, absent controller
and absent disk). Ownership/stack/domain guards and independent unchanged-media
checks passed. These checks do not qualify new physical-device compatibility.

## UM1 empty control service and lazy resources

Explicit management can start an empty service after a failed boot mount set or
with no configured disks. It waits for the previous worker's actual retirement,
disables the failed boot set and preserves the copied failure report. Each
startup call attempts startup once; joining a failed ordinary startup returns
failure rather than silently retrying that set inside the same call.

A RAM-only or empty service creates no disk adapter, parser extension or mutation
workspace. The first physical mount acquires shared disk resources; the first
writable disk acquires mutation state. Failed admission frees only resources
newly acquired for that candidate, leaving RAM and existing mounts usable.
Definitions and the shared Task pools are unchanged. The service gains a byte
for resource-acquisition tracking in its upper-RAM heap record. Fixed, per-Task
and private-idle bank-zero reservation deltas are all zero.

Development checks: 469 host cases and optimized emitted empty startup (11
assertions), first disk/writer allocation (10), failed admission rollback (7),
registry/remount (17), and failed-boot retirement/recovery (10). Final cases
reuse one checked emitted build with explicit boot-descriptor stimuli; the runner
rejects stale production inputs. Guard, ownership and unchanged-media checks
passed. The recovery case found and verifies the bounded startup-attempt fix.

## UM2 bounded disk discovery

New SIO definitions issue READ sector 1 (128 bytes), STATUS (four bytes) and
PERCOM GET (12 bytes) on one opened binding through the existing queued,
cancellable transfer boundary. The retained boot sector feeds SpartaDOS
admission directly; MyDOS reads its VTOC afterwards. RAM and known boot geometry
skip discovery. Only a clean PERCOM NAK permits the conventional 720/1,040-sector
STATUS fallback; malformed or contradictory reports and transport failures
remain failures. No admission command writes to disk.

The upper registry reserves 594 bytes, 18 more than UM0/UM1, for copied raw
STATUS/PERCOM observations and their source/reason. Emitted upper-heap records
are 468 bytes for the service and 96 for each mount; the heap rounds the service
to 472 bytes. Discovery reuses the existing transfer buffer and request, with
no additional sector buffer, Task or bank-zero reservation. Fixed, per-Task and
private-idle bank-zero deltas are all zero.

Development checks: 469 host cases, 15 optimized emitted decoder assertions,
and nine assertions each for real MyDOS, SpartaDOS and stock-810 PERCOM fallback.
The pinned observer verifies READ → STATUS → PERCOM wire order, one subsequent
MyDOS VTOC read, no second SpartaDOS boot-sector read and no writes. Focused
registry, failed boot recovery and lazy-resource rollback remain covered.
Stack/domain guards, final ownership and unchanged media are checked by the
runner. These cases do not establish stock-XF551 or physical-drive compatibility.

A fastest-profile file-read failure exposed missing pinned disk timing settings
in the new runner. Applying the pin's actual configuration fixes the regression;
the final discovery and read/remount cases use those settings. The unchanged
UM1 emission was also replayed as an isolation check; no driver code changed.
