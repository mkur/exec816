# QED native build and runtime feasibility design

[GEM plans](README.md) · [Port strategy](qed-port-strategy.md) ·
[Initial scope](qed-scope-and-dependencies.md) ·
[Implementation plan](qed-native-feasibility-implementation-plan.md)

Prove that the selected QED sources can use Exec's native C ABI, runtime and
memory model before extending GEM for the editor. Use a runnable application
containing the real runtime and selected QED text-storage code, plus a separate
whole-application compilation and layout study. This permits useful executable
progress while resource, workstation and drawing support remain later work.

Status: proposed design for strategy step 2. No native QED compilation or
execution result is established by this note. The
[step 1 source manifest](../../../ports/gem4xe/apps/qed/inputs.json) fixes the
upstream inputs and initial native baseline.

## Boundaries and deliverables

Keep the [initial editor scope](qed-scope-and-dependencies.md#initial-supported-scope).
Step 2 establishes the native foundation; the real QED window remains step 3,
editing and dialogs step 4, and trusted saving step 5. A small fixture may use
already supported AES operations to exercise Process Stop and teardown.

| Artifact | Purpose and acceptance |
| --- | --- |
| Source and ABI report | Compile the retained source candidates with recorded adaptations; identify layouts, runtime symbols, exclusions and missing interfaces. Object sizes alone are incomplete size evidence. |
| Runtime proof APP | Execute real argument, allocation, descriptor, file and cleanup paths through the normal loader and Process wrapper. Link selected QED text-storage routines into this fixture. All executed dependencies must have real implementations. |
| QED layout ELF | Measure the selected complete QED call graph, private data, runtime and bank placement. Any bindings standing in for later GEM work make this an analysis-only artifact, excluded from APP packaging and execution. |
| Feasibility record | Reconcile image, heap, stack and remaining work against explicit budgets. Identify which conclusions come from execution, layout analysis or a documented allowance for later code. |

No success-returning compatibility placeholders are permitted. Any symbol
needed by an executed runtime path must be implemented or the path must fail
explicitly with its real operational error.

## Source preparation and native ABI

Restore the pinned sources into an immutable cache and apply recorded patches
to a separate work copy under `build/qed-native/`. Keep port adaptations under
`ports/gem4xe/apps/qed/`. Preserve upstream notices and raw-byte hashes. The
37 QED and 120 cflib candidates are the starting inventory, not a promise to
link every donor feature. Record every scope-driven exclusion and its callers,
including startup, keyboard dispatch, timers and cleanup.

Use the existing Calypsi large-code/huge-data model and current toolchain pins.
Keep QED's unsigned-character compilation and explicit legacy word typedefs
local to the port. Use one public Exec definition of OBJECT and other shared
records; adapt donor union/member access instead of installing a competing
public GEM layout. Private cflib records remain application-owned.

The [C types](../../../c/include/exec/types.h) distinguish four-byte huge
pointers from three-byte native ABI pointer fields. Confirm target-emitted
widths, field offsets, integer conversions and function-pointer calls with
small raw/optimized probes. Include pointer arithmetic and copies near a bank
boundary, unsigned character values above 127, and calls from the native
Process wrapper into ordinary `int main(void)`. Frontend assertions alone
are insufficient for the packed native layouts.

Declare retained foreign calls with their real signatures. The timer argument
shape used by donor `evnt_multi`, pointer-bearing parameter blocks and cflib's
system-header aliases require explicit source adapters. Declarations needed
only to compile later GEM paths do not advertise those paths as implemented.

The donor's compiler-version recommendation does not authorize an automatic
upgrade. Reproduce a suspected defect with a focused emitted-code case and
fix it in the owning toolchain before changing the pin. Do not change integer
or time types merely to avoid a defective runtime helper.

## Entry and resource ownership

Keep ordinary `int main(void)` as the loaded entry and invoke an adapted QED
entry from it. Copy and parse the borrowed `ExecGetArgStr()` text into bounded
upper-memory storage for zero or one document argument, preserving quoted
paths. Reject malformed or extra arguments before opening a document. Resource
discovery uses an explicit native location for the selected English resource;
it must not depend on donor `shel_read`, drive letters or a fabricated argv[0]
path. Relative document names retain native current-directory semantics.

Each loaded image owns its runtime state: argument storage, allocation chain,
descriptor table, optional runtime buffers and cflib globals. Keep that state
out of the resident provider. Two probe images must not share mutable runtime
state, even though the first QED acceptance scope has one editor instance.

Normal completion follows this order:

1. Stop application activity and release its explicitly owned GUI references.
2. Flush and close owned C streams/descriptors, retaining the first meaningful
   failure and respecting native terminal Close ownership.
3. Release runtime requests, locks and all remaining application allocations.
4. Return a conventional status through native `main`.
5. Let the existing wrapper settle AES, then let Process finalization retire
   DOS ownership; the parent collects before the image can be released.

Release storage only after every GUI/drawing borrower has released it. A
teardown failure retains reachable storage under the existing failure protocol.
Keep the application's first failure privately through cleanup. Where a native
secondary result must survive, use the ordinary SetIoErr binding at the final
return boundary and verify preservation through the shared C wrapper; any
required wrapper fix applies to all C applications.

The existing [C wrapper](../../../c/calypsi/program.c) and
[Process contract](../../reference/process.md) remain authoritative. Do not
call `ExecDOSDetach` from the application, force-remove its Task, or reclaim
an image while execution or teardown still refers to it.

Adapt retained QED/cflib `exit` calls, including allocation-error choices, into
error returns through the owning call chain. This phase does not introduce a
nonlocal jump across C/native calls. Expected failures must reach normal
cleanup; an unexpected assertion or system invariant failure is a diagnostic
fault, not evidence of graceful recovery. Audit the linked C-library closure
for board-exit dependencies as well as explicit application calls.

## Allocation model

Start with directly freed native upper-heap backing allocations and private
ownership metadata. Use one implementation beneath the required `malloc`,
`calloc`, `realloc`, `free`, `Malloc` and `Mfree` entry points. QED's existing
text allocator can continue subdividing its own bank-contained blocks. Do
not import the donor's assumption that OS exit reclaims arenas.

Keep ordinary returned blocks within one bank, with alignment suitable for the
native heap. Retain each original backing pointer and exact allocation size;
account for metadata and rounding before accepting a request. Free removes
that allocation from the ownership chain. Final cleanup walks only remaining
owned backing blocks, so releasing text storage earlier cannot double-free it.

Check size arithmetic before allocation. Failed `realloc` leaves the original
block and contents owned; `realloc(p, 0)` frees p and returns NULL. Zero-byte
malloc/calloc return NULL, and `calloc` reports multiplication overflow. The
largest-block answer to `Malloc(-1)` must describe an actually allocatable
payload after metadata, alignment and bank constraints. Expose the existing
public `AvailMem` in the C import set if this query requires it, rather than
inventing a QED-specific kernel service or a constant available-memory value.

This design adds allocation bookkeeping for ownership and normal failure
handling, not repeated pointer validation. Correct frees remain the caller's
responsibility under the [memory contract](../../reference/memory.md).

## Files and C library hooks

Use one bounded per-image descriptor table for GEMDOS-shaped file calls and
the retained Calypsi stdio hooks. Successful owned opens return descriptors
above 2, satisfying both QED's positive-handle tests and the library's standard
stream convention. Entries retain the complete native BPTR and ownership;
never cast it into a short descriptor. Borrowed standard output/error may use
the inherited Output handle and are not closed as owned files. Implement
standard input only if the retained source closure requires it.

Use the installed, pinned `<calypsi/stubs.h>` declarations for hook signatures
and return conventions, including the error representation in `size_t`
read/write results. Record that header and the selected runtime archive hashes
in build evidence. Do not substitute host POSIX signatures by resemblance.

| Operation | Required adapter behavior |
| --- | --- |
| Open/create | Translate only used modes, preserve native paths, acquire a descriptor after a successful native Open, and roll back the handle if descriptor admission fails. |
| Read/write | Preserve EOF, confirmed prefixes and errors. GEMDOS and stdio share ownership but retain their own documented result/error conventions. Capture IoErr before another call can overwrite it. |
| Seek | Translate origins and return the new position expected by GEMDOS/stdio, while native Seek returns the old one. Preserve position on rejected seeks and retain native no-extension behavior. |
| Close | Report finalization failure even after successful writes. A terminal Close of an idle owned file consumes its native handle; retire the descriptor and do not retry it during cleanup. |
| Rename/delete | Expose the existing same-parent, non-replacing rename and deletion guarantees, with truthful errors. Replacement and backup policy remain in the later QED save design. |
| Metadata | Use availability flags and ExamineExact where exact length is needed, especially on MyDOS. Preserve unavailable dates or attributes rather than turning them into valid zeros. |

Use one explicit mapping from native operational errors to the retained
GEMDOS errors and C errno values, preserving the original failure in evidence.
The native [file contract](../../reference/dos.md#files-and-directories) and
[write contract](../../reference/filesystem-writes.md) govern handle lifetime.
The runtime proof uses disposable files; it does not qualify document backup
or replacement workflows.

Link only the C-library facilities the selected paths need. Keep string,
formatting and arithmetic helpers local. An empty environment is a truthful
initial result while legacy configuration discovery remains deferred. Large
format buffers and metadata records belong in owned upper storage, not deep
automatic call frames.

Treat stored file timestamps separately from elapsed time.
[TD_READCLOCK](../../reference/timer.md) is a monotonic VBI clock, not UTC.
Convert supported file DateStamps with range checks when needed, preserve an
explicit unavailable state, and adapt callers of optional calendar display
or deferred autosave. Do not report uptime as `time()` or fabricate a date for
changed-file detection. Any essential unresolved time/stdio dependency keeps
the runtime gate open.

Any newly required C binding exposes an existing general public operation.
Update the machine-readable import ABI, generated/native bindings, provider
and rebuilt applications together. No private provider callback table or
exported mutable runtime globals are introduced.

## Image layout and relocation

Measure the actual selected QED build with the native memory model. Inspect
both serialized bytes and complete span, including BSS, inter-bank holes,
alignment and imports. The [current bounded profile](../../../abi/c-program.json)
has a 192 KiB span limit and 256 KiB file limit. Its
[linker placement](../../../c/calypsi/layout.scm) and
[ELF reader](../../../tools/calypsi_image.py) impose additional code-bank,
single-data-bank and table-placement constraints. Raising one JSON limit does
not solve those constraints.

If unimplemented GEM calls prevent a complete link, create a distinctly
marked analysis ELF. Only enumerated later GEM interfaces may receive typed,
nonreturning trap bindings; unknown runtime or compiler helpers stay unresolved
until classified. Keep the trap bindings and their bytes visible in the report.
Reject an analysis marker in the APP packager even if its input is renamed or
passed through another build entry point. This artifact must never enter media
or an executable acceptance test.

The layout report must distinguish measured source/runtime bytes, real import
thunks, analysis bindings and allowances for future local code. Report remaining
resident-provider work separately. A small runtime fixture is not evidence
that the complete editor fits. An unquantified missing component leaves the
fit decision open.

Prefer a bounded general layout extension only when the measured graph needs
one. Keep bank-aligned image relocation and eager function imports. Update the
layout, ELF extraction/metadata, packer, loader constants and tests together;
retain one current application profile and rebuild callers after an ABI change.
Do not add a QED-only loader or put excess data in bank zero. Preserve the
[independent relink proof](../../../tools/build_c_program.py) at every legal
base in the bounded profile, including symbol positions and reconstructed
bytes, plus focused executable relocation coverage.

## Stack and Process admission

Start with the current generated stack map. Native stack checks and canaries
remain enabled, but the [C image reader](../../../tools/calypsi_image.py)
records C stack checks as absent. Native checks therefore do not establish a
bound on arbitrary C prologues. Inspect emitted frame reservations and observe
S at deep calls and frame-allocation boundaries; a fill watermark alone can
miss unwritten reserved space.

Attribute measurements to the live Process and physical pool. Include the
entry bridge, runtime/stdio paths, error cleanup, interrupts and the kernel
stack. Require at least 128 bytes above the existing interrupt floor in the
selected executable scenarios, retaining the platform's interrupt reserve and
guards. Use frame/call analysis to account for QED paths that cannot yet run;
record recursion or unknown depth as unresolved rather than assuming the
runtime fixture is the deepest path.

Prefer moving long-lived buffers and models into owned upper memory and
removing donor near-data assumptions. The donor's 4 KiB reservation is not a
native requirement. Current Process admission selects the first free slot;
it has no stack-size request. A successful run in a larger pool therefore
cannot establish reliable ordinary launch.

If measured requirements exceed the ordinary pools, decide before step 3
whether a budgeted general pool change or declared minimum-stack admission is
needed. The latter must be reusable by loaded applications, select a compatible
free pool under existing ownership rules, and reject exhaustion before running
the entry. Record its precise public/serialized contract in an addendum before
implementing it. Preserve one Task API; never depend on launch order, a private
QED slot or an out-of-band launch hook.

## Evidence and decision to proceed

Use development checks under the [testing policy](../../contributing/testing.md).
Runtime/file/ownership scenarios use optimized emitted code. Restrict raw and
optimized duplication to focused ABI, pointer, bridge or changed code-generation
probes. Verify actual ROM/emulator identities, native IRQ/NMI delivery, context
restoration, bounded completion, guards and resource return where exercised.

Proceed to step 3 when the selected sources compile, the real runtime and
text-storage fixture pass, the complete layout and remaining allowances fit
a documented bounded profile, and stack/admission feasibility is explicit.
Record any scope limitation of those results. Later GUI paths must be measured
again as they become executable; step 2 does not qualify full QED or the hosted
system.

This design changes **0 fixed, 0 per-public-Task and 0 private-idle reserved
bank-zero bytes**, including guards, alignment and unused capacity. The default
implementation target is also zero growth. Conditional layout/admission/pool
work must report actual deltas from its immediate baseline, with upper-heap,
resident-image and temporary observer costs separate. Follow the
[platform budget](../../reference/platform.md#bank-zero-memory-budget).
