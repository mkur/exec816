# SYS: implementation plan

Status: SYS1–SYS3 complete, with refreshed standard and OF816 play bundles. Runtime baseline `66d48c3`. Follow the [platform contract](../reference/platform.md) and
[development testing policy](../contributing/testing.md). Implement three executable slices,
with a commit after each completed slice.

## Behavior

`SYS:` names the root of the selected **system volume**. It gives programs and
users a stable path to system files when that disk moves between SIO drives.
The XEX may have been loaded from somewhere else; SYS does not identify its
source or change how the kernel image is loaded.

For the standard image:

```text
Default:       SYS:HELLO → D1:HELLO
Drive 2 boot:  SYS:HELLO → D2:HELLO
```

Implement one fixed DOS alias to an existing mount. Both names use the same
mount, filesystem worker, generation, locks, handles and sector cache. No
second mount, filesystem, worker or public kernel operation is needed. SYS is
case-insensitive and available through ordinary DOS calls, including callers
outside the shell.

Keep this milestone small: no general ASSIGN command, assign chains, `C:`,
`RAM:`, startup scripts or command search path. A user can run `SYS:HELLO`
from another directory; bare command names retain their current lookup rules.

## System-volume selection

Add an optional `system_mount` name alongside `mounts` in the build's filesystem
configuration. The standard shell configurations select `D1`. Resolve that name
to one mount slot during packaging and record the selection in image metadata;
do not infer it from mount order. Configurations without a selection have no
SYS alias and retain ordinary explicit-volume access.

For this first milestone, the selected descriptor must use the physical name
`D1` through `D8`, matching its SIO unit. Other configured mounts can retain
their existing names. Reserve `SYS` as a DOS name in both host and runtime
validation so it cannot also be configured as a separate mount.

The boot parameter `system_drive` is a drive number **1 through 8**, translated
to SIO unit `$30 + number`. Its default comes from the selected descriptor.
Zero represents an image with no system mount; it is not an interactive disable
option for an image that has one.

A valid override relocates the designated system descriptor: change its
effective unit and physical alias to `Dn`, retaining its filesystem format,
sector count, sector size, short-boot-sector convention and SIO profile.
Thus the existing standard disk can be mounted in D2 and used by the same XEX,
without also requiring a disk in D1. Other configured mounts are unchanged.
The original D1 name is not retained as another name for D2.

Validate the effective configuration before publishing any mount. Reject an
override that collides with another configured unit or alias; do not merge
mounts or silently choose another disk. An unavailable or invalid selected disk
reports its causal mount error and leaves a usable console where possible.
There is no fallback scan of other drives. Disk geometry/profile must match the
descriptor; drive selection does not detect a different media format.

## Shared boot record and OF816

Use the same generated boot record proposed by the
[sector-cache plan](sector-cache-implementation-plan.md), rather than adding
another handoff mechanism. Coordinate its first eight-byte layout now:

| Offset | Bytes | Field |
| --- | --- | --- |
| 0 | 2 | Magic |
| 2 | 1 | Version |
| 3 | 1 | Record size |
| 4 | 2 | `cache_blocks` |
| 6 | 1 | `system_drive` |
| 7 | 1 | Reserved zero |

One machine-readable definition generates loader, kernel and OF bindings.
Direct XEX loading initializes defaults after clearing boot state; native
startup validates and captures them before bootstrap storage is reused.
Malformed records or out-of-range fields use documented build defaults and
retain a diagnostic, as in the cache plan. A valid drive selection whose
effective mount configuration conflicts is an error, not a default request.

Proposed Forth words, implemented in SYS2:

```forth
decimal
2 SYSTEM-DRIVE!
SYSTEM-DRIVE@ .
EXEC816
```

The setter validates the entire Forth cell, requires a designated system mount
and rejects configuration conflicts while retaining the old value. Native
startup repeats validation. The getter reports the requested drive, not whether
a disk has successfully mounted. Defaults still work through the five-second
autoboot. Settings last for one boot and are frozen after handoff.

The shared boot plumbing is a dependency; the sector cache itself is not.
If cache slice C1 is implemented first, SYS2 reuses it. If SYS2 comes first,
implement that common prerequisite once and update both plans' status.

## DOS resolution and lifetime

Use a selected mount-slot identity, not recursive path rewriting or a retained
root lock. Add a small shared helper for the selected slot and its effective
unit/name. Apply the override when copying the existing descriptor into its
runtime mount; the packaged descriptor remains unchanged. Startup validation,
DOS name admission and shell diagnostics must use the same effective values.

Update both `DOSCALLS.Configured`/`Destination` and `FSREGISTRY.Lookup`:
the former currently rejects names absent from the configured descriptor list,
while the latter finds and retains a published mount. Recognize SYS in both
paths, strip its prefix normally, and retain the selected mount under the same
publication/reference protocol used for physical names. Normal path bounds and
error handling still apply; no extra per-call pathname buffer is needed.

Preserve these semantics:

- `SYS:` always starts at the selected volume root. Relative names and `:`
  continue to use the caller's current directory/current volume.
- `CurrentDir(NULL)` still means no current directory. Adding SYS does not
  change null-lock behavior or manufacture a default lock for every Task.
- Locks reached through either name carry the same mount/generation identity.
  `NameFromLock` returns the physical configured name, such as `D2:TOOLS`, and
  directory information uses that same canonical name.
- Missing selection or an unpublished selected mount returns
  `ERROR_DEVICE_NOT_MOUNTED`. Offline media preserves the existing causal error;
  SYS must not bypass that state or serve stale cached data.
- The alias itself holds no mount reference. Open files, directory locks and
  in-flight requests retain the usual references and block unmount as before.
- Successful unmount makes SYS unavailable. Remounting the same selected slot
  restores it with a new generation. Failed/busy unmount leaves it unchanged.
  Store no unprotected mount pointer across publication changes or service
  teardown. Service restart retains the boot selection, not old mount objects.

## Implementation slices

### SYS1 — Alias and build selection

Extend `tools/generate_dos_mounts.py`, packaging metadata and the relevant build
callers with explicit `system_mount` selection. Add SYS reservation/recognition
in `FSNAMES` and both DOS routing paths. Resolve it to the selected mount slot
without adding a second mount or pinning a root lock. Initially use the build's
selected drive, with no runtime override.

Development checks: host configuration validation, then a focused raw/optimized
DOS fixture covering `Open`, `Lock`, directory enumeration, case-insensitive
SYS names, physical/SYS identity, canonical names, independent current
directories, absent selection, offline state and unmount/remount. Keep normal
guard, ownership, bounded-completion and cleanup assertions. These are focused
extensions to existing DOS fixtures, not a full filesystem qualification run.

Bank-zero reservation delta: **0 fixed bytes, 0 bytes per Task**. Keep selection
state in upper RAM and reuse existing mount references and synchronization.

### SYS2 — Drive override and OF816 words

Implement/reuse the shared boot-record prerequisite. Add `system_drive`
validation, effective unit/name handling and the two OF words. Audit
`FSINIT.Config` and `AllocateMount`, DOS admission, generated build information
and packaging together so every path sees one effective mount configuration.
Preserve the original image/media hashes and record defaults separately from
the effective boot selection.

Development checks: default and D2 overrides, full-width invalid Forth values,
missing system descriptor, unit/alias collisions, malformed boot record and
preservation through loader entry. Boot the same standard media on D2 with D1
empty, proving that filesystem reads address unit 50. Exercise direct-XEX
defaults and both OF autoboot/manual handoff, including existing guards and OS
restoration. Reuse C1 results where the exact shared inputs are unchanged.

Bank-zero reservation delta: **0 fixed bytes, 0 bytes per Task**. The boot field
uses one byte already budgeted in the eight-byte shared record. Keep OF words
in its upper-RAM dictionary and preserve the adapter's existing size limit.

### SYS3 — Shell integration and play images

Start the standard shell with a real lock on `SYS:`. Replace the hard-coded
`shellRoot`, `EXECBUILD.BOOT_UNIT` and D1 startup text with the effective system
selection. SIO startup and its profile message must describe the selected unit.
Show a short mapping such as `SYS: -> D2: ready, read-only`; keep mount listings
to one row per actual volume. Update intent comments to say system volume.

Preserve a working console after mount failure, with explicit `CD SYS:` retry.
Keep `CD`/`PWD` canonical names and bare-command lookup unchanged. Explicit
`SYS:HELLO`, `TYPE SYS:STORY.TXT` and `SYS:CAT SYS:STORY.TXT | SYS:WC` should work
from any current directory, through ordinary DOS resolution.

Refresh standard and OF play bundles and their guides. Run one focused shell
session for default D1 and one for OF-selected D2: startup, SYS-qualified file
and command access, CAT/WC pipeline, directory changes and EXIT cleanup. If the
sector cache is present, include one physical-name/SYS-name warm read proving
they share cache identity. Record compiler, ROM, emulator and media pins;
release qualification remains separate.

Bank-zero reservation delta: **0 fixed bytes, 0 bytes per Task**. Report actual
upper-RAM state/code growth and full reserved bank-zero totals, including guards,
alignment and unused capacity. No extra task slot or stack/DP arena is planned.

## SYS1 implementation record

SYS routing uses a generated mount-slot constant and ordinary publication and
reference handling. Selection is explicit in image metadata; the standard
configurations select D1. There is no new runtime allocation or retained lock.

Focused raw and optimized native cases each passed 48 checks; the optimized
no-selection case passed nine. These cover physical/SYS cache identity,
canonical names, enumeration, independent task directories, offline errors,
busy/successful unmount, remount generation and service restart. Host tests:
232 passed. [Pinned execution evidence](../development/sys-volume-sys1.json).

Reserved bank-zero delta: **0 fixed, 0 per Task**, including guards, alignment
and unused capacity. The eight-slot reservation remains 24,672 runtime bytes
excluding OS and 61,536 including OS (fixed 10,560, root 2,080, seven public
slots at 1,568, idle 1,056). SYS1 adds no resident selection-state bytes;
selection constants and routing code use the existing upper kernel image.

## SYS2 implementation record

The existing boot byte now selects the effective physical drive. Startup,
DOS admission and runtime descriptor copies share its unit/name rules. Native
validation rejects conflicts before allocation/publication; OF rejects them
using a generated mask. No extra resident state was added.

Raw and optimized D1/D2 runs passed; D2 had no disk in D1. Optimized cases also
covered zero/out-of-range/malformed fallback, unit and alias conflicts, and
absent system selection. OF words passed full-cell rejection, both conflicts,
no-selection rejection and D2-only handoff into the native DOS fixture.
Five-second autoboot passed across a clock wrap, with guards and OS state
restored. Host tests: 234 passed.
[Pinned execution evidence](../development/sys-volume-sys2.json).

Reserved bank-zero delta remains **0 fixed, 0 per Task**, with the same full
reservation totals as SYS1. Captured state remains four upper-RAM bytes, shared
with the cache; SYS2 uses its existing drive byte. OF adds 100 upper dictionary
bytes (21,942 total); its bank-zero adapter stays 1,059 bytes within the existing
1,264-byte allowance. Shell startup and refreshed standard bundles follow in SYS3.

## SYS3 implementation record

The shell starts with a real SYS root lock, opens SIO on the effective system
unit, and reports the SYS-to-physical mapping. Build information uses explicit
selection. Existing shell fixtures now select their system mount explicitly.
The demo disk includes WORK so SYS-qualified commands can be exercised outside
the root directory. Standard and OF guides describe drive selection and retry.

The optimized direct-XEX development session passed startup, a single physical
MOUNT row, canonical CD output, SYS:HELLO, TYPE and CAT/WC from WORK, return to
SYS root, bare HELLO and EXIT cleanup. The physical read had six hits/20 misses;
the subsequent SYS read had 16 hits/20 misses.
[Direct execution evidence](../development/sys-volume-direct.json).

The raw shell session started with invalid media, retained its working console,
reported the causal mount error, then mounted replacement media with `CD SYS:`
and successfully read `SYS:HELLO.TXT`. Guards, ownership and OS restoration
passed. [Recovery evidence](../development/sys-volume-recovery.json).
Host tests: 234 passed; changed documentation links checked. Full release
qualification remains separate. Final clean-image/OF records are below.

Reserved bank-zero delta: **0 fixed, 0 per Task**. Full eight-slot reservations
remain unchanged as reported above. No extra runtime selection state, mount,
Task, stack, direct page or cache is allocated. Final linked payload growth is
recorded with the refreshed images; it includes additional text inside the
existing bank-zero data arena, whose reservation did not grow.

## Final play bundles

Built cleanly from `7ddd012` with compiler pin
`bcabe0a4cbb8bb57b389a8596aa8fd72cb9ee0c7`:

- `build/demo/program.xex`: 520,299 bytes; matching `sdfs.atr`: 92,176 bytes.
- `build/of816/of816-exec.xex`: 545,208 bytes, with the identical companion ATR.
- Both folders have refreshed README guides and pinned manifests.

Final OF autoboot used D1 and the default 512 cache blocks. Manual handoff used
D2 with D1 empty and 128 cache blocks. Both passed SYS commands from WORK,
canonical names, a single physical mount row, CAT/WC, physical/SYS cache
identity, EXIT, guards, ownership and OS restoration. BYE and occupied-IOCB
checks also passed. [Final artifact and execution record](../development/sys-volume-play.json).

Against the preceding standard play image, linked upper payload grew by 4,553
bytes; resident selection state did not grow. Initialized bank-zero payload
uses 75 more bytes inside the existing data reservation; zero-fill is unchanged.
All reserved bank-zero totals, including guards/alignment/unused capacity,
remain identical: fixed runtime 10,560 bytes; root 2,080; seven public slots at
1,568; idle 1,056; runtime 24,672 excluding OS / 61,536 including OS; loading
20,368 excluding OS / 57,232 including OS. OF's extra 100 dictionary bytes are
transient upper RAM; its adapter remains 1,059 bytes.
