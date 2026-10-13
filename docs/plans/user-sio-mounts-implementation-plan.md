# User mounted SIO filesystems implementation plan

[Plans index](README.md#filesystems-and-dos) ·
[Design](user-sio-mounts-design.md) · [Roadmap](../roadmap.md) ·
[DOS contract](../reference/dos.md) ·
[SIO interface](../reference/device-io.md#siodevice) ·
[Testing policy](../contributing/testing.md)

Status: UM0–UM4 implemented at the development tier; UM5 pending.
[Implementation record](../history/user-sio-mounts.md). Complete and commit each
executable slice after its focused development checks.

## Outcome and boundaries

Users can mount and unmount MyDOS and SpartaDOS disks on SIO D1–D8 without
rebuilding Exec816. A new definition selects the filesystem and discovers disk
geometry. Read-only is the default; READWRITE requests the existing write path.

```text
MOUNT D2: FORMAT MYDOS
MOUNT DATA: DRIVE 3 FORMAT SPARTA READWRITE
MOUNT FLOPPY: DRIVE 4 FORMAT MYDOS PROFILE STOCK810
UNMOUNT DATA:
MOUNT WORK:
```

Keep plain MOUNT and MOUNT DIAGNOSTICS observational. Name-only MOUNT remounts
a detached boot-configured SIO definition. New definitions have no geometry
arguments. Unknown or contradictory geometry fails with a retained diagnostic;
filesystem mismatch does not trigger another parser.

Reuse the nine-slot registry, shared filesystem worker, block adapter and cache.
Keep boot's all-or-nothing publication, SYS selection, IDE/RAM mounts and SIO
driver recovery policy. Automatic filesystem selection, formatting, filesystem
checking, baud negotiation, forced unmount, IDE Plus BIOS ATR slots and FujiNet
network/control commands are outside this work. Stock-XF551 density ambiguity
remains outside automatic compatibility until a safe probe is implemented.

## Current implementation

The existing pieces provide much of the lifecycle:

- [FSMANAGER](../../lib/fs/fsmanager.act) sends slot-based management packets
  while retaining the caller context and a service control reference.
- [FSMOUNT](../../lib/fs/fsmount.act) remounts a configured slot and rejects an
  unmount when the selected mount has live references.
- [FSINIT](../../lib/fs/fsinit.act) creates private mounts, opens devices, admits
  the selected filesystem and publishes completed mounts. It currently assumes
  immutable, contiguous boot definitions and allocates disk resources at startup.
- [FSBOOT](../../lib/fs/fsboot.act) requires a configured mount set; it cannot
  start an empty management service after failed startup.
- [FSINSPECT](../../lib/fs/fsinspect.act) snapshots published mounts, but derives
  a failed mount's identity from its configured slot. Reused slots need a copied
  failure record.
- [sio.device](../../lib/io/siodriver.act) already admits the needed disk IDs
  and the 128-, 4- and 12-byte READ/STATUS/PERCOM transactions. Discovery needs
  no larger-frame SIO ABI or new kernel operation.

Implement UM0 → UM1 → UM2 → UM3 → UM4 → UM5. Early slices use focused internal
fixtures; expose the public calls only when complete operations can execute.

## UM0: mutable definitions and stable slots

Introduce a bounded, registry-owned upper-RAM definition table initialized from
the packaged boot descriptors. Keep boot, defined and enabled masks for the
nine stable slots; never compact them. A user definition holds name, drive,
filesystem, profile and access. Its concrete mount holds discovered geometry.
Boot definitions retain their existing internal geometry and SYS slot rules.

Update configuration validation, lookup, duplicate-name checks, ASSIGN admission,
worker iteration, inspection, shell boot reports and cleanup to distinguish
unused slots, detached definitions and published mounts. Preserve GetVolume's
existing slot-index contract: callers inspect all nine slots and skip empty
records. Guard zero-count loops and publication of an empty set.

Make definitions and copied failure storage survive filesystem worker stop and
restart. Reserve them in the kernel-owned upper DOS registry so their lifetime follows
the kernel image. UM0 reserves 576 bytes instead of 114: 414 for nine definitions,
eight for masks/control state and 40 for copied failure identity. Worker stop
requires no heap teardown for these fields. Keep lifecycle baselines focused on
disposable worker allocations.
Keep existing build-time mount encoding unchanged.

Validation: boot a focused MyDOS/SDFS configuration and RAM-only configuration;
check stable SYS selection, holes, name collisions, nine-slot exhaustion,
snapshots and worker stop/restart. Exercise an existing mixed IDE/SIO fixture
for unchanged boot descriptors. Host checks cover table and mask boundaries;
emitted checks cover ownership and final release.

## UM1: empty management startup and lazy disk resources

Add an explicit management startup path in FSBOOT/FSMANAGER. It joins a running
startup or waits for the previous worker's actual retirement before creating
the control service. When ordinary boot mounting has failed, start with saved
boot definitions disabled. Ordinary file lookup must not implicitly retry that
failed boot set after management has selected the empty-service path.

Allow zero published volumes without requiring SYS. Create the existing
management port and cancellation state, then enter the multiplexing loop.
Make packet handling and cancellation valid before disk workspace exists.
Concurrent management callers must join the same worker rather than create
competing services.

Split shared resource acquisition into reusable operations: first physical
disk acquires the block adapter and parser/operation resources; first writable
disk acquires mutation state. Reuse those resources across mounts. A failed
first mount releases newly acquired resources when no other mount owns them.
Keep driver bindings and queues in their existing drivers.

Validation: extend the no-mount and mount-retry fixtures for zero boot disks,
missing boot media, RAM-only service followed by a disk, first writable mount,
two simultaneous management callers, startup allocation failure, old-worker
retirement and clean shutdown. Check that a failed request leaves unrelated
mounts usable and that observational queries start neither workers nor I/O.

## UM2: bounded SIO geometry discovery

Add a small internal discovery state machine, proposed as `lib/fs/fsdiscover.act`,
and a compact upper-RAM observation record. Reuse the adapter request and
existing sector/transfer workspace. Separate opening the physical SIO binding
from completing geometry admission: the candidate can issue discovery commands
before its logical sector bounds are known, but ordinary block operations and
publication require resolved geometry. Retain one binding throughout admission;
do not open a temporary duplicate connection.

Use the existing queued [BLOCKWIRE](../../lib/io/blockwire.act) transfer boundary
and foreground cancellation scope. Execute:

1. READ `$52`, sector 1, 128 bytes; retain its boot-sector data.
2. STATUS `$53`, four bytes; retain density/status bits.
3. PERCOM GET `$4E`, twelve bytes.
4. Decode and cross-check PERCOM against STATUS.
5. On a clean unsupported-command response, use the supported standard fallback.

Decode sectors-per-track and sector size as big-endian; decode sides as
sides-minus-one + 1. Check the geometry product in 32 bits, supported 128/256
sector size, boot-sector convention, profile and per-format limits. Accept
ordinary PERCOM geometry such as 40/80 tracks and one/two sides when consistent.
Retain raw responses, effective sector count/size and PERCOM/STATUS provenance.

Start the STATUS fallback table with conventional 720 × 128 and 1,040 × 128
layouts. A double-density status bit alone does not establish total capacity;
require usable PERCOM or established peripheral-specific evidence. Keep this
table small and documented; timing profiles must not stand in for drive-model
identification. Treat stale contradictions, malformed replies and unsupported
layouts as discovery failures. Preserve checksum, framing, timeout and bus-offline
errors; only an explicitly classified unsupported PERCOM response allows fallback.
Keep existing SIO deadlines and recovery policy.

Feed the retained sector 1 into the existing admission path when the selected
filesystem needs it, preserving one header-validation path. MyDOS still reads
its VTOC; SpartaDOS still validates its declared geometry. Acquisition remains
read-only, with no PERCOM SET, data-sector guessing or whole-volume scan.
Record stock-XF551 cases separately: sector 1 can leave DD media reported as ED,
and an unknown-size sector-4 read is outside this slice.

Validation: host decoder cases and optimized emitted discovery through the
pinned SIO integration fixture. Assert wire order and lengths, SD/ED fallbacks,
256-byte and larger PERCOM layouts, big-endian fields, sides conversion,
overflow/range rejection, stale values, clean NAK versus device/transport failure,
BREAK at each phase and no writes. Verify cancellation collects the exact reply
before freeing or reusing the request. Rare response fixtures belong at the
integration boundary; emulator correctness fixes belong in actionc-vm.

## UM3: public mount and unmount operations

Add both public calls together:

```text
DOS.MountVolume(name, spec) -> DOSTRUE / DOSFALSE, IoErr
DOS.UnmountVolume(name)    -> DOSTRUE / DOSFALSE, IoErr
```

Define SioMountSpec in [abi/dos.json](../../abi/dos.json) as four CARD fields:
drive, format, profile and access, for an eight-byte record. Drive is logical
1–8, converted internally to wire ID $31–$38. Define public named constants for
MyDOS/SpartaDOS and read-only/read-write access. The API name omits its colon.
Null spec remounts a saved SIO boot definition; new specs require a filesystem.
Geometry is exclusively an output of discovery.

Generate native/COMMAND definitions and import metadata together. Update DOS
implementation delegates, program API/provider bindings, C headers, Calypsi
wrappers/table and [C program ABI](../../abi/c-program.json). Check provider and
table reservations before appending calls; advance the affected ABI versions
and rebuild applications/providers together. Keep one current interface.

Resolve names and reserve a candidate slot/name/unit through the existing
management queue. Check namespace and active/pending unit conflicts once at
admission. ASSIGN creation must see pending name reservations while discovery
is running. Preserve a detached boot definition until its replacement commits.
Keep caller name/spec storage alive through terminal reply collection; publish
copied definitions only, with no retained caller pointers.

Mount acquires resources, runs UM2 and filesystem admission, then commits the
definition and publication together under a short protected interval. Failure
or BREAK before commit retires I/O, frees the private candidate and releases
reservations. Adapt FSABORT explicitly: its current generic management error
reply does not own candidate cleanup. Successful publication wins over a late
BREAK. Copy failure identity/reports before freeing the candidate.

Unmount rejects live files, directory/current-directory locks, inherited
backings and accepted requests. An idle unmount withdraws publication, retires
cache identity, closes the binding and frees mount state before acknowledgment.
User definitions free their slots; boot definitions remain saved but disabled.
Detachment wins over late BREAK. Preserve existing write finalization; add no
new metadata flush pass or forced-close path.

Validation: focused raw/optimized native, COMMAND and C ABI probes for the record
and both calls, then optimized public lifecycle fixtures. Cover successful
read-only/writable mounts, namespace/unit conflicts, SYS restrictions, failed
replacement, table exhaustion, busy reference categories, precommit cancellation,
commit races and copied failure identity after slot reuse. Inspect independent
disk bytes and require no admission writes. Update old private slot-management
fixture callers to the current named API where appropriate.

## UM4: resident shell commands and diagnostics

Extend classification, arity checks and dispatch in the shell session; add
UNMOUNT and a small MOUNT argument parser using existing token storage. Parse
FORMAT, DRIVE, PROFILE and READWRITE case-insensitively, reject duplicates or
missing values, infer DRIVE from Dn and reject disagreement. Strip the trailing
colon before calling DOS. Keep filesystem selection mandatory for a new
definition and preserve existing name-only and DIAGNOSTICS forms.

Print effective name, unit, format, sector count/size, profile, access and
geometry source after success. Extend FSINSPECT and the existing batched shell
reports for retained READ/STATUS/PERCOM/fallback failure phases and observations.
Show why discovery or selected-format admission failed; diagnostic queries
perform no new probes. Preserve causal IoErr across formatting and cleanup.

Update HELP and command metadata. Support ordinary redirection and the shell's
existing resident-command pipeline rules, without routing resident commands
through external loading. Keep rows readable on the standard console and
reuse the bounded shell output buffer.

Validation: emitted parser/formatter cases plus a short physical shell session
that mounts a disk, uses it, rejects busy unmount, changes directory, unmounts
and remounts. Check bad options, removed geometry arguments, absent SIO in an
IDE-only build, startup-script use, redirection and BREAK. Extend shell-report
tests to check bounded Write counts and read-only diagnostics.

## UM5: integration coverage and documentation

Add a selectable `tools/test_user_sio_mounts.py` runner and native fixture for
the public workflow, reusing the existing SIO/DOS runners and media audits.
Keep decoder, lifecycle, shell and ABI cases selectable so earlier slices run
only their relevant subset.

Exercise both filesystems with 128/256-byte media, disk swaps after unmount,
fresh generations and cache retirement, concurrent clients, RAM-only and empty
startup, first-writer allocation and service restart. Assert accepted operations
retain resources through reply collection and that unrelated mounted disks
remain usable after ordinary rollback. Distinguish a shared SIO bus failure
from a mount-local failure. Confirm final worker/request/port/heap ownership,
stack/domain guards and OS restoration.

Update the shell guide, DOS and filesystem references, filesystem architecture
and testing-policy entries. Add a development history page and compact evidence
record containing pins, emitted builds, observations, actual check scope and
memory costs. Update indexes and link the design/plan to the completed record.
Refresh story.txt examples through the demo's existing content source; a demo
build or release qualification runs only when separately requested.

## Validation and memory budget

Use the compiler revision in [toolchain/actionc.json](../../toolchain/actionc.json)
and the pinned AltirraOS/SIO setup used by the existing device fixtures. Run
host checks after code changes and the optimized cases for the affected slice.
Raw/optimized duplication is limited to new ABI/layout/bridge probes or a
compiler defect investigation. Full release matrices and physical-device
compatibility claims are separate from development completion.

Every slice targets **0 additional fixed, per-Task and private-idle reserved
bank-zero bytes**, including guards, alignment and unused capacity. Report the
actual three deltas at each slice. Reuse the existing filesystem/SIO Task pools,
shared cache/transfer buffers and shell storage. New definitions, pending mount
state and retained reports belong in bounded upper RAM. The definition and
failure identity reservation uses kernel-owned storage; disposable per-operation
state uses the existing upper heap. Measure record sizes,
nine-slot table capacity, masks, allocation rounding, provider reservations,
upper executable growth and stack headroom; enlarge no reservation without
evidence. A newly active existing worker consumes a Task slot but introduces
no new reserved stack/direct-page pool.

Completion requires UM0–UM5, both public and shell operations, discoverable
geometry with the specified failure behaviour, correct busy/unmount semantics,
coherent regenerated interfaces and recorded focused integration results.
