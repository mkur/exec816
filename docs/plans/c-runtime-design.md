# Shared C runtime for Exec816

[Plan index](README.md) · [Implementation plan](c-runtime-implementation-plan.md) ·
[C application contract](../reference/c-program-loading.md) ·
[Memory contract](../reference/memory.md)

Status: proposed, 2026-11-09. This note selects a common runtime design; it does
not add supported interfaces or change the current C application ABI. Implement
and document each executable slice before advertising its capabilities.
The implementation baseline is Exec816 0.2.3, including packaging commit
`8deec045`; the implementation plan records its exact source and cutover order.

## Problem and decision

QED already has native allocation, arguments, descriptors, stdio and error
adapters. GemARC needs substantially the same facilities. Keeping those services
inside each port would create several allocation policies, cleanup sequences and
interpretations of native file errors.

Provide one Exec-hosted C runtime, initially extracted from QED's MIT-licensed
native adapters and the pinned Calypsi library integration. Applications use
ordinary C interfaces such as `malloc`, `free` and `fopen`. The runtime obtains
storage and files through public Exec/DOS operations. Kernel heap policy,
filesystem consistency and Process retirement remain with their existing owners.

The first target is the existing Calypsi 5.18 large-code/huge-data APP profile.
This is a documented hosted-C subset, not a claim of complete ISO C or POSIX
conformance. The portable runtime has no GEM dependency; the existing hosted
runner continues to provide GUI attachment and retirement. A C provider for
headless builds and C commands in the native o65 format are separate work.

## Existing foundation

| Component | Current source and reuse |
| --- | --- |
| Allocation and ownership | [QED allocation.c](../../ports/gem4xe/apps/qed/native/allocation.c): allocation headers, an ownership list, calloc and realloc. Generalize the implementation and fix alignment as described below. |
| Arguments and cleanup | [baseline QED entry adapter](../../ports/gem4xe/apps/qed/native/README.md): bounded argument storage and cleanup. Replace its single-document argument rule with the common parser and runner lifecycle. |
| Descriptors and stdio hooks | [QED files.c](../../ports/gem4xe/apps/qed/native/files.c): full native handles, error translation, new-position seeking and terminal Close. Separate generic hooks from GEMDOS and editor metadata helpers. |
| Library preparation | [Runtime pin](../../toolchain/calypsi-runtime.json) and [preparation](../../tools/calypsi_runtime.py): checked library sources/headers and the explicit FILE initialization correction. |
| C entry and native retirement | [Shared C runner](../../c/calypsi/program.c) and [Process implementation](../../lib/dos/process.act): caller-context execution, GUI detach, native DOS cleanup and acknowledged Task retirement. |

The existing QED implementation is evidence and migration input. It is not yet
a general runtime: its argument rule, descriptor capacity, allocation prefix,
library exit handling and cleanup placement need deliberate changes.

## Proposed application contract

### One runtime scope per execution

An execution owns its allocation chain, `errno`, FILE list, standard-stream
wrappers, descriptors, argument vector and exit-handler stack. Keep that state
in the application's private upper-memory image or owned upper-heap storage.
Link the stateful C adapters and selected Calypsi library objects into each APP
initially. This gives separate library globals to separately loaded Images;
there is no resident process-global `errno` or FILE list shared by applications.
Inventory mutable state in every selected vendor object as part of its reset
contract, including any retained tokenizer pointer or random-number seed. A
library function with mutable globals cannot become a shared resident helper
without an explicit execution-local implementation.

One Image still admits only one running Process. Restarting a retained Image
creates a fresh runtime scope and clears its runtime globals, while ordinary
application globals retain the existing Image semantics. A pointer allocated
in the previous execution does not survive runtime cleanup. Applications must
initialize their own per-run state accordingly.

The first implementation has one calling Task per runtime scope. Other Tasks
may borrow buffers under the ordinary lifetime rules, but may not call that
scope's C allocator or stdio concurrently. Raw Tasks continue to use explicit
Exec allocation and synchronization. General C threads and shared-scope library
locking require a later public contract.

Correct pointers, matching frees and live borrowed buffers remain caller
responsibilities. Do not add repeated ownership scans or pointer validation to
every C call. Establish scopes and descriptors at admission and maintain their
state transitions.

### Startup, return and termination

Use one generated C runtime entry with synchronous lifecycle phases:

| Phase | Responsibility |
| --- | --- |
| INIT | Reset runtime state, construct arguments and initialize standard-stream wrappers. Record each completed initialization stage for rollback. |
| RUN | Establish the C termination boundary and call the application's main function. Return its result or a requested termination result. |
| FINISH | Run normal exit handlers when applicable, flush/close C streams and retire remaining owned descriptors. Preserve errors and leave the heap alive. |
| RELEASE | Release the argument storage, remaining allocations and runtime-only state after external borrowers have retired. |

The resident C runner invokes these phases as ordinary calls on the same
Process Task, stack and direct page, while its Image execution reference remains
held. The loaded entry is never installed as an AddTask finalizer, interrupt
callback or deferred kernel callback. No loaded code runs during collection.

The runner owns this order:

1. Enter with the existing native Process DOS context established; perform INIT.
2. Establish the current GUI attachment. A failed attachment or early stop skips
   RUN and unwinds only initialized resources.
3. Call RUN. Applications using asynchronous I/O or helper Tasks must settle
   those borrows before returning or requesting C termination.
4. Call FINISH. Normal exit handlers run while DOS, GUI bindings, arguments and
   allocated storage remain available. Stream/descriptor cleanup follows them.
5. Retire the GUI attachment through the existing runner's detach path. A failed
   ownership retirement retains the Task, Image and allocation scope; do not
   call RELEASE or report ordinary completion.
6. Call RELEASE after successful retirement. A terminal file error does not
   prevent release of a consumed descriptor or its buffers.
7. Return through the resident Process finalizer. It performs the existing
   native DOS cleanup, publishes retirement readiness and removes the Task.
8. Collect the Process and release the retained Image reference only after the
   kernel's retirement acknowledgement.

This is cleanup of the runtime's known resources. It does not discover or
repair arbitrary outstanding native requests, raw Task resources or application
ownership errors. Explicit early `free` remains valid after its borrowers end;
RELEASE walks only allocations still on the scope's list.

Support both `int main(void)` and `int main(int argc, char **argv)` through a
declared build-time signature and a matching generated call. They use the same
runtime entry ABI; do not guess a signature or call through an incompatible
function-pointer cast. Returning from main follows normal C termination.

`exit(status)` requests normal termination through RUN, including exit handlers
and stream flushing. It must not call RemTask or bypass native retirement.
`atexit` registers up to 32 callbacks, executed in reverse registration order;
exhaustion returns failure. Recursive termination from an exit handler is outside
the supported contract.

`_Exit(status)` and `abort()` skip user exit handlers and buffered-output
flushing. They still pass through mandatory GUI/native-resource retirement:
close underlying owned native descriptors without flushing discarded FILE
buffers, then release storage only when safe. An assertion uses the same
controlled failure path after a bounded diagnostic. This is an orderly native
retirement request, not recovery from arbitrary stack or memory corruption.

Normal return and exit support require a checked termination boundary. Audit the
pinned Calypsi nonlocal-return primitive before using it: preserve S, D, DBR,
return bank, processor widths/interrupt state and compiler workspace. The jump
must remain inside RUN on the owning Task; it must never cross a live native
gateway, ROM, IRQ/NMI or other Task activation. Keep unsupported library-exit
dependencies rejected by the builder until the focused emitted-code gate passes.

### Arguments and errors

Construct `argv[0]` from the Process's available name and parse the existing
bounded, NUL-terminated argument tail. Separate arguments at spaces/tabs outside
double quotes; remove those quotes and retain empty quoted arguments. Do not
perform wildcard expansion, environment expansion or shell execution. Reject
an unmatched quote before main. Preserve backslashes as ordinary bytes. The
native tail's 255-byte bound limits storage and argument count; size the vector
from the actual bounded input rather than allocating a large permanent arena.

`errno` is private to the image's current execution and starts at zero. Preserve
the exact native error separately when translation is necessary; map file-not-
found, read-only media, descriptor exhaustion, cancellation and I/O failure
consistently. Native DOS APIs retain their existing `IoErr` contract. Successful
C calls do not clear a prior C errno merely to indicate success.

Snapshot the application's primary result and native secondary cause before
automatic cleanup. Preserve an earlier application failure. A flush or terminal
Close failure after an otherwise successful main produces RETURN_FAIL (20) and
the first causal native error. Cleanup continues for all independently owned
resources. An application error number, errno value and IoErr are distinct
values; do not return one accidentally as another.

A previously observed errno, IoErr or stream-error indicator alone does not
turn a successful main into failure: the application may have handled that
error. Automatic result promotion applies to an actual flush/Close failure or
an unreported pending transfer failure encountered during finalization.

### Allocation

Use the public upper heap directly, with one backing allocation per malloc
block. There is no new heap algorithm, allocator Task or pre-reserved C heap.

| Call | Selected behavior |
| --- | --- |
| `malloc(n)` | Return an eight-byte-aligned pointer or NULL. Zero returns NULL without an allocation. |
| `free(p)` | Unlink and release the original backing; NULL is a no-op. |
| `calloc(count, size)` | Check multiplication before allocation and clear the complete requested payload. A zero factor returns NULL. |
| `realloc(p, n)` | Preserve the old block and bytes on failure; copy the smaller payload length on success. NULL acts as malloc. Zero frees p and returns NULL as an explicit runtime convention. |

Use a 16-byte allocation prefix containing the ownership links, requested size
and reserved padding. Its fixed size preserves the native heap's eight-byte
alignment. Store enough information to pass the original pointer and requested
backing size to FreeMem. The current QED prefix contains twelve bytes of fields;
it must not be copied unchanged into the aligned common interface.

Keep every ordinary backing allocation in one 64 KiB bank. The maximum payload
is therefore 65,520 bytes with this prefix, subject to available memory. Calypsi's
current `size_t` is 16 bits even in huge-data mode. Widen before adding the
prefix, check calloc overflow before multiplication, and retain native backing
sizes in a 32-bit type. Larger native linear allocations remain explicit
AllocMem operations; standard malloc does not silently cross banks in this
profile. Allocation/overflow failure returns NULL with ENOMEM.

The ownership list is execution-private. Its edits need no IRQ masking or
Forbid because no interrupt or peer Task consumes it; the backing heap already
serializes its own operations. Automatic cleanup is confined to this list and
does not alter the explicit ownership semantics of AllocMem/AllocVec.

### File descriptors and stdio

Provide up to sixteen owned file descriptors per execution, in addition to
the three standard descriptors. Each slot retains a complete native BPTR,
access/append state and a causal error. Small C descriptor numbers are indexes,
never truncated native identities. Descriptor exhaustion reports EMFILE.

Standard input borrows Input(); output and error borrow Output(), since there
is currently no separate native error stream. Closing a standard C wrapper
retires that wrapper without closing the Process's borrowed selected handle.
Standard output and error share the selected native stream and its position;
do not advertise independent stderr redirection.

Build standard streams and FILE bookkeeping with the actual pinned Calypsi
implementation and its recorded initialization correction. Keep FILE buffers
and the FILE list inside the runtime scope. The Exec runtime supplies the
vendor hook ABI; those hooks are not a promise of a general POSIX API.

Support read, truncate/create, existing-file update, append and exclusive create
through the corresponding public DOS modes. Test the advertised `r`, `w`, `a`
and update/exclusive forms against the pinned library parser before exposing
them. Text and binary file modes preserve bytes; there is no implicit ATASCII
or newline conversion. Native console behavior remains a property of its device.

Translate Seek's old-position result to the new position required by C hooks.
Preserve native limits, including rejection of seeks past EOF and the actual
same-parent/no-replacement Rename semantics. Append seeks to EOF before each
write; it does not provide atomic multi-writer append.

A positive short Read or Write may carry a causal IoErr. Return the confirmed
prefix, retain its pending error and make it observable through the C stream's
error state; never turn a failed read into EOF or retry away a disk-full error.
Honor Calypsi's exact signed-error encoding inside its 16-bit size_t hooks and
bound transfers accordingly. Terminal Close consumes the descriptor on either
result and is never retried using the old native handle.

FINISH closes all dynamically opened streams, flushes the live standard output
wrappers on normal termination, then closes remaining owned raw descriptors.
Free FILE structures and buffers exactly once while the allocator remains live.
Preserve the first causal error through the rest of cleanup. Namespace mutation
and finalization retain the [filesystem contract](../reference/filesystem-writes.md);
archive replacement, backup naming and recovery stay application policy.

### Library subset and limits

Select pure arithmetic, string/memory, conversion and formatting helpers from
the pinned compiler runtime. Record the actual linked closure. The initial
formatted-I/O profile selects the existing integer/long formatter explicitly;
floating-point formatting is not implied by the presence of printf declarations.
Support and test only the advertised format set.

An empty environment is supported: getenv returns NULL for absent variables.
There is no native UTC clock to synthesize. Preserve the current honest failure
for time() until a clock contract exists; file DateStamps are separate metadata.
Locale services, signals, C threads, dynamic library loading, process spawning,
system(), C++ constructors and an unrestricted vendor CRT are outside v1.

GEMDOS Malloc/Mfree and Fopen/Fread compatibility names stay in port adapters
over the common runtime. QED metadata and document policy stay in QED. GemARC's
date conversion and safe replacement protocol stay in GemARC; any needed
SetFileDate C binding is a reusable DOS interface extension, not a CRT-specific
kernel service.

## Implementation and migration

Create common adapters under `c/runtime/`, with public Exec-specific lifecycle
declarations under `c/include/exec816/`. Continue using the pinned standard C
headers. Keep reusable compiler primitives in their compiler/runtime owner;
the Exec adapters supply host services and lifetime integration. Preserve the
MIT notices on extracted native adapters and the original notices on selected
Calypsi/Apache/NuttX sources.

Keep the current [actionc pin](../../toolchain/actionc.json), C compiler/runtime
pins and platform configurations; record any local override explicitly. A
runtime source correction remains a pinned, reproducible input, not an edited
installed library or an application-specific code-generation workaround.

Add a machine-readable `abi/c-runtime.json` for lifecycle phases, invocation
records, limits and generated shared definitions. The fixed APP entry becomes
the generated runtime entry; update packaging and every-bank relocation checks
to verify that symbol and its calls. The resident native/C bridge remains an
ordinary call. Make the entry-contract change through a coordinated C APP ABI
revision and rebuild all applications/providers; keep one current implementation
and reject obsolete artifacts. Do not retain a QED-only allocator or an older
startup profile after migration.
Keep QED's single-document argument validation in the editor above the common
parser; it is application policy, not a second runtime argument convention.

The existing GUI provider requirement remains explicit during this work. The
runtime core must not require AES just to allocate or manage FILE objects;
optional host retirement remains the runner's responsibility. Splitting out a
headless provider can follow without defining another allocator or stdio ABI.

| Slice | Executable outcome and acceptance |
| --- | --- |
| CR0: freeze contracts | Inventory QED/vendor dependencies; add generated runtime layouts and a minimal phased-entry probe. Check both main signatures, partial INIT rollback, direct-page use, target type sizes and the existing native/C bridge. |
| CR1: shared allocation | Move allocation into common support with aligned headers and per-execution reset/release. Exercise calloc overflow, failed realloc preservation, maximum bank-contained blocks and two simultaneous images. |
| CR2: files and stdio | Move descriptor/error/library hooks and pinned FILE preparation. Cover standard streams, multiple files, supported modes, confirmed-prefix errors, EOF distinction, append/seek and failed terminal Close. |
| CR3: lifecycle and coordinated cutover | Integrate INIT/RUN/FINISH/RELEASE, update the current APP ABI and rebuild all providers/APPs together, including QED's common runtime ownership. Qualify exit's C-only unwind, atexit ordering, abnormal termination, stop, GUI retirement and results. |
| CR4: QED consumer acceptance | Complete QED's compatibility/document adaptation on the common implementation. Compare editing/saving, failure cleanup, image size and stack observations; update current runtime documentation. |
| CR5: second consumer and delivery | Port GemARC against the same runtime, initially as a listing/extraction consumer, then add its checked mutation path. Cover repeated launches and coexistence. Refresh the demo only through build_demo.py, preserving OF816, autoboot, notices and the small distribution ZIP. |

Allocation extraction can start in component fixtures before every termination
API is available, but each slice must leave a runnable current profile. New exit
interfaces remain unavailable until CR3 passes; entry ABI and all callers land
together in that slice. CR4 accepts the migrated consumer without retaining an
older startup or allocation implementation alongside it.
GemARC's archive codecs and its file-publication fixes require their own focused
tests; runtime completion does not establish archive correctness.

## Validation and memory budget

Use the [two-tier policy](../contributing/testing.md). For each implementation
slice, run host checks and focused optimized emitted-code behavior/failure tests.
Use small raw/optimized probes for layouts, entry/return shapes, compiler
workspace, pointer arithmetic and the termination boundary. Exercise actual
IRQ/NMI entry and Task preemption around allocation publication and C return;
SEI alone is not an NMI exclusion protocol. No runtime cleanup runs from IRQ/NMI.

The common acceptance cases include two independently loaded images with
different errno/FILE/heap state; one retained Image run twice; allocation and
stream initialization failure at every owned acquisition; explicit free followed
by automatic cleanup; outstanding GUI borrowers during retirement; and exact
parent heap/resource restoration after collection. A failed GUI retirement must
retain storage. A terminal Close failure must consume its handle, preserve its
cause and prevent a false success. Native raw-Task allocation behavior stays
covered by its existing tests.

Run QED's retained text, stdio, save/recovery and lifecycle cases after migration.
Use an independent archive reader for GemARC output and inject read, short-write,
Close and rename errors. Development results do not qualify the hosted system;
full qualification is reserved for the release/explicit qualification gate.

Target additional reserved bank-zero bytes: **0 fixed, 0 root/kernel,
0 per-public-Task and 0 private idle**, including guards, alignment and unused
reserved capacity. Reuse existing Task direct pages/stacks; add no private CRT
direct page, interrupt stack, service Task or hidden bank-zero arena. Runtime
code, tables, arguments, FILE objects and allocation headers live in upper RAM.
Transient stack use still needs measured bounds; retain all existing guards.

Account upper memory separately: each malloc backing requests payload plus the
16-byte prefix, rounded by the existing heap; image-local tables have bounded
descriptor/exit-handler capacities; stdio and argv consume only their actual
owned allocations. Record emitted table sizes, dead-code-selected library code,
loader alignment capacity and peak live allocations per program. Report stack
headroom and relocation span for QED and GemARC before expanding any reservation.

This design-note edit changes **zero** executable bytes and **zero** reserved
bank-zero bytes. Its validation is content and local-link checking only; all
CR0–CR5 implementation and executable acceptance remain pending.
