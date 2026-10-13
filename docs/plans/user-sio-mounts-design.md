# User mounted SIO filesystems

[Plans index](README.md#filesystems-and-dos) · [DOS contract](../reference/dos.md#paths-and-mounts) ·
[Filesystem architecture](../architecture/filesystems.md) ·
[SIO interface](../reference/device-io.md#siodevice)

Status: UM0–UM4 implemented; integration coverage and final documentation (UM5)
are in progress.
[Implementation plan](user-sio-mounts-implementation-plan.md).

Let users attach their own MyDOS and SpartaDOS disks without rebuilding Exec816.
Extend the resident MOUNT command and add resident UNMOUNT. Use named volumes,
automatic disk-geometry discovery, read-only access by default, and the existing
shared filesystem worker. The user selects MyDOS or
SpartaDOS; mounting discovers disk parameters and performs the existing bounded
format checks, with no filesystem scan or repair.

## Commands and supported media

```text
MOUNT
MOUNT DIAGNOSTICS
MOUNT D2: FORMAT MYDOS
MOUNT DATA: DRIVE 3 FORMAT SPARTA READWRITE
MOUNT FLOPPY: DRIVE 4 FORMAT MYDOS PROFILE STOCK810
UNMOUNT DATA:
MOUNT WORK:
```

MOUNT without arguments and MOUNT DIAGNOSTICS retain their observational role.
A new mount supplies FORMAT and discovers disk geometry automatically.
DRIVE is required for a custom name; a name D1: through D8:
supplies its matching drive when DRIVE is omitted. Reject an explicit DRIVE
that disagrees with a Dn name. FORMAT accepts MYDOS or SPARTA, the latter
selecting the existing SDFS backend. Filesystem type is always user-provided,
with no automatic parser selection or fallback. These are mount names, not the
disk's stored volume label or a directory ASSIGN.

New and replacement descriptors require READWRITE for writable access;
omission means read-only. PROFILE defaults to GENERIC57600, matching the
current SIO demos. Users can select STOCK810 or
FASTEST125 by name. These are fixed driver profiles, with no negotiation or
fallback: the attached peripheral must support the chosen profile. STOCK810
admits only 128-byte sectors. The other two admit 128 or 256. A successful mount
prints its effective name, drive, format, geometry, profile and access mode.
It identifies whether geometry came from PERCOM or standard STATUS fallback.
MOUNT DIAGNOSTICS also exposes these fields without reading the disk.
READWRITE does not probe a drive's physical write-protect switch; normal device
write errors still apply.

A name alone, such as MOUNT WORK:, remounts a saved, detached **boot-configured
SIO** descriptor, preserving its configured access, geometry and profile. It
does not reinterpret that explicit boot configuration. A detached non-system
boot descriptor may be replaced by a new descriptor with FORMAT and automatic
geometry discovery under the same name. A successful replacement becomes a user definition, so unmount discards it;
a failed replacement leaves the saved boot definition intact. An active
descriptor is never replaced:
unmount it first.
User-created definitions are discarded on successful unmount, so remounting one
requires its definition again; geometry can be discovered again. This keeps
repeated disk changes from consuming all the definition slots.

SIO drives are D1–D8, mapped internally to wire units $31–$38. Supported media
have 128/256-byte data sectors and three initial 128-byte boot sectors. The
sector count is the count of addressable logical sectors, including those boot
sectors; the existing per-format bounds and header rules still apply. The
common transport limit is 65,535 sectors. The command has no track, side or
ATR-file parameters.

The kernel accesses actual SIO peripherals, including emulator SIO drives.
IDE Plus BIOS ATR slots are not supplied by this driver. Creating IDE, RAM or
image-backed mounts, formatting disks, automatic filesystem detection,
media-change detection and speed probing are outside this first version.
Existing boot-configured IDE and RAM volumes continue to work unchanged.
An IDE-only build without sio.device rejects these new operations explicitly.

## Disk geometry discovery

Discover geometry only while preparing an unpublished mount, after acquiring
its SIO binding and the shared disk workspace. Use the selected SIO profile
throughout; geometry discovery does not negotiate a serial speed. All probes
are read-only, bounded and cancellable, and use current media responses rather
than cached sectors from a previous mount generation.

For each new or replacement definition, use this sequence:

1. Read sector 1 with READ `$52`, requesting its 128-byte boot-sector payload.
   This gives the drive an opportunity to detect the inserted disk's density.
   Retain the sector in the existing shared workspace for filesystem admission;
   do not execute its boot code.
2. Issue STATUS `$53`. Record density bits 7 (enhanced density) and 5 (double
   density), plus relevant capability-specific status information.
3. Try PERCOM GET `$4E`, receiving its 12-byte block. Decode tracks, sectors per
   track, sides-minus-one, recording method and bytes per sector. Multibyte
   values are big-endian. For a conventional floppy layout, calculate logical
   sector count as tracks times sectors per track times (sides-minus-one + 1),
   using checked 32-bit arithmetic before applying the 65,535-sector bound.
4. Cross-check PERCOM's sector size and density against STATUS and the supported
   peripheral behaviour. Some firmware retains a previous PERCOM configuration
   after a disk change. A structurally valid block is not sufficient when the
   reports conflict; matching density also cannot prove track count or sides.
5. If PERCOM is cleanly rejected as unsupported, infer standard Atari geometry
   from STATUS and known drive capabilities. Use a small documented fallback
   table: conventional single density is 720 sectors of 128 bytes; enhanced
   density is 1,040 sectors of 128 bytes. Additional standard double-density
   entries require evidence of the applicable drive's capabilities. Speed
   profiles are timing contracts, not drive-model identification. Unresolved
   capacity, sidedness, contradictory reports or unsupported nonstandard layouts
   reject the mount with a discovery diagnostic.

Then run the user-selected filesystem's existing bounded header admission with
the resolved geometry. SpartaDOS's declared size must agree; MyDOS's VTOC checks
establish allocation-layout consistency, not an exact independent measurement
of physical capacity. No scan of file chains or probing of the last readable
sector is required. Retain effective geometry and its source with the mount.

A clean unsupported-command response permits fallback. A malformed PERCOM
response, checksum/framing failure, cancellation or uncertain timeout is a
mount failure, preserving the transport error and existing bus recovery policy.
Filesystem mismatch does not select the other filesystem. Discovery does not
issue PERCOM SET or otherwise reconfigure the drive.

Automatic discovery has a stock-XF551 limitation: reading sector 1 can select
enhanced density even for a double-density disk. A sector-4 read can resolve
that distinction, but its reply can be 128 or 256 bytes and the current SIO
transport requires an exact length. This ambiguity remains unsupported until a
safe bounded probe is implemented; matching STATUS/PERCOM after the sector-1
read alone does not establish full XF551 compatibility. Drive firmware may
also assume sidedness rather than detect it.
See the [Altirra hardware reference, disk density detection and XF551 firmware
behaviour](https://www.virtualdub.org/downloads/Altirra%20Hardware%20Reference%20Manual.pdf).

## Names and system volume

Use the existing case-insensitive, 1–31-byte mount-name rules. Reject stream
names, a new SYS: or RAM: definition, active mount names, and ASSIGN-name
collisions. A matching detached boot name selects its existing slot rather than
creating a second definition. Boot definitions keep their names reserved while
detached. A user
mount's name becomes available again after it is removed. Check duplicate
physical SIO units against active or attaching mounts, even if their names or
access modes differ; a disk cannot have two filesystem views simultaneously.
Detached definitions do not own a device binding.

SYS remains attached to its boot-selected slot and effective drive, including
any OF816 drive override. A runtime descriptor cannot change that selection or
replace the system descriptor. MOUNT SYS: may remount the saved SIO system
configuration. UNMOUNT SYS: follows the same busy-volume rule as a physical
name; it does not redirect SYS to another mount. While detached, SYS is
unavailable. Boot-configured IDE/RAM mount management remains internal.

Existing directory ASSIGNs store path text rather than permanent mount locks.
They remain defined after unmount and fail normally while their target is
absent. Reusing a physical name makes subsequent resolutions use the new disk;
old files and locks cannot survive the successful unmount. NameFromLock stays
canonical. Command PATH and shell command aliases need no additional policy.

## Public interface and shared worker

Propose two synchronous DOS operations:

```text
MountVolume(name, spec) -> DOSTRUE / DOSFALSE, IoErr
UnmountVolume(name)    -> DOSTRUE / DOSFALSE, IoErr
```

The API name omits its trailing colon, as AssignPath does. SioMountSpec is a
small public record containing drive, format, profile and requested access.
Disk geometry is a discovery result, not an API input. A null spec requests the
saved SIO boot definition. The format field is always required for a new spec.
Define its exact layout and constants in the machine-readable ABI inputs, then
generate the native and supported COMMAND/C bindings together. Do not expose
FSTYPES.Spec, numeric registry slots or private management-packet action codes.
Rebuild affected clients when the ABI changes; check provider-table capacity.

The caller owns the name/spec storage until terminal reply collection. The
worker copies the admitted descriptor before publication and retains no caller
pointer after return. As elsewhere in Exec816, valid application-owned pointers
are caller responsibilities. Validate names, supported geometry/profile and
namespace/device conflicts at one admission boundary, without repeating RAM-map
walks through the wrappers and driver.

Reuse FSMANAGER/FSMOUNT control packets, the existing caller context and its
single outstanding packet. A control reference keeps the service alive until
reply collection. The filesystem worker serializes management with ordinary
file requests through its existing multiplexing loop. Device transactions,
cancellation and bus lifecycle remain in sio.device, using ordinary Exec I/O.
Do not add a kernel gateway operation or a Task per volume.

Named DOS volumes follow the project's Amiga model. Keep Exec816's existing
shared filesystem worker rather than introducing a separate handler Task for
each new volume: the current worker already owns the format state and disk
serialization, and extra Task stacks/direct pages would consume bank-zero RAM.

## Mutable definitions and startup

Keep the existing **nine-slot total capacity**, shared with boot-configured
IDE/RAM volumes. Do not compact slots: the SYS slot and mount identities must
remain stable. Copy boot definitions into a bounded mutable upper-RAM table,
with small defined/boot/enabled masks. A slot with no definition is reusable;
a detached boot definition keeps its slot. Published Mount records retain
their own descriptor copies and normal monotonically increasing generations.
All registry loops must distinguish unused, detached and published entries.

A failed new mount does not install its definition. A failed replacement leaves
the previous detached boot definition unchanged. Successful unmount removes a
user definition or disables a boot definition. Service restart restores only
enabled definitions; explicitly detached boot disks must not silently return.
The kernel-owned upper DOS registry reserves the definition table and retained
failure copy. Their lifetime follows the kernel image, so worker stop requires
no heap teardown for this state. They survive a worker restart within one boot,
but not reboot. Cold boot imports the build
definitions again. Users can put complete MOUNT commands in
S:USER; no mount-list file parser or settings-save mechanism is needed.

Normal automatic boot mounting keeps its existing all-or-nothing publication
rule. Explicit management also needs a way to start an **empty control service**
when no filesystem service is ready, including after a failed boot mount set.
It must wait for a previous worker's actual retirement before starting another.
This avoids making MOUNT depend on SYS or on every configured disk being present.
Once started this way, boot entries are marked disabled and remain detached
until explicitly mounted; ordinary DOS lookups do not silently retry the entire
boot set. This is an
explicit management transition, not a change to normal boot mounting.

Provision shared disk resources when the first physical mount needs them.
A RAM-only or empty service may lack the block adapter and parser buffers.
A read-only-only service may lack the mutation workspace required by its first
READWRITE disk. Acquire these before accepting the new mount; roll back new
resources on admission failure when no other mount owns them. Reuse one shared
adapter, sector/transfer buffers, mutation workspace and cache. There is no
per-disk cache or new fixed allocation for absent disks.

## Publication, unmount and disk changes

Prepare a candidate privately, open the SIO binding, discover geometry for a
user definition and run the existing MyDOS/SDFS header admission. Keep discovered
sector count and size in the concrete mount, separate from the user's definition.
Restarting an enabled user definition rediscovers the disk parameters instead of
reusing the previous incarnation's result. Name-only boot remounts retain their
saved internal geometry as described above.
Mounting does not write to the disk. Commit the runtime definition and publish
the completed mount together in a short
protected interval. No Forbid or interrupt mask spans disk I/O. Before that
commit, failure or BREAK cleans up the candidate and returns the original error.
A completed publication wins over a late BREAK; do not return cancellation with
a successfully installed volume.

UNMOUNT rejects a volume with any live file, directory lock, inherited backing
or accepted request reference, using ERROR_OBJECT_IN_USE. It neither forcibly
closes another Task's objects nor waits indefinitely for them. The caller's
current directory counts as a lock: CD elsewhere before unmounting it.
A busy rejection leaves the mount fully published and usable.

For an idle volume, atomically withdraw publication, retire its cache identity,
close its device binding and free its mount/backend resources before replying.
Current writes settle required data/metadata before their reply, and the last
Close finalizes a writer, so unmount adds no write-back sweep. Completion wins
over late BREAK once detachment starts. An offline mount can be removed after
its objects have retired; removal is not filesystem recovery.

The supported media-change sequence is UNMOUNT, change the disk, MOUNT. Each
successful new incarnation has a fresh generation, even on the same drive and
with the same name. Retire old block tags and retained format metadata before
resource reuse. Do not infer a disk change from an error or continue serving
old cached sectors after the user swaps media without unmounting.

## Errors, costs and validation

Preserve ordinary DOS errors for invalid arguments, duplicate/in-use names or
drives, exhausted mount slots, unavailable service/driver, unsupported format,
header mismatch and physical I/O failure. A missing unmount target reports
ERROR_DEVICE_NOT_MOUNTED. A full table is bounded resource exhaustion, reported
as ERROR_NO_FREE_STORE with a specific diagnostic. Output identifies the
requested name/drive and failed admission phase, retaining the causal IoErr.
Geometry diagnostics identify READ sector 1, STATUS, PERCOM or fallback as the
failed phase, retain the available reports, and explain why discovery failed.
Parser diagnostics distinguish a user-selected format/header mismatch
from unresolved disk parameters.

The last failed mount needs a copied identity/geometry, not only a slot index:
a rejected user definition may never enter the table, and a freed slot can be
reused. MOUNT DIAGNOSTICS remains observational and uses the existing batched
output path. Other published mounts survive ordinary request rollback. A
physical failure that takes the shared SIO bus offline retains the driver's
existing reset-required behavior; mount support adds no automatic retry or
bus recovery. Read-only admission and successful remount do not certify a disk
for writes. Existing allocation-consistency assumptions and external repair
requirements remain those of the filesystem write contract.

Target **0 additional fixed, per-Task and private-idle reserved bank-zero bytes**,
including guards, alignment and unused capacity. New definition/failure state
belongs in bounded upper RAM. Reuse shared sector/transfer workspace for boot,
STATUS and PERCOM payloads, shell argument/output buffers and existing Task
pools. Measure the actual descriptor table, geometry provenance and retained
reports, masks, allocation rounding, code size and invocation-stack use during
implementation; no new reservation has been made by this design note.

Development coverage should exercise real emitted operations for both formats
and sector sizes, automatic PERCOM geometry and standard STATUS fallbacks,
read-only and writable admission, wrong headers/profiles,
duplicate names/units and table exhaustion. Cover busy files/current directories,
concurrent clients, cancellation and failed admission with unrelated mounts live,
first-disk/first-writer resource allocation, empty-service startup, worker restart,
boot drive overrides and copied diagnostics after slot reuse. Discovery cases
must check wire command order, stale/conflicting PERCOM, big-endian decoding,
side-count conversion and arithmetic bounds, clean unsupported PERCOM versus
transport failure, unsupported capacity/profile and filesystem-header mismatch.
Cover XF551 ambiguity without claiming automatic compatibility, rediscovery
after media changes, and absence of writes or PERCOM SET during admission.
Independently check media bytes, cache generation retirement after disk swaps,
ownership, stack/domain guards and OS restoration. Add the focused raw/optimized checks
needed for the new ABI layouts; full release qualification is separate.
