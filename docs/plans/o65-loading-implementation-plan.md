# o65 loading and external commands implementation plan

Status: L1–L4 implemented, 2026-09-25. The scoped L4 qualification matrix passed. See the
[implementation record](../history/o65-loading-implementation.md) for checks and compiler inputs.
Baseline: `407df9d`. Implementation requires console slices S0–B5 and Process
slices P1–P3 first.

Scope: bounded native o65 validation, placement/relocation and providers,
MyDOS loading, shell dispatch and integrated external-command qualification.
Apply the [shared delivery and validation rules](interactive-programs-implementation-plan.md#baseline-ownership-and-delivery-rules).
The loader/provider contract is published in
[program-loading-design.md](../reference/program-loading.md).

Start after [Process lifetime qualification](process-lifetime-implementation-plan.md#p3-teardown-and-failure-qualification).
Use its resident trampoline, inherited context and retirement protocol. Console
windows are qualified independently with existing Tasks in the
[console plan](console-interaction-implementation-plan.md#w-independent-console-windows);
they are not a loader prerequisite.

## Sequence and dependencies

| Slice | Executable outcome | Depends on |
| --- | --- | --- |
| L1 | The native loader validates bounded serialized o65 input | [P3](process-lifetime-implementation-plan.md#p3-teardown-and-failure-qualification) |
| L2 | Relocation, checked imports and hosted execution work at distinct placements | L1 |
| L3 | The shell loads and runs a command from MyDOS | L2 |
| L4 | External commands pass integrated lifetime, interruption and SIO qualification | L3 |

## L: hosted o65 loading and external commands

### L1: profile and bounded native validation

Consume the pinned actionc profile `actionc.o65.experimental.v1`, documented in
that checkout's `docs/MIR65816_O65_PROFILE.md`. It already defines native 65816,
wide structural fields, an empty zero segment, required entry/profile exports,
descriptor contracts, relocation checks and an explicit raw overflow import.
Its entry retains the native routine signature; it supplies no Process ABI.
Its compiler/reference-VM results are inputs to this work, not hosted acceptance.

Write a native Exec816 reader/validator for that profile. Use the compiler's
reference relocator and independent byte fixtures as comparison oracles, not a
Python loader standing in for execution on the Atari. Begin with explicit
resource caps: 256 KiB file, 128 KiB text, 64 KiB each data/BSS/descriptor,
256 routines, 512 objects and 64 imports. Also enforce the actual free-memory
budget and all encoded-length bounds. Reject larger supported-format inputs
with a resource-limit error; these caps are Exec policy, not format limits.

Validate counts before allocation, complete 24-bit address calculations,
section/file intervals, alignments, descriptor version/features, entry signature,
routine containment, symbols, import contracts and relocation-check agreement.
Decode binary fields from exact bytes; newline normalization applies only to
host text fixtures. Keep file reads bounded and interruptible through
[console B4](console-interaction-implementation-plan.md#b4-active-filesystem-and-transport-cancellation).

**Acceptance:** execute the native parser in raw/optimized code on a valid
serialized file and every truncated prefix, plus corrupt counts, tags, lengths,
exports, section overlap and arithmetic wrap. Invalid input publishes no Image
or Process; all writes stay within owned staging allocations. Test exhaustion and
all rollback edges. No compiler JSON sidecar may be required to load the file.

### L2: placement, providers and execution

Allocate text/data/BSS from the existing upper heap. The bank manager has already
assigned that memory to the heap; the loader must not reserve the same banks
again through a competing whole-bank owner. Text requires 64 KiB alignment;
initially overallocate a checked linear backing by up to 65,535 bytes, align the
text base within it, and retain the original base/size for FreeMem. Account for
that unused prefix/suffix and the complete staging/metadata peak. Data/BSS obey
the profile's four-byte alignment, satisfied by the allocator's stronger normal
alignment. Reject layouts that cannot fit rather than weakening placement rules.

Generate a provider manifest from the actual kernel build and public ABI inputs:
explicit linker names, full physical contracts, addresses and extents. Compare
signature and complete argument/result/domain/IRQ/stack contracts, including the
raw nonreturning overflow adapter. Resolve eagerly. Start with the smallest
provider set needed for console/file I/O, argument/result access and cooperative
break. Missing/incompatible providers fail before publication.

The first hosted o65 path requires stack checks enabled in both the kernel
providers and application. The experimental profile requires checked ordinary
providers; reject launch from an unchecked kernel instead of binding incompatible
imports. Further unchecked support needs its own compiler/provider contract work.

Validate all relocation sites and complete effective targets against immutable
input before patching private sections. Clear BSS explicitly. Publish the Image
only after validation, copying and imports succeed. Execute through
[P1's resident trampoline](process-lifetime-implementation-plan.md#p1-resident-process-task-admission-and-result-collection)
with a retained Image reference. Keep text, mutable sections and
loader records alive until all Processes using that Image have retired; no saved
PC, finalizer, callback or outstanding I/O may reference freed image storage.
The first command import set does not support untracked application-created
Tasks or callbacks into an image after Process exit.

**Acceptance:** load identical raw/optimized artifacts at two distinct valid
text/data placements and run them under the pinned emulator. Cover a routine
in a nonzero bank, multi-bank text, direct/indirect calls, split-address carry,
initialized data, BSS, two instances with independent mutable storage, bad imports,
near-bank boundary rejection, guard/fault behavior and unloading/reloading.
Compare relocation bytes with the reference oracle. Kernel banks 1 and 3 must
both generate usable provider manifests.

### L3: MyDOS and shell integration

Load an explicitly named command path from MyDOS in bounded chunks, close its
file after the immutable staging copy is complete, then admit its Process.
Keep existing built-ins first in dispatch; an unknown command token is resolved
as an exact current-directory or explicitly qualified file path. Do not add
implicit extension search, PATH, scripts, pipelines or background syntax in this
slice. Pass the owned bounded argument tail according to
[P1](process-lifetime-implementation-plan.md#p1-resident-process-task-admission-and-result-collection)
and duplicate the selected streams/directory according to
[P2](process-lifetime-implementation-plan.md#p2-inherited-streams-and-current-directory).
Preserve private diagnostics.

**Acceptance:** place compiled HELLO and ECHOARGS commands on an isolated ATR;
launch through the physical shell, verify output/status, and return to a usable
prompt. Cover quoted arguments, relative/absolute paths, missing/corrupt files,
incompatible imports, file/NIL redirection, foreground break and repeated launch
without retained image, handle, lock or Task ownership. Keep original media
fixtures immutable. The kernel still boots through its established XEX loader.

### L4: integrated external-command qualification

Combine full-capacity admission, two simultaneous native test Processes,
foreground shell execution, long file reads, break during loading/execution,
allocation failure, disk error/offline recovery and repeated unload/reuse.
Record all code/data/provider placements and prove no code is released before
retirement. Repeat raw/optimized 128/256-byte FASTEST125 workloads and the shell's
57.6 kbaud profile, with observer-free replay where timing is claimed. Include
stock 128-byte and alternate-kernel-bank regressions within their existing scope.

**Acceptance:** ordinary DOS calls launch a serialized program
from disk, its child inherits the selected context, break and exit clean up,
and another command can run with unchanged guards and accounted ownership.
Compiler tests alone, or loading a pre-relocated host image, do not meet this gate.

## Integration and memory

| Area | Existing integration points / proposed additions |
| --- | --- |
| Loaded programs | Native `PROGRAM`/`PROGRAMFILE` modules and provider generator; `tools/native_program.py`, allocator interfaces, pinned actionc o65 options/profile |

MyDOS and shell integration also touch `examples/shell/shell-session.inc`, DOS entry
points and isolated command/media fixtures. Keep provider and program definitions
machine-readable, tied to the actual kernel build and pinned compiler ABI.

Target reserved bank-zero delta: **zero fixed and zero per Task**, including
all guards, alignment and unused capacity. Loading runs in the caller; child
execution uses the Process plan's existing context slots. Allocate staging,
sections and loader metadata from upper memory. Preserve the
[shared memory gates](interactive-programs-implementation-plan.md#memory-gates).

| Resource | Planning budget / accounting requirement |
| --- | --- |
| Loaded Image | Complete staging file, descriptor/validation state, text/data/BSS, provider/relocation tables and up to 65,535 unused alignment bytes; retain original allocation identities |

Completion requires L1–L4, including actual disk loading, execution, cooperative
break, cleanup and repeated launch under the pinned hosted system. Compiler/VM
results alone do not qualify this loader. PATH/extension search, scripts,
pipelines, background jobs and unchecked-provider support remain separate work.
