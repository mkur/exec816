# Small GEMDOS source compatibility layer

[Plan index](README.md) · [Hosted C runtime](../reference/c-runtime.md) ·
[Native DOS contract](../reference/dos.md) · [Memory contract](../reference/memory.md)

Design recorded 2026-11-14; delivered through the
[implementation plan](gemdos-compatibility-implementation-plan.md). The
[source contract](../reference/gemdos-compatibility.md) describes the installed
subset. This page retains the design rationale. MGVIEW is the first new
consumer model; its complete GUI port remains separate. QED uses the shared
wrappers rather than keeping a second implementation.

The initial consumer is [MGVIEW's loader](https://gitlab.com/AndreasK/Atari-Mac-MagiC-Sources/-/blob/28cfdd29aa16fef692cc287bad3046b44ddcce3d/MagiC/APPS/MGVIEW/SRC/MGWIND.C),
at the MagiC revision recorded in
[the Atari reference pin](../../toolchain/atari-st-reference.json). It opens a
file, queries its size, allocates a buffer and reads the document. The application
also uses Pterm/Pterm0. Fcntl is a MiNT/MagiC extension to the GEMDOS interface.

## Decision and boundary

Provide opt-in GEMDOS-shaped C calls over the existing common C runtime and
public Exec/DOS interfaces. Retain familiar application call sites such as
`Fopen`, `Fread`, `Fcntl`, `Malloc` and `Mfree`. Recompile applications for the
current Calypsi large-code/huge-data profile.

The library owns argument/result translation. The common runtime continues to
own descriptors, allocations, errno and execution cleanup. Native DOS owns
handles, exact file metadata, filesystem requests and cancellation. Drivers
retain their queue and device policy. There is no GEMDOS worker, new Task,
gateway, scheduler lock or filesystem implementation in this layer.

This is a documented source subset. It does not provide 68000 binaries,
`TRAP #1`, a TOS basepage, drive tables, DTA searches, process/thread emulation,
MiNT pipes or a complete GEMDOS dispatcher. AES/VDI binding adapters, window
gadgets, mouse handling, MGVIEW's parser and its 68000 `memchr2` replacement
belong to their respective port or GEM interfaces.

## Existing implementation to reuse

| Component | Current owner and disposition |
| --- | --- |
| GEMDOS file names/error mapping | [QED files.c](../../ports/gem4xe/apps/qed/native/files.c): promote its generic wrappers and one error translator. Keep editor metadata, exclusive-save and recovery helpers in QED. |
| GEMDOS allocation names | [QED allocation.c](../../ports/gem4xe/apps/qed/native/allocation.c): promote the thin adapters; keep `QedHeapSnapshot` as an editor diagnostic. |
| Descriptor identities and LONG transfers | [Common files.c](../../c/runtime/files.c): retain the sole descriptor table, pending-error protocol and consumed-close semantics. |
| Allocation bookkeeping | [Common allocation.c](../../c/runtime/allocation.c): retain its ownership chain, size prefix and deferred release. |
| Arguments and exit | [Common scope.c](../../c/runtime/scope.c): retain typed main, return/exit, FINISH, GUI retirement and RELEASE. |

QED already translates these calls through the common runtime. The new work is
to extract that reusable boundary, publish one subset, and add the missing
handle-based metadata path. It is not a reason to replace the runtime.

## Initial source interface

Public declarations/constants live in `c/include/compat/gemdos.h`;
implementations live in `c/compat/gemdos/`.
`abi/gemdos-compat.json` records supported calls, constants, integer widths and
the XATTR layout, with a generator for the C declarations and layout checks.

Use WORD/UWORD for modes, descriptors and command selectors; LONG for byte
counts, offsets and scalar results; and ordinary four-byte huge C pointers.
File operations return LONG, matching the existing QED adapters. Use
`void *Malloc(LONG bytes)` and `LONG Mfree(void *memory)`, including the
conventional pointer-shaped result for the `Malloc(-1)` query. QED's existing
LONG-returning Malloc declaration must migrate with its callers; do not leave
conflicting declarations or a second allocator entry point.

| Calls | Initial supported behavior |
| --- | --- |
| `Fopen`, `Fclose`, `Fread` | MGVIEW's ordinary file loading; preserve native counted binary reads. |
| `Fcntl(handle, argument, FSTAT)` | Exact size and regular-file type for the already opened object; narrow XATTR profile below. |
| `Malloc`, `Mfree` | Common-runtime allocation, release and largest-payload inquiry. |
| `Pterm`, `Pterm0` | Terminate through common `exit`, preserving ordinary runtime and GUI retirement. |
| `Fcreate`, `Fwrite`, `Fseek`, `Fdelete`, `Frename` | Promote the generic operations already used by QED, with their existing admitted modes. |

The last row avoids leaving duplicate generic wrappers in QED during migration;
it does not add further GEMDOS services. QED's current restrictions remain:
Fcreate accepts default attributes only, and Frename accepts its reserved
argument only when zero. Other Fcntl commands and unsupported open/share bits
return EINVFN before starting an operation. No successful placeholder stubs.

Port-local `mgx_dos.h` or `mintbind.h` may include the shared header and supply
the source spelling aliases required by that port. They must not supply their
own descriptor table, allocator, cleanup sequence or error translation.
The library uses native byte order and native huge pointers. Atari binary
record serialization and pointer-bearing desktop messages are separate work.

## Files, descriptors and errors

Use the current runtime's sixteen owned descriptor slots, 3–18. Its 0–2
wrappers keep the current Input/Output borrowing rules. GEMDOS descriptors
remain small integers; never truncate a native BPTR into a WORD. Capacity is
reserved before an Open can create or truncate. There is no compatibility
handle registry or separate descriptor lifetime.

Fopen modes 0/1/2 map to existing read/write/update opens, without implicit
creation or truncation. Paths and current directory use native DOS semantics:
for example `SYS:`, `WORK:` and inherited relative paths. Do not silently map
`C:\\...` into SYS or introduce a second current-drive mechanism.

Fread/Fwrite pass LONG lengths through `ExecCRuntimeRead/Write`, rather than
the vendor size_t transfer stubs. Preserve positive short prefixes, EOF and
the runtime's pending error for the following transfer. Do not add a loop that
changes a short read into an exact-fill operation. No CR/LF or ATASCII
translation occurs in the compatibility layer.

Fclose consumes the descriptor even if terminal native Close fails. It returns
that failure, never retries the native handle, and does not replay a previously
reported transfer failure. Preserve the common runtime's cleanup accounting.
Fseek returns the resulting position, reusing the existing runtime adaptation
of native Seek's old-position result. Caller-owned buffers must remain live
through synchronous I/O; valid pointers and capacities remain caller duties.

Publish one error map, based on QED's current table:

| Native cause | GEMDOS result |
| --- | --- |
| OBJECT_NOT_FOUND | EFILNF (-33) |
| DIR_NOT_FOUND | EPTHNF (-34) |
| Descriptor admission exhausted | ENHNDL (-35) |
| BAD_NUMBER / invalid descriptor | EBADF (-37) |
| NO_FREE_STORE | ENSMEM (-39); Malloc returns NULL |
| ACTION_NOT_KNOWN / unsupported operation | EINVFN (-32) |
| BAD_ARGUMENTS, SEEK_ERROR | ERANGE (-64) |
| File/delete protection, read-only media, object busy or exists | EACCDN (-36) |
| Other I/O failures, disk full and BREAK | Generic -1, with the original native cause retained |

For file calls, record the full cause in native IoErr and the runtime file
error slot before any cleanup can replace it; errno keeps the common C
translation. Allocation failures retain the common allocator's errno/IoErr
convention. Success follows the existing runtime rules rather than clearing
every error channel. An application preserving an earlier failure across its
own subsequent calls must still save that cause.

Separating EPTHNF from EFILNF is an explicit refinement of QED's current
ENOENT-to--33 collapse. Migrate and test those QED expectations with the shared
translator; do not retain two interpretations. This profile does not implement
every MiNT errno or GEMDOS device-error distinction.

## Open-handle metadata foundation

MGVIEW calls Fcntl with FSTAT before allocating its document buffer. FSTAT is
an open-handle query in the [GEMDOS/MagiC reference](https://freemint.github.io/tos.hyp/en/gemdos_file.html#Fcntl).
At design time, the native public interface exposed Examine/ExamineExact on
locks without a corresponding open-file operation. ExamineFH supplies it now.

SpartaDOS provides a useful precedent for the underlying operation. Original
SpartaDOS's `XIO 39` returns the currently open channel's 24-bit file length on
SpartaDOS-formatted disks; see the
[Construction Set manual, Get File Length](https://www.atarimania.com/documents/atari-8bit-spartados-construction-set-owners-manual.pdf).
SpartaDOS X exposes `FILELENG` with an open handle in `file_id` and the length
returned in `addpos`, separately from FTELL/FSEEK; see the
[Programming Guide, section 8.6](https://sdx.atari8.info/sdx_files/4.50/SDX450_Programming_Guide.pdf).
The native foundation is an open-file query; GEMDOS's Fcntl command selector
belongs at the compatibility boundary.

Exec's [SDX adapter](../../lib/dos/sdxfiles.act) already implements FILELENG in
`Length`, dispatched by [sdxservice.act](../../lib/dos/sdxservice.act).
It returns the session's cached `fileSizes` entry, captured from resolved
metadata during read-open. It does not query the live native handle or provide
a general public metadata operation. Reuse this consumer knowledge when
building the native operation below. A later, explicit SDX migration can use
the same foundation as GEMDOS FSTAT, retaining SDX's 24-bit result convention,
error mapping and admitted application profiles at its boundary. Do not expose
the SDX session/cache to the C runtime or expand the first extraction slice.

Add a reusable public DOS operation with the Amiga-shaped name
`ExamineFH(file, info)`, available to ordinary native Tasks and the C binding.
Its selected contract is:

- Query the object identified by the live owned file handle. Preserve its
  position and any shared inherited position on success and failure.
- For supported regular files, return FileInfoBlock metadata with an exact
  size flag. Use existing exact-measurement paths when directory metadata is
  only a bound, including MyDOS. Propagate I/O, cancellation and unavailable
  metadata errors; an approximate size cannot authorize an allocation/read.
- Return native DOS true/false and IoErr. Unsupported stream/device metadata
  returns ACTION_NOT_KNOWN. Caller pointers follow normal DOS responsibilities.
- Keep identity resolution and measurement in DOS/the filesystem handler using
  the existing request/retention protocol. The compatibility code never reads
  private handle structures or sector chains.

This adds useful native functionality: an open object's metadata without a
pathname lookup or cursor mutation. It follows classic Amiga's handle-oriented
DOS model; requiring exact regular-file size is the explicit Exec profile,
consistent with the existing ExamineExact distinction. It is a public DOS
operation, not a private compatibility gateway or a combined performance trap.

Do not implement FSTAT by saving the pathname and reopening it: rename,
replacement and relative-directory changes can select another object. Do not
emulate it with seek-to-end/restore: failure during restoration can change the
caller's cursor. Neither gives the selected operation's guarantee.

Add one private CRT helper accepting a descriptor and caller-owned FIB. It
resolves the existing descriptor once and forwards its full native handle to
ExamineFH; the handle never escapes into the public GEMDOS binding. This is
shared runtime composition for future descriptor metadata clients as well.
Metadata queries must not consume a descriptor's pending transfer error.
Use temporary upper-memory scratch for the 260-byte FIB, keeping large records
off scarce Task stacks. It belongs to the common allocation/cleanup path.

Implementation must update the machine-readable DOS operation definitions,
generated C/Action!/assembly bindings and applicable loaded-program imports.
Advance affected ABI revisions and rebuild providers and callers together.
The design reserves no signature or ordinal and adds no new COP service.

### Initial FSTAT information profile

Use the documented [XATTR field order](https://freemint.github.io/tos.hyp/en/gemdos_structures.html#XATTR):
52 bytes with the LONG size at offset 16, using the selected C layout. Generate
and execute layout/access checks rather than trusting host sizeof or casts.
FSTAT has selector `0x4600`; the LONG argument carries the target pointer.
The shared header must advertise that only the size/type information profile
is supported, so later ports do not mistake it for full XATTR support.

The first consumer contract guarantees **exact size and regular-file type**.
Initialize the complete record, fill size and the S_IFREG type bits, and leave
other fields zero, explicitly unavailable in this profile. Do not invent file
IDs, Unix permissions, sector counts or timestamps. Those fields are outside
the supported information contract even though the source record has their
names. In particular, zero date fields do not claim a real calendar date.
This is a size/type subset, not complete MiNT stat conformance.

On unsupported command/type, failed measurement or temporary allocation
failure, return the translated error without publishing an output record.
Reject a bounded/unknown size. A valid empty file succeeds with size zero.
The query is an observation, not a freeze: growth/shrink between FSTAT and
Read remains possible, and the application must handle short reads.
Additional XATTR information needs a separately specified native source and
translation before being advertised.

## Allocation and execution lifetime

Malloc uses the common runtime's allocation path and 16-byte ownership prefix.
Test the LONG request before converting to size_t. The initial ceiling is the
current 65,520-byte payload limit; failure returns NULL and records the cause.
Zero returns NULL using ordinary malloc's no-allocation convention. Negative
sizes other than -1 return NULL with BAD_ARGUMENTS; requests above the ceiling
return NULL with NO_FREE_STORE. The scope deliberately does not introduce a
separate cross-bank allocator or change ordinary malloc.

For `Malloc(-1)`, return the largest currently admissible common-runtime
payload encoded in the pointer-shaped result. Calculate it from the native
largest upper allocation, subtract the prefix, cap at the runtime ceiling and
account for existing alignment/rounding. It is a snapshot, not a reservation.
The caller converts that result to a LONG and never dereferences it. These
conventions follow the [memory-call interface](https://freemint.github.io/tos.hyp/en/gemdos_memory.html#Malloc).

Mfree releases a valid common-runtime allocation and returns zero. In this
single-user profile, ownership, matching allocation family and live pointers
are caller responsibilities; do not scan every block to detect arbitrary or
already freed pointers. Mfree(NULL) retains the current QED/free no-op
behavior as an explicitly supported extension. It does not expose native
FreeMem's required size or allocate another bookkeeping prefix.

MGVIEW's `fileSize+1` and `lineCount*sizeof(pointer)` must each fit the initial
ceiling, with overflow checked by its loader before allocation. Larger document
support is a later allocation/runtime decision, not an implicit consequence of
LONG Fread. Buffers supplied by other native allocation APIs can still use LONG
transfers when their caller owns a sufficient contiguous extent.

The initial profile requires the common loaded-C runtime's one calling Task
per execution. Link state into each APP through the existing builder and select
the wrapper sources explicitly. Do not add a process-global library singleton.
No second INIT/FINISH/RELEASE sequence or atexit sweep is introduced.

Pterm/Pterm0 call ordinary exit; FINISH closes runtime resources, GUI retirement
acknowledges borrowers, and RELEASE sweeps remaining backing. Never remove the
Task or free its Image directly. Valid retirement failure retains the existing
Task/Image/backing rather than bypassing cleanup. Raw Tasks that do not enter
this runtime continue to use native services directly.

The layer does not acquire UPDATE/MCTRL or suppress preemption around I/O.
MGVIEW's controller must keep loading outside drawing ownership and reset its
own document/window globals when a retained Image is executed again.

## Delivery slices and checks

1. **Extract the existing wrappers and migrate QED.** Establish the generated
   source header/error map and opt-in builder selection. Move generic file,
   allocation and termination adapters to the shared layer; remove duplicate
   QED definitions in the same slice. Keep QED save/recovery helpers and policy
   private. Prove unchanged descriptor/heap ownership and explicitly updated
   Malloc declarations and path-error expectations.
2. **Add native ExamineFH.** Generate the reusable native operation and rebuild
   its callers. Cover real regular files on RAM, MyDOS and SDFS; exact lengths,
   unchanged position, inherited shared positions, failures and cancellation.
   Where native rename/replacement is permitted, verify the opened object's
   identity survives it; preserve existing mutation restrictions otherwise.
3. **Add Fcntl(FSTAT).** Check generated XATTR layout, exact-size publication,
   unavailable fields, empty files, rejected streams/commands, memory failure
   and unchanged output/cursor on failure. Keep descriptor resolution inside
   the common runtime and file measurement inside native DOS/handlers.
4. **Execute consumer probes.** Compile the MGVIEW loader/model against these
   bindings and exercise small, maximum-admitted and oversized documents,
   short reads, errors, repeated execution and unwind paths. Retain the QED
   file/save regressions and a focused real-disk consumer check. The complete
   MGVIEW GUI port remains a separate application slice.

Use development-tier checks: host source/generation checks, small raw/optimized
emitted probes for C return types and shared layouts, and focused optimized
file/lifetime/integration cases. Include LONG transfers above 32,767 bytes,
bank-crossing caller buffers, descriptor exhaustion, two distinct loaded
Images and cleanup with outstanding allocations/files. QED migration must
cover its write/seek and consumed-close paths, not only MGVIEW's reads.

Documentation-only checks suffice for this note. Implementation evidence must
pin the actual compiler, ROM and emulator inputs; it does not establish full
hosted qualification. If a demo is rebuilt, use build_demo.py and its standard
OF816, SYS/WORK, notices and distribution checks.

## Memory and implementation ownership

The design changes **0 reserved bank-zero bytes**: fixed, root/kernel, idle
and per public Task, including guards, alignment and unused capacity. The
proposed implementation must retain those zero deltas and measure stack use;
it does not justify enlarging a Task pool. VRAM and the CPU aperture do not
change. Shared wrappers add selected APP code and temporary upper scratch;
reuse the existing descriptor table and heap prefix. Record actual emitted
bytes, scratch rounding and any native upper metadata growth per slice.

New C interfaces/adapters inherit the existing MIT scope of `c/`; preserve QED
adapter notices when extracting them. Native DOS/handler implementation follows
its repository licence. Keep donated MGVIEW code and its notices in the port.
Language/compiler defects remain actionc's responsibility; this design adds
no Exec-routine-specific compiler behavior.
