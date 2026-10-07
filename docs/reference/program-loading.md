# Native program loading

Exec consumes `actionc.o65.compact.v3` with the checked
`action65816.native.v2` ABI. The compiler profile defines the file format;
[abi/program.json](../../abi/program.json) defines Exec's resource policy and
errors. This is separate from the XEX image that boots the resident kernel.

## Validation

`O65.Validate(bytes, length)` reads an immutable, caller-owned buffer and returns
an upper-heap validation record, or null with a task-local DOS error.
`O65.Release(record)` frees its metadata. The caller must retain the exact
buffer, unchanged, until release. The validator does not publish executable
images, start Processes, modify source bytes, or read a compiler JSON sidecar.

Limits are 256 KiB file, 128 KiB serialized text, 64 KiB each initialized
data and BSS, and 64 imports. Counts are checked against both caps and remaining
bytes before allocation. Allocation failure unwinds every successful allocation.
Unsupported features, malformed data, resource caps and heap exhaustion have
distinct DOS errors. Older compact-v1/v2 and detailed profiles require rebuilding commands.

The standard o65 header, import names, relocations and entry export remain.
`__a816_o65_compact_v3` marks a text trailer: `A8C3`, a little-endian 16-bit
native ABI revision (2), 16-bit zero flags, then one 32-bit signature per import
in the standard table's order. Total metadata is **8 + 4 × import count bytes**,
at most 264 bytes. No import name, count or relocation record is repeated.

The loader checks exact file/trailer termination, version, ASCII names, entry
bounds, relocation sites and overlap, import indices and zero import addends.
Bank/long targets are bounded by their sections and placed addresses by 24 bits.
Low/high records contain truncated addends and use standard modulo byte/carry
patching. The compiler checks their complete symbolic targets, routine bank
containment, frames, objects/aliases and zero-extension containers on the host.
`build_command.py` retains those details in `.profile.json`, referenced by its
build record. Neither JSON file is needed on the Atari.

The profile fixes the entry to checked, IRQ-preserving `LONGINT FUNC()`, ordinary imports
to checked Task-only routines with zero unchecked stack allowance, and extra NMI
allowance to zero. The first import is the raw overflow adapter with signature
zero. Absolute storage and arithmetic-fault imports are rejected by the compiler.
The loader preserves the generated runtime stack guards.

These checks validate layout and declared contracts. They do not establish that
arbitrary machine code obeys those contracts or provide memory isolation.

## Memory accounting

Validation uses the existing upper heap. Its record contains two bounded
cursors, section offsets/counts and an owned import table. It uses the actual import
count and retains source spans rather than copying strings or allocating a
record for each relocation. Relocation streams are traversed twice. Peak memory
includes the complete caller-owned staging allocation and rounded metadata
allocations. No whole-bank owner competes with the heap.

Reserved bank-zero delta: **0 fixed bytes and 0 bytes per Task**, including
guards, alignment and unused reserved capacity. Loading runs in its caller's
existing stack/direct-page context.

## Placement and execution

`PROGRAM.Load(bytes, length)` validates the immutable source and returns an Image
instance, or null with a DOS error. After it returns the caller may release the
source buffer. `PROGRAM.Unload(image)` releases the caller's ownership. Image
records and fields are private implementation storage and must not be modified.

Each instance owns a separate text backing, initialized data and zeroed BSS.
Text is aligned to 64 KiB inside a linear upper-heap allocation of
`textBytes + $FFFF`, rounded by the allocator. The original base and requested
size are retained for freeing, including unused prefix/suffix capacity. Placement
checks prove the aligned extent stays inside that backing. Data and BSS inherit
the heap's eight-byte alignment. The compiler rejects absolute objects for this
profile. The compact trailer is excluded from the resident text allocation.

Representable relocation targets are checked before any private section is
patched, with the low/high validation boundary described above. BSS is explicitly requested with `MEMF_CLEAR`; text/data are fully
copied from source. Publication follows complete eager import binding and
relocation. Separate loads of the same file have separate mutable state. An
instance can have one running Process; a concurrent second start is rejected.
Starting a retained instance again preserves its mutable state; load a new
instance when fresh initialized data/BSS is required.

`PROCESS.StartLoaded(BYTE POINTER(image), arguments, length, foreground)` uses
the resident Process trampoline and finalizer. A nonzero `foreground` requests
the same loan as `StartForeground`. Successful admission holds an Image reference
until collection after the kernel's retirement acknowledgement. Unloading the
caller's reference while the child runs is safe. Admission rollback releases its
reference without publication. Ordinary `AddTask` still accepts only registered
resident procedures; the resident `PROCESS.ExecuteImage` function dispatches the retained
dynamic entry. No loaded-code finalizer or asynchronous callback is published.

## Checked providers

`COMMAND.Delay(ticks)` waits for LONGCARD VBI ticks through timer.device and
returns LONGINT -1 on success, zero with IoErr on failure. Positive waits require
Task context with scheduling enabled. A pending BREAK returns ERROR_BREAK;
interrupted alarms are aborted and their exact replies collected before return.
Zero ticks completes immediately unless cancellation is already pending.
The DOS context lazily caches one clock/alarm request and binding, using its
existing reply port. Context cleanup closes the idle binding and frees it.


`COMMAND.OpenPane(rows)` returns an owned, output-only lower console handle,
or NULL with IoErr. It preserves the default console's input route and focus.
`COMMAND.Close` and Process cleanup restore the parent's full height and retire
the pane. Only one full-width pane is supported; desktop mode and inheritance
of the pane handle are unsupported. See [console instances](console-windows.md).

`COMMAND.WriteAt(handle,column,row,buffer,length)` writes a printable horizontal
span to an owned console handle. Coordinates are zero-based CARD values; length
and result are LONGINT. It returns the accepted byte count, or -1 with IoErr.
It preserves the ordinary cursor, rejects non-console streams and does not
interpret escape sequences. Cancellation may return an accepted prefix with
ERROR_BREAK; wait for the synchronous call before reusing the buffer.

[abi/program.json](../../abi/program.json) defines the explicit `COMMAND` imports.
[build_command.py](../../tools/build_command.py) compiles a standalone o65 command
against their generated declarations. Names are `exec816_<operation>_v1`, plus
the profile's raw overflow adapter. Providers cover selected streams, synchronous
file/console I/O, arguments/results, cooperative break, Yield, buffered readers,
complete writes, directory enumeration, foreground-console queries, fault text
and template help. Commands do
not receive imports for creating Tasks or retaining callbacks into their image.

Program API version 4 exposes `COMMAND.GetArgStr()` as a borrowed `CSTRING`.
It replaces `Arguments()` / `ArgumentLength()` with the single
`exec816_getargstr_v1` provider. Argument payloads cannot contain NUL; an empty
argument tail is a valid non-null empty string. Commands may use `STR.strlen()`
for a length, or inspect the first byte to test for emptiness. The query preserves
`IoErr()` and does not allocate or copy. Rebuild commands and the resident image
together; the removed provider names have no compatibility aliases.

The [small argument parser](command-arguments.md) exposes
`COMMAND.ReadArgs()` in program ABI version 8: positional strings, `/A`, `/K`,
`/S` and unsigned `/N`,
with caller-owned result slots/storage. It reads the Process argument tail and
sets IoErr; it never consumes standard input or allocates memory. Program ABI
version 10 adds bounded `/M` results in the same caller storage. Rebuild all
commands with the current ABI when changing the parser contract.
Program ABI version 11 adds `AssignPath` and `GetAssign` for the bounded
[ASSIGN directory table](assigns.md).

`COMMAND.MODE_OLDFILE`, `MODE_NEWFILE` and `MODE_READWRITE` share the DOS
open-mode definitions in `abi/dos.json`. They are generated compile-time
constants and add no command imports or runtime storage.

Commands declare `LONGINT FUNC Main()` and return `COMMAND.RETURN_OK=0`,
`COMMAND.RETURN_WARN=5`, `COMMAND.RETURN_ERROR=10` or `COMMAND.RETURN_FAIL=20`. These are numeric constants;
no casts or runtime storage are needed. Arbitrary signed `LONGINT` results remain
supported. `build_command.py` selects `Main` explicitly before optimization.

`COMMAND.ERROR_*` exposes the shared DOS errors, including `ERROR_BAD_NUMBER`,
`ERROR_OBJECT_TOO_LARGE` and `ERROR_BREAK`. These constants are generated from
[abi/dos.json](../../abi/dos.json); commands do not define their own copies.
They add no runtime storage or imports.

The Process wrapper clears `IoErr()` after setup, then captures the returned
primary value and the final `IoErr()` before teardown. After a failed DOS call,
`RETURN(COMMAND.RETURN_ERROR)` preserves its cause. For a command-defined error
or an error saved across cleanup, call `COMMAND.SetIoErr(error)` before returning;
it returns the previous error. Both resident and loaded Processes use this
contract. Ordinary Task entries remain procedures.

The kernel packager generates `providers.json` and a native manifest from actual
emitted provider routines, checking their complete physical shapes against the
public API. The `EPV2` native manifest stores each provider's name, address,
extent and 32-bit signature. The loader matches names and signatures in one
manifest pass. Complete physical shapes remain in the host-side `providers.json`.
Ordinary providers are checked Task-only entries; the raw overflow provider is
the resident nonreturning adapter. Unchecked kernels are rejected.

The provider manifest remains within the existing 1,664-byte upper Task-arena interval
at offsets `$4000–$467F`; version 8 uses 1,218 bytes for 36 providers and adds
ReadArgsOrHelp, Fault and PrintFault. Its reserved capacity is unchanged. Its location and
capacity are generated from the program ABI. This adds no arena reservation.
Process ABI v3 uses three previously reserved row bytes for the Image reference;
the row remains 128 bytes. An Image record is 42 requested/48 rounded heap bytes.

## Disk loading and shell dispatch

`PROGRAMFILE.Load(path)` opens an exact DOS path, determines its bounded length,
and stages it in upper memory using reads of at most 4,096 bytes. Seek/read use
ordinary cancellable DOS calls. The file is closed before `PROGRAM.Load` validates
and publishes an Image; staging is freed before return. Break is checked between
reads and before/after validation. The first causal error survives cleanup.

The shell dispatches built-ins first. Bare tokens use the shell's bounded
[PATH search](../guides/shell.md#path), initially CurrentDir then C:. Standard
shell startup assigns C: to SYS:C, which holds the supplied disk commands. Tokens
containing `:` or `/` use one exact loader call. PROGRAMFILE.Load itself remains
an exact-path service. There is no implicit extension, script or background
syntax; one foreground pipeline of two external commands is supported. The bounded argument tail keeps
its original quoting and escapes, removes redirections, and joins arguments with
one space. Process admission copies it into owned storage. Selected input/output
and directory are inherited through the existing Process protocol; diagnostics
and prompts remain on the shell's private console. Application results, including
primary status 20, do not terminate the shell.

File input, NIL redirection and output to explicitly writable MyDOS/SpartaDOS
mounts work. Output redirection creates or truncates when Open commits; a later
command failure does not restore the previous file. A failed final Close retires
the handle and reports command failure while preserving a usable shell.
See [filesystem writes](filesystem-writes.md). Files are ordinary serialized o65 bytes,
without compiler sidecars. Example sources are [HELLO](../../examples/commands/hello.act)
and [ECHOARGS](../../examples/commands/echoargs.act), plus the usable
[WC counter](../guides/shell.md#wc); compile with
`python3 tools/build_command.py examples/commands/hello.act -o build/HELLO`.

The shell reuses its transfer buffer for arguments and final fault text. PATH
adds 1,024 upper-RAM bytes per shell; the shell header remains 128 bytes. There
is no fixed or per-Task bank-zero reservation increase.
The staging allocation is the exact file length, rounded by the existing heap.
