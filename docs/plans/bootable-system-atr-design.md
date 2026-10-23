# Bootable Exec816 system ATR

Status: implemented at the development tier, 22 October 2026. See the
[BA0–BA4 plan](bootable-system-atr-implementation-plan.md) and
[execution record](../history/bootable-system-atr.md). Current contracts belong
in [boot loading](../reference/boot-loading.md#bootable-system-atr).

[Plan index](README.md) · [Platform contract](../reference/platform.md) ·
[Fixed-image loader](../reference/boot-loading.md) ·
[OF816 monitor](../guides/boot-monitor.md)

## Outcome

Provide one `exec816.atr` containing the boot loader, matching OF816/kernel XEX,
system commands, applications and writable workspace. Mount it writable in
FujiNet's D1 slot and cold-boot. The existing five-second OF816 countdown leads
to the selected Exec shell or desktop. No D2 kernel disk, D8 workspace disk,
drive override or disk swap is required.

```text
ROM disk boot from D1
  → boot sectors load the disk reader
  → reader streams EXEC816.XEX
  → OF816 countdown or interactive Forth
  → reader finishes the compressed Exec payload
  → Exec takes hardware ownership and mounts the same D1 volume as SYS:
  → C:, S: and WORK: are assigned; shell or desktop starts
```

Retain the pinned AltirraOS 65816 platform, 4 MiB linear RAM, disabled BASIC and
no cartridge. The graphical variant retains its VBXE and mouse requirements.
An ATR changes the boot transport; it does not extend machine compatibility.
IDE power-on boot, arbitrary DOS launch environments and cartridge launching
remain outside this design.

## Reuse the existing XEX

Store the final combined OF816/kernel executable as root `EXEC816.XEX`. The
disk reader implements ordinary segment loading and INITAD/RUNAD execution.
Keep the current staging records, manifest, LZ4 decoder, progress reporting,
native entry and boot-settings record. OF816 remains an INITAD callback: both
countdown expiry and `EXEC816` return to the paused reader with RTS.

The reader must keep its file position, partially consumed sector, map cursor
and page-one caller frame live across every callback. Clear INITAD before
calling its captured address so a subsequent segment cannot repeat a stale
callback. Support segment headers crossing sectors, repeated XEX markers and
files larger than 64 KiB. Invoke RUNAD only after exact file completion and all
callbacks; the existing loader still rejects incomplete native extents.

The reader uses firmware SIO before Exec exists. Finish every firmware transfer
before calling a callback or entering RUNAD. After handoff, ordinary
`sio.device` and filesystem workers own storage through the existing public Exec
primitives. No boot Task, resident firmware reader or new kernel operation is
needed. In particular, Exec must not invoke ROM SIO after native disk ownership.

Do not replace this path with an installed SpartaDOS/MyDOS operating system.
The boot reader needs only enough SDFS reading to find and stream the kernel;
the native filesystem remains the sole runtime implementation.

## Disk layout and capacity

Use SDFS 2.1 with 256-byte data sectors and the existing three initial 128-byte
boot sectors. Preserve the header fields and `JMP $3080` signature required by
the [filesystem contract](../reference/spartados.md). Changing the executable
boot code does not change the SDFS format or its sector-map semantics.

Choose **8,192 sectors, 2 MiB nominal capacity**, for the first combined image.
The current 720 KiB system image cannot hold its system files and the combined
XEX together. Measure allocated sectors, map overhead and remaining workspace
in the build report; fail on insufficient capacity rather than omit files.
The ATR encoder must retain short-sector layout, including its effect on the
actual host file length. Confirm this geometry through the selected emulator
and FujiNet rather than infer support from a successful host image build.

| Disk content | Purpose |
| --- | --- |
| Sectors 1–3 | ROM boot header, first-stage reader and generated locator |
| `BOOT.LDR` | Second-stage disk reader, allocated as an ordinary SDFS file |
| `EXEC816.XEX` | Exact final combined OF816/kernel executable |
| `C/` | Commands, language engines and applications |
| `S/` | Existing startup and user scripts |
| `WORK/` | BASIC examples, user files and saved desktop settings |

The small first stage loads `BOOT.LDR` from the generated locator. Require its
data sectors to be contiguous in the packaged image; record their first sector,
count, load extent and version in a machine-readable boot description and
generate the assembly definitions. Confirm the allocation by reading the final
filesystem maps. Mark the file write/delete protected. A locator avoids putting
a filesystem parser into the three short boot sectors.

The second stage finds root `EXEC816.XEX` through SDFS directory entries and
follows its sector maps, using the exact 24-bit file length. Support fragmented
kernel files and map-page transitions. Limit the reader to this known format,
root-file lookup and sequential reads. It does not need directories below root,
file creation, writes, a command line, DOS CIO handlers or a filesystem checker.
Protect `EXEC816.XEX` against ordinary write/delete operations too. Replacing
either boot file requires repackaging so locator, executable and system files
stay matched.

Keep boot files inside normal filesystem allocation and mark all their sectors
allocated. Do not hide a kernel copy in sectors the runtime allocator considers
free. The three boot sectors remain the only format-reserved boot sectors.

## One volume and writable workspace

Select D1 as SYS with one read-write SDFS mount. Keep RAM: as the existing
volatile filesystem. Remove the required physical WORK mount on D8 from this
profile. SYS: and D1: retain one volume identity, worker and cache.

Publish `WORK:` through the existing directory assignment:

```text
ASSIGN WORK: SYS:WORK
```

Install this action in the packaged system startup before any workspace access
or desktop launch. C: and S: keep their existing startup assignments. The three
assignments consume three of the current four slots; no table growth is needed.
Use the ordinary [ASSIGN semantics](../reference/assigns.md), including
canonical paths, replacement and existing open-reference lifetime.

WORK: is a directory assignment, not a separately mounted volume or an access
boundary. SYS: is also writable. Do not mount the same D1 device twice to create
a read-only SYS view and writable WORK view. MOUNT reports D1 once; ASSIGN
reports WORK's directory target. Startup failure messages must no longer ask
for a missing D8 disk.

This keeps current application paths such as `WORK:DESKTOP.CFG` and
`WORK:HELLO.BAS`. Copy existing workspace examples into WORK/ and verify ARC's
workspace paths, editor saves and desktop preferences there. The disk must be
mounted writable in FujiNet; a read-only attachment must report ordinary save
failures without pretending that changes persisted.

## Memory and execution lifetime

The disk reader must survive all XEX writes and OF816 borrowing. Loading the
whole kernel into bank zero first would violate the existing memory budget.
Stream sectors instead.

Reserve an initial **8 KiB boot-only reader arena at $4000–$5FFF**, including
code, buffers, state, guards, alignment and unused capacity. This borrows
currently idle worker-stack storage before Task initialization. The first
stage occupies the ROM's three-sector load range at $3000–$317F and transfers
control out of it before any XEX loading. These are proposed placement bounds;
the generated map must prove them for every selected build before packaging.

In particular, reject overlap with the root/kernel pools borrowed by OF816,
the live OS stack, adapter, manifest, staging area, LZ4 loader, VBXE aperture,
OS display or any XEX destination. Include OF816's guards and native caller
stack, not just its emitted adapter code. The first-stage range may be reused
by OF816 only after it has no live code, data pointer or return address there.
Leave firmware bank $01 untouched.

Keep firmware MEMLO truthful and within the existing $0A00 admission bound.
Borrowed boot storage must be described by phase ownership; lowering MEMLO to
conceal an installed DOS or loader reservation is not an acceptable substitute.
The reader uses absolute private state without borrowing OS zero page. Firmware
SIO and XEX callbacks run in the existing emulation-mode context; preserve the
complete context, hidden accumulator byte and page-one stack required by the
current loader. OS VBI continues while loading and waiting in OF816. IRQ masking
alone must not be treated as NMI exclusion.

Before RUNAD, retire the file cursor, all reader callbacks and reader-owned
return targets, and finish firmware I/O. Enter the existing native entry with
no expectation that it will return to the disk reader. Native initialization
may then initialize the borrowed worker stacks. Normal EXIT retains Exec's
existing restored-OS display and park behavior; it cannot resume overwritten
boot code. OF816 BYE and pre-entry errors also park through a safe path.

The reservation target is **0 additional fixed, root, kernel, per-public-Task
and idle bank-zero bytes at runtime**, including guards and padding. There is
no additional Task or enlarged Task pool. Loading adds a phase-specific claim
on the 8 KiB arena and 384-byte first-stage range, reusing existing reservations;
report their union and actual lifetime separately from runtime deltas. If the
reader cannot fit, revise and justify the layout before changing reservations.
This planning change itself adds no target storage.

Implementation accounting: the worker stacks borrowed at $4000–$5FFF are not
already live in the native loading phase. The disk-loading union therefore
grows by 8,192 bytes, despite zero runtime growth. The first-stage range is
already covered by the loading kernel stack and adds zero union bytes.

## Handoff and failure behavior

Default boot and SYS selection to D1. The boot reader always reads its boot
drive; `SYSTEM-DRIVE!` remains the later SYS selection, independent of that
reader. The single-disk path needs no override. Keep the disk attached and
unchanged throughout Forth: `EXEC816` still needs the remaining XEX sectors.

Use standard-rate firmware SIO for initial boot, without SIO Patch, burst I/O or
a new accelerated reader. Preserve the current explicit native SIO profile at
handoff. Measure firmware loading, OF816 countdown, decompression and native
mount time separately before considering boot acceleration.

At the on-disk transport boundary, reject unsupported headers, invalid sector
ranges, short/cyclic map chains, truncated segment headers/data and writes into
live reader storage. Bound directory/map traversal and SIO retries. Let the
existing manifest/decoder own native extent admission; do not repeat its full
validation inside the disk reader or add runtime filesystem scans.

Missing boot files, SIO failure, BREAK and malformed input must stop before
native entry and report a concise ROM-screen error with the phase, relevant
sector or file offset and status. Do not jump to a partially loaded kernel or
resume an invalid first-stage frame. Require cold reset after a stopped boot.
An Exec startup failure after RUNAD follows the existing native failure path.

## Build and distribution

Add a SIO `--bootable-atr` build option through
[build_demo.py](../../tools/build_demo.py), selecting SDFS/256, the larger
geometry, one writable system mount and WORK assignment startup. Reuse the
current shell/desktop selection and one kernel implementation. Keep the
external-XEX route available for development and recovery. This design does
not add IDE or MyDOS variants of the boot reader.

Build in this order:

1. Build matching commands, applications and native kernel with the selected
   mount/startup configuration.
2. Compose the final OF816/kernel XEX through
   [build_of816.py](../../tools/build_of816.py).
3. Add that exact XEX, BOOT.LDR and WORK/ to the system staging tree. Format
   SDFS using the independent producer, patch the boot sectors from the verified
   allocation and read back every file and boot locator.
4. Finalize media hashes and manifests without changing executable bytes. Use
   the existing explicit media-finalization pattern: the XEX cannot contain a
   digest of the completed disk containing itself.
5. Produce `exec816-demo.zip` with `exec816.atr`, the matching external XEX,
   pinned ROM, short guide, license notices and checksums. Exclude the old
   separate system/work ATRs for this profile, CAR/BIN images and intermediates.

The guide and local launch script should default to cold-booting the ATR in D1,
with no other disk mounted. Include OF816 and all existing third-party notices;
FastBasic corresponding-source packaging must also include the new boot sources
when this profile ships. Keep development manifests and test results outside
the user ZIP. A refreshed image is a new distribution artifact, not an in-place
update of the user's writable disk.

## Acceptance and next work

Start on the pinned AltirraSDL/AltirraOS configuration. Cold-boot the extracted
ATR through ROM sector reads with the emulator's direct-XEX loader disabled.
Mount only D1. Cover countdown expiry and manual Forth, retained cache/verbosity
settings, a fragmented EXEC816.XEX, headers crossing sectors and a file beyond
64 KiB. Compare expanded native bytes and guards with the ordinary XEX path.
Observe live OS VBI and verify retirement before native stack initialization.

After boot, check one physical mount, the C:/S:/WORK: assignments, command/app
loading and normal last-shell EXIT. Save BASIC source and desktop settings,
perform copy/rename/delete, then cold-boot the same modified disk and read back
the changes. Verify boot files and boot-sector bytes remain intact. Include
read-only media, disk-full writes and bounded boot-read/corrupt-file failures.

Then repeat the core one-disk boot/save/reboot walkthrough through FujiNet-PC's
actual ATR/SIO path, recording firmware revision, configuration, ROM/emulator
pins and exact image hashes. Direct emulator ATR boot alone does not establish
FujiNet support; FujiNet-PC does not establish physical-hardware support.

Follow the [two-tier testing policy](../contributing/testing.md): host image and
layout checks plus focused emitted boot/handoff and native integration checks
at the development tier. Use raw/optimized probes only if implementation changes
a compiler-facing ABI. Releases and hardware qualification retain their own
broader gates. Record memory reservations and actual execution scope per slice.

The [BA0–BA4 plan](bootable-system-atr-implementation-plan.md) separates media
construction and reader placement, emitted XEX/OF816/native handoff,
one-volume startup, persistence/transport checks, and delivery freezing. Its
execution record distinguishes loading-phase reservations from runtime growth
and development checks from hardware qualification.
