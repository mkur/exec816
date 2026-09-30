# Loader and bank/region manager implementation plan

Status: implementation completed; see [banked loading](../history/banked-loading.md) for
the concrete layout, interfaces, build commands and qualification record.
This implements milestone 4 of the [roadmap](../roadmap.md), following the
[bank-manager contract](../history/bank-manager.md) and
[AltirraOS platform contract](../reference/platform.md).

## Outcome and scope

Produce one ordinary Atari XEX that boots Exec816 under the dedicated AltirraOS
65816 ROM. A standalone bank-zero bootstrap establishes memory reservations,
uses `INITAD` callbacks to copy the kernel into upper RAM, and hands control to
the native kernel through a guarded `RUNAD` entry. The running kernel adopts
the bootstrap's bank table and provides checked whole-bank ownership operations.

The first application can remain linked with kernel policy in the same compiler
image. Loading the kernel does not depend on a running allocator, scheduler,
filesystem adapter or Exec COP service. Keep the existing bank-zero examples
and PAL/64K qualification available as a separate profile.

The initial region layer describes physical memory and validates fixed range
reservations. It does not allocate arbitrary byte-sized regions. Byte heaps,
general Lists/task management, relocation, independently loaded applications,
unloading, compression, DOS-prompt return and additional hardware backends are
later work. Resident DOS file loading needs its own qualification; this milestone
uses Altirra's cold XEX loader and the existing OS console adapter.

## Existing implementation to extend

| Location | Current behavior and required change |
| --- | --- |
| [tools/native_program.py](../../tools/native_program.py) | Validates version-2 compiler images against `$6000-$8FFF`, emits only bank-zero XEX segments, and binds the assembly imports. Make validation and packaging use the selected memory profile, retaining ABI/import and entry checks. |
| [platform/altirraos/hosted.s](../../platform/altirraos/hosted.s) | Combines startup, state clearing, native entry and resident OS adapters. Separate load-time setup from final handoff; preserve bootstrap state and reservations. |
| [platform/altirraos/hosted.cfg](../../platform/altirraos/hosted.cfg) and [layout.inc](../../platform/altirraos/layout.inc) | Fix resident assembly at `$3000-$3FFF` and bank-zero stacks/domains elsewhere. Account for bootstrap, manifest, staging and table storage in one checked layout. |
| [lib/exec/execpolicy.act](../../lib/exec/execpolicy.act) and [cooperative.s](../../platform/altirraos/cooperative.s) | Serialize policy on the kernel stack/domain and construct initial contexts. Add internal bank policy calls and a boot initialization path without exposing partially initialized dispatch state. |
| [tools/os_boundary.py](../../tools/os_boundary.py) | Hard-codes zero high banks in isolated emulator settings. Accept an explicit pinned profile and check full execution addresses when testing upper-bank code. |
| [tests/test_native_package.py](../../tests/test_native_package.py) | Protects the existing bank-zero package boundary. Preserve these checks and add separate banked-profile cases. |

Keep the compiler revision and native ABI from
[toolchain/actionc.json](../../toolchain/actionc.json). If a compiler defect blocks
the work, fix it in actionc with focused coverage and update the pin separately;
do not weaken image validation or special-case an example.

## Shared memory model

Use three related descriptions, with explicit ownership of each fact:

| Description | Contents and purpose |
| --- | --- |
| Platform memory map | Usable native RAM, absent/aliased/excluded ranges, bank-zero OS constraints, and the exact emulator profile. Addressability alone never means available RAM. |
| Region reservations | Base, length, purpose and owner for bootstrap, manifest, staging, resident adapters, metadata, stacks/direct pages, buffers and image initialized/zero-fill extents. Validate exact ranges and lifetimes. |
| Bank ownership table | One four-byte record per bank index: state/flags, reserved byte, 16-bit owner. The runtime authority for complete upper-bank claims. |

`MAX_BANKS` is a kernel build parameter in `1..256`, default 16, including bank
zero. Allocate exactly `4 * MAX_BANKS` table bytes in a reserved bank-zero
region: 64 bytes at the default. The limit bounds bank indices; it does not
enable RAM. Holes remain unavailable. A higher-numbered usable bank requires a
limit covering its index, even on a machine with little installed RAM.

Bank zero is reserved for system use and excluded from whole-bank acquisition.
Its individual ranges still need overlap and ownership validation. Initially,
partially usable upper banks are unavailable for image placement and acquisition.
Normalize all image extents into one claim per touched bank. Disjoint segments
of one image can share a bank; different owners cannot share that bank in this
first implementation. An image shared by tasks owns its banks independently of
those tasks, and its reservations survive either task's exit.

Use half-open ranges for validation. The host can use integer base/end values;
target code must handle bank/offset carries explicitly. A 64 KiB length must
not become zero in a 16-bit field, and the end of bank `$FF` is `$1000000`, which
does not fit a 24-bit address. Validate before narrowing or indexing. Use
16-bit counts/indices wherever 256 must be representable.

## Implementation sequence

Each stage is a reviewable change with its own acceptance check. The complete
milestone depends on all six stages; passing a model or a bank-zero fixture
does not qualify the banked kernel.

### 1. Define generated layout and qualify an upper-RAM profile

Add a machine-readable memory ABI, kernel build configuration and platform
memory map. Proposed new files are `abi/memory-v1.json`, `config/kernel.json`,
`platform/altirraos/memory-*.json` and `tools/generate_memory.py`. Keep state
codes, record fields, errors and boot wire layouts in the ABI; put `MAX_BANKS`
and bounded manifest/staging capacities in build configuration. Resolve physical
addresses from the selected platform map and assembly/linker layout.

Generate Action!, assembly and host-readable definitions into each build's own
directory. Different `MAX_BANKS` builds must not overwrite each other's includes.
Resolve the compiler entry/import addresses into the final manifest after
linking. As with the current packager, verify that final assembly has not shifted
already bound imports. Record configuration, ABI, generated-layout and artifact
hashes in build provenance.

Add an upper-RAM qualification pin alongside `toolchain/altirra.json`, keeping
its ROM and emulator hashes unless a demonstrated limitation requires a change.
Start with a profile intended to cover the default `$00-$0F` address span;
verify actual enabled banks and exclusions before declaring them usable. Do
not assume an emulator setting counts banks in the same way as `MAX_BANKS`.
Generalize isolated emulator settings/profile selection without changing the
existing default. Audit breakpoint/address helpers for nonzero PBR handling.

Choose concrete bank-zero addresses only after checking linker sizes and all
existing state, stack, DP, guard, OS and console reservations. The bootstrap and
manifest must fit memory already safe at initial load; an `INITAD` check cannot
undo a collision incurred while loading itself. Check the largest table build
and reject any configuration whose table/manifest cannot fit.

Acceptance: generator rejects invalid limits and overlaps; generated consumers
agree on record size and addresses. An isolated target probe verifies writable,
independent RAM in the new profile, including alias checks and untouched OS
regions. Memory probing is a qualification experiment, not startup writes to
unknown addresses. Existing PAL/64K profile selection remains reproducible.

### 2. Implement internal bank ownership policy

Add an Action! module, proposed `lib/exec/execmemory.act`, consuming the generated
record layout. Keep the initial interface internal to kernel policy:

| Operation | Required semantics |
| --- | --- |
| Query | Bounds-check the bank ID; return state and owner without mutation. |
| ReserveExact | Validate the owner and reserve a free complete bank for a pinned system/image lifetime. Repeated segments are coalesced before this operation. |
| Acquire | Choose the lowest eligible free bank deterministically and mark it client-owned; report exhaustion separately from the returned bank number. |
| Release | Accept only a client-owned bank with the matching valid owner; clear ownership and return it to the free state. |

Define explicit statuses for invalid bank/owner, unavailable/reserved storage,
conflict, wrong owner and exhaustion. Failures leave table contents unchanged.
ReserveExact requires a free bank; repeat reservations return an error rather
than silently changing ownership. Initialize the padding byte deterministically.
Use static, validated owner IDs for this launch; zero means no owner and IDs
are not recycled. Reusable owner lifetimes need a later generation scheme.

Provide a kernel adoption check for the bootstrap table's version, size,
initialization state and manifest identity. Adoption must not clear claims.
Execute all runtime operations in the existing serialized dispatch context;
the NMI hook neither inspects nor mutates the table. No additional COP signature
or public memory service is needed in this milestone. Test entry points can
call the module from controlled kernel context.

Acceptance: a small emitted Action! fixture exercises these operations in raw
and optimized modes, without adding the whole manager to the nearly full
current cooperative image. Cover owner errors, exhaustion, bank zero, holes,
indices around the configured limit, release/reacquire, and immutable reserved
banks. Compare complete table snapshots on rejected operations. Use synthetic
inventories for index-255/count-256 policy cases; do not equate them with physical
qualification of every native bank.

### 3. Implement manifest validation and staged XEX packaging

Refactor image validation to use the selected region map, preserving existing
checks for version, ABI, imports, executable entry, writable code, overlap and
bounded input sizes. Keep the old profile's rejection of upper-bank placement.

Define a bounded boot manifest with version/layout identity, `MAX_BANKS`, owner
records, fixed destination extents, COPY/ZERO operations, expected byte counts,
and the kernel's 24-bit entry. Serialize it from validated compiler segments
and zero-fill records. This is private bootstrap metadata inside ordinary XEX
segments, not a new DOS executable format or a replacement compiler image ABI.
Specify every wire field's width and maximum before implementing its parser.

Emit the bootstrap/manifest first, a setup `INITAD` trigger, then staging records
and a copy `INITAD` trigger after every record. End with the guarded `RUNAD`
entry. Keep literal XEX segments within the bootstrap/manifest/staging and
vector ranges approved by the layout; managed image bytes, including bank-zero
image data, go through the validated callback path. This prevents later literal
segments from bypassing bootstrap destination checks.

Use uncompressed, bounded chunks. Split transfers at destination bank boundaries
and staging capacity; represent larger extents through multiple chunks. ZERO
records advance the same validated cursor without carrying a full zero payload.
Give each record an extent identity and position/count that can be checked
against the expected sequence. Initialize the pending count before callbacks,
and clear it after consumption. An extra callback with no pending data is a
no-op; a replayed, reordered or overlapping record is a failure.

Acceptance: host tests interpret the produced XEX under both callback patterns
(every segment versus explicit INITAD updates), reconstruct exact initialized
bytes and zero-fill, and compare against the compiler image. Cover multiple
segments per bank, boundary splits, holes, conflicting owners, overflow, bad
entry/imports, oversized manifests, and attempts to overwrite loader/state.
Publish `program.xex` only after complete validation and final assembly.

### 4. Implement the standalone bootstrap and copy callbacks

Add bank-zero assembly, proposed `platform/altirraos/loader.s`, with separate
setup, consume-record and guarded-start entries. Use the GEM4XE mechanism
referenced in the [contract](../history/bank-manager.md#loader-integration); adapt it to
Exec's layout and OS boundary rather than importing its hardware setup.

Setup validates the complete manifest and platform bounds before committing
image claims or writing payloads. Preflight every touched bank, then seed the
table and publish its initialized state only after the whole reservation pass
succeeds. This assembly path initializes fixed storage and never calls unloaded
Action! code. Save the original host memory reservation once, and define which
boot state survives into normal/fault shutdown.

Keep a bounded boot-state record separate from memory the current launcher
clears: manifest identity, expected extent/cursor, completion and first error.
On each callback, validate the next record before any destination write, perform
the COPY/ZERO, then update progress and consume it. Once an error is recorded,
later callbacks must not write payloads or permit kernel entry. Failed loads
remain terminal for that launch; retry and allocation rollback after a partially
copied image are outside this milestone.

Preserve the loader's live return stack and required CPU/DP/bank state on every
callback. Prefer an emulation-mode copy loop using 65816 long addressing, so
normal OS loader interrupts can continue. Any native-mode helper requires an
explicitly tested transition; never invoke the existing launcher per chunk or
reset the host stack while its loader frame is live. IRQ masking alone cannot
protect against NMI. Scheduling stays disabled, and callbacks must return with
the host interrupt/I/O environment usable.

Make the bootstrap's default start address and RUNAD path check completion, so
a load that stops after the bootstrap cannot accidentally enter kernel code.
Guarded start requires all extents, including BSS, complete and no recorded error.
Distinguish failures handled by the XEX loader from errors reported by our
callback; do not assume an INITAD return value aborts every host loader.

Acceptance: actual emitted assembly transfers a fixture to upper RAM and zeros
its BSS with intact source/destination guards. Inject real VBI and IRQ activity
during callback work and between records. Exercise redundant callbacks, malformed
records, unavailable destinations, incomplete loads and early RUNAD. Verify
return-stack preservation, bounded termination, no post-error writes and no
kernel-entry marker on failure. A host Python model alone is insufficient.

### 5. Boot the banked kernel and adopt reservations

Split final native initialization from bootstrap setup in `hosted.s`. Preserve
the published bank table, boot diagnostics and original MEMLO; existing bulk
state clearing and repeated initialization must not overwrite them. Establish
the kernel stack/DP and install resident COP/NMI/IRQ adapters under the existing
transition protocol before calling compiled kernel initialization. Keep task
dispatch disabled until all kernel and task state is ready.

Compile bulk kernel policy and the first example into explicit upper-RAM code
regions using the existing version-2 image layout. Retain the assembly adapters
and OS-visible buffers in bank zero. Keep the current console pointer contract
for this milestone; place its data in the existing permitted arena and reject
far console buffers as before. Do not assume the staging buffer automatically
becomes a valid console buffer.

Bind the actual kernel initialization, dispatch and task entries through the
build output and validate their native calling conventions. Use full 24-bit
addresses for far calls and saved contexts. Audit initial synthetic frames,
return paths and test breakpoint comparisons for bank-zero assumptions. Kernel
initialization adopts the existing claims, creates the existing initial task
contexts, and enables scheduling only at the established safe boundary.

Initially retain bootstrap/staging reservations until launch shutdown. Record
which bytes are resident so later reclamation cannot free the bank table or OS
adapters. Preserve the existing controlled termination behavior; do not add
general task creation, an idle-task redesign or independent image loading here.

Acceptance: a kernel entry in a nonzero bank observes the exact bootstrap claims,
performs bank operations and starts the banked preemptive example. Both tasks
progress without yields, print through COP `$00`, and exit with image banks
still reserved. Verify nonzero PBR restoration, all relevant M/X combinations,
DBR/D/S preservation, locks/pending delivery and OS interrupt coexistence.

### 6. Consolidate qualification and reproducible build instructions

Add host boundary tests, target fixtures and a bounded target runner, proposed
`tools/test_banked.py`. Match the existing `--compiler-dir`, `--bridge-dir`,
`--rom` and `--case` conventions; add explicit profile/config selection to the
builder and runner. These new interfaces are deliverables, not existing commands.

Record accepted runs in a new `docs/qualification/banked-loading.json`, with
compiler/ROM/emulator identities, generated configuration and memory map hashes,
optimization mode, image/XEX hashes and per-case results. Update the bank-manager
and launch contracts, README and roadmap with actual limitations and commands.
Keep the old qualification records tied to their original profile.

Run the focused checks below as their stages become executable. Because final
integration changes shared startup, packaging and emulator configuration, run
the existing hosted, cooperative and preemptive suites once on the completed
change, in addition to the new banked suite. Repeat passing suites only when
further changes or unresolved failures justify it. No repository-wide compiler
suite is required unless compiler behavior changes.

## Acceptance matrix

| Area | Required evidence |
| --- | --- |
| Build limits/layout | `MAX_BANKS=1,16,256`; invalid 0/257; exact table size; final valid index and out-of-range ID; unavailable holes; no overlap with guards, stacks, OS or bootstrap. |
| Ownership | Reserve/query/acquire/release; deterministic allocation; exhaustion; invalid/stale-for-this-launch owner; wrong-owner/double/reserved release; failures preserve complete table; shared image survives task exit. |
| Region/image validation | Disjoint segments sharing one owner/bank; cross-bank data; conflicting image owners; initialized/BSS overlap; endpoint and length overflow; forbidden bank-zero ranges; entry/import checks. |
| Bootstrap execution | Multiple chunks and zero-fill; both callback patterns; CPU/stack restoration; real interrupt delivery; replay/order/count errors; missing final chunk; guarded RUNAD; no entry after failure. |
| Native integration | Raw and optimized emitted code; nonzero PBR at interruption and dispatch; register widths and D/DBR/S; intact guards; serialized COP `$00` console; pending preemption delivered after protected transitions. |
| Regression/provenance | Existing PAL/64K hosted/cooperative/preemptive suites; isolated emulator settings; pinned inputs; recorded complete map/layout; bounded execution and reproducible output. |

Use the existing Python unittest discovery and ABI-generator check conventions.
Add the new generator's check mode and target runner to documented validation.
Normalize host text before newline-sensitive fixture processing and exercise LF
and CRLF through that parsing path; preserve exact XEX/ATASCII bytes.

## Completion criteria

The milestone is complete when a reproducibly built XEX boots the banked native
kernel through INITAD/RUNAD, bootstrap and kernel agree on region/bank ownership,
invalid operations and incomplete loads fail as specified, and the acceptance
matrix passes with a committed qualification record. Exact bootstrap addresses,
chunk capacity and wire layouts are fixed by stage 1 and checked thereafter;
they must not be inferred independently by the packager, assembly and Action!
code.

## Implementation decisions

The implemented fixed-image bootstrap compares the external manifest with an
embedded expected copy assembled after host preflight. It does not contain a
general manifest parser. Runtime staging validation uses those bound descriptors.
The pinned bridge exposes only a 16-bit PC, so tests rendezvous in bank zero
and exercise native PBR restoration with actual bank-2 probe execution. The
MAX_BANKS=256 policy test required a compiler correction: native absolute array
addresses must remain typed native pointers in NIR. The compiler pin includes
that correction and its focused verifier and emitted-execution regressions.
