# C application image profile

The `exec816.c-program` profile describes bank-relocatable Calypsi 5.18 code
using the large-code/huge-data ABI. It is separate from the
[native o65 contract](program-loading.md). Its constants and import ordinals
are defined in [abi/c-program.json](../../abi/c-program.json).

`PROGRAMFILE.Load` and `PROGRAM.Load` recognize this profile alongside native
o65. A desktop build supplies the fixed C provider; a build without that
provider rejects the image with `ERROR_BAD_PROVIDER`. Loading does not start
an application. Use the ordinary Process start, wait/collect and Image unload
operations to retain ownership through execution.

## Build profile and relocation

`tools/build_c_program.py --source file.c --output build/application` produces
`program.app` and a development-only `app.json`. Add `--source` for another C
translation unit or `--raw` for unoptimized C. The target needs only the APP.

Code starts in relative bank zero; initialized data, constants and BSS retain
the linker's relative placement. The packer links the same objects at banks
12 and 13 and derives bank-byte fixups. It then independently links at **every
legal base in the bounded 64-bank profile** and verifies segment sizes, flags,
all loaded symbol positions and reconstructed bytes. Unsupported layout or
address arithmetic fails packaging. Small compiler runtime helpers stay local.
This is a checked build profile, not a relocator for arbitrary C binaries.

Imported calls use application-local `JML` tail thunks. Loading replaces their
three-byte targets once. A function pointer to an import points to its local
thunk; ordinary calls have no dispatcher or repeated ABI validation. Import
ordinals select functions in the build's fixed resident C provider. Mutable
service globals and additional application Task entries are not imports.
Rebuild applications when the ABI changes; there is no legacy-profile shim.

## File layout

All integers are little-endian. The 32-byte header is followed by segment
records, import records, bank-fixup offsets and concatenated segment payloads.
The header's file length must match exactly.

| Header offset | Width | Meaning |
| --- | --- | --- |
| 0 | 4 | `C816` |
| 4 | 2 | Container version, 1 |
| 6 | 2 | Import ABI version, 2 |
| 8 | 1 | Reference link bank, 12 |
| 9 | 1 | Bank address limit, 64 |
| 10 | 2 | Segment count |
| 12 | 4 | Complete memory span |
| 16 | 4 | Entry offset from aligned image base |
| 20 | 4 | Number of bank-byte fixups |
| 24 | 2 | Number of imports |
| 26 | 2 | Compiler lower-DP workspace, 20 or 23 bytes |
| 28 | 4 | Complete file bytes |

Each 16-byte segment has four 32-bit values: relative offset, serialized bytes,
reserved bytes and flags (1 executable, 2 writable, 0 read-only data). Segments
are ordered and disjoint. Zero serialized bytes describes BSS. An import is an
8-byte record: ordinal (16 bits), zero reserved word, and the 32-bit relative
offset of its thunk's three-byte operand. Each fixup is a 32-bit relative
byte offset; fixups are strictly increasing. The loader adds the signed bank
displacement modulo 256 to that byte.

Limits are four segments, a 256 KiB file and a 192 KiB memory span. Admission
checks versions, file/segment bounds, executable entry, serialized fixup sites
and available imports once. This does not verify arbitrary instruction streams
or provide memory protection. Callers retain responsibility for valid API use.

## Storage and entry bridge

One upper-heap allocation of `span + 65535` bytes supplies a bank-aligned image;
the original base and size remain available for freeing. Allocator rounding,
alignment padding and gaps are part of its cost. The backing is cleared before
copying data. Each load therefore has private initialized data and BSS; another
call to a retained instance preserves its state.

`CALYPSICALL.Invoke(entry, argument)` is an internal ordinary native/C bridge
for a Calypsi `LONG __simple_call function(ULONG)`. It returns A/X as a signed
32-bit native result and preserves D, DBR, Y, caller mode and all 24 lower-DP
bytes, including Calypsi's spill-helper workspace. Native scratch remains
caller-owned. IRQ/NMI and scheduling stay enabled. Its own peak stack cost is
40 bytes, in addition to the caller's outgoing arguments and the C call chain.
A synthetic RTL target keeps the bank unchanged when the entry is at `$0000`.

The shared Process wrapper attaches and registers the Task's AES context, calls ordinary
`int main(void)` with its C ABI and sign-extends the 16-bit result to the native
32-bit Process result. `ExecGetArgStr()` returns the borrowed, NUL-terminated
Process argument string; it returns null outside a Process. There is no hosted
`argc`/`argv` startup or command-line parser.

On return, the wrapper detaches AES, settling windows, drawing references,
resources and timers before native DOS cleanup and Process retirement. An
application can explicitly close its resources earlier. The Process owns DOS
cleanup; an application must not also call `ExecDOSDetach`. If AES attachment
or registration fails, the Process returns 20. If teardown fails, it reports the failure to
its output and parks with its Task and image retained. There is no forced
unload. The parent must collect every child before it exits.

`PROCESS.RequestStop` (also used by `ExecBreakProgram`) requests `WM_CLOSED`
through the child's AES registration. A stop before entry skips `main` and
returns zero; a stop before `wind_open` remains pending until the window opens.
Native children retain ordinary Process BREAK behavior. Applications must
handle the close event and return; a nonresponsive application remains alive.
The sender uses retained Process/AES ownership, not application model pointers.

Passing a C entry to native `LONGINT FUNC()` directly is unsupported.
Calypsi routines have no Action! per-routine stack checks;
Task/domain guards remain and stack use must be measured for each application.

Fixed, per-public-Task and private-idle bank-zero reservation changes are all
**0 bytes**, including guards, alignment and unused reserved capacity. The
bridge and image use existing Task stacks and DPs; loader metadata and image
backings live in upper RAM.

The [LG2 development record](../development/loadable-gem-lg2.json) covers raw
and optimized native/C emission, two simultaneous copies at different bases,
all permitted link bases, retained state, IRQ/NMI and heap/guard restoration.
It does not qualify arbitrary C programs or a hosted desktop release.
The [LG3 record](../development/loadable-gem-lg3.json) adds SDFS/MyDOS Process
dispatch, signed `main` results, argument access, failure rollback and complete
AES/image retirement over repeated cycles.
