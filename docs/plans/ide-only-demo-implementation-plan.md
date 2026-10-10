# IDE-only SYS: and WORK: implementation plan

Status: implementation in progress; ID0–ID4 are implemented. See the
[development record](../history/ide-only-demo.md). This is a separate build
profile following the completed
[IDE Plus driver plan](ideplus-block-driver-implementation-plan.md).

Follow the [platform contract](../reference/platform.md),
[contributor instructions](../../AGENTS.md) and
[development testing policy](../contributing/testing.md). Implement and commit
one executable slice at a time, recording checks and memory costs.

## Outcome

Build a standard-console, shell-only demo whose persistent storage is entirely
on one IDE Plus ATA master. SYS: is a read-only SpartaDOS partition; WORK: is a
separate writable SpartaDOS partition. Keep RAM:, the command set, aliases,
startup scripts and manually launched PRIMES. Retain OF816 and its five-second
autoboot. No floppy disk attachment is needed.

The selected build excludes the Exec SIO driver, resident registration and
serial-disk interrupt paths. It must not initialize sio.device, advertise it in
DEVICES, call firmware SIO as a fallback, or start a SIO worker. Ordinary builds
and the existing mixed SIO/IDE development profile keep their current defaults.
Shared keyboard, timer and interrupt services remain available; POKEY use for
those services is independent of serial disk I/O.

Use the existing pinned AltirraOS816, compiler and
[IDE Plus emulator configuration](../../toolchain/altirra-ideplus.json):
revision E, PBI ID 0, ATA master, LBA28, 512-byte physical sectors and 4 MiB
linear RAM. Keep SDX and firmware UltraSpeed SIO disabled.

The first executable build boots from its matching cartridge or externally
loaded XEX. The final profile also places the combined OF816/kernel XEX on SYS:
and verifies loading it through the IDE Plus ROM executable loader. Automatic
power-on disk boot, a new boot-sector loader, an OF816 ATA/filesystem reader,
other controller revisions and physical hardware qualification are separate
work. The standard console is the initial presentation; a VBXE/GEM variant can
reuse the profile later.

## Disk and namespace

Start with a 4 MiB raw APT image, two 720 KiB nominal partitions, 2,880 logical
sectors of 256 bytes each, and packing mode 3. This preserves current filesystem
geometry and leaves room in SYS for the compressed boot XEX. The builder must
measure actual file allocation and fail if either filesystem is full.

| Name | APT mapping unit | Access | Contents |
| --- | --- | --- | --- |
| SYSTEM: / SYS: | 1 | read-only | EXEC816.XEX, C/, S/, demo text |
| WORK: | 2 | read-write | Workspace README and free space |
| RAM: | none | read-write | Existing volatile filesystem |

Select `system_mount: "SYSTEM"`; SYS remains the reserved alias for that selected
slot, rather than a second mount. Both disk descriptors use
`device: "ideplus.device"`, `profile: 0`, explicit geometry and format 2.
C: resolves to SYS:C, S: to SYS:S, and the shell starts at SYS root. Neither
partition is mounted twice under different block bindings.

Create a firmware-readable APT, including real partition entries after the
fifteen mapping slots, valid mapping IDs, metadata names, non-overlapping
leaders/data and a boot-drive field selecting unit 1. SYS protection is set in
both APT and Exec policy; WORK is writable in both. Use actual logical units,
without relying on firmware D1 swapping. The current single-partition test
fixture is not the production image format for this profile.

The board's protection switch must permit WORK writes. Writable admission still
requires the existing IDE durability policy. Reads and verified writes use one
controller worker and its existing 512-byte buffer; no new ATA cache or write
ordering policy is introduced. Short boot-sector tails and neighbouring packed
sectors remain intact.

## Keep system selection small

SYS selection is by configured mount slot and backend. Extend
[select_system](../../tools/generate_dos_mounts.py) and
[FSSYSTEM](../../lib/fs/fssystem.act) to accept an IDE system descriptor and
retain its configured unit and physical alias. Remove the SIO-specific
admission rejection in [FSINIT](../../lib/fs/fsinit.act), while retaining the
ordinary SIO drive override and conflict checks for SIO system mounts.

The IDE-only profile fixes SYS at APT unit 1. Do not add a general boot-device
browser or runtime partition switching. Keep the eight-byte boot record:
`system_drive=0` means no SIO override, and the generated selected slot still
identifies SYS. Update [BOOTCONFIG](../../lib/exec/bootconfig.act) so that this
is valid for a selected IDE mount. Nonzero SIO overrides in that profile are
invalid and cannot redirect it to SIO. Cache and verbosity settings remain
usable in OF816. SYSTEM-DRIVE@ returns zero; SYSTEM-DRIVE! rejects changes with
the existing Forth error and leaves settings intact. Document this restriction.

This extends the current record's semantics without changing its layout or
adding another ABI version. Backend and IDE unit are already present in the
immutable mount descriptor. Treat RAM as a separate filesystem and keep it
unsupported as SYS for this work.

## Build and package ordering

Add an explicit `--ide-only` option to
[build_demo.py](../../tools/build_demo.py), initially with `--text-shell-only`.
Make it mutually exclusive with the existing additional `--ideplus` profile.
Carry one enabled-backend selection through build generation, resident routing,
inspection, native assembly and provenance. Preserve public request layouts
and resident IDs; excluded drivers fail ordinary OpenDevice admission. Use
generated build-specific definitions/modules instead of duplicating kernel or
driver implementations. Reject configured SIO mounts in an IDE-only build.

Build commands and the native kernel first, then compose the matching OF816 XEX.
Copy those final bytes into SYS as the 8.3 file EXEC816.XEX, create both
filesystems, and assemble ideplus.img. Finalize media hashes and manifests only
after the image is complete. The kernel/XEX must not embed a digest of the whole
disk containing itself. Account for the existing build_of816 media-hash checks
with an explicit finalization pass that does not change executable bytes.

Host-side filesystem staging may reuse existing ATR encoders, but those files
are build intermediates. The IDE-only ZIP contains ideplus.img, the matching
external XEX and old/new Atarimax cartridge images, pinned OS ROM, a short
IDE-specific guide, license notices and checksums. Include the IDE image as
required user media in this profile; retain the older mixed profile's external
test-fixture policy. No system.atr, work.atr, vendor IDE BIOS, build manifests or
test output belongs in the new ZIP.

Check both native and OF816 compressed image capacity before packaging carts;
stop if either does not fit. Preserve source/provenance hashes and ensure every
external boot image matches EXEC816.XEX inside SYS. Test the extracted package.

## Executable slices

| Slice | Deliverable | Suggested commit |
| --- | --- | --- |
| ID0 | Backend-aware SYS selection and fixed IDE boot settings | Allow IDE Plus system volumes |
| ID1 | IDE-only driver selection through Action! and native assembly | Add an IDE-only storage build profile |
| ID2 | Shell startup, assigns and diagnostics without SIO assumptions | Start the shell from IDE SYS |
| ID3 | Two-partition firmware-readable APT image | Build IDE system and work partitions |
| ID4 | OF816/XEX/cart composition and IDE-specific distribution | Package an IDE-only demo |
| ID5 | Real firmware XEX loading and controller handoff | Validate IDE firmware boot handoff |
| ID6 | Persisted WORK walkthrough, failure checks and final records | Validate IDE-only SYS and WORK |

### ID0 — System volume and boot settings

Update mount selection, boot-setting generation/capture and FSSYSTEM's unit/name
resolution together. A selected IDE mount keeps its original alias/unit through
Config, Apply, SYS lookup and NameFromLock. SYS and SYSTEM: share identity,
generation and cache. Emit normal operational errors for unsupported/conflicting
configuration; do not add repeated handle checks.

Exit: host selection checks and a small optimized emitted DOS case resolve IDE
SYS, including its command directory. Existing SIO drive override checks still
pass. Valid IDE defaults do not print an invalid-settings warning; attempts to
set a SIO override cannot alter the IDE selection.

### ID1 — Exclude SIO from the selected profile

Trace the unconditional dependencies in IOCore, BLOCKTRANSPORT, DEVICEINSPECT,
generated IORESIDENT/task admission, task-policy generation and native assembly.
Generate only enabled resident routes and transport calls. Gate sio.s and its
serial IRQ/cleanup entry points while preserving shared signals, keyboard,
timer.device, platform timer and context restoration. Do not remove a shared
service just because its current storage has a SIO-related name.

Keep existing reservations initially; do not compact upper metadata or Task
pools as a side task. Audit emitted symbols/imports and the linked map: no
SIODRIVER/SIOADAPTER implementation or serial-disk engine is included. IDE,
console and timer operations still use the same public kernel facilities.

Exit: an IDE-only optimized program reads geometry/data with timer/peer progress;
opening sio.device returns the ordinary unavailable/open error. The default
profile still supports its existing SIO operations. Generated code is checked
through its generator.

### ID2 — Shell startup and diagnostics

Replace ShellBootSIO's forced warm-up with backend-aware startup, preferably
letting filesystem attachment own the required device opening. Preserve normal
initial-mount ownership and error reporting. Generate backend-appropriate
status/failure text; do not index a SIO speed name using IDE profile 0.

Report SYS on IDE Plus unit 1 and WORK on unit 2 with their access modes. DEVICES
lists console.device, timer.device and ideplus.device, with no sio.device row.
MOUNT lists each physical volume once. C:, S:, PATH, optional STARTUP/USER scripts
and ordinary command lookup work from SYS. An IDE failure must not suggest
attaching D1/D8 or silently fall back to a floppy.

Exit: optimized shell startup with two IDE mounts and no SIO attachment reaches
the prompt, executes a startup marker and loads HELLO through C:. An absent IDE
disk leaves the existing usable-console failure path and accurate diagnostics.

### ID3 — Media construction

Extend the host APT builder for two real partitions and mapping entries. Reuse
the existing SpartaDOS image builder for system/work files and packing helpers
for container conversion. Validate table/leader/data extents, IDs, boot mapping,
geometry and protection, then independently reconstruct/audit each filesystem.
Record partition mapping and hashes outside the ZIP.

Exit: native IDE discovery opens units 1 and 2 with matching geometry; unit 1
rejects writes and unit 2 accepts verified writes. Host image audits preserve
APT metadata and packed neighbours. No byte of WORK overlaps SYS or a table.

### ID4 — Build and distribution

Implement the finalization order above across build_demo, build_of816 and
package_demo. A single final ideplus.img is the required companion medium.
Build OF816 and both cartridge variants without staging floppy dependencies in
the user guide or final ZIP. Keep the five-second autoboot and no automatic
PRIMES. Retain capacity, stack-bound and hash gates.

Exit: an extracted cart package boots with D1–D8 empty, reaches IDE SYS/WORK and
loads a command. Its ZIP members and checksums are audited, and its SYS copy of
EXEC816.XEX equals the external OF816 XEX byte for byte.

### ID5 — Firmware-menu boot

Configure the pinned IDE BIOS to use partition 1, SDX off and no serial disks.
Use its actual ROM executable loader to load SYS's EXEC816.XEX; do not substitute
the emulator's direct-XEX hook for this case. Record the actual MEMLO and loader
workspace, including the page-one return context, against the $0A00 limit.

Verify that INITAD pauses the firmware reader for OF816, its countdown or
EXEC816 returns to that reader, subsequent callbacks expand the kernel, and
RUNAD executes only after complete loading. The native IDE worker begins after
firmware reads are finished. Check PBI selection/shadow and controller IRQ
ownership at handoff. Resolve any loader/firmware incompatibility explicitly;
do not bypass the memory guard or add a DOS-dependent fallback.

Exit: a recorded firmware-menu boot reaches the same IDE shell with no SIO
disk. If firmware loading proves incompatible, record the exact cause and keep
this slice open; cart boot alone does not establish firmware boot support.

### ID6 — Focused integration and documentation

Run a bounded packaged walkthrough: DEVICES, MOUNT, C:HELLO, startup scripts,
COPY SYS:LONG.TXT WORK:COPY.TXT, CMP, append, MAKEDIR, RENAME, DELETE, remount and
readback. Audit the persisted WORK partition independently; SYS, APT metadata,
leaders and unmodified neighbouring bytes remain exact. Include a copy larger
than 16 KiB and BREAK during copy, with peer/timer progress and settled replies.

Check absent media, protected WORK/writable-admission rejection and one accepted
write/verification failure. An uncertain controller outcome invalidates both
IDE mounts, even on cache hits; SYS and WORK share the controller's offline
state. RAM and console remain usable, and cold reset is required. Check
last-close/EXIT retirement, stack/domain guards and full OS context restoration.

Record serial-disk observations over cartridge/IDE loader entry through Exec's
session: zero SIO transactions and no SIO worker. Distinguish any earlier Atari
ROM reset probing from the selected Exec boot path. No firmware serial fallback
is accepted as successful IDE boot.

Update the SYS, boot-record, device/build contracts and guides only when their
changes are implemented. Add a history record linking exact compiler, emulator,
ROM/BIOS, artifact hashes, commands, failure cases and memory reports. Keep
ordinary SIO build coverage focused; no complete release matrix is required for
these implementation slices. Public qualification/publishing remains separate.

## Memory and validation gates

Target **0 additional fixed, per-Task and idle reserved bank-zero bytes**,
including guards, alignment and unused capacity. Leave $010000–$01FFFF untouched.
Use the existing eight-Task pools and one IDE worker for both mounts, one shared
filesystem worker/cache, and the existing 512-byte ATA buffer. Mount objects and
open requests for the two partitions are normal upper-heap allocations.

Report actual code/upper-RAM changes, active allocations, worker call bound and
stack observations per slice. No new Task or enlarged stack pool is justified
by eliminating the SIO worker. A failed existing stack or cartridge bound stops
the relevant build instead of silently increasing reservations.

Use development-tier host checks and focused optimized emitted-code cases.
Small raw/optimized layout/access probes are needed only if a compiler-facing
record or binding changes; the selected boot-record layout does not change.
Documentation-only planning work requires content/link checks, not a rebuild.
Successful FLUSH on cached physical media and physical Antonia/IDE Plus support
remain unqualified until separate evidence exists.

## References

- [SYS contract](../reference/sys-volume.md)
- [Boot record and memory](../reference/platform.md#boot-service-settings)
- [Fixed-image loader](../reference/boot-loading.md) and
  [OF816 monitor](../guides/boot-monitor.md)
- [IDE Plus device](../reference/ideplus-device.md) and
  [development setup](../guides/ideplus.md)
- [APT specification](https://drac030.krap.pl/APT_spec.pdf)
- [IDE Plus firmware guide](https://drac030.krap.pl/ide-plus-config-screen-reference-2.0.pdf),
  especially executable loading, boot drive selection and reported MEMLO
