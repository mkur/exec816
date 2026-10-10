# IDE 512-byte sector refactor

Status: planned; implementation has not started. This supersedes the IDE
128/256-byte partition packing in the
[IDE Plus driver plan](ideplus-block-driver-implementation-plan.md) and the
media geometry in the [IDE-only demo plan](ide-only-demo-implementation-plan.md).
Current behavior remains documented in the
[IDE device](../reference/ideplus-device.md) and
[SpartaDOS](../reference/spartados.md) contracts until the corresponding slices
are implemented.

Follow the [platform contract](../reference/platform.md),
[contributor instructions](../../AGENTS.md) and
[development testing policy](../contributing/testing.md). Implement and commit
one executable slice at a time, recording checks and memory changes.

## Outcome

Support only **512-byte logical sectors on IDE Plus**. One partition sector
maps directly to one 512-byte ATA sector. Remove the driver's 128/256-byte
packing, short-prefix transfers and physical read-modify-write path. Retain
128/256-byte MyDOS and SpartaDOS on SIO, RAM:, and the existing DOS interfaces.
Use SpartaDOS SDFS 2.1 for IDE SYS: and WORK:; MyDOS on IDE is unsupported.

Keep one IDE worker, one shared filesystem worker and the existing cache. Device
queueing, lifetime, cancellation, protection, durability and offline policy stay
in the driver, coordinated through public Exec services. This refactor needs no
new kernel operation, worker, Task pool, ATA write-back cache or filesystem
checker. Mount recognition remains bounded header validation.

Keep the pinned revision E/PBI ID 0/ATA master/LBA28 setup in
[altirra-ideplus.json](../../toolchain/altirra-ideplus.json). Preserve unit 0 as
read-only raw ATA access and units 1–15 as APT mappings. Filesystems retain the
65,535-sector and 24-bit file-length limits. Changing sector size does not add
large-volume addressing, clustering or automatic power-on disk boot.

## Why replace the current layout

The current builder packs two 256-byte filesystem sectors into one ATA sector.
The pinned BIOS 2.1 skips APT entries with nonzero packing bits. A disposable
low-byte 256-byte repack was admitted, and the real BIOS loader listed both SYS
and WORK, including EXEC816.XEX. That experiment established partition visibility
and directory reads; it did not launch the XEX or establish boot handoff.
Its evidence is under
`build/development/ide-only/apt-reference/low-byte-partitions/directory/`.

APT defines 512-byte partitions directly. Moving to that layout also removes the
read needed to preserve another packed sector before each write. Preserve the
post-write verification read and required ATA flush; this is a simpler sector
model, not a relaxation of completion guarantees.

## Geometry and format

| Transport / format | Data-sector bytes | Mount `boot` | Transfers and boot reservation |
| --- | --- | --- | --- |
| SIO / MyDOS or SDFS | 128 or 256 | 1 | Sectors 1–3 transfer 128 bytes; three reserved boot sectors |
| IDE Plus / SDFS 2.1 | 512 | 0 | Every transfer is 512 bytes; only sector 1 is reserved for boot |
| RAM | No physical geometry | 0 | Existing behavior |

Use the existing mount byte: `boot=1` keeps the three-short-sector layout;
`boot=0` means uniform sector lengths. This flag describes transfer layout, not
whether the machine can boot the volume. Make the generator choose the proper
default for each backend, while explicit incompatible values fail admission.
Do not change the 46-byte mount record, IOStdReq, 12-byte IDE geometry record,
command numbers, backend IDs or OF816 boot-settings record.

For IDE, require SDFS revision `$21`, sector-size marker `$01` at offset 31,
512 at offsets 33–34, 254 data pointers per map page at offsets 35–36, and one
physical sector per logical sector at offset 37. Recognize the documented
512-byte boot signature (`JMP $0440`) rather than the floppy signature
(`JMP $3080`). Sector 1 is read/written in full, including its boot code and
reserved bytes. The bitmap may begin at sector 2; derive protected boot bounds
and allocator scan origins from the admitted format, replacing `sector<4` and
`bitmap<4` assumptions. Preserve existing floppy recognition.

These layouts are described in chapter 7.1 of the authors'
[SpartaDOS X User Guide](https://sdx.atari8.info/sdx_files/4.51/SDX450_User_Guide.pdf#page=187).
APT mapping flags and offsets follow the
[APT specification](https://drac030.krap.pl/APT_spec.pdf).

## Changes by layer

### IDE device

In [ideplus-apt.inc](../../lib/io/ideplus-apt.inc), admit active DOS mappings with
BPS bits `%11` and no packing bits. Skip 128/256-byte mappings as unsupported
units; a mixed APT must still expose supported 512-byte mappings and raw unit 0.
Retain table decoding, protective MBR support, bounded header chains, physical
sector-1 offsets, metadata leaders, extent checks and access flags. Low-byte
**APT table storage** is independent of partition-sector packing and remains
supported.

Use `partition.start + io_Offset` for all mapped transfers. Remove PackedIndex,
CopyLogical and packing/count conversions; retain existing metadata reservation
initially rather than compacting it as a side task. Require exactly 512 bytes
for READ_SECTOR and WRITE_SECTOR, including sector 1. Keep raw writes prohibited.

In [ideplus-write.inc](../../lib/io/ideplus-write.inc), copy the complete caller
sector into the existing 512-byte controller buffer, then issue WRITE, wait for
terminal status, flush when required, reread and compare all 512 bytes. No
preparation read is needed. Keep the request and source bytes owned until the
terminal reply. Cancellation accepted before command issue must prevent any
write; after issue it remains declined. An ambiguous write/flush/verification
failure reports zero actual bytes and makes the controller offline, without
retry. Keep PBI selection, IRQ/NMI coordination and bounded waits unchanged.

### Shared block adapter and cache

Change [BLOCKIO](../../lib/io/blockio.act) to use one 512-byte scratch sector.
SectorBytes applies short-sector handling only to an admitted short layout;
IDE sector 1 must return 512. Update
[BLOCKTRANSPORT](../../lib/io/blocktransport.act) and the
[mount generator](../../tools/generate_dos_mounts.py) together: SIO accepts its
existing geometry; IDE accepts only 512 bytes, profile 0 and uniform sectors.
Reject IDE/MyDOS during filesystem configuration. Match GET_GEOMETRY at open.

Keep [BLOCKCACHE](../../lib/io/blockcache.act) allocated in 128-byte blocks and
preserve the meaning of OF816 CACHE-BLOCKS. Generalize the two-half code into
one, two or four pieces, with a zero-based part tag and a hash that keeps a
sector's parts in distinct sets at supported capacities. Find every required
piece before returning a hit or copying bytes. A missing piece is a whole-sector
miss. Store only complete successful transfers; invalidate every piece before
write, on failure, volume retirement or controller offline. Do not introduce a
separate IDE cache or enlarge the user's configured payload budget.

### SpartaDOS reader and writer

Use a shared maximum sector-buffer constant of 512. Enlarge the SDFS map buffer
and FSWTYPES data/map/scratch/bitmap arrays. Use CARD-sized indexes, lengths and
offsets throughout; 512 cannot be represented by a byte. Keep directory-record
scratch, per-handle cursors and extent-cache capacity unchanged.

Update [SDFS](../../lib/spartados/sdfs.act) header/protected-sector recognition
and [SDFSFILE](../../lib/spartados/sdfsfile.act) byte-to-sector and extent
rounding: the current two-way shifts only distinguish 128 from 256. Use the
admitted sector size consistently for reads, seeking, map traversal and block
accounting. Preserve sparse-file reads, directory ancestry and generation tags.

Audit [SDFSWRITE](../../lib/spartados/sdfswrite.act),
[FSALLOC](../../lib/fs/fsalloc.act) and
[FSWRITEIO](../../lib/fs/fswriteio.act) for full-sector copies, bitmap coverage,
map boundaries, directory records spanning sectors and header updates. Make
Zero take an explicit byte count and update its MyDOS callers too. Initialize
only metadata and bytes required by existing filesystem semantics; add no
zero-fill write pass over allocated data sectors.

Retain four-sector extension batches and current ordered publication:
completed payloads, allocation bitmap, free-count header, map, then directory
length. Preserve confirmed-prefix counts, rollback rules and BREAK checkpoints;
do not retain dirty metadata across Write calls as part of this refactor.

### Host media and demos

Extend the pinned independent Altirra producer wrapper
[sdfs_reference.cpp](../../tools/sdfs_reference.cpp) to create uniform 512-byte
images with **zero short boot sectors**. Its formatter already implements the
one-sector SDFS boot region. Reproducibility edits must read and write all of
sector 1 so they preserve its tail. Keep independent producer/reader pins.

Separate sector-container access from the MyDOS assumptions currently inherited
by [filesystem_audit.py](../../tools/filesystem_audit.py) through
mydos_fixtures.Image. Share a small host sector view for short-boot ATRs and
uniform 512-byte SDFS staging; validate container offsets and lengths once.
Keep MyDOS fixtures and runtime support restricted to 128/256 bytes. Extend
SDFS allocation audits to reserve one boot sector on 512-byte media. Remove
packed IDE fixture generation; keep small explicit unsupported-size APT cases.

Rebuild the IDE-only image with 1,440 × 512-byte sectors per nominal 720 KiB
partition, retaining the 4 MiB raw image, starts 64 and 1,536, metadata leaders,
boot unit 1, SYS read-only and WORK writable. Emit APT BPS `%11`, zero packing
bits and physical count 1,440 (access byte `$43` when a metadata leader exists).
Reformat and import source files; changing an old filesystem's BPS flag or
repacking its bytes does not convert its maps and bitmap.

Update [build_demo.py](../../tools/build_demo.py), build/finalization records and
the mixed SIO/IDE demo together. In mixed builds, SIO disks keep their geometry;
the additional IDE filesystem must be independently formatted at 512 bytes.
Preserve OF816, five-second autoboot, manual PRIMES, matching XEX inside SYS,
both cartridge variants, capacity checks and the established ZIP contents.
Existing writable user images are not converted or overwritten automatically.

## Executable slices

| Slice | Deliverable and exit check | Suggested commit |
| --- | --- | --- |
| I512-0 | Independent uniform-512 SDFS producer, container view and allocation audits; exact tree read-back, sector-1 tail preservation, and real BIOS SYS/WORK directory listing on a disposable 512-byte APT | Add independent 512-byte IDE media fixtures |
| I512-1 | Shared 512-byte buffers and one/two/four-piece cache; focused emitted cache hits/misses, missing pieces, collisions, invalidation, allocation failure and bank crossings; existing floppy behavior remains executable | Extend filesystem sector storage to 512 bytes |
| I512-2 | 512-only IDE discovery/transfers and full SDFS read integration; update requests/configuration/fixtures together, remove packed runtime paths, read SYS files and load a command beside timer/peer activity; keep SDFS-512 write admission closed until I512-3 | Use native 512-byte IDE sectors |
| I512-3 | Enable SDFS-512 mutation after allocator, metadata initialization and write ordering checks; persisted create/append/overwrite/directories/rename/delete, confirmed-prefix BREAK and injected failure audits | Enable SpartaDOS writes on 512-byte IDE volumes |
| I512-4 | Rebuild IDE-only and mixed demos, update contracts/guides, verify extracted ZIP and both carts, and attempt the real firmware EXEC816.XEX load through OF816 and kernel handoff | Rebuild IDE demos with native sector geometry |

Each slice updates affected callers and fixtures rather than keeping a legacy
packed driver/profile. I512-2 may verify the device's full-sector writes directly;
I512-3 opens filesystem write admission only after its paths are checked.
Temporary read-only admission is removed in that next slice.

## Memory and validation gates

Target **0 additional fixed, per-Task and idle reserved bank-zero bytes**,
including guards, alignment and unused capacity. Leave `$010000–$01FFFF`
untouched. Reuse current workers, stacks, DPs and the 512-byte ATA buffer.

The expected shared upper-RAM buffer increase is 1,536 bytes when the SDFS
reader and mutation workspace are present: 256 for BLOCKIO, 256 for the SDFS
map, and 1,024 for four mutation buffers. This is shared across volumes and
files. Fixed 512-byte arrays also increase these workspaces in floppy builds;
keep that explicit rather than adding another build-profile mechanism. Cache
payload/tag capacity and per-file allocations stay unchanged. Report actual
heap alignment, code-size changes and worker stack observations per slice.
Do not grow stack pools to hide a failed bound.

Use host checks and focused optimized emitted-code tests for behavior. Use a
small raw/optimized probe for changed buffer/tag layouts and compiler-facing
bank crossings. Reuse emitted images across fixture cases. Cover:

- Exact 512-byte reads/writes, rejected short requests and unsupported mapping
  sizes; APT chains/MBR/leaders/offsets, bounds and access protection.
- Boundaries 127/128, 255/256 and 511/512; map entry 253 to the next page;
  bitmap allocation across sectors 4,095/4,096; directory records straddling
  sectors; preserved sector-1 bytes outside modified header fields.
- Cancellation before ATA issue and completion afterward, one terminal reply,
  timeout/verification/flush failure, offline denial even for cached reads,
  PBI selection restoration, VBI progress and ownership cleanup.
- One focused MyDOS and SDFS floppy read/write regression plus mixed transport
  isolation, including cache-disabled operation.

Adapt the existing IDE APT/write/lifetime/filesystem runners, block-cache cases
and independent SDFS audits; do not run a full qualification matrix per slice.
Measure matched loaded COPY on fresh IDE media before/after this change, with
the same compiler, ROM/BIOS, emulator timing, source bytes and cache budget.
Record physical ATA reads/writes and terminal/flush/verify phases: a normal
full-sector write should lose its preparation read, retaining verification.
Do not claim a speedup until that measurement exists.

The final firmware test must execute EXEC816.XEX, visit OF816 INITAD while
kernel payload loading is paused, resume after its five-second countdown, and
reach the shell with native IDE SYS/WORK and no Exec SIO fallback. Directory
visibility or cartridge boot alone does not close the old ID5 handoff gate.
If the firmware path still fails, record its exact stage and leave ID5 open;
stop before any failed cartridge-capacity or stack limit. A package build and
development checks do not qualify hardware or authorize GitHub publication.

Update the relevant references and development record as slices complete.
Keep manifests, hashes, diagnostics and disposable images outside the ZIP.
