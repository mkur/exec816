# Shared C runtime implementation plan

[Plan index](README.md) · [Design](c-runtime-design.md) ·
[Testing policy](../contributing/testing.md) ·
[Current C application contract](../reference/c-program-loading.md)

Status: in progress, 2026-11-09. CR0 passes development checks
([record](../development/c-runtime-cr0.json)); CR1–CR5 remain pending. Complete each slice's
selected development checks before committing it or starting dependent work.
New source, generator and fixture paths below are deliverables, not existing
commands or supported APIs.

## Baseline and scope

Start from the agreed Exec816 **0.2.3** baseline:

| Input | Frozen starting point |
| --- | --- |
| Release source | `v0.2.3`, source commit `bcf3b381be037e16446eb978fa054f6c1ef998ad` |
| Packaged baseline | `8deec0452d8ce5b86f7b42eebd564073d2f514b1`, already on `feature/c-runtime` |
| Original design note | `7300805986eb8902699c499c7786f45057461b1f` |
| Compiler and runtime | Existing [actionc pin](../../toolchain/actionc.json), Calypsi large-code/huge-data configuration and [runtime source pin](../../toolchain/calypsi-runtime.json) |
| Current APP interface | [c-program.json](../../abi/c-program.json), version 30 at the baseline; one current interface after each cutover |

Record actual compiler/runtime, firmware, emulator and media hashes in the new
execution records. Record local overrides explicitly. Use the existing 0.2.3
release records as historical evidence, not as execution results for changed
runtime code. Before code changes, retain the baseline APP/image sizes, stack
observations and shipped-payload checksums needed for matched comparisons.
Do not start a full release matrix just to prepare that comparison.

Deliver the design's application-private allocation, arguments, errno,
descriptors, stdio and termination support, followed by QED migration and a
second consumer. Keep the existing heap, filesystem, Task and Process policies.
Headless C-provider packaging, C o65 commands, C threads, floating-point printf,
locale and a native UTC clock remain outside this plan.

## Slice order and deployment rule

| Slice | Deliverable | Completion gate |
| --- | --- | --- |
| CR0 | Dependency inventory, generated contract and executable component fixture | Emitted layouts and both main signatures pass focused raw/optimized checks; initialization/rollback phases execute through the current APP fixture. |
| CR1 | Common aligned allocation and bounded arguments | Actual C allocation, overflow, failure, bank containment, argument parsing and execution reset pass, with exact cleanup and isolated instances. |
| CR2 | Common descriptors, errno, FILE integration and library reset | Real RAM/MyDOS/SDFS I/O and injected transfer/finalization errors pass; no failed read becomes EOF and no terminal Close is retried. |
| CR3 | Complete lifecycle and one coordinated entry-ABI cutover | Runner, builders, all shipped APPs and QED use the same phased entry and ownership path; termination/context and retirement-order gates pass. |
| CR4 | QED consumer acceptance and current runtime documentation | Native text/storage, stdio, normal editing/saving, stop, retained-image reuse and coexistence pass with the common implementation. |
| CR5 | GemARC consumer, archive-specific correctness and refreshed delivery | Listing/extraction and checked archive mutation pass independent byte/fault checks; the exact OF816 package passes selected application and boot walks. |

CR0–CR2 exercise common components from ordinary test APPs under the current
entry ABI. The proposed phase entry can be called directly by those C fixtures;
it is not an alternate loadable production profile. QED's existing adapter
remains the production path until the cutover.

**CR3 is the coordinated cutover.** Switch the entry ABI, resident provider,
application builders, source adapters and all shipped APPs together. Move QED's
runtime ownership to the common implementation in that same slice. CR4 is its
consumer acceptance and documentation gate, not permission to leave an older
startup or heap active alongside the new one. If CR3 needs several development
edits, commit the coherent runnable cutover only after its required checks pass.
Do not keep compatibility profiles or obsolete implementations.

## CR0 — Inventory dependencies and freeze the generated contract

Audit [QED allocation](../../ports/gem4xe/apps/qed/native/allocation.c),
[entry](../../ports/gem4xe/apps/qed/native/entry.c),
[files](../../ports/gem4xe/apps/qed/native/files.c) and
[library hooks](../../ports/gem4xe/apps/qed/native/library.c). Classify each
symbol as common runtime, GEMDOS compatibility, editor policy, pure vendor
helper or unsupported facility. Keep QED's single-document rule, metadata and
recovery logic above the common library.

Inspect the actual pinned Calypsi sources and hook conventions. Inventory
mutable globals, their reset procedure and the selected formatter. Include errno,
FILE lists, standard streams, tokenizer/random state when linked, and the
setjmp/longjmp or equivalent termination primitive. Identify implicit board CRT,
default-heap initialization and termination dependencies before linking them.

Add `abi/c-runtime.json` and a generator such as
`tools/generate_c_runtime.py`, producing matching C declarations/layout probes
and any native definitions required by the runner. Freeze:

- One synchronous `__exec_c_runtime_entry` signature, invocation record, phase
  constants and initialization/completion flags. Its result carries full-width
  native primary/secondary values separately from the C main result.
- INIT/RUN/FINISH/RELEASE transitions, normal versus abnormal termination and
  partial-initialization rollback. Define when a phase may be called and what
  remains live on each failure; initialization must publish its stage before
  a later failing acquisition can require cleanup.
- The 16-byte allocation prefix, eight-byte payload alignment, 65,520-byte
  payload ceiling, sixteen owned descriptors plus standard descriptors, and
  thirty-two exit-handler slots. Define statistics separately from public ABI.
- Build-time main signature selection. Emit a matching call for main(void)
  or main(argc, argv), without an untyped function-pointer cast.

Create `tests/programs/c_runtime_abi.c` and a selectable runner such as
`tools/test_c_runtime.py`. Before CR3, use the ordinary existing APP entry to
exercise the component; no new ABI is admitted by the production loader.
Normalize host text before newline-sensitive fixture parsing and preserve binary
and ATASCII bytes exactly.

**Gate:** execute small raw and optimized probes for target widths, pointer and
function-pointer fields, invocation/prefix offsets, both main calls, sign/width
restoration, phase transitions and partial INIT rollback. Check the observed
size_t=2, BPTR=4 and existing 20/23-byte compiler workspace. Reuse the current
[native/C context probe](../../tools/test_calypsi.py) where it already proves a
boundary. This slice must leave existing production APP builds runnable.

## CR1 — Extract allocation, arguments and scope reset

Implement common sources under `c/runtime/`, provisionally `allocation.c`,
`arguments.c`, `scope.c` and a private internal header. Preserve extracted MIT
notices. Provide the pinned standard C declarations through the existing headers;
Exec-specific scope declarations belong under `c/include/exec816/`.

Use AllocMem/FreeMem directly. Prefix metadata and the ownership head live in
upper memory. Widen size arithmetic before adding the prefix; check calloc's
product before multiplication. Keep ordinary backings within one bank. Failed
realloc retains the old pointer, contents and list membership. RELEASE frees
only remaining linked blocks. Do not add IRQ masking, Forbid, a heap Task or
runtime ownership scans to these execution-private lists.

Implement the design's general argument parser over the native 255-byte tail,
including empty quoted arguments, tabs, literal backslashes and unmatched-quote
failure. Allocate the actual bounded vector/text size. Reset runtime-owned state
for each execution, without reinitializing unrelated application globals in a
retained Image.

Add `c_runtime_allocation.c`/argument fixtures and failure injection confined to
the fixture build. Execute the production allocation routines; host models may
provide independent expected results but must not substitute for emitted code.

**Gate:** optimized cases must cover zero sizes, free(NULL), all eight-byte
alignment residues, the maximum payload and its refusal boundary, calloc
overflow, failed growth with unchanged bytes, successful shrink/growth, explicit
free followed by automatic cleanup, initialization failure at each allocation,
and two simultaneously loaded instances. Run a retained Image twice and verify
fresh runtime counters/errno/arguments while a deliberate application-global
counter retains its documented Image behavior. Check actual bank containment,
free-memory restoration and bounded completion. Use a small raw/optimized
prefix/layout access probe; the complete allocation scenarios run optimized.

Record prefix/rounding overhead, peak backing, scope storage and transient stack
use. These are upper-memory costs; do not describe automatic cleanup as a change
to raw AllocMem/AllocVec semantics.

## CR2 — Extract descriptors, errors and stdio integration

Add common descriptor, error and stdio sources. Retain full BPTR values in
sixteen owned slots; reserve descriptors 0–2 for runtime wrappers over the
Process's selected streams. Preserve standard-handle borrowing. Reserve a slot
before admitting a create/truncate operation, so descriptor exhaustion cannot
cause an unowned filesystem mutation.

Separate generic hooks from QED's Fopen/Fread/Malloc names and metadata helpers.
Freeze the native-to-errno map, EMFILE versus ENOMEM, and the exact vendor hook
return conventions. Keep a descriptor's terminal state, pending transfer cause
and reported-error state explicit. An error the application already handled
must not be invented again during otherwise successful exit cleanup.

Make the pinned FILE initialization correction part of the common build path
through [calypsi_runtime.py](../../tools/calypsi_runtime.py). Pin any additional
vendor reset/hook corrections by source/header hash and explicit patch; never
modify the installed runtime archive. Select the real integer/long formatter
and preserve that selection in every independent relink. Audit out the vendor
default heap, board exit and conflicting allocator definitions.

Implement read/write/update/append/exclusive modes that the pinned stdio parser
actually supports. Include `+` modes only with real read/write tests. Translate
Seek to a new-position result. Return a confirmed short prefix and expose its
pending error through the library's ferror/errno path without retrying away the
cause or losing the last buffered bytes. A negative read is distinct from EOF.
Terminal Close consumes its descriptor on success or failure; never retry it.

**Gate:** optimized component APPs exercise actual RAM and writable MyDOS/SDFS
operations. Select normal bytes/cursors/modes on each backend, plus deeper
failure cases where their finalization differs. Include:

- Simultaneous FILEs, close/reopen reuse, standard-input borrowing, shared
  stdout/stderr destination and wrapper close without closing the native handle.
- Native handles whose identity cannot fit in sixteen bits; descriptor
  exhaustion, FILE allocation failure and FILE-buffer allocation failure.
- EOF, immediate read error, short read with a cause, short write with a cause,
  full write followed by failed Close, and a consumed-handle retry detector.
- Append position, existing update, exclusive-name collision, rejected seek,
  bytes above 127, ATASCII and all supported line-ending bytes unchanged.
- Observed/reported versus pending errors, clearerr behavior, an earlier main
  error and multiple independent cleanup failures; preserve the right first
  cause without retaining stale errors forever.
- A second execution resetting errno, FILE lists and selected mutable vendor
  state. Poison fresh allocations to expose missing FILE initialization.

Use small raw/optimized probes for vendor size_t error encoding and full-width
secondary results. Reuse the existing QED native file fixture when its case
matches; move generic assertions into the common fixture instead of maintaining
two copies. No complete desktop matrix is required in this component slice.

## CR3 — Integrate termination and cut over the APP entry ABI

First prove the C-only termination boundary in the component fixture. Pin and
audit the actual primitive's register, bank, stack, processor-state and compiler-
workspace behavior. Reject a compiler defect at its owner with a focused
reproducer; do not add an application-specific stack escape. Execute with real
IRQ/NMI entry, preemption and a computing peer during the unwind/return window.
No jump may cross a native service, ROM or interrupt activation.

Implement normal main return, exit, 32-handler LIFO atexit and its exhaustion
case, _Exit, abort and bounded assertion reporting. Abnormal termination must
discard buffered bytes without flushing them, while closing underlying owned
native descriptors and retaining buffers until all borrowers are gone. The
common runner must keep its context valid through every exit mode.

Then make the entry-contract cutover as one runnable change:

| Existing integration point | Required update |
| --- | --- |
| [c_program.py](../../tools/c_program.py) and [build_c_program.py](../../tools/build_c_program.py) | Generate/link the runtime entry, pack that symbol and independently prove every permitted relocated placement. |
| [calypsi_build.py](../../tools/calypsi_build.py) and [calypsi_image.py](../../tools/calypsi_image.py) | Make the expected entry explicit for APP builds. Preserve ordinary resident/standalone C images using their existing entry; do not globally reinterpret every C main as an APP. |
| [c-program.json](../../abi/c-program.json), [generator](../../tools/generate_c_program.py) and [loader](../../lib/dos/cprogram.act) | Advance the current APP ABI, regenerate shared definitions and reject old artifacts before entry. Keep container growth separate from the entry change; justify any actual layout extension. |
| [program.c](../../c/calypsi/program.c) and generated CPROGRAMBIND | Invoke INIT/RUN/FINISH, retire GUI borrowers, invoke RELEASE, then return to the existing resident Process finalizer. Preserve its Image reference through every call. |
| [build_gem_desktop.py](../../tools/build_gem_desktop.py), calculator/benchmark builders and all APP fixtures | Select each main signature, use the common build path and rebuild every shipped APP with the matching provider. |
| [QED builder](../../tools/build_qed.py), native-selection manifest and adapters | Replace private ownership/startup with common services at cutover. Leave only thin port compatibility/document adapters. Update fixture injection points and remove duplicate implementations. |
| [relink_qed.py](../../tools/relink_qed.py), source packaging and observers | Preserve runtime sources/attributes in relinking and source ZIPs; observe the real new entry and owner state rather than assuming entry==main. Keep analysis-only rejection intact. |

Factor fixture execution separately from production APP entry selection where
needed; this must not become an old runtime profile. Update packager/ELF-reader
tests which currently hard-code main, and record each linked runtime component
and its owner. Keep library state private even if pure helpers are shared.

**Gate:** optimized lifecycle APPs pass ordinary return, every INIT acquisition
failure, early stop before main, cooperative stop after window creation, exit
from nested C calls, all exit-handler cases and repeated execution. Check:

- A heap-backed title/menu remains valid through the final GUI retirement
  acknowledgement; RELEASE occurs afterward, with no observer pointer retained
  past collection. Native Process DOS cleanup still occurs after C return.
- A failed GUI retirement never reaches RELEASE or ordinary completion; the
  Task, Image reference and heap remain held. Use a bounded diagnostic fixture
  observation, not forced production cleanup.
- A terminal file error consumes handles and continues independent cleanup.
  A failed flush/Close after main success produces 20 and its first cause; a
  prior main failure remains the primary result. Full-width native causes such
  as `$0000C219` are preserved.
- _Exit/abort write no pending FILE buffer, yet retire their owned descriptors
  and GUI safely. Application invariant faults are not claimed as recoverable.
- Obsolete APPs are rejected; every rebuilt shipped APP starts/returns under
  the new ABI; ordinary resident C images still execute with their own entry.

Run the new entry and nonlocal-return/context cases in both raw and optimized
modes. The broader lifecycle and GUI cases remain optimized. Reuse selected
[C Process tests](../../tools/test_c_process.py),
[C image tests](../../tools/test_c_program.py) and
[launch tests](../../tools/test_program_launch.py), updating their assumptions
rather than retaining stale providers in reusable build directories.

## CR4 — Accept QED on the common runtime

Complete consumer-specific adaptation after the CR3 cutover. QED's main receives
the common argv and applies its own single-document rule. Its GEMDOS wrappers
forward to common descriptors/allocation; metadata availability, text storage,
dialogs and save/recovery policy remain in the port. Remove private initialization,
heap sweeps, FILE lists and board-exit fallback definitions from the native
selection and linked closure. Do not preserve a dormant duplicate implementation.

Update tests that assumed QED's old twelve-byte allocation prefix or exact
allocator peak. Derive new expected totals from the selected common layout and
actual requested payloads, while retaining independent content/failure checks.
Do not weaken a failed check to a larger memory or timeout allowance without
measured evidence and a documented reason.

**Gate:** run the selected optimized QED native runtime, files, stop and
admission groups from [test_qed_native.py](../../tools/test_qed_native.py), plus
affected real editor Open/edit/Save/Save As/cancel/recovery and cleanup cases.
Use [saving](../../tools/test_qed_saving.py),
[cleanup/stop](../../tools/test_qed_cleanup_stop.py) and
[coexistence lifetime](../../tools/test_qed_coexist_lifetime.py) runners for the
specific affected boundaries; do not automatically rerun the entire historical
QED matrix. Compare two applications' errno/streams/allocations under preemption,
normal and failed saves, partial initialization and repeated launch/collection.

Record matched 0.2.3/current image span, code/data/BSS, serialized APP size,
rounded loader backing, stack high-water observations, and runtime allocation
overhead. Validate the existing small-stack applications as well as QED's
declared pool. Change a declared minimum only with measured bounds and report
its Task-admission effect; expanding bank-zero pools is a separate decision.

Add a current `docs/reference/c-runtime.md` and update its reference index,
C application contract, C guide, QED native README and relevant build/relink
instructions. Current documents describe only delivered behavior; the design
and this plan retain pending work. Preserve historical qualification records.

## CR5 — Prove reuse with GemARC and deliver matching artifacts

Implement CR5 in smaller executable application commits; it is not complete
merely because a codec links against malloc. Freeze GemARC source/resource and
notice hashes in `ports/gem4xe/apps/gemarc/inputs.json`. The reviewed donor was
`0692b5519112dcde1f29f061ebcebe7a095aaf60`; select an explicit revision and
review any difference before import. Prepare cached originals and patched work
outside the donor checkout, following the calculator workflow.

1. **Build/list:** add preparation/build tooling, the resource patch and an
   ordinary `C:GEMARC.APP`. Open/list/select/scroll uses the common parser,
   allocator and descriptors. Adapt drawing to existing bars/fixed text and
   the current update protocol. Remove unsupported OUTLINED resource state;
   keep busy/status feedback within current public GUI facilities.
2. **Extract:** preserve donor method/CRC behavior and explicit unsupported
   methods 5–7. Distinguish read errors, truncation, CRC errors and cancellation.
   Extract through a temporary file when replacing an existing destination;
   validate bytes and terminal Close before publication. Keep processing bounded
   so redraws and cooperative close requests are serviced during work.
3. **Create/add/replace:** fix the donor's EOF/error conflation and discarded
   Close results. Use exclusive temporary names and a recoverable same-parent
   backup/publication sequence; a failed final rename must leave recoverable
   original/replacement copies. This is application policy over existing DOS
   semantics, not an invented atomic-replace guarantee. Keep full descriptor
   identities and native volume paths throughout.
4. **Integrate:** add launch arguments/ARC association, any required reusable
   SetFileDate C binding and honest backend timestamp limits, user documentation,
   source/notices and matched demo packaging. A further public binding addition
   requires a coordinated ABI update and rebuilt provider/APPs too.

**Gate:** compare extracted bytes and newly created archives with an independent
archive implementation, including empty files, stored/RLE/squeezed/LZW input,
dictionary growth/clear, CRC failure, member/batch limits and filenames needing
native 8.3 handling. Inject read, short-write, final Close and rename errors.
Reproduce the two known donor failures: read failure must not publish an empty
member as success; failed replacement rename must not lose the original.

Exercise partial allocation, directory enumeration failure, read-only media,
disk exhaustion, cancel/close during work, multiple instances and repeated
launch/collection beside QED and a computing/GUI peer. Check exact persisted
bytes, recovery names, ownership and heap restoration, not just UI messages.

Build any refreshed demo with [build_demo.py](../../tools/build_demo.py), keeping
OF816, the five-second standard autoboot, the matching combined writable system
ATR, MD5/ARC/EDX and required notices. QED remains a separate artifact under its
existing distribution policy. Run selected cold-boot and physical application
walks on the exact extracted optimized ZIP, including launch/stop, saved files
and clean EXIT. ZIPs contain only the prescribed boot files, short guides,
licenses and checksums; development outputs stay under build/.

## Checks, records and stopping criteria

Add narrow selectors to the new runtime runner from CR0 onward: `abi`,
`allocation`, `arguments`, `files`, `lifecycle` and `coexistence`, with individual
case selection. Default behavioral runs to optimized code. A typical future
selection after those tools exist is:

```sh
python3 tools/generate_c_runtime.py --check
python3 tools/test_c_runtime.py --group allocation --case opt --output build/c-runtime/cr1
python3 tools/test_c_runtime.py --group files --case opt --filesystem sdfs --output build/c-runtime/cr2-sdfs
python3 tools/test_c_runtime.py --group lifecycle --case opt --output build/c-runtime/cr3
```

For each coherent implementation slice run the host suite and relevant generator
checks. Raw/optimized execution is limited to affected ABI/compiler-facing
cases; do not duplicate full file/editor/desktop scenarios in raw mode. If a
runner cannot select the needed boundary, add a bounded selector first. Repeat
passing work only after changed inputs or a newly exposed concern justify it.

Each result record must name its tier, source/toolchain/input hashes, actual
case identifiers, expected/observed results, stack/guard state, IRQ/NMI evidence
where relevant and memory budget. Reused execution must match the actual code,
provider, APP and observer hashes. Keep per-slice records under
`build/c-runtime/crN/`; publish a reconciled development record with the current
reference once its corresponding slices pass.

All slices target **0 added reserved bank-zero bytes**: fixed, root/kernel,
each public Task and private idle, counting guards, alignment and spare
capacity. No new direct page, stack, worker or service Task is planned. Report
each actual slice's reservation delta even when zero. Account image-local
tables, 16-byte malloc prefixes, rounding, FILE/argv storage, linked code and
loader alignment capacity separately in upper RAM.

CR0–CR4 establish the shared runtime and migrated QED at the development tier.
CR5 establishes the second real consumer and selected distribution acceptance.
Do not mark the whole plan complete with a component-only pass, claim archive
correctness from malloc tests, or claim hosted-system qualification from
compiler tests. Full release qualification runs on frozen inputs for an actual
release or an explicit request, following the existing two-tier policy.

This plan-only change adds **0 executable bytes and 0 reserved bank-zero bytes**.
Its checks are documentation content, local links/anchors and whitespace;
all implementation and emitted-code gates remain pending.
