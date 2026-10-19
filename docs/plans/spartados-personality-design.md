# SpartaDOS personality for 6502 applications

[Implementation plans](README.md) · [Open roadmap](../roadmap.md) ·
[Platform contract](../reference/platform.md) ·
[Static input audit](spartados-personality-inputs.json) ·
[Implementation plan](spartados-personality-implementation-plan.md)

Status: proposed, 18 October 2026. The milestone sequence is **MD5 → ARC →
Sparta Commander**. Binary headers, allocations and imports have been inspected;
execution under Exec816 remains to be established.

The [patch infrastructure record](../development/sdx-patches.md) now documents
native CRC32 identification and patch transactions plus executable component
tests. This has not yet enabled either application as an Exec Process.

The execution model uses emulation mode and version-specific load-time patches.
MD5's indexed zero-page wrapping rules out the earlier native-mode proposal.
The [emulation-mode experiment](../experiments/emulation-preemption.md)
demonstrates NMI-driven native entry and guest restoration despite `SEI`;
production IRQ/NMI, page-one ownership and application execution still need
the gates in the implementation plan.

## Goal and scope

Run useful existing SpartaDOS X applications as ordinary Exec Processes, with
independent state and preemptive scheduling alongside native commands and GEM
applications. Prioritize the original 6502 binaries and preserve their code
where the execution model permits it. Source availability is helpful for
diagnosis but is not an admission requirement.

The first supported subset consists of well-behaved applications using OS and
SDX services. Hardware access, replacement interrupt handlers, disk drivers,
formatters, repair tools and programs that take over the machine are outside
scope. A filename ending in `_816` does not establish compatibility: the
inspected SDX 4.50 MD5_816 switches between native and emulation modes while
retaining the legacy SDX imports. Native 65816 variants and SHA256 are separate
future candidates, not prerequisites for this sequence.

The implementation will execute selected 6502 instruction streams directly in
65816 emulation mode, with small audited adaptations where the address layout
or interrupt behavior differs. It does not begin with a CPU interpreter or
dynamic binary translator. Correct behavior depends on an instruction and ABI
audit of each admitted binary. This is the same single-user, unprotected
execution model as Exec; admission checks do not make arbitrary code safe.

## Existing system boundary

Exec's [SpartaDOS support](../reference/spartados.md) implements the filesystem,
not the SDX executable format, symbol library or Atari CIO interface. Existing
[program loading](../reference/program-loading.md) provides native o65 and C
image lifetimes. Add an SDX format handler and execution adapter while retaining
one Task API, the existing Program/Process ownership model and ordinary DOS and
device operations.

Follow the Amiga Exec model already used for scheduling, signals, messages and
device requests. The personality translates application conventions; it does
not introduce a second scheduler or move device policy into the kernel.
New filesystem or console capabilities must have reusable public interfaces.
Compiler defects belong in actionc and CPU emulation defects in actionc-vm.

## Initial application inputs

The [input audit](spartados-personality-inputs.json) records distribution URLs,
SHA-256 hashes, archive paths, module hashes, imports, exports and declared
allocation blocks. It contains no third-party executable payloads and no
runtime qualification results.

| Target | Frozen distribution | Initial behavior |
| --- | --- | --- |
| MD5 | SDX 4.50 toolkit, `UTILS/FILEUTIL/MD5.ARC`, ordinary `MD5.COM` | Hash named files, then verify checksum lists |
| ARC | SDX 4.50 Maxflash 1 Mbit cartridge, `ARC.COM` and three overlays | List, decode, extract, then create and modify archives |
| Sparta Commander | SDX 4.51 toolkit, `SHELLS/SC111.ARC`, version 1.1.1 | Browse two panels, then file operations and command execution |

The versions are intentional per-application baselines, not a claim to support
all of either SDX release. SDX 4.51 packages MD5 differently, with CPU-specific
overlays; it must receive a separate audit before replacing the standalone 4.50
fixture. Bind behavior against the documented SDX interfaces and the pinned
programs' actual use of them.

| Module | File bytes | Declared code, data and BSS bytes |
| --- | ---: | ---: |
| `MD5.COM` | 3,488 | 4,727 |
| `ARC.COM` | 3,203 | 6,764 |
| `ARCLST.OVL` | 1,998 | 1,714 |
| `ARCEXT.OVL` | 1,911 | 18,892 |
| `ARCADD.OVL` | 4,645 | 24,586 |
| `SC.COM` | 1,246 | 1,073 |
| `SCMAIN.OVL` | 15,866 | 18,157 |
| `SCBATMAN.OVL` | 1,228 | 903 |

These sums exclude alignment, runtime allocations, the compatibility image and
bank-zero resources. ARC's main module plus its add overlay declares 31,350
bytes; main plus extraction declares 25,656 bytes. A private 64 KiB bank is
plausible, but peak live allocations and overlay lifetimes must be measured.
Extra machine RAM does not enlarge an application's 16-bit near address space.

## Execution and address layout

Give each guest Process a private, bank-aligned 64 KiB upper-memory image.
Use the existing memory ownership machinery, respecting reserved platform
banks and recording any allocation padding. Start with `E=1`, which enforces
eight-bit accumulator/index operation, and `PBR=DBR=guest_bank`. The guest
uses a private aligned direct page in bank zero. Its active emulation stack
occupies physical `$0100–$01FF`; its suspended 256-byte stack image lives in
upper RAM. Native services use the existing guarded native Task stack.

Absolute JSR/JMP remain within the program bank; ordinary absolute data
accesses use DBR. Direct-page operations use D in bank zero. This permits much
6502 code and its data to reside above bank zero, but it does not reproduce all
6502 addressing behavior. The executable audit must cover:

| Assumption in a binary | Required treatment |
| --- | --- |
| Direct-page and absolute accesses to the same low address | They address different physical storage in this layout. Establish consistent use or an explicit adaptation. A copied page in upper RAM is not an alias. |
| `JMP ($addr)` and indirect DOS return vectors | The pointer fetch uses bank zero. Classify each use; private-bank copies do not redirect it automatically. |
| Zero-page indexing or pointers wrapping at `$FF` | Use emulation mode with page-aligned D and verify the exact addressing forms. |
| `TSX`/`TXS`, `$0100,X` stack accesses or stack relocation | The stack is in bank-zero page one; absolute references still use DBR. Adapt explicit accesses where necessary and bound stack depth. |
| `PLP`, decimal arithmetic, undocumented opcodes or mode changes | Audit CPU semantics and every status restore. Admit IRQ-enabled guest computation; arbitrary mode changes, undocumented NMOS opcodes and unreviewed IRQ masking are unsupported. |
| Near buffers, self-modifying code and computed calls | Keep valid extents within the guest layout; include modified code and indirect targets in the audit. |

The [WDC datasheet](https://www.westerndesigncenter.com/wdc/documentation/w65c816s.pdf)
is the CPU reference. Import tables establish dependencies, not absence of
hardware access or compliance with these restrictions. Do not identify and
rewrite instructions by scanning arbitrary bytes for opcode patterns.

Select the patch manifest by original file size and CRC32 at load time,
including every admitted overlay. Host preparation retains SHA-256 input pins;
the target loader does not need a cryptographic hash implementation. CRC32
provides version/corruption screening, not collision-proof identity. Reject
ambiguous selectors and check exact patch preimages, relocation intersections
and replacement extents before publishing executable state.
Use same-bank replacements to preserve near calls and known guest PBR; keep
the original files unchanged. Record patch identities and behavioral tests.
Unknown versions need an audit, not a best-effort opcode scan.

ARC's internal helper needs both real-stack access and consistent direct-page
stores. MD5's compression `SEI` is a candidate for replacement by `NOP`, subject
to interrupt-enabled correctness tests. These are compatibility adaptations,
not compiler defects. The implementation plan defines the patch transaction
and first known sites; it does not claim that this list completes the audit.

## Private OS image and service entry points

Provide the application's expected low-memory OS/SDX variables and standard
OS entry addresses within its private address layout. The proposed starting
point allows a copy of the pinned AltirraOS ROM in the private bank, with
supported entry points patched to native compatibility veneers. This preserves
familiar addresses; it does not make the copied ROM reentrant or authorize
execution of its hardware routines.

Implement only the services reached by the admitted applications. Audit internal
ROM calls and computed entry points before admitting them; unspecified ROM
internals are unsupported. Mutable OS state, file-control data and SDX library
variables belong to the guest. Direct-page variables require the explicit
mapping described above rather than a second unsynchronized copy.

SDX calls need an additional layer: bind imported names to guest-local veneers
or data, not merely to CIO vectors. Preserve each service's register, status,
buffer, handle and error conventions. For example, PRINTF must interpret its
inline arguments and return address using the guest calling convention.

Record implemented symbol contracts, data offsets and error mappings in
machine-readable ABI definitions and generate shared assembly/Action! constants.
The static input audit is a dependency inventory, not the runtime ABI definition.

Veneers translate guest near pointers to the appropriate physical storage;
ordinary upper-memory buffers become `guest_bank:offset`, with separate handling
for direct-page and stack storage according to audited API/call-site semantics.
PRINTF pointers to MD5 digest bytes in zero page need this translation too.
Never truncate far pointers when calling native or
real OS services. File payload bytes are unchanged. Translate ATASCII at text
device boundaries: the [native console](../reference/console.md) does not treat
`$9B` as newline or high-bit text as inverse video.

Use native DOS and devices for files, console and input. Any necessary real ROM
call goes through the existing serialized OS adapter. Keep `COP #$50` as the
Exec gateway, preserve AltirraOS `COP #$00`, and leave `$80–$FF` unused by Exec.
There is no need to load the original SDX kernel, cartridge mapper or drivers.

## Task context and interrupt safety

Guest direct-page use cannot overwrite Exec's native DP metadata. The
[current DP layout](../../abi/native-dp.json) reserves compiler scratch and
owner/domain/stack fields above the caller workspace. The initial design keeps
that native DP intact and provides a separate complete 256-byte guest page.

Before guest dispatch, publish an adapter-owned association between the current
Task, guest DP, native DP/stack, page-one image, guest code bank and executable
image. Interrupt entry must identify and save a guest context without
interpreting guest bytes as native metadata. Existing foreign-frame exclusions
do not automatically admit this context; extend classification and restoration
explicitly, including transition instruction ranges.

Each guest-local veneer saves context before touching native scratch and enters
native mode before transferring to another code bank. It switches to the native
Task stack/DP and releases page-one ownership before blocking or OS entry.
On return, a trampoline in the guest bank re-enters emulation mode. Emulation
interrupt frames omit PBR, so interrupt return must explicitly restore the
recorded code bank before RTI. Preserve the full accumulator including hidden
B, status, banks, D and S wherever the guest ABI requires it.

Use the platform's [SWITCHING and OS-call protocol](../reference/platform.md#vbi-preemption)
across partial saves, DP/stack changes and returns. SEI alone cannot protect
against NMI. Save/restore the complete guest and displaced host page-one images
when ownership changes; snapshots live in upper RAM. Pure computation must be
preemptible, and blocking native I/O must leave no live kernel/ROM activation
behind. Two guest slots share the physical page-one window by scheduling.

Production guest computation keeps IRQs enabled. NMI reclamation despite SEI
does not establish timely device service. Route emulation IRQ/NMI with correct
banks before any DBR-sensitive ROM access, preserve normal VBI work, and prove
serial/timer/input latency. The experiment's private D40F byte is not a
production solution. Short device IRQ handlers should retain page-one ownership
and avoid copying its full image at every high-frequency edge. Nested NMI must
defer ownership changes across that live interrupt activation.

Error traps and DOS exit paths must restore the native domain before cleanup.
Nonlocal guest error returns may unwind only their own guest/load-level frames.
There is no global zero-page swap on every context switch; each guest keeps its
own D page. Page-one ownership changes are explicit, guarded transitions.

Latch BREAK for the owning Process and translate it at supported service
boundaries. Cancellation latency includes the guest's longest computation
between those boundaries; measure that interval for each target. Preempting a
loop does not by itself make the loop respond to BREAK. Original guest code
also lacks compiler-inserted stack checks: retain native checks, verify bounds
at adapter boundaries and inspect canaries without claiming memory protection.

## Loader and process state

Implement the standard SDX relocatable blocks, BSS, alignment, fixups, imports
and exports needed by the frozen inputs. Validate file bounds, relocation sites,
patch preimages/intersections, layout overlap and resource requirements before
publishing an executable image. Apply replacements after ordinary relocation
using the transaction defined in the implementation plan.
The [SDX programming guide](https://sdx.atari8.info/sdx_files/4.50/SDX450_Programming_Guide.pdf)
defines those records and load-level semantics. Other executable formats and
extended-memory segment types remain unsupported until required and tested.

Resolve required imports eagerly. A staged milestone may bind a deliberately
unsupported operation to a defined failure veneer, but it must not silently
pretend success. Keep a supported-service list for the exact build. Exported
symbols are scoped to their guest and nested load level; two ARC instances
must never share the `_ARC` binding or mutable overlay state.

`U_LOAD` validates and patches each overlay before loading it into the caller's
executable scope, with nested allocation, symbol and error-trap lifetimes.
Provide `CAR:` as a read-only
virtual device backed by the pinned support files, so ARC's embedded overlay
paths resolve without cartridge hardware. Reclaim an overlay only after its
calls, pointers and pending I/O have retired. Measure actual overlay reuse
rather than assuming all modules can be freed immediately on return.

Each guest Process owns its handles, command-line state, error traps and
nested-load records. A top-level SDX launch also owns a session containing its
environment and virtual current directory. Keep this state in upper RAM. The
session survives a Commander overlay unload/reload and is independent of
another top-level launch. `FCLOSEAL` and related cleanup honor the owning
load level, including files retained by its caller.

For Commander, implement a bounded `XCOMLI` command subset with synchronous
child execution through the existing Process start/wait/collect lifecycle.
Each child has a separate image, stack, DP and symbol/load-level scope while
the parent's image remains retained. Subordinate commands share the session's
environment and virtual current directory while the parent waits, so changes
are visible on return. Synchronize native directory references at dispatch and
directory changes, and inherit streams through the existing ownership rules.
Use existing foreground/input handoff. Background SDX shell syntax and general
batch-language compatibility are outside the first Commander milestone.

Admission failure unwinds allocations before exposing the guest. Normal exit,
BREAK and operational errors close owned files and retire overlays, symbols,
console/input ownership and the image. Drain or collect outstanding native I/O
before releasing its guest buffers. Cleanup runs in retained native code and
respects the existing Process retirement acknowledgement.

## Filesystem and console semantics

Translate SDX drive/device names, path separators, masks, attributes and errors
at the personality boundary. Map `NUL:` to the native NIL service. Do not change
the [SpartaDOS filesystem contract](../reference/spartados.md) merely to make one
application's wrapper convenient.

The [write contract](../reference/filesystem-writes.md) already provides create,
read/write, seek within EOF, deletion and same-parent rename. Preserve partial
transfer counts and terminal Close errors. The following gaps affect acceptance:

| Existing behavior | Consequence for the personality |
| --- | --- |
| New SDFS timestamps are zero; no SetFileDate | Exact ARC timestamp restoration and useful date-based update/freshen need a general metadata API. |
| No SetProtection | Commander's CHMOD operations cannot be claimed until a general implementation exists. |
| Exclusive writable-file ownership; rename cannot replace an existing object | Audit ARC's rewrite/backup sequence and simultaneous opens. Do not promise atomic archive replacement. |
| Mutation invalidates enumeration cookies | Translate SDX enumeration semantics explicitly, using bounded snapshots or a defined restart strategy where needed. |
| No seek beyond EOF, sparse creation or cross-directory rename | Return the appropriate unsupported/operational result or use an explicitly supported copy/delete operation. |

ARC temporary and backup paths must also be audited for collisions between
instances. Preserve native conflict errors; do not claim safe concurrent
modification of the same archive. Missing metadata capabilities must be visible
in the supported-command subset, not reported as successful no-ops.

Sparta Commander's installation instructions specify display access through
`_RAWCON`, with an 80-column screen. Implement that software interface over an
owned Exec text view, including the required cursor, character, attribute and
keyboard behavior. An existing stream console is not by itself a complete
`_RAWCON` implementation. Preserve focus and BREAK routing between windows;
VBXE or ANTIC register emulation is unnecessary for this display interface.
The [SDX user guide](https://sdx.atari8.info/sdx_files/4.51/SDX450_User_Guide.pdf#page=274)
describes the driver-based display requirements. Other Commander code still
requires the same instruction audit as MD5 and ARC.

## Memory budget

This documentation change adds **0 fixed and 0 per-Task reserved bank-zero
bytes**, including guards, alignment and unused capacity. The following is a
proposed implementation budget, not an achieved allocation result:

| Resource | Proposed ownership and accounting |
| --- | --- |
| Guest image | One private 64 KiB upper bank per loaded guest Image, including patches, veneers, private OS layout and unused address space; count allocator backing/alignment slack in full. |
| Guest metadata and transfer staging | Bounded upper-heap allocations, measured per guest or shared service as appropriate. |
| Native DP and stack | Reuse the admitted Task's existing guarded reservation; do not enlarge it without measured justification. |
| Guest DP | Two aligned 256-byte pages: 512 fixed reserved bank-zero bytes in enabled builds, including idle slots. Each guest uses one slot; do not double-count it as a per-Task reservation. |
| Physical guest stack | Existing 256-byte OS page one, with explicit ownership: zero additional bank-zero reservation. |
| Stack images | 256 upper-RAM bytes per guest plus one 256-byte displaced-host image; native stack reservations are unchanged. |
| Fixed adapter storage | Target zero additional bank-zero reservation; prove code fits existing reservations or report and justify growth. |

The [bank-zero budget](../reference/platform.md#bank-zero-memory-budget) and each
build's `memory.json` remain authoritative. If guest pages come from a fixed
pool, count the entire reserved pool even while slots are idle. Account for
alignment, any guards and retained capacity, and keep per-guest costs separate.
Do not consume bootstrap memory before its retirement or assume all Task slots
are available to guests in a desktop build. Stack and NMI headroom must include
both guest code and native veneers.

## Executable milestones

### Foundation

Freeze the binary and machine inputs, produce an instruction/entry-point audit
and patch manifests, and implement the loader and emulation/native transition.
Start with small emitted probes before running MD5. Exercise every
context-transition boundary with IRQ/NMI entry, full register restoration,
guest/native DP isolation,
stack guards, allocation failure and repeated start/exit. Include a compute
loop making no service calls to establish actual preemption.

Admission requires bounded completion, real device IRQ service, page-one
ownership and clean OS/native Task coexistence.
Record supported operations and unresolved instruction sites. The copied OS
image and SDX library must not mask missing entry points by falling through
into uncontrolled ROM execution.

### MD5

First validate the candidate SEI patch with interrupts enabled. The frozen
binary imports 14 symbols: `COMTAB`, `FCLOSE`, `FCLOSEAL`, `FGETC`,
`FILE_P`, `FOPEN`, `FREAD`, `PRINTF`, `TOUPPER`, `U_FAIL`, `U_GETATR`, `U_SFAIL`,
`U_SLASH` and `U_XFAIL`. Implement their actual used conventions, including
command parsing and error unwinding. Begin with named-file hashing; then add
multiple specifications, attribute/mask behavior and `/C` verification. The
hardware screen-off `/H` option is unsupported.

Acceptance compares digest bytes against an independent host implementation
for empty files, lengths 55/56/63/64/65, binary contents and streamed files over
64 KiB. Cover missing files, read errors, checksum mismatch, BREAK and recovery
to a usable caller. Text fixtures distinguish ATASCII, LF and CR/LF without
altering binary bytes.

The first application milestone is complete when two MD5 instances produce
correct independent results while a native Task continues to progress, with
guard/context checks, no leaked ownership and bounded cancellation. This
remains MD5 acceptance, not a general SDX compatibility claim.

### ARC

The four modules import 36 distinct names, including the internal `_ARC` export;
35 are external dependencies and 11 overlap MD5. Extend the shared service
layer for overlays, seek/tell, writes, enumeration, console input and arithmetic.
Trace the listing overlay's `__MISC` dependency before claiming listing support.

Deliver ARC in three executable steps:

1. `L` and `V`: load the listing overlay, traverse headers and display correct
   entries and totals. Cover masks, empty archives and malformed/truncated input.
2. Decode to `NUL:`, then `X`/`E` to files: exercise stored, packed, squeezed
   and crunched fixtures, CRC failures, destination errors and overwrite prompts.
   Compare extracted bytes with independent reference results. Paths requiring
   timestamp restoration wait for the public metadata operation; do not silently
   discard timestamps.
3. `AS`, then `A`: create stored archives before compressed ones, verify them
   with an independent decoder and compare original/extracted hashes. Add
   rewrite/delete/backup operations only after their file-lifetime and failure
   sequences are established. Date-dependent `U`/`F` and source-deleting `M`
   require their own acceptance cases before being advertised.

Use fixtures from original SDX ARC where another decoder does not implement an
Atari-specific method. Exercise disk full, failed Close, cancellation during
write/finalization, same-archive conflicts and independent concurrent instances.
Exclude screen-off `H`; encryption is a later explicit subset decision. Do not
infer support for an undocumented test command from other ARC implementations.

### Sparta Commander

The inspected modules import 52 distinct symbols. Extend the shared personality
for environment and directory state, free-space queries, directory mutations,
load levels, command execution and `_RAWCON`. Keep the first executable slice
to a working 80-column view with two panels, navigation and correct selection.
Then add copying, renaming, deletion and directory creation; expose unsupported
attribute operations honestly until their native service exists.

Finish with external command launch and return, overlay reload, retained panel
state, keyboard focus, BREAK and ordinary error dialogs. Launch the already
accepted MD5 and ARC through Commander. Verify persisted bytes independently,
continue native Task progress, and test two independent guest sessions where
the configured Task and memory capacity permits. Unqualified games, drivers
and hardware-owning applications remain outside the launch subset.

## Validation and completion records

Follow the [two-tier testing policy](../contributing/testing.md). This note needs
content/link checks only. Implementation slices use host checks and focused
optimized emitted-code tests, with small raw/optimized probes for changed ABI,
layout or compiler-facing transitions. Interrupt and ownership changes require
targeted deeper cases; full release matrices remain a separate activity.

Before executing compatibility cases, record the actual compiler revision from
[actionc.json](../../toolchain/actionc.json), application hashes, pinned AltirraOS
ROM and exact emulator/machine configuration. The existing
[desktop platform pin](../../toolchain/altirra-gem-vdi.json) is a starting input,
not evidence that guests already work. Run original-SDX behavior controls on a
separately recorded configuration, with identical file fixtures.

For every accepted slice, record supported commands/services, adaptations,
remaining limits, test inputs/results, stack peaks, reserved bank-zero delta,
upper-memory use and measured scheduling/cancellation behavior. No compiler
test or static import audit alone qualifies hosted execution.

Publish supported behavior in reference documentation only after executable
acceptance. Any later demo refresh must use `tools/build_demo.py`, retain OF816
and the five-second standard autoboot, and follow the existing package rules.
Distribute guest binaries only with their applicable redistribution terms and
notices established; source access and binary redistribution are separate
questions. The design does not depend on obtaining unpublished sources.
