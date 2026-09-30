# Bank manager

> Historical record: applies to the revisions and profiles described below.
> See the [current documentation](../reference/platform.md) and [history index](README.md).

Status: implemented with the [banked loader](banked-loading.md). The separate
[upper-RAM profile](../../toolchain/altirra-1m.json) enables native banks `$01-$0F`;
the original [PAL/64K profile](../../toolchain/altirra.json) remains available.
See [banked loading](banked-loading.md) for the generated layout, internal
function signatures, statuses, build commands and executable qualification.
The [implementation plan](../plans/loader-bank-manager-plan.md) records the accepted scope.

## Responsibility

The bank manager owns the inventory and exclusive ownership of physical RAM
in the native 24-bit address space. Its initial allocation unit is one complete
64 KiB bank. The platform supplies which address ranges represent usable RAM;
an addressable bank number alone does not establish available memory.

The loader reserves banks containing images. A future heap acquires banks
and allocates smaller blocks inside them. Both use the same ownership table,
so a heap cannot acquire storage occupied by an image or the kernel.

PBR and DBR remain CPU context/ABI state. Bank ownership does not require
changing them, impose one bank per task, or provide memory protection. This
first manager covers the platform's native linear RAM; PORTB-window memory
and other mapped expansions need separate platform support.

## Inventory and reservations

The historical profiles use a fixed table in a statically reserved bank-zero
region, established during bootstrap without calling a heap allocator. Its size
is determined when building the kernel. Each bank record distinguishes physical
availability from allocation state and carries an owner identity when claimed.
The [eight-task upper-RAM placement](#planned-upper-ram-table-placement) removes
this bank-zero cost on the banked platform.

| State | Meaning |
| --- | --- |
| Unavailable | Absent, aliased, ROM, I/O, partially usable, or otherwise excluded by the platform map |
| Free | A complete, verified usable RAM bank available for acquisition |
| Reserved | System or image storage held for the launch lifetime |
| Owned | A bank acquired by a client that may later release it |

Bank `$00` is always excluded from whole-bank acquisition. Its OS state,
vectors, kernel metadata, task stacks/direct pages and console buffers retain
explicit range reservations. A later bank-zero pool allocator must respect
those reservations rather than treat the whole bank as free.

The initial inventory comes from an explicit platform memory map tied to a
new emulator configuration and qualification record. Do not discover memory
by overwriting arbitrary addresses in a running hosted system. Qualification
must establish that enabled upper banks are writable and independent, with
existing OS/platform regions intact. Absent or aliased banks cannot contribute
duplicate capacity.

## Table layout and build limit

Define `MAX_BANKS` as a kernel build parameter, in the range 1 through 256,
including bank zero. Use 16 as the initial default: this covers the native
address span `$00:0000-$0F:FFFF`, or 1 MiB. The bank-zero-only platform can
use an abstract inventory of `MAX_BANKS=1`; the current banked builder requires
at least 2 and `MAX_BANKS > KERNEL_BANK` so its upper image can be placed.
Setting the parameter does not enable RAM or change the emulator configuration.

The initial record is four bytes:

| Offset | Size | Purpose |
| --- | --- | --- |
| 0 | 1 | State and flags |
| 1 | 1 | Reserved/alignment byte |
| 2 | 2 | Owner handle |

The bank number is the table index; bank address and 64 KiB extent are
implicit. Reserve exactly `4 * MAX_BANKS` bytes for the table, separately from
task stacks and direct pages. A 16-bank build therefore needs **64 bytes**,
while a full 256-bank build needs 1 KiB.

`MAX_BANKS` bounds the represented bank numbers, not the amount of installed
or free RAM. Entries cover `$00` through `MAX_BANKS-1`; absent banks and holes
within that span remain unavailable. A sparse platform map that manages a
higher-numbered bank must raise the limit to cover that bank's index. Bank
zero remains reserved even though it counts toward the table capacity.

Generate the same limit and record layout for Action!, assembly, the bootstrap
and host packager from one kernel build configuration. Record them in build
provenance. Initialization, scans and index validation use that limit; a count
or loop bound must represent 256 without wrapping to zero.

Reject invalid build limits and managed-bank/image claims outside the compiled
table before accessing records or writing payloads. The runtime platform map
may expose fewer usable banks than the build supports; those extra table
entries remain unavailable.

### Planned upper-RAM table placement

Implemented for the [eight-task layout](../architecture/task-capacity.md). The table occupies
`4 * MAX_BANKS` bytes at the configured kernel bank's base, 64 bytes by default.
Code starts immediately after it. The prefix is checked against every loaded
extent; the containing bank stays reserved. Bootstrap seeds through the generated
24-bit address and the native manager adopts through far pointers, preserving
all existing claims. This requires no allocator or extra whole bank.

Moving the table releases the complete `$2800–$2BFF` bank-zero reservation.
The capacity pool generator may reuse it for CPU-required DP storage. Raw and
optimized qualification covers kernel banks 1 and 3, seeded state, adoption,
image lifetime and rejected table overlaps. The historical profiles retain the
[bank-zero table map](banked-loading.md#current---tasks-runtime-map); they do not
implicitly acquire the capacity profile's reclaimed ranges.

## Initial operations and invariants

The internal interface provides four ownership operations after boot adoption;
[the implementation contract](banked-loading.md#internal-ownership-interface)
specifies their Action! signatures and statuses:

- Query a bank's availability, state and owner.
- Reserve an exact bank for a system/image owner.
- Acquire a free bank for an owner, with deterministic selection.
- Release a client-owned bank after validating ownership.

Acquisition reports exhaustion explicitly. Invalid IDs, conflicting claims,
double release, wrong-owner release and attempts to release reserved storage
fail without changing ownership. Counts must represent all supported banks
without using zero as an ambiguous overflow or failure result.

An image is its own resource owner when several tasks share its code/data.
Exiting one task must not release that image's banks. The initial kernel and
loaded image reservations remain pinned until launch shutdown. A future heap
may return a bank only after its last allocation is released. Reusable owner
identities must distinguish successive lifetimes.

Ownership updates execute through serialized kernel dispatch under the
existing NMI-safe transition protocol. The interrupt tick hook does not read
or modify bank records. A public service can later use the existing COP `$50`
gateway; bank management does not need another COP signature.

## Loader integration

Use the established Atari XEX staging approach for the initial banked bootstrap.
An ordinary XEX carries a bank-zero copier and successive chunks in a reserved
bank-zero buffer. Each chunk is followed by an `INITAD` segment invoking the
copier, which writes to the chunk's 24-bit destination and returns to the loader.
The final `RUNAD` enters the bank-zero native launcher. Rewrite `INITAD` for
each chunk and consume its count after copying, so an extra callback is harmless.
This requires no extension to the XEX segment address fields.

[GEM4XE's packager][gem-xex] and [65816 copier][gem-farload] implement this
pattern. The inspected revision is `c43cbde10b8942ea44c9086278d9a665ec192a17`.
Its current chunks are compressed; compression is not required for Exec's first
implementation. Exec adapts the loading mechanism to its version-2 compiler
images, reserved memory and AltirraOS transition contract. GEM4XE's linker,
bootstrap addresses and interrupt setup are not Exec ABI definitions.

The current compiler images contain fixed linked addresses. Before copying
or zeroing an upper-bank payload, the loader must validate all its extents
and claim every destination bank for the image. Multiple segments within a
bank share that image claim. An extent crossing a bank boundary claims every
touched bank; bank-zero extents still require range validation.

The host packager and bootstrap use one machine-readable memory map and
reservation description. The bootstrap establishes the reserved ownership
state before copying payloads, and the native manager adopts that state.
This permits the manager's compiled code itself to reside in a reserved upper
bank without depending on an already running native allocator.

A conflicting or unavailable destination rejects the load before payload
writes. Validation failure must not leave partial claims behind. The initial
loader does not relocate a fixed-address image to an arbitrary free bank.
Unloading/reusing live executable storage is a later lifecycle feature.

Runtime file access is a separate adapter concern. GEM4XE's
[`far_read_file`][gem-app] reads through DOS/CIO into a bank-zero buffer and
copies the returned bytes into upper RAM. Exec can use the same transport
pattern through its serialized `COP #$00` OS adapter. Disk filenames require
a resident DOS `D:` handler; the current console-only qualification does not
establish that service. GEM4XE's [G4A application format][gem-g4a] adds its own
relocation metadata; adopting it is not required for fixed-address Exec images.

[Rapidus OS / DracOS][dracos-spec] offers high-memory SIO and `COP #$01`
allocation, discoverable through `@:SYSDEF`. SIO supplies device/sector I/O;
filesystem access still needs a DOS handler. The pinned AltirraOS ROM's
`SysDevData` advertises zero for memory management and SIO extensions, so this
platform must not assume those facilities. A future DracOS adapter must obtain
RAM through the host allocator before treating it as Exec-owned.

Ownership remains a separate requirement even with an existing loading path.
GEM4XE's [compatibility notes][gem-ownership] explicitly leave host `kmalloc`
integration outstanding: finding writable RAM does not establish that it is
free. Exec's image reservations and bank ownership contract address that gap.

## Booting the kernel

The initial deliverable is one XEX containing the bank-zero bootstrap, a build-
generated image manifest, and the kernel payload. Altirra's cold XEX loader is
the first supported launch environment. Loading through a resident DOS uses
the same file mechanism but requires separate memory-layout and I/O qualification.
The ROM starts first; Exec starts as a hosted program loaded into RAM.

Boot proceeds in this order:

1. Load the small bootstrap and manifest into their fixed bank-zero region.
   That region must already be safe in the qualified launch environment; a
   callback cannot retroactively protect memory overwritten while loading it.
2. Invoke an initial `INITAD` setup entry. Check the platform and memory bounds,
   validate the complete manifest against the platform map and `MAX_BANKS`, and
   seed the static ownership table with system and kernel/image reservations.
   Establish the bank-zero reservations before loading the remaining segments.
   This is assembly bootstrap initialization, with no calls into unloaded
   kernel code and no dependency on a heap, scheduler or Exec COP service.
3. Load successive payload chunks into the reserved staging buffer. The copy
   callback validates each destination against those reservations, copies it,
   consumes the chunk, and returns in the host loader's CPU/stack state. OS
   interrupt and I/O operation must remain usable between callbacks. Exec task
   scheduling stays inactive throughout loading.
4. At final `RUNAD`, verify that every required extent, including zero-fill, is
   complete and that no bootstrap error was recorded. Establish the native
   kernel stack and direct page, install the resident interrupt/COP adapters
   through the platform transition protocol, and enter the kernel using its
   compiler ABI and 24-bit entry address. Never enter a partially loaded kernel.
5. The kernel adopts the existing ownership table without clearing its claims,
   initializes kernel services and the initial task contexts, and enables
   scheduling only when all dispatch state is ready.

Keep the OS transition adapters, stacks, direct pages and metadata that require
bank-zero addressing in reserved bank-zero memory. Bulk kernel code and other
metadata can reside in explicitly assigned upper banks, following the
[bank-zero memory budget](../reference/platform.md#bank-zero-memory-budget).
The startup path must distinguish temporary staging storage from
resident state; the first implementation can leave both reserved for the launch
lifetime. Loading independent applications and returning to a DOS prompt remain
later features. Initially, an example can still be packaged with the kernel.

## First executable slice

Implement the fixed inventory and ownership operations, an explicit upper-RAM
platform profile, and XEX bootstrap integration together. The bootstrap must
initialize the ownership table before banked image writes; the native manager
adopts that table as its source of ownership information after loading.

Acceptance must exercise emitted raw and optimized code on the new pinned
profile: reserve/query/acquire/release, exhaustion and unchanged state after
rejected operations, bank-zero exclusion, independent upper-bank storage,
and rejection of overlapping or unavailable image destinations. Run a banked
preemptive example through the existing context/OS boundary checks, including
nonzero PBR restoration. Retain the existing bank-zero qualification profile.
Cover build limits 1, 16 and 256, the final valid index, out-of-range claims,
invalid limits and platform maps with unavailable entries. Verify that table
storage and generated consumers agree on the selected build limit.

Byte-level allocation, dynamic image relocation/unloading and arbitrary
memory-expansion detection follow separate contracts.

[gem-xex]: https://github.com/slaapliedje/gem4xe/blob/c43cbde10b8942ea44c9086278d9a665ec192a17/tools/mkxex.py
[gem-farload]: https://github.com/slaapliedje/gem4xe/blob/c43cbde10b8942ea44c9086278d9a665ec192a17/src/farload.s
[gem-app]: https://github.com/slaapliedje/gem4xe/blob/c43cbde10b8942ea44c9086278d9a665ec192a17/src/sys/app.c
[gem-g4a]: https://github.com/slaapliedje/gem4xe/blob/c43cbde10b8942ea44c9086278d9a665ec192a17/tools/mkg4a.py
[dracos-spec]: https://drac030.krap.pl/en-specyfikacja.php
[gem-ownership]: https://github.com/slaapliedje/gem4xe/blob/c43cbde10b8942ea44c9086278d9a665ec192a17/docs/phase41.md
