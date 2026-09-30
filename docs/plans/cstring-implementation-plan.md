# CSTRING module implementation plan

Status: **C1–C3 implemented and development checks passed**. Implements the
[C-string design](../reference/cstrings.md) across actionc and Exec816, targeting
`wdc-65816-native` first. Start from the compiler revision recorded in
[toolchain/actionc.json](../../toolchain/actionc.json).

Deliver three slices in two batches: **C1+C2 in actionc**, then **C3 in Exec816**.
Batch small edits before running checks. Near/far pointers remain deferred;
this work uses the current native pointer representation.

## Implementation record

Initial compiler C1+C2 is committed as `91c57696`; the reproducible
[patch](../../toolchain/patches/actionc-cstring.patch) applies after `f3ad9693`.
The external interface and provider contract live under
`embedded/modules/cstring` in the pinned compiler checkout. All seven exact
semantic signatures match the implementation. The hosted interface includes
only referenced imports, with no library bodies. Standalone code explicitly
uses `CSTRING.IMPL AS STR`.

The initial implementation costs 3,497 raw / 3,248 optimized code bytes, no library data
objects and no imports. Reported local stack peaks are 12–30 bytes; callers
retain their own frames. Compiler-facing bank-zero reservation delta is **0
fixed / 0 per Task**. Near/far pointers remain deferred.

Compiler validation passed: 3,548 tests, the NIR snapshot check and 51-fixture
sweep; focused native raw/optimized execution covers bounded accesses, separate
invocations, a 65,538-byte scan and compact-o65 execution at two placements.
LF and CRLF passed through the source loader. The native example also builds.
Scalar declarations retain existing Action! storage/address rules; assign a
CSTRING view in a routine or use LET. C-literal BYTE ARRAY initialization is
implemented as planned, including inferred extent and padding.

Initial Exec C3 publishes the seven functions directly through the existing EPV2
manifest and compact-o65 imports. The manifest grows from 479 to 707 bytes
inside its unchanged 1,664-byte upper-RAM reservation. Library functions are
excluded from Task-entry admission. Existing COMMAND signatures are unchanged.
At the initial C3 delivery, the refreshed play bundle's HELLO was 517 bytes
(previously 991) with no CSTRING imports; CAT and WC were byte-for-byte unchanged.
The subsequent HELLO source update uses a local CSTRING pointing to a literal,
calls the resident `strlen` once and reuses its result for the write and
byte-count check. The cleanup uses LET bindings and an IF expression in RETURN.
Raw/optimized command builds passed (720/689 bytes); runtime suites were not
rerun for this source cleanup, and the existing play bundle was not refreshed.

The loaded fixture checks every library call's relocated address, rejects
missing/version-mismatched/signature-mismatched imports, and runs two live
commands with separate stack pathnames and BSS read buffers. File Read keeps
its existing upper-RAM buffer requirement. It also exercises truncation, Process
results, image retirement, heap restoration, guards and OS restoration.
Run it with `python3 tools/test_cstring.py --case raw --output build/cstring/raw`
and the corresponding `opt` command after a coherent integration change.

Both modes passed all 91 checks. The host suite plus the focused provider rerun
cover 215 passing host tests; generated-interface checks and the refreshed play
bundle's loading/BREAK/recovery smoke passed. The bank-zero map, Task pools and
runtime reservations match the previous play image exactly. Full SIO,
filesystem and release matrices were not rerun. Detailed hashes, platform pins,
stack observations and costs are in the [development record](../development/cstring.json).

## Unsigned decimal conversion follow-up

Compiler revision `3607196d` adds `u32toa`; the reproducible
[patch](../../toolchain/patches/actionc-cstring-u32toa.patch) applies after
`91c57696`. Exec's compiler pin adopts that revision and publishes the eighth
library function through the same checked native import path. WC now calls it
three times and retains only report layout, removing its private `Number`
routine and decimal table. The 33-byte report still holds three maximum-width
counts plus two spaces and a newline; each intermediate NUL is overwritten by
its separator.

WC's compact-o65 size changes from 3,999 to 3,764 raw bytes and from 4,191 to
4,016 optimized bytes. Conversion adds 1,222 raw / 1,133 optimized resident code
bytes. Local stack peaks are 34 / 30 bytes respectively, within unchanged Task
reservations; the incoming argument area is 11 bytes. The table and its pointer
occupy 43 data bytes, rounded to 44 by the following global's alignment in the
resident fixture. The existing 2 KiB near-image reservation absorbs this data.
Reserved bank-zero delta is **0 fixed / 0 per Task**, including guards,
alignment and unused reserved capacity. The play bundle is not refreshed by
this change; using the new WC requires a rebuilt resident image with its export.


Development checks passed: three compiler interface/frontend tests and four
native CSTRING tests. The new decimal test covers 628 raw/optimized invocations
across decimal boundaries, maximum unsigned values, zero/short/exact buffers,
bank-crossing writes and both IRQ-mask states. The Exec host suite covered 215
tests; after correcting the expected manifest length, the five provider tests
passed on the focused rerun. Both generators pass `--check`.

WC passed all 16 controlled-stream cases in each mode. The updated resident
fixture passed 95 checks in each mode, covering the new import, maximum-value
conversion, separate live callers, relocation, retirement, guards and OS
restoration on the pinned platform. Results are under
`build/cstring-u32toa/{wc,resident}/{raw,opt}/results.json`. The bank-zero budget,
runtime reservations and Task pools match the original C3 builds. No release
matrix or broad compiler suite was run.

## Character constants follow-up

Compiler pin `ed07a4c6` adds the constants-only `ASCII` module; the
[patch](../../toolchain/patches/actionc-ascii.patch) applies after `3607196d`.
It also includes the explicitly named `ATASCII_EOL=$9b` extension. WC and CAT
use qualified character names. CAT retains its semantic `ESCAPE` alias for
`ASCII.ASTERISK`.

Raw and optimized command builds are byte-for-byte identical to the preceding
WC and CAT builds. Build records under `build/ascii` record the local compiler
override used before pinning the identical source. No execution suites were
rerun for these constant substitutions. There is no added code, data, import,
or reserved bank-zero memory: **0 fixed / 0 per Task**.

## System constant follow-up

Compiler revision `c5e9e267` introduced the typed compile-time constant
`SYS.MAXLONGCARD=$ffffffff`; WC uses it instead of a private limit.
The [patch](../../toolchain/patches/actionc-system-constants.patch) applies after
`ed07a4c6`. Raw and optimized WC binaries are byte-for-byte identical to the
local-constant builds. Records under `build/sys-maxlongcard` capture the local
compiler override checked before committing the identical source. Execution
tests were not rerun for this substitution. Added code, storage, imports and
bank-zero reservations are all zero (**0 fixed / 0 per Task**).

The current pin `d3e91900` also exports `SYS.MININT=-32768`,
`SYS.MAXINT=32767`, `SYS.MINLONGINT=-2147483648` and
`SYS.MAXLONGINT=2147483647`, typed as INT and LONGINT respectively.
The same patch now includes both additions. Focused raw/optimized builds under
`build/sys-integer-limits` emit identical bytes for these system constants and
equivalent typed private constants. No runtime suites were rerun, and no code,
storage, imports or reserved memory are added by the constant declarations.

## Command argument follow-up

Program API v4 and Process ABI v6 replace the public argument pointer/length
getters with `GetArgStr()` returning a borrowed `CSTRING`. COMMAND stays the
small command-facing module. Process startup rejects embedded NUL while copying
the bounded payload; allocation and cleanup retain the length privately. WC,
CAT, ECHOARGS and the loaded fixtures use the new getter. The provider manifest
shrinks from 739 to 699 bytes. Reserved memory is unchanged, including
**0 fixed / 0 per Task** bank-zero bytes.

Focused development checks with compiler pin `ed07a4c6` passed: 215 host tests;
raw and optimized command builds; 16 WC and 15 CAT stream cases per mode;
8,171 Process lifecycle checks per mode, including empty/255-byte arguments,
independent copied storage and embedded-NUL rollback; and 103 resident-library
checks per mode, including loaded imports and Image-retention rollback. Results
are under `build/getargstr/{wc,cat,process,resident}/{raw,opt}/results.json`.
The inheritance fixture passed interface compilation; its full scenario matrix
was not rerun. Both ABI generators pass `--check`. This is development validation,
not a release qualification. The play bundle has not been refreshed; commands
and the resident image must be rebuilt together for the changed provider API.

## Scope and ownership

actionc owns `c"..."`, the `SYS.CSTRING` type, the public `CSTRING` interface and
its implementation in ordinary Action!. Exec owns compiler-pin adoption,
resident library packaging, provider publication and application callers. The
implementation has no allocator, DOS, Exec, OS or cartridge dependency, no
mutable global scratch, and no initialization or cleanup routine.

Link the implementation **once into the resident system image**, alongside Exec.
It remains library code running on the calling Task's stack and context, with
ordinary native calls and no COP transition. Commands contain external imports
for the routines they use, rather than another copy of the library bodies.
Keep the library resident for the system image's lifetime; command unloading
does not unload it. Dynamic library discovery/unloading is outside this slice.

The initial seven functions are extended with unsigned decimal conversion.
`SIZE` supplies native lengths and capacities; `INT` supplies signed comparison
results. Declarations below describe the implemented API.

| Function | Parameters | Result |
| --- | --- | --- |
| `strlen` | `SYS.CSTRING text` | `SIZE` |
| `strnlen` | `BYTE POINTER bytes`, `SIZE maximum` | `SIZE` |
| `strcmp` | `SYS.CSTRING left, right` | `INT` |
| `strncmp` | `SYS.CSTRING left, right`, `SIZE maximum` | `INT` |
| `strchr` | `SYS.CSTRING text`, `BYTE value` | `SYS.CSTRING` |
| `strlcpy` | `BYTE POINTER destination`, `SYS.CSTRING source`, `SIZE capacity` | `SIZE` |
| `strlcat` | `BYTE POINTER destination`, `SYS.CSTRING source`, `SIZE capacity` | `SIZE` |
| `u32toa` | `LONGCARD value`, `BYTE POINTER destination`, `SIZE capacity` | `SIZE` |

Use `USE CSTRING AS STR` in examples, giving calls such as `STR.strlen(text)`.
This keeps the module alias separate from the contextual type spelling
`CSTRING`. Use canonical `SYS.CSTRING` in the module's own declarations and test
both type spellings under an aliased import. Do not redesign name resolution
just to support an unaliased module/type collision.

## Function contracts

`u32toa` converts `0` through `4294967295` to decimal, with no leading zeros
except the single digit for zero. Capacity includes NUL. It returns the full
digit count even on truncation, writes at most `capacity-1` digits, and appends
NUL when capacity is nonzero. Zero capacity permits a null destination and
performs no destination access. Unused padding is unchanged. An 11-byte buffer
always suffices; `result >= capacity` means the complete string did not fit.
This is an Action library extension, not a standard C function. It has no
allocation, division helpers or global working state; its shared decimal-place
table contains 40 bytes plus a three-byte Action array pointer. The current
resident image layout puts compiler globals in the existing bank-zero
`near-image` arena: 44 active bytes including following alignment, with no
reservation enlargement. Sharing this table avoids a per-call table on the
Task stack. Signed and general formatting remain deferred.

`strlen` counts bytes before NUL. `strnlen` reads at most `maximum` bytes and
returns the count before NUL, or `maximum` if none occurs. Its byte-pointer
parameter deliberately permits checking a buffer before borrowing it as a
`CSTRING`; it does not require a terminator beyond the bound. Neither reads a
length prefix. See the [C length API](https://man.openbsd.org/strlen).

`strcmp` and `strncmp` compare unsigned bytes, stop at NUL, and return a negative,
zero or positive `INT`. Callers must not rely on an exact difference. `strncmp`
compares at most `maximum` bytes and performs no reads when that limit is zero.
These are case-sensitive byte comparisons, with no locale or ATASCII folding.
See the [comparison API](https://man.openbsd.org/strcmp).

`strchr` returns a borrowed view beginning at the first matching byte, or
`SYS.CSTRING(0)` if absent. Searching for byte zero returns the terminator's
address. The result has the source's lifetime and remains a read-only view.
`BYTE value` is our explicit byte-oriented adaptation of C's integer parameter.
See the [character-search API](https://man.openbsd.org/OpenBSD-7.3/strchr.3).

Follow [strlcpy/strlcat semantics](https://man.openbsd.org/strlcpy):

- Capacity is the complete destination extent, including room for NUL.
- `strlcpy` copies at most `capacity-1` payload bytes, terminates when capacity
  is nonzero, and returns the full source length.
- `strlcat` finds the existing terminator within capacity, then appends as much
  as fits and terminates. Its result is the bounded initial destination length
  plus the full source length. If there is no destination NUL within capacity,
  leave the buffer unchanged and return `capacity + source length`.
- A result `>= capacity` means the complete terminated result did not fit.
- Zero capacity performs no destination access; the source is still scanned.
  A null destination is permitted only in this zero-capacity case.
- Do not zero-fill unused capacity. Source and destination must not overlap.

Except for explicitly unused zero-bound inputs, pointers must identify live,
accessible storage; a `CSTRING` source must have a reachable terminator. Counts,
capacities and returned lengths must fit `SIZE`. No address wrap is supported.
There is no `IoErr` or errno state, and no hidden buffer validation or allocation.
Check bounds before loads rather than relying on Boolean evaluation order.

Copy and append must count the remaining source after truncation to preserve
their return contract. Implement counting in the same traversal as copying;
avoid a preliminary `strlen` plus a second full source pass. Append needs one
bounded destination scan. More elaborate string builders are outside this slice.

## C1 — actionc: literals, type and emitted storage

1. Add a distinct C-string token/literal carrying decoded bytes. Recognize
   adjacent `c"`/`C"`; implement the escapes and malformed-input diagnostics
   from the design, with `\n=$0A` and two-digit `\xHH`. Append one NUL, preserve
   embedded NUL, and leave ordinary Action! literal decoding unchanged.
2. Add canonical `SYS.CSTRING` and its contextual unqualified spelling. Give it
   pointer-sized storage and a stable semantic signature identity. Implement
   assignment, parameters/results, record fields, null, explicit byte-pointer
   conversions, and read-only indexing/dereference. Reject writes through a
   CSTRING view and implicit conversion of ordinary Action! strings.
3. Support C-literal initialization of byte arrays: infer payload-plus-NUL
   extent, check explicit capacity, zero-fill excess declared space, and keep
   writable array backing separate from immutable literal-expression backing.
   Preserve existing array representation and initialization lifetime rules.
4. Carry storage identity, bytes and access permissions through SemIR/NIR.
   Use native data pointers, existing static-data emission and relocations in
   MIR65816 and compact o65. No runtime conversion or new o65 metadata is needed.
   Cover direct and indirect calls with CSTRING parameters/results. Gate new
   constructs with an explicit diagnostic on targets not yet supported.
5. Document literal/type semantics in actionc and add focused fixtures to the
   existing frontend, NIR, native ABI and o65 test infrastructure. No near/far
   qualifier, new pointer memory model or general const system is part of C1.

**Exit:** C-literals and mutable array initialization execute in raw/optimized
native code, preserve byte values across relocation, and keep ordinary Action!
strings unchanged. The compiler, rather than individual Exec callers, enforces
the new source rules.

## C2 — actionc: ship the small library

1. Add `embedded/modules/cstring.act` as the seven-function **external interface**
   and `embedded/modules/cstring/impl.act` as `MODULE CSTRING.IMPL`, holding the
   single implementation. Publish a compiler-owned machine-readable contract
   for those declarations and versioned public symbols; generate the interface
   or check it against that contract. Register both through normal embedded
   module packaging. `USE SYS` for type names must not pull legacy runtime code.
   Do not rely on an Exec module-path override: embedded modules currently win
   lookup, so the public interface must already be external.
2. Use pointer movement and `SIZE` counters that work across a 64 KiB boundary.
   Keep the borrowed result of `strchr` tied to the original backing. Do not
   implement copy/append through allocating helpers or shared temporary buffers.
3. Add a short module guide and runnable native example showing literal use,
   copying, appending and checking `result >= SIZEOF(buffer)`. Show explicit
   conversion when a mutable byte array becomes a CSTRING input. Standalone
   examples/tests can explicitly use `CSTRING.IMPL AS STR` to include the source
   implementation; hosted commands use `CSTRING AS STR` for resident imports.
   This is one implementation with two binding choices, not two library ABIs.
4. Inspect dependencies and emitted sizes for both bindings. A hosted
   `strlen`-only command must contain one CSTRING import and no CSTRING routine
   bodies or data. The source implementation still follows current whole-module
   inclusion; measure its seven-routine cost once in the resident image. Keep
   optional functions separate. Generic selective linking is not required.

**Exit:** a compiler-owned implementation, external interface and checked
contract available from the pin. Record raw/optimized code/data bytes, stack
peaks and imports; verify that importing the interface alone adds no library
bodies or hidden mutable state.

### Compiler batch validation

Run this after C1+C2 form a coherent change, not after every small edit. Reuse a
single bounded native fixture per raw/optimized mode for the function cases:

- Exact escape bytes, empty strings, embedded NUL and a literal over 255 bytes;
  malformed escapes, failed type conversions and writes through read-only views.
- Exact/oversized/undersized array initialization; parameters, returns, record
  fields, alias/type lookup and literal lifetime after returning from a routine.
- Empty/equal/prefix/unequal comparisons, unsigned bytes `$80`–`$FF`, zero bounds,
  bounded scans without a NUL in the inspected prefix, and `strchr` hit/miss/NUL.
- Copy/append capacities zero, one, exact fit and truncation; a full unterminated
  destination; required-length returns and unchanged bytes outside capacity.
  Verify bounded reads as well as writes with the existing VM access observer.
- A length over 65,535 and a terminator across a bank boundary; no 16-bit wrap.
  Use canaries, existing stack/register checks and bounded completion. Demonstrate
  independent native invocations without global scratch.
- Existing compact-o65 relocation fixtures with C-literal references in two
  placements; compare external declarations with implementation signatures.
  A hosted caller imports only used functions; implementation fixtures have no
  allocator, Exec or OS dependencies.

Normalize LF/CRLF host text before fixture parsing; exercise both forms through
the actual source-loading path while preserving expected binary bytes.

Because C1 changes shared semantic/NIR contracts, actionc's contributor rules
also require these checks once before delivering the compiler batch:

```sh
cargo test nir_fixtures_match_snapshots
cargo run --bin actionc-nir-sweep -- fixtures/nir
cargo test
```

Reuse the focused results when their inputs have not changed. Commit the coherent
compiler batch after checks, recording the revision and reproducible patch if
the existing Exec toolchain workflow still requires one.

## C3 — Exec816: publish the resident library and demonstrate

1. Move the [compiler pin](../../toolchain/actionc.json) to the completed C1+C2
   revision, with matching provenance. Include `CSTRING.IMPL` once in the
   resident image's library composition. Do not create a second implementation
   under Exec's `lib`, place it in kernel dispatch, or add a worker.
2. Extend [provider generation](../../tools/generate_program.py) to accept an
   explicit CSTRING library group alongside the current COMMAND providers.
   Consume the pinned compiler's library contract and bind its versioned symbols
   directly to the emitted implementation routines, checking exact signatures,
   native calling shapes, stack checks and executable extents. Support `SIZE`,
   `INT`, `BYTE` and `SYS.CSTRING` in contract validation. Use symbols such as
   `cstring_strlen_v1`; keep existing COMMAND names/signatures unchanged.
3. Extend [command builds](../../tools/build_command.py) to recognize the declared
   CSTRING externals and map them to that group. Discover actual references;
   do not import all seven functions merely because the interface was loaded.
   Use the existing o65 imports, relocations and EPV2 provider manifest. The
   loader already resolves names/signatures once before execution, so calls need
   no lookup or wrapper on each invocation. Keep publication allowlisted rather
   than exposing every public routine or widening Task-entry admission.
4. Migrate HELLO's greeting to a CSTRING variable pointing to a literal containing
   its newline. Keep counted `COMMAND.Write` with an explicit byte-pointer bridge.
   HELLO obtains the length through the resident `strlen` and reuses it for the
   result check.
5. Add one small disk-loaded integration fixture that imports CSTRING, builds a
   pathname with `strlcpy`/`strlcat`, checks capacity results, opens/reads a known
   file, and exercises comparison/search. Include one truncation path with a
   named command result and deterministic output. Use explicit raw-pointer
   bridges to the current COMMAND API where needed. Verify that two live native
   callers use the same library code with independent buffers and stack state.
6. Preserve current Exec provider signatures. General migration of
   `Open`, `FindName`, shell helpers and other public text APIs to CSTRING is a
   separate ABI slice; the [design note](../reference/cstrings.md#exec-api-use-and-abi-impact)
   records its rules. Preserve counted Process arguments and binary I/O.
7. After the batch, run the host suite, affected provider/generator checks and
   the focused raw/optimized loaded fixture with guard, resource-retirement and
   OS-restoration checks. Cover missing/version-mismatched/signature-mismatched
   CSTRING imports through existing rejection machinery. Inspect binaries to
   confirm library bodies occur only in the resident image and calls resolve
   directly to those addresses. Rebuild the play bundle once and run its short
   loading/recovery smoke. Record results and commit the Exec slice.

Do not rerun complete SIO, filesystem, shell or release matrices for this change.
If a focused failure exposes a broader issue, investigate that issue before
choosing additional checks; successful unchanged results remain reusable.

## Completion and deferred work

Completion means C-literals and CSTRING work on the native 65816 target; all
published library functions have the documented byte/length behavior; hosted commands
share one resident implementation through checked imports, without an allocator
or new kernel services; and compiler/Exec provenance and validation are recorded.

The original C3 play image's EPV2 manifest occupied 707 of its reserved 1,664
upper-RAM bytes. Adding `cstring_u32toa_v1` brought this to 739 bytes; replacing
the two argument getters with `GetArgStr()` brings current manifests to 699
bytes, still inside that reservation. No capacity enlargement is needed.
Resident code size is measured in the implementation record above. Commands pay
the usual o65 name/relocation/signature cost only for functions they import.

Report added reserved bank-zero bytes for each delivered batch, including guards,
alignment and unused capacity, with per-Task costs separate. Delivered: **0 fixed
and 0 per Task**. Report ordinary emitted code/data and actual stack use
separately; the library's machine code is not free merely because it allocates
no heap storage. Compact o65 metadata remains **8 + 4 × import count bytes**.

Defer near/far pointers, allocating strings/`strdup`, growing buffers, general formatting,
locale/Unicode support, case-insensitive filesystem policy, generic selective
linking, assembly tuning, dynamic library loading and broad public text-API
migration. Other reusable modules can join the same explicit resident-provider
mechanism later. None is required
to deliver this module. See the implementation record above for the checks run.
