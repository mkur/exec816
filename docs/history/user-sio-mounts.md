# User mounted SIO filesystems development

[History index](README.md#filesystems-and-dos) ·
[Design](user-sio-mounts-design.md) ·
[Implementation plan](../plans/user-sio-mounts-implementation-plan.md) ·
[Compact evidence](../development/user-sio-mounts.json)

Status: UM0–UM5 implemented at the development tier. Public DOS operations and resident shell forms are available.

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

## UM3 named public operations

DOS, COMMAND and C export MountVolume/UnmountVolume together with the eight-byte
SioMountSpec. The worker copies caller input, reserves a stable slot/name/unit,
checks ASSIGN collisions and commits definition/publication in one protected
interval. ASSIGN publication checks pending names again. Failure and early BREAK
retire only private candidate state; late BREAK cannot undo a committed mount or
detachment. Mount pointers are published/withdrawn under Task exclusion.

Idle user unmount frees the definition slot. Saved boot definitions remain
reserved while detached, and name-only remount preserves their geometry/access.
Failed replacement leaves them unchanged; successful replacement converts the
slot to a user definition. SYS selection remains immutable. Live references
prevent unmount; IDE/RAM management stays internal. An SIO-disabled build returns
error 209 without disk resources.

Upper service storage is 516 bytes (520 allocated), 48 more than UM2. The C entry
table grows by six upper bytes. New provider names increase the manifest to
1,700 bytes, requiring a 1,728-byte reservation (+64) and moving the 160-byte
pointer-input state by 64 within existing arena slack. No bank-zero reservation
changes: fixed 0, per Task 0, private idle 0, including alignment/guards.

Development checks include raw/optimized native signatures and cross-bank record
layout; raw/optimized C and loaded COMMAND calls through the real shared worker;
27 public lifecycle assertions, invalid-argument/table-full checks, saved boot
replacement, first-writer/rollback and empty-service recovery. Final workflow
cases use the intended GENERIC57600 default. FASTEST125 discovery and stock
fallback have separate UM2 coverage; these development checks do not qualify
all transfer timing across arbitrary image layouts or physical peripherals.

## UM4 resident commands and retained diagnostics

MOUNT accepts mandatory FORMAT for new definitions, DRIVE or Dn inference,
PROFILE and explicit READWRITE; UNMOUNT accepts a name. Duplicate/unknown
options, missing values, disagreement with Dn and removed geometry arguments
fail before dispatch. Name-only remount and observational MOUNT/DIAGNOSTICS
remain distinct forms. Both new commands run through the resident dispatcher,
redirection and EXECUTE, without external command loading.

Successful mounting prints name, drive, selected filesystem, effective access,
geometry, fixed profile and geometry source. Diagnostics display retained
READ/STATUS/PERCOM/admission phases, precise geometry rejection reasons and raw
responses, without probing. PERCOM bytes split into six-byte rows for the
standard console. Private inspection records grow from 42 to 52 bytes; nine
rows use 468 of the existing 512-byte shell transfer area. No shell allocation
or bank-zero reservation increases; fixed/per-Task/private-idle deltas are zero.

Development checks: 469 host cases, 31 optimized emitted report cases with exact
Write counts and 21 parser cases, plus a real standard-console workflow (31
assertions) covering busy current directory, detach/redefine, redirection,
observational diagnostics and an EXECUTE script. Disk admission leaves media
unchanged; resource baselines and stack/domain/ownership guards pass. No demo
or release qualification was run for this slice.

## UM5 integration and completion

Management operations now register for ordinary foreground cancellation, using
machine-readable private packet opcodes. The worker claims the foreground
operation in the same protected interval as dequeue, so cancellation cannot
mistake an active control packet for one still queued. Caller-context admission
precedes management startup. Allocation stages use separate early-return checks:
Action! logical expressions do not provide a safe sequencing boundary for
resource acquisition. Injected mount/block allocation failures verify cleanup.

The final integration batch records 619 native assertions over 25 native cases,
plus an optimized C/loaded-COMMAND bridge replay. Earlier slices additionally
cover raw/optimized signatures, record layouts and both bridges. Coverage:

- BREAK before READ, STATUS, PERCOM and publication, during wire activity, and
  before/after unmount detachment; late publication/detachment returns success.
- Mount and block allocation failures; short replies, timeout and device errors,
  clean unsupported PERCOM fallback, invalid size/capacity and stale density.
- Independently audited MyDOS/SpartaDOS writes on 128/256-byte media, directory
  creation, busy references, close, unmount and fresh remount/readback.
- Actual 256-byte disk replacements on both formats after cache/binding retirement.
- Two management callers joining one empty worker; pending-name ASSIGN exclusion,
  duplicate-drive rejection and control-reference collection.
- The real standard-console workflow rerun with cancellable control packets,
  including redirection, diagnostics and EXECUTE.

All successful final cases verify stack/domain/ownership guards, bounded
completion and final memory baselines. Read-only cases verify unchanged media;
write cases reconstruct allocation ownership and stored payloads independently.
Host checks remain 469; generated bindings and current documentation links pass.
New public profile constants match the machine-readable SIO IDs. Memory remains
594 fixed upper registry bytes, 516/520 service record/allocation bytes, 96 per
mount, and 468/512 shell inspection bytes. UM5 changes bank-zero reservations by
fixed 0, per Task 0 and private idle 0. No new Task pool, buffer or kernel gateway
operation was introduced.

Scope remains development validation under pinned AltirraOS/SIO configurations.
Additional FASTEST125 file-read trials in larger emitted layouts exposed
transport timeout/checksum and reset-recovery failures; the final workflow uses
GENERIC57600, matching the shell default. FASTEST125 discovery had passed the
UM2 probes, but broader transfer-timing qualification remains a separate follow-up.
No baud fallback/retry workaround was added. Stock-XF551 ambiguity, physical
peripheral qualification, forced unmount, filesystem checking/repair, image-backed
BIOS ATR devices and runtime IDE/RAM mount creation remain outside this feature.
No demo refresh or release matrix was run.
