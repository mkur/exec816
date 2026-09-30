# Banked loading and memory ownership

> Historical record: applies to the revisions and profiles described below.
> See the [current documentation](../reference/platform.md) and [history index](README.md).

The banked launcher packages the native kernel and its first application in an
ordinary Atari XEX. `INITAD` callbacks copy the image into native upper RAM;
`RUNAD` enters the resident launcher only after every COPY and ZERO extent is
complete. Kernel initialization adopts the bootstrap's ownership table before
starting tasks. The original `--banked` profile starts two tasks;
[general task management](../guides/tasks.md) uses `--tasks` to support **four simultaneous
user tasks, including the initial root**, plus a private idle task. The kernel
has its own stack and direct page, separate from those five task contexts.
The [eight-task layout](../architecture/task-capacity.md) supports eight
public Tasks plus idle and uses the separate generated map documented there.
The [memory contract](bank-manager.md) defines ownership;
the [implementation plan](../plans/loader-bank-manager-plan.md) records the acceptance scope.

## Build and run

Prepare the compiler, dedicated 65816 ROM and bridge using
[native launch](native-launch.md). Use the revision in
[toolchain/actionc.json](../../toolchain/actionc.json), including the absolute-array
pointer correction needed for a 256-entry table.

The earlier two-task example uses `--banked --preemptive`:

```sh
python3 tools/native_program.py --compiler-dir build/actionc --banked --preemptive \
  --source examples/preemptive.act --output build/banked
```

Open `build/banked/program.xex` in Altirra with the dedicated AltirraOS 65816 ROM,
800XL, PAL, 65C816 at 1x, BASIC disabled, 64K base RAM and **15 high banks**.
This is native linear RAM in banks `$01-$0F`; it is separate from PORTB-window
expansion. The exact configuration is pinned in
[toolchain/altirra-1m.json](../../toolchain/altirra-1m.json). Add
`--bridge-dir build/altirra-irq-bridge` to the build command to run in an isolated
instance with those settings and the [corrected pinned emulator](emulator-native-irq-fix.md).

The example prints `A0` through `A3` and `B0` through `B3`, with VBI-dependent
interleaving. Both tasks share the compiled kernel/application image and use
separate stacks and direct pages. Their exit leaves image banks reserved.
Omit `--preemptive` to use cooperative scheduling with a cooperative example.
The bank-zero launch modes continue to use the original PAL/64K profile.

For the public Task example with native console output, use:

```sh
python3 tools/native_program.py --compiler-dir build/actionc --tasks --console --task-capacity 8 \
  --source examples/tasks.act --output build/tasks
```

This selects banked loading and preemption automatically. Root admits three
workers alongside the console service; removed user contexts can be reused.
Press Return after the result to exit. Plain `--tasks` still selects the
four-slot profile, which fits the [Amiga message example](../guides/messages.md).
See
[Task preparation and lifetime](../guides/tasks.md) for the public API.

`--max-banks N` overrides the default 16-entry table for this build. The valid
range is 2 through 256, including bank zero, and must exceed `KERNEL_BANK`;
table storage is exactly `4*N` bytes. This limit never enables physical RAM.
A limit of 1 is rejected because no upper kernel bank fits. Entries above the
profile's physical RAM remain unavailable in a 256-entry build.

`--kernel-config PATH` selects the manifest/staging capacities and bank limit;
`--memory-profile PATH` selects the explicit RAM map and near-data arena.
Defaults are [config/kernel.json](../../config/kernel.json) and
[platform/altirraos/memory-1m.json](../../platform/altirraos/memory-1m.json).
Fixed adapter, stack, console and OS reservations are checked against the
hosted layout; changing them requires a platform change and fresh qualification.
Custom maps are build inputs, not newly qualified hardware profiles.

The [kernel bank build parameter](platform-contract.md#kernel-bank-build-parameter)
selects the starting code bank through `kernel_bank` in the kernel config or
`--kernel-bank`, default `$01`. The generated eight-task profile puts the bank
table at its start. Task builds place heap metadata and the port registry
before code: offsets $250 for eight tasks or $210 for four at MAX_BANKS=16.
The four-task profile retains its bank-zero table; non-Task probes retain
their original code origin. The profile's old `code_origin` field
is superseded by this parameter. See the [eight-task map and full budget](../architecture/task-capacity.md).

The root Action! source must declare a named module. The builder retains
`EXECMEMORY` in a generated copy beside this build's includes, preserving root
INCLUDE paths and module lookup. It binds the retained `EXECMEMORY.Init` entry
as a zero-argument native CARD function. No compiler source is generated or
modified by the packager.

## Placement and lifetime

### Current `--tasks` runtime map

The table below describes the four-task layout after memory adoption
and task initialization. User contexts 0–3 provide four simultaneous user tasks;
context 0 initially runs the root. Context 4 is private idle storage. The kernel
does not consume a user context.

All ranges below are inclusive and in bank `$00` unless a bank prefix is shown;
host validation uses half-open intervals. Stack and direct-page (DP) ranges
include 16-byte guards at each end. Each actual DP is 256 bytes and each actual
stack allocation is 1536 bytes. Stack floors, initial S values and the interrupt
reserve are detailed in the [Task storage table](tasks.md#storage-and-loading-lifetime).

| Address | Contents |
| --- | --- |
| `$0000-$1FFF` | OS low memory, including the page-one OS stack |
| `$2000-$20FF` | Resident kernel state and diagnostics |
| `$21F0-$230F` | User context 0 DP and guards (initial root) |
| `$23F0-$250F` | User context 1 DP and guards |
| `$25F0-$270F` | Kernel DP and guards |
| `$2800-$2BFF` | Bank-table reservation; active table is `$2800-$283F` with the default 16 entries |
| `$2C00-$2CFF` | Boot state, manifest identity and callback work area |
| `$2D00-$2DEF` | Unused reserved space in this layout; private metadata is in upper RAM |
| `$2DF0-$2F0F` | User context 2 DP and guards |
| `$3000-$3FFF` | Resident startup, COP/NMI/IRQ and OS adapters |
| `$41F0-$480F` | User context 0 stack and guards (initial root) |
| `$49F0-$500F` | Kernel stack and guards |
| `$51F0-$580F` | User context 1 stack and guards |
| `$59F0-$5B0F` | User context 3 DP and guards |
| `$5BF0-$5D0F` | Private idle context 4 DP and guards |
| `$6000-$67FF` | External manifest arena, retained after adoption |
| `$68F0-$6F0F` | User context 2 stack and guards; reuses loader storage |
| `$70F0-$770F` | User context 3 stack and guards; reuses loader storage |
| `$78F0-$7F0F` | Private idle context 4 stack and guards; reuses loader and staging storage |
| `$8800-$8FFF` | Near image data: kernel globals, public Task records and application data, including OS-visible console buffers |
| `$9000-$FFFF` | Excluded OS/display/ROM/I/O space |
| `$01:0000-$0F:FFFF` | Native upper RAM; code starts at the configured kernel bank. The highest usable bank reserves Task metadata and signal adapter code |

Public `EXEC.Task` records are 62-byte image objects, separate from the private
64-byte contexts in upper RAM. They may occupy near or upper-bank writable application
data; the root's public record belongs to the upper metadata arena. The fixed context
pool limits simultaneous execution, not the total number of task lifetimes.

The active bank table uses four bytes per configured bank: 64 bytes by default,
up to the full 1 KiB reservation. Unused table bytes and unlisted bank-zero gaps
are not exposed by an allocator. Bank zero remains SYSTEM-reserved. Touched
upper banks belong to the shared image, including unused bytes within those
banks; eligible unclaimed upper banks are available to the bank manager.
Task removal does not release image banks. Byte-level heap allocation remains
pending.

Future layout changes follow the
[bank-zero memory budget](../reference/platform.md#bank-zero-memory-budget), which
counts the full reserved footprint and requires a reason for bank-zero placement.
The bank table [moves into the configured kernel bank in the eight-task profile](bank-manager.md#planned-upper-ram-table-placement)
(default `$01`), recovering its 1 KiB bank-zero reservation; the map above describes
the four-task layout.

The layout is defined jointly by the base platform reservations in
[memory-1m.json](../../platform/altirraos/memory-1m.json) and the task pools/private
arena in [tasks.json](../../abi/tasks.json). The packager validates their
overlap and records the resolved map in each build's `memory.json` and
`build.json`.

### Loading and the earlier two-task profile

Before runtime initialization, the loader uses these bank-zero reservations:

| Address | During loading | After adoption in `--tasks` |
| --- | --- | --- |
| `$6000-$67FF` | External manifest arena | Retained; task pools cannot overlap it |
| `$6800-$7BFF` | Bootstrap and its embedded expected manifest | Listed stack ranges become user contexts 2/3 and part of idle context 4 |
| `$7C00-$800F` | Staging reservation: eight-byte header and up to 1024 payload bytes, ending at `$8007` | Listed overlapping range becomes part of idle context 4's stack |

Reusing those stack ranges happens only after all COPY/ZERO callbacks finish
and standard `EXECMEMORY.Init` adopts the bootstrap table. They are never live
task stacks while the loader still needs them. Remaining gaps are not offered
as heap storage; the additional DPs and private context arena are separate
fixed reservations.

The earlier `--banked` two-task profile uses only the user-context 0/1 and
kernel stack/DP ranges from the runtime table. It has no private idle task or
additional user contexts, keeps its private task records in `$2000-$20FF`, and
retains the manifest, copier and staging reservations after handoff. Its
two-task limit does not apply to `--tasks`.

In both profiles, the table and boot record are outside the launcher's
state-clear range.
The original MEMLO is saved before the bootstrap raises it to `$9000`; normal
and native fault termination restore it and the OS vectors, then park under
the OS. A failed bootstrap parks in emulation mode with its first error intact.
It does not reclaim partial loads or enter native code.

## Wire format and validation

[abi/memory-v1.json](../../abi/memory-v1.json) defines the private memory ABI.
`generate_memory.py` emits `memory.inc`, `memory-action.inc` and `memory.json`
inside each output directory. Builds with different limits do not share these
files. `build.json` records compiler/ABI identities, the complete resolved map,
source and generated-input hashes, image, manifest and XEX hashes.

The little-endian manifest starts with a 32-byte header:

| Offset | Bytes | Field |
| --- | --- | --- |
| 0 | 4 | `EBM1` |
| 4 | 2 | Version 1 |
| 6 | 2 | Compiled bank count |
| 8 | 2 | Extent count, at most 64 |
| 10 | 3 | Native program entry |
| 13 | 1 | Zero |
| 14 | 2 | Manifest byte length |
| 16 | 16 | Build identity |

Next come `MAX_BANKS` four-byte seed records, then eight-byte extent descriptors:
24-bit address, one-byte kind, 16-bit nonzero length and 16-bit owner. Kinds are
COPY=0, ZERO=1 and executable COPY=2. Extents never cross a bank boundary and
never encode 65536 as a zero length: a full bank becomes lengths 65535 and 1.
The build identity is a truncated SHA-256 of the resolved map, header, seed,
descriptors and initialized bytes. It identifies a build; the bootstrap does
not calculate a payload checksum or authenticate executable files.

The host validates all image extents and coalesces claims before assembling the
bootstrap. It rejects overlap, holes, bank-limit/24-bit overflow, different
owners sharing one upper bank, forbidden near ranges, writable code, bad entry
or import bindings, and capacity overflow. Every literal XEX segment belongs to
the bootstrap/resident/manifest/staging/vector layout. Image data goes through
staging, including initialized data and BSS in bank zero.

For this fixed-image loader, runtime manifest preflight is an exact comparison
with a second manifest embedded in the bootstrap. That embedded copy was
assembled only after host range/ownership validation. A mismatch rejects the
entire manifest before any table or payload write. This binds each bootstrap
to one image and avoids a general manifest parser in the first-stage loader.
It assumes the bootstrap executable itself is intact, as does ordinary XEX
execution. It is not a format for loading arbitrary later images.

A staging record contains 16-bit extent index, 16-bit extent offset, 16-bit count,
one-byte kind and one zero byte. COPY appends `count` bytes; ZERO carries none.
The callback accepts only the next expected extent/offset, a matching kind,
`1..CHUNK` bytes and an endpoint within that descriptor. It validates before
writing, advances the cursor, then clears the pending count. A zero count is a
no-op, allowing loaders that invoke INITAD after every segment. Replay,
reordering, invalid counts and missing final records cannot reach kernel entry.
After the first error, all later callbacks return without payload writes.

`loader_error` is valid immediately after loading the first segment: 1 means
host bounds, 2 manifest mismatch, 3 record rejection, and 4 incomplete RUNAD.
`M_ERROR` mirrors errors once the boot area is safe/initialized. INITAD preserves
the live emulation-mode stack, A including hidden B, X/Y, P, D and DBR. It uses
long-address byte transfers, no direct-page scratch and no native transition.
OS VBI/IRQ service continues; Exec scheduling starts only at final native entry.
The cold-loader environment supplies E=1, D=0 and the OS bank/stack conventions.

## Internal ownership interface

`lib/exec/execmemory.act` supplies native CARD-returning functions; every status is
separate from any result. These are trusted internal calls on the serialized
kernel stack/domain. They are not additional COP services or task-callable APIs.
NMI never reads or mutates the bank table.

| Function | Behavior |
| --- | --- |
| `Adopt()` / `Init()` | Check ready/error, version, count, completed cursor, identity and exact seed table; publish adoption without clearing claims |
| `Query(bank, BankRecord POINTER result)` | Copy a checked record; failed queries preserve output |
| `ReserveExact(bank, owner)` | Turn FREE into a pinned RESERVED claim; repeated reservations fail |
| `Acquire(owner, CARD POINTER result)` | Acquire the lowest FREE bank above zero; failed allocation preserves output |
| `Release(bank, owner)` | Release only OWNED storage with the matching valid owner |

Owner IDs are fixed: SYSTEM=1, IMAGE=2, CLIENT_A=3 and CLIENT_B=4. Zero and other
IDs are invalid. States are UNAVAILABLE=0, FREE=1, RESERVED=2 and OWNED=3.
The reserved record byte is zero. Statuses are OK=0, BANK=1, OWNER=2,
UNAVAILABLE=3, RESERVED=4, CONFLICT=5, OWNERSHIP=6, EXHAUSTED=7 and BOOT=8.
Failures preserve ownership. There is no owner recycling or automatic release
on task exit; these require a later lifetime protocol.

## Qualification and limits

```sh
python3 tools/generate_exec_abi.py --check
python3 tools/generate_memory.py --output build/memory-check
python3 tools/generate_memory.py --output build/memory-check --check
python3 -m unittest discover -s tests -p 'test_*.py'
python3 tools/test_banked.py --compiler-dir build/actionc \
  --bridge-dir /path/to/AltirraBridge-nightly-macos-arm64
```

`--case NAME` selects one bounded target case. The 48-case banked matrix covers the
physical bank map; raw/optimized policy at 1, 16 and 256 entries; banked task and
OS operation; locks; all M/X combinations in a bank-2 register probe; selected
NMI transition checkpoints; timer IRQs; real INITAD context/interrupt behavior;
cross-bank copies and full-bank zero-fill; redundant callbacks and rejected
manifests, records, bounds and incomplete loads. A native adoption-failure
case also verifies that corrupted claims prevent task dispatch and preserve
normal vector/MEMLO cleanup. The 256-entry policy inventory
is synthetic and sparse, with reserved intervening banks and a free bank 255;
it does not qualify 16 MiB of physical RAM. The dense 16-entry inventory covers
repeated acquisition through exhaustion. Policy runs have a 12,000-frame bound
and a 120-second wall limit for the 256-entry case. Test-only probes and
CPU memory-transfer helpers are absent from production XEX output.

The pinned bridge reports only 16-bit PC values. Tests stop at resident bank-zero
rendezvous points; PBR restoration is exercised by the bank-2 probe returning
through the full interrupt frame. Unsupported upper-bank debugger breakpoints
are rejected by the runner. Native guards, OS clock/console operation and vector/
MEMLO restoration are checked after both tasks finish.

The accepted banked results are in
[qualification/banked-loading.json](../qualification/banked-loading.json).
[qualification/banked-regressions.json](../qualification/banked-regressions.json)
records all 134 existing hosted/cooperative/preemptive cases on the updated
compiler pin; their original qualification records retain their original inputs.
This milestone qualifies cold XEX launch with the pinned ROM/emulator only.
Resident DOS file loading, relocation, independent application loading/unloading,
byte allocation, mapped expansions, arbitrary owner lifetimes and DOS-prompt
return remain separate work.
