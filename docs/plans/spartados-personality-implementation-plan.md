# Patched SDX binaries on Exec816

Status: implementation started, 18 October 2026. The first applications are **6502 MD5,
then 6502 ARC**. No application is yet accepted under Exec. This replaces the
earlier MD5-only plan and its native-mode guest proposal.

The [first execution record](../development/sdx-patches.md) covers native CRC32
identification, checked patch transactions, original/patched SDX MD5 controls
and isolated ARC helper tests. The [P2 runtime slice](../development/sdx-runtime.md)
adds two synthetic guests on ordinary Tasks, native waits, forced final-return
NMI checks and traced stock-810 reads alongside pointer IRQs.
P0/P1/P2 are partial. [P3](../development/sdx-loader.md) now passes for
source-audited synthetic commands through ordinary Processes; third-party
application admission and acceptance remain pending.

[Design](spartados-personality-design.md) ·
[Frozen inputs](spartados-personality-inputs.json) ·
[Platform contract](../reference/platform.md) ·
[Emulation experiment](../experiments/emulation-preemption.md) ·
[Testing policy](../contributing/testing.md)

Run audited SDX binaries in private upper banks, in 65816 emulation mode,
with small patches applied during loading. Keep the applications' hashing,
compression and command logic. Bind their OS/SDX calls to native Exec DOS
services and run them as ordinary Processes under the existing scheduler.

The first usable result is MD5 hashing one real file. MD5 completion includes
multiple files, checksum verification, errors, cancellation and independent
instances. ARC follows with listing, extraction, then archive creation and
modification. Sparta Commander remains a later target; a general SDX shell,
hardware emulation, arbitrary binaries and native 65816 SDX programs are outside
this implementation plan.

## Decisions and existing evidence

- Use `E=1`, an aligned private guest direct page, and
  `PBR=DBR=guest_bank` during application execution. This preserves the indexed
  zero-page wrapping found in MD5. Keep the native Task DP intact.
- Use physical bank-zero page one only while the guest owns it. Save each
  guest's complete 256-byte page-one image in upper RAM. Native execution uses
  the Task's existing guarded native stack.
- Support audited module versions. Select the runtime patch set by original
  file size and CRC32, then check every patch site's exact expected bytes.
  Retain SHA-256 for host-side input verification and reproducibility. This is
  application compatibility on an unprotected machine, not a sandbox or a
  dynamic binary translator.
- Allow selected 65816 instructions in patches while staying in emulation
  mode. Stack-relative accesses can reach the real stack without changing DBR.
- Keep ordinary guest execution IRQ-enabled. An audited MD5 `SEI` replacement
  is required before hosted acceptance; NMI preemption alone does not preserve
  serial, timer or pointer IRQ latency. Do not implement a general virtual I bit.
- Use public DOS/device operations and the existing Task API. Keep device
  policy in drivers. Native Exec entry remains `COP #$50`; preserve the OS's
  `$00` service and leave `$80–$FF` unused.

The standalone experiment demonstrates 64 NMI-driven emulation/native round
trips despite guest `SEI`, including restoration after page-one clobbering.
It does not exercise an Exec Task, normal OS VBI work, blocking services, device
IRQs or either application. The current platform only admits native Task
frames; the guest adapter and production interrupt integration remain work.

`tools/sdx_file.py` already contains a host SDX record parser and relocation
helper. `tools/test_sdx_md5.py` contains initial input/reference tooling, not a
completed MD5 execution suite. Reuse these without treating their existence as
milestone completion. Use the compiler revision in
[actionc.json](../../toolchain/actionc.json) and record any local override.

Start runtime fixtures with the [paced platform pin](../../toolchain/altirra-shell-paced.json):
AltirraOS 3.44 for 65816, 800XL/PAL, 8x CPU, 64 KiB base RAM and 63 upper
banks, with shadow ROM enabled and BASIC/DLI disabled. Record a separate
original-SDX control configuration. Desktop input coexistence uses the
[GEM platform pin](../../toolchain/altirra-gem-vdi.json), with its actual
combined configuration and effective interrupt routing recorded explicitly.

## Inputs and first patch candidates

Use the standalone SDX 4.50 `MD5.COM`, SHA-256
`833706e1cab61f52e50e3d8446b53f696d7bd22e8184a64cb1bc350038fd6f79`.
Use the four ARC modules pinned in the input JSON. A different packaging or
version needs a separate audit even when the command has the same name.

| Module | Declared code, data and BSS bytes | Initial work |
| --- | ---: | --- |
| `MD5.COM` | 4,727 | Audit and remove the compression routine's IRQ masking if interrupt-enabled controls pass; reject `/H` hardware behavior. |
| `ARC.COM` | 6,764 | Replace the internal inline-argument helper's stack accesses and absolute/direct-page alias. |
| `ARCLST.OVL` | 1,714 | Complete instruction/ABI audit; no executed `SEI` identified by the initial static review. |
| `ARCEXT.OVL` | 18,892 | Audit the overwrite-question stack read and hardware-oriented `H` option; reject unsupported hardware behavior. |
| `ARCADD.OVL` | 24,586 | Complete addressing, mutation and service audit; no executed `SEI` identified by the initial review. |

Known locations below are **offsets in initialized code block 1**, not file
offsets or final CPU addresses. They are candidates to verify against the
original bytes in P0, not a complete executable patch manifest:

| Location | Observation and treatment |
| --- | --- |
| MD5 `+$0419`, `+$041A`, `+$0965` | `PHP`, `SEI`, matching `PLP` around compression. Candidate: replace only `$78` at `+$041A` with `$EA` (`NOP`), retain the balanced status saves, and prove correct interrupt-enabled operation. Do not remove other opcode-shaped bytes. |
| ARC main `+$05ED` | Helper consumes six inline bytes using the outer return at `$0103,X/$0104,X`. Replace with real stack accesses and preserve return-address carry, registers, flags, count storage and six-byte ordering. |
| ARC main `+$060C` | `STA $00EF,Y` writes `$F0–$F5` through DBR while callers load them through D. Rewrite the helper's copy to use actual direct-page storage. |
| ARC extraction `+$00C6` | `TSX`, add seven, read `$0100,X` on the `H` overwrite path. Classify the complete path; a stack patch does not authorize its display manipulation. Exclude `H` in the initial supported commands. |

At the ARC helper entry, before any new pushes, `3,S` and `4,S` address the
outer return. A replacement can use these while reading inline data through
the guest bank and storing the result through D. Redirect with a same-bank
`JMP` if the replacement does not fit; an extra `JSR` would change those offsets.
Keep the replacement and return path in the guest bank. Preserve both the
helper's own return and the eventual skip past the six argument bytes.

The audit must also cover indirect jump pointer fetches, absolute accesses to
zero page/page one, decimal behavior, status restoration, computed calls,
self-modifying operands, undocumented opcodes and hardware addresses. Neither
an import list nor a linear disassembly separates all code from inline data.

## Execution and interrupt contract to implement

Maintain a guest descriptor associated with the live Task identity. It records
the private bank, guest D, native D/S, complete guest registers and status,
page-one image, saved code bank, Process/image ownership and transition state.
Generate the shared layout from a machine-readable ABI definition.

### Page one and execution states

| State | Ownership and permitted work |
| --- | --- |
| Native | Native D/S and existing platform rules; the suspended guest stack is in upper RAM. |
| Entering guest | Save the displaced host page-one image, restore the selected guest image, and publish ownership under the existing asynchronous-entry protocol. |
| Guest | `E=1`, aligned guest D, guest PBR/DBR and page-one stack. Native metadata is untouched. |
| Guest interrupt | Save the guest frame and enter an owned native context. A short IRQ path retains page-one ownership and may not run an OS call or schedule another owner. |
| Leaving guest | Complete the saved context on a native stack; snapshot guest page one and restore the displaced host image before releasing ownership. |
| Native service or wait | The original guest call/frame is suspended. Native DOS may block and other Tasks or guests may run. No live kernel/ROM activation is abandoned. |

Only one guest owns physical page one at a time. Two guests can still be
preemptively scheduled: the scheduler exchanges their saved stack images at
ownership changes. Preserve the host's page one too; an old ROM, loader or
return frame must not be replaced by a guessed empty stack. Establish that no
live OS activation exists before guest admission.

A guest-local service veneer changes to native mode **before** jumping to
another code bank. On return, native code reaches a guest-bank trampoline
before re-entering emulation mode. Thus ordinary emulation execution stays in
the recorded guest bank. Emulation interrupts do not stack PBR: restore that
bank explicitly before the guest `RTI`. Classify interrupt-entry and transition
PC ranges separately; do not guess a bank for an unclassified frame.

Preserve full A including hidden B, X/Y, P, D, DBR, S, PC, code bank and mode.
Establish binary arithmetic and native widths before compiled work. Retain the
original guest `JSR` frame separately from native call frames. Error traps
unwind only guest frames after native services and I/O have retired.

### Platform entry and timing gate

Production IRQ/NMI routing must work with arbitrary admitted guest D, DBR and
A. The pinned ROM accesses `D40F` through DBR before `VVBLKI`; its vector entry
cannot simply be reused as though DBR were zero. P2 must establish an owned
entry before those accesses or an equivalently proved pinned-ROM route. If a
ROM-shadow patch is necessary, record its exact expected/replacement bytes,
installation/restoration and effective ROM image hash separately from the
unchanged ROM input. The experiment's controlled private `D40F` byte is not
production interrupt routing.

Use SWITCHING/OS_BUSY and explicit transition classification to cover partial
saves, stack swaps, mode changes and final return. `SEI` does not exclude NMI.
Keep normal OS VBI processing and retire it before scheduling; do not replace
it with the experiment's private worker. Preserve native I/Forbid rules rather
than making every masked native frame eligible because guest NMI worked.

The high-frequency IRQ path must enter the existing native source handlers
with the guest context preserved, acknowledge the real device and return to
the guest. It should retain page one and avoid a full 256-byte snapshot on
every timer edge. Nested NMI must recognize that activation and defer ownership
changes until it retires. Reserve full snapshots for scheduling, OS entry or
blocking service transitions that actually release page one.

Measure IRQ service delay, interrupt stack peaks, transition exclusion and
page-one copy time on the pinned machine. Derive numerical acceptance limits
from the active serial profiles and timer/input contracts before admitting
real applications. Exercise guest computation during native SIO and pointer
sampling, not just during an otherwise idle VBI loop. An unresolved entry or
timing failure blocks hosted execution, not static loader/patch development.

## Patch representation and loader sequence

Keep application-specific data out of the compiler and kernel. Proposed files
are `compat/sdx/md5-450.json`, `compat/sdx/arc-450.json`, assembly replacement
routines under `compat/sdx/`, and a generator that emits bounded loader tables.
These version manifests select third-party binaries; they do not introduce
multiple Task ABIs. Initially require the pinned complete ARC module set.

Each manifest must contain:

- Schema/personality ABI version, module role, original size and CRC32 for
  runtime selection, plus SHA-256 for host-side input verification; companion
  module identities, allowed operations and entry export.
- Patch identity and reason, SDX block number and offset, exact expected bytes,
  and typed replacement bytes/fixups or a named assembled replacement routine.
- Relocation/import intersections, preserved register/flag/stack contract,
  scratch ownership, replacement-space requirements and branch range checks.
- An audit reference and executable regression IDs for each change. List
  intentionally excluded paths, such as hardware options, and their rejection
  mechanism before they can mutate hardware or application files.

Use the ZIP/gzip CRC-32 variant (CRC-32/ISO-HDLC): reflected polynomial
`$EDB88320`, initial internal state `$FFFFFFFF`, final XOR `$FFFFFFFF`.
The empty input result is `$00000000`; ASCII `123456789` gives `$CBF43926`.
Store the checksum as eight hexadecimal digits in source manifests and
generate a defined byte order for runtime tables. Compute it over the entire
original file, including record/relocation/import data, before modifications.

Start with a shared 256-entry, 32-bit table in upper RAM (1,024 bytes) and a
four-byte running state in existing native scratch. Compute once over the
staged bytes without an extra disk read. Measure emitted-code time and footprint
in P1; do not add SHA-256 to the target loader. Host tools verify the pinned
SHA-256 before generating runtime CRC32/patch tables and retain SHA-256 in
build and diagnostic records.

CRC32 is a practical version/corruption check, not collision-proof identity or
authentication. Reject ambiguous size/CRC32 selectors when generating tables
and at selection; retain structural validation and exact patch-byte checks.
The supported-input policy remains specific audited binaries.

Use one deterministic transaction:

1. Stage exact file bytes; validate record bounds and match file size plus
   CRC32. Unmatched or ambiguous selections fail as unsupported before execution
   or guest file mutation. The checksum helper runs in native upper-memory
   code and must not depend on launching a guest tool.
2. Validate every pre-relocation expected byte and all block/patch/fixup ranges.
   Reject overlapping patches, unauthorized relocation intersections and
   unknown replacement IDs. Never wildcard opcode bytes or scan for `$78`.
3. Reserve the guest layout, replacements and veneers; copy initialized data,
   clear BSS, and perform ordinary SDX relocations/import binding.
4. Check the relocated preimage against the relocation-aware expectation, then
   write the replacements and their fixups. Do not run another relocation pass
   over the replacements. Fixed-size edits may use NOP padding; larger routines
   use explicit reserved destinations without shifting the rest of the image.
5. Verify the final extents and patch result, then publish the Image. On any
   failure, discard the unpublished image/load level. No partly patched module
   becomes runnable. Retain runtime size/CRC32, manifest revision, placement
   and patch IDs; host development tools add original/final SHA-256 records.

Leave original files unchanged. Every overlay load repeats identity checking,
relocation and patching before its entry or exports become visible. Code that
modifies a patched site, jumps into a replaced instruction's interior, or
generates new code requires an explicit audited treatment; otherwise reject
that module/path. Reapplying a patch to an already patched image is an error.

All CPU-visible near code/data must fit the guest bank. Application blocks,
maximum live overlays/BSS, private OS/SDX variables, ROM-entry veneers and
replacement code have non-overlapping reservations. A ROM-layout copy is only
an address-compatibility aid; no unsupported call may fall through into copied
hardware code. Reserve and guard the admission/return veneers themselves.

## Integration and services

| Existing area | Planned change |
| --- | --- |
| `lib/dos/program.act`, `programimage.act` | Recognize SDX records explicitly, add an SDX Image kind, and retain/free its owned bank and metadata. Preserve native o65/C dispatch. |
| `lib/dos/process.act`, `programfile.act` | Dispatch the resident SDX adapter through the existing launch/wait/collect route, arguments, streams and foreground ownership. |
| `platform/altirraos/cooperative.s`, `preemptive.s`, `interrupt-work.s` | Admit published guest contexts and integrate IRQ/NMI entry, page-one ownership, native services and final returns. |
| `abi/sdx.json`, `tools/generate_sdx.py` (new) | Generate guest descriptor, service, patch-table and state constants shared by Action! and assembly. |
| `lib/dos/sdx*.act`, `platform/altirraos/sdx.s` (new) | Bounded loader, patch application, guest state, service translation and mode bridge. |
| Memory/profile/build generators | Account for guest DP slots, fixed state, upper code/data and reserved guest extents; reject overlaps and linker overflow. |

Keep substantial code and descriptors in upper RAM. Establish resources once
at load/open/admission and report ordinary operational failures. Boundary and
stack/domain checks remain necessary, but wrappers must not repeatedly
revalidate live application-owned handles. Continue using the existing Process
retirement protocol; never release a DP, stack image, file buffer or Image
while a guest/native continuation or I/O request can still reference it.

Generate actual calling contracts, including flags, for the 14 MD5 imports:

| Imports | Required behavior |
| --- | --- |
| `COMTAB`, `FILE_P` | Private command buffer/index, file specification and documented variable indirections. |
| `U_SLASH`, `U_GETATR`, `TOUPPER` | Actual SDX option, filename/attribute and byte conversion behavior; reject `/H` using the parsed option, not substring matching. |
| `FOPEN`, `FREAD`, `FGETC` | Owned native handles, binary buffers, partial transfers and the audited EOF/error conventions. `/C` needs simultaneous checksum-list and target-file streams. |
| `FCLOSE`, `FCLOSEAL` | Close only owned handles at the appropriate load level; preserve first errors and terminal Close failures. |
| `PRINTF` | Read inline format and argument pointers from the guest bank, dereference them using audited address classes, and resume after the complete record. |
| `U_SFAIL`, `U_XFAIL`, `U_FAIL` | Guest-local trap installation/removal/delivery, stack restoration and native Process result/IoErr mapping. |

Ordinary pointers map to `guest_bank:offset`; pointers to guest zero-page
variables must map to `00:(guest_D+offset)`. Record these classes per API and
call site where necessary. In particular MD5 can pass pointers to digest bytes
in zero page through PRINTF; it is not enough to redirect only CPU zero-page
instructions. Check whether any API also needs a pointer into the active/saved
guest stack. Do not infer storage solely from a small numeric address or keep
unsynchronized low-page copies.

ARC adds command/filename processing, writing/seeking, enumeration, arithmetic,
vectored output and nested loading. The static union is 29 external symbols
for main plus listing, 30 for main plus extraction, and 35 across all modules,
excluding the main module's `_ARC` export. Use the input JSON for exact lists;
these counts do not measure implemented services.

Implement guest-local `_ARC` exports and nested load levels, including every
unload/error path actually used. Provide `CAR:` as a read-only namespace backed
by the pinned overlay files. Native I/O may use a far guest buffer only while
its allocation remains retained; callbacks such as `PUT_V` re-enter through
the guest bridge with correct bank, stack and synchronous lifetime.

Keep bounded activation records for service/callback nesting: one mutable
saved native S is insufficient when a callback invokes another SDX service.
Each transition releases page one before native work; a callback temporarily
reacquires it through the same protocol. Freeze the required nesting depth in
P0 and test preservation of both native and guest continuations. Never invoke
guest callbacks from hardware IRQ context.

Translate SDX paths, masks and attributes through ordinary DOS APIs. Start
with an explicit per-guest SDX drive mapping to native directories; do not
create global assignments on launch. Preserve file bytes and ATASCII checksum
fixtures. Adapt console text at the output boundary, while redirected output
retains the defined guest byte stream.

BREAK is latched for the owning Process and delivered at supported boundaries.
Freeze a measured cancellation bound from the longest compute interval, next
check, and native I/O drain. If an ARC codec loop exceeds that bound, add an
audited checkpoint patch preserving its state; do not forcibly abandon it or
mistake preemption for cancellation. A caught BREAK must not permit indefinite
guest retry. Fault cleanup runs on a retained native context after I/O settles.

## Executable slices

P0/P1 now have the component implementation recorded above; their full exit
gates remain open. The other slices below are pending. P1 helper probes and P2 synthetic context work
can proceed after their P0 inputs are frozen; real guest admission requires
both. Each slice records its exact supported operations and memory delta.

| Slice | Deliverable and exit gate |
| --- | --- |
| P0 Inputs and audit | Reproducible original-SDX controls; complete instruction/service/path classification for MD5 and staged ARC operations; patch candidates and machine pins. |
| P1 Patch engine | Size/CRC32 selection, exact preimage checks, relocation-aware application and replacement assembly; focused emitted helper tests pass before real application launch. |
| P2 Guest runtime | Upper-bank synthetic guests can be preempted, use native services, block/resume and exit with IRQ/NMI and host page-one coexistence. |
| P3 Loader and Process | **Passed for the audited synthetic catalog.** Commands load/patch/bind and execute through ordinary Process ownership; rollback and slot reuse pass. |
| P4 MD5 services | The fourteen-symbol subset passes guest-call probes, including inline output, two handles and nonlocal traps. |
| M1 Named-file MD5 | The adapted binary computes correct digests through native DOS and an ordinary shell launch. |
| M2 Complete MD5 subset | Multiple files, masks/attributes, `/C`, errors, BREAK, redirection and two independent guests pass. |
| A1 ARC loading and listing | Main plus listing overlay execute with the patched helper, private exports and read-only `CAR:` resolution. |
| A2 ARC extraction | Required codecs, output files, overwrite decisions, CRC failures and cleanup pass through native DOS. |
| A3 ARC creation and mutation | Creation/addition/deletion and the admitted update operations preserve data, error reporting and temporary/backup ownership. |
| A4 Mixed use and documentation | MD5 plus ARC, two ARC instances on separate archives, shell recovery and measured resource/timing limits pass; publish the supported subset. |

### P0 and P1 audit and patch proof

Run original controls under the pinned SDX distribution with identical files,
recording exact command tails, console bytes and Process-equivalent results.
Complete the unfinished MD5 reference run. Archive module hashes, relocations,
expected patch bytes, reachable indirect targets and file/option semantics.
Freeze maximum handles, trap depth, path/argument lengths and live overlays.

Use independent host parsing/relocation checks and focused emitted-code tests
for the patch engine. Cover wrong size/CRC32/preimage, ambiguous selectors,
truncation, unsupported record,
relocation overlap, capacity/branch failure, duplicate application and allocation
failure without publishing an executable. Place synthetic blocks at two offsets
and guests in two legal banks; patches must not depend on the audit's `$2000`
disassembly base.

Compare the emitted CRC32 helper with an independent host implementation for
the known vectors, every byte value, split updates and the five pinned module
files. Include corruption outside patched code, including relocation/import
records. Record target cycles/load time and the shared table/code footprint;
host checksum timings do not establish 65816 performance.

Exercise the replacement ARC helper with an actual nested `JSR`, six distinct
argument bytes, a return-address low-byte carry, nonzero D, DBR/PBR in upper
RAM, several valid stack depths and IRQ/NMI interruption. Assert both returns,
the next instruction, all six destination bytes and the preserved CPU state.
Include a deliberately different upper-bank low page to expose alias mistakes.
Test MD5's SEI replacement with digest oracles and interrupts during compression;
if it needs atomicity, resolve it with a bounded audited adaptation before M1.

### P2 through P4 runtime and boundary proof

Exercise all 256 guest DP bytes, hidden B and decimal/status restoration,
native DP metadata, page-one save/restore, host ROM calls and a native peer
Task. Two synthetic guests must compute without yielding, block independently,
and survive page-one reuse by native services and each other. Inject IRQ/NMI
at partial-save, D/S change, bank/mode change and final-return boundaries;
include deferred wake/return redirection, nested native NMI and pending IRQ.

Use normal OS VBI and real timer/serial events on the pinned platform. Record
device progress and worst-case delay while the guest computes. Deliberately
vary A, guest bank and D so the ROM-entry workaround cannot pass accidentally.
Keep guest stack headroom for CPU/ROM/wrapper pushes; prove no page-one wrap
overwrites live frames. Canary checks supplement, not replace, that analysis.

Test error delivery after successful native work, trap nesting/removal, short
reads/writes, late Close failures, failed admission, image-owner release during
execution and repeated collection/reuse. Include a third launch when two guest
slots are occupied: fail cleanly, then succeed after collection. Unsupported
imports/operations must fail explicitly; never use successful no-op services.

### M1 and M2 MD5 acceptance

Compare against an independent host digest implementation and original-SDX
controls: empty input, `abc`, lengths 55/56/63/64/65, read-buffer boundaries,
every byte value, 65,535/65,536/65,537 bytes and larger streamed files. Start
with controlled RAM files, then actual SDFS I/O. Files need not fit in a bank.

Exercise multiple specifications and `/C` with matching/mismatching entries,
missing files, malformed/overlong records, empty lists and final lines without
terminators. Preserve separate ATASCII, LF and CR/LF fixtures. Establish the
binary's actual exit/error result; do not invent status by parsing its output.

Test BREAK before launch, during compression, native I/O and output; reject
hardware `/H` before its effect. Run two separately loaded instances, including
verification alongside hashing, with different arguments and output streams.
Require native peer progress, no cross-guest state changes, intact guards,
released handles/slots and a usable shell after success, failure and BREAK.

### A1 through A3 ARC acceptance

Start with listing because it exercises the main helper and overlay lifecycle
without modifying the archive. Use original controls and an independent archive
reader to compare names, sizes, methods and CRCs. Enumerate the supported codecs
from the pinned binary; include each admitted method in the corpus rather than
assuming every ARC-family extension works.
Trace the listing overlay's `__MISC` dependency and its calling convention
before admitting the listing path; its name alone is not a service contract.

For extraction, compare exact output bytes and metadata with independent
fixtures: empty members, several members, buffer/bank-size boundaries, binary
data, CRC damage, truncated archives, unsupported methods, missing overlays,
existing targets, declined overwrite, full media, output failure and BREAK.
Do not write past confirmed lengths or lose the first causal error during Close.

For creation/modification, independently decode the result and verify contents
and archive directory fields. Test temporary/backup collisions, insufficient
space, read-only sources, partial writes, seek/Close/rename failures and BREAK
at mutation boundaries. Preserve the original archive until the command's
documented replacement point; do not claim atomic replacement beyond the
[native write contract](../reference/filesystem-writes.md). Never remove a
temporary or backup file merely because its name matches a convention.

Native DOS currently lacks SetFileDate/SetProtection, seek beyond EOF and rename
with replacement. P0 must identify which exact ARC paths require them. Implement
needed metadata operations as reusable public DOS capabilities in a separate
executable dependency slice before accepting those paths. Do not silently drop
timestamps or fake date comparisons: date-based update/freshen remains unavailable
until that gate passes. Listing and other independent slices can complete first.
The advertised ARC subset must match the completed gates, not a generic claim
that every switch works. Hardware-oriented `H` stays unsupported.

### A4 coexistence and completion

Run MD5 plus ARC and two ARC guests on different archives, with private `_ARC`
bindings, overlays, output, traps and file tables. Include failure/BREAK in one
guest while the other continues, a native compute peer and native device I/O.
Native file ownership must reject incompatible access to the same archive;
separate temporary names alone do not establish safe shared-archive mutation.

Finish with shell launch/redirection and prompt recovery. Publish the actual
supported commands, original hashes, patch revisions, device profile, numeric
timing/cancellation bounds and memory limits. Commander follows only after this
scope; its display API and child execution are not hidden acceptance requirements.

## Memory and ownership budget

The patch/decoder components add **0 fixed and 0 per-Task reserved bank-zero bytes**.
Enabled P3 builds add **544 fixed and 0 per-Task bytes** for guarded guest DPs.
Implementation reservations, including unused capacity, are:

| Resource | Budget and lifetime |
| --- | --- |
| Guest DP pool | Two aligned 256-byte pages plus two 16-byte outer guards: **544 fixed reserved bank-zero bytes** in enabled builds. Each active guest uses one page from this pool; do not count it again as a per-Task increase. Generated placement adds no further padding. |
| Physical guest stack | Existing `$0100–$01FF` OS reservation: **0 additional bytes**. Shared by ownership protocol, not a second stack allocation per guest. Budget interrupt pushes within its 256-byte capacity. |
| Native Task DP/stack | Reuse current guarded pools: **0 planned growth** per public Task, root, kernel or idle. P2 must prove native service and interrupt headroom. |
| Bank-zero bridge/state | Target **0 growth** within existing reservations, including code padding. Prove fit; any extra state, stack, guards or linker capacity requires a revised measured budget before admission. |
| Guest stack snapshots | **256 upper-RAM bytes per guest**, including every unused page-one byte. |
| Displaced host stack snapshot | **256 fixed upper-RAM bytes** initially; nested ownership is prohibited rather than sharing an untracked buffer. Other existing OS stack buffers retain their own lifetimes. |
| Runtime CRC32 | **1,024 shared upper-RAM bytes** for the initial lookup table, plus measured code/alignment capacity. Four-byte transient state uses existing native scratch; **0 planned bank-zero growth**. |
| Private guest bank | 65,536 CPU-visible bytes. With the current alignment strategy, requesting 131,071 bytes rounds to **131,072 backing bytes per Image**; count the entire backing. Replacements, veneers, OS layout and unused address space are included within the bank. |
| Guest/loader/service state | Bounded upper-RAM descriptors, handles, trap/load records and staging. Freeze capacities in P0/P3 and report full rounded allocations and peak live overlay usage. |

ARC main plus add declares 31,350 bytes; main plus extraction declares 25,656.
These are capacity inputs, not final layout proofs. Include all simultaneously
live allocations, support tables, veneers and replacement code before admission.
If the layout cannot fit, revise overlay placement/lifetime; do not spill
ordinary application storage into bank zero or wrap a near pointer.

Generate reservations from the platform profile. Respect ROM/OS storage, the
VBXE aperture, Task pools, protected firmware bank and bootstrap retirement;
do not hard-code an old free address. Count the full two-slot pool while idle.
Descriptors and snapshots retain the Image/Process lifetime through final
guest frame retirement; native I/O keeps its buffers until completion/collection.

## Validation and deliverables

Extend `tools/test_sdx_md5.py`; add focused patch/context and ARC runners with
independently selectable groups matching the slices. Keep proposed command
options out of usage guides until implemented. Record original input hashes,
patch schema/revision, before/after bytes and relocated image hashes, platform
ROM/effective routing, emulator configuration, compiler revision, executed
cases, results, stack peaks, memory deltas and timing bounds.

Development checks are the default: host suite for code, affected generators
with `--check`, and focused optimized emitted-code functional/failure tests.
Use small raw/optimized probes for generated layouts and compiler-facing
marshalling/context changes; do not duplicate every application scenario in
raw mode. Compiler defects belong in actionc, CPU defects in actionc-vm, and
guest/ROM/platform adaptation in Exec. Keep deeper IRQ/NMI tests at P2 rather
than postponing them to a release matrix.

Store current execution records under `docs/development`, full artifacts under
`build`, and completed records under `docs/history` with index updates. Publish
the personality reference/usage guide only after their behavior passes. Full
release qualification is separate from these development slices.

Demo publication is also separate. Any refresh uses `tools/build_demo.py`,
includes OF816 and the five-second standard autoboot, and follows the existing
XEX/cartridge/BIN package rules. Preserve third-party notices and establish
redistribution terms before including guest binaries; patches do not change
their ownership. No demo build is needed for this documentation-only change.

## Primary specifications

- [SDX 4.50 Programming Guide](https://sdx.atari8.info/sdx_files/4.50/SDX450_Programming_Guide.pdf): executable records, imports, file/command services, PRINTF and load levels for the pinned applications.
- [SDX 4.51 Programming Guide](https://sdx.atari8.info/sdx_files/4.51/SDX451_Programming_Guide.pdf): later API comparison; it does not substitute for the pinned binary behavior.
- [W65C816S datasheet](https://www.westerndesigncenter.com/wdc/documentation/w65c816s.pdf): direct/absolute/stack addressing, emulation restrictions, opcode availability and interrupt bank restoration.
- [zlib checksum interface](https://www.zlib.net/manual.html#Checksum): host CRC32 comparison and incremental checksum conventions.
