# C-string literals and CSTRING

> Historical record: applies to the revisions and profiles described below.
> See the [current documentation](../reference/cstrings.md) and [history index](README.md).

Status: **native compiler and resident library implemented**. See the
[CSTRING implementation plan](../plans/cstring-implementation-plan.md).
Language changes belong in actionc;
Exec816 owns its API declarations and their callers. This note specifies a small
byte-string facility, with no managed storage or new kernel service.

## Contract

Use `c"Hello"` literals and a distinct `CSTRING` type. A `CSTRING` is a borrowed
pointer to NUL-terminated bytes: **one native data pointer**, with no stored
length, capacity, ownership flag or allocation. Under the current native 65816
ABI this is three bytes; pointer width is not intrinsic to the string type.
It is not an inline character array or an owning string object.

Use C-strings for names, paths and ordinary text. Retain pointer-and-length APIs
for I/O, binary buffers and text whose length is already known. Existing limits
on paths, command lines and other API inputs do not change.

Exec already uses NUL-terminated [list names](../../lib/exec/execlists.act) and
[DOS paths](../reference/streams.md). Action! literals still carry a length
prefix. [HELLO](../../examples/commands/hello.act) uses a CSTRING variable, and the
[shell](../../examples/shell/shell-session.inc) uses C-string messages and shared
string/decimal helpers.

## Literal syntax and bytes

```action
c"Hello"           ; 48 65 6c 6c 6f 00
c"Hello\n"         ; 48 65 6c 6c 6f 0a 00
c""                ; 00
c"D1:STORY.TXT"
```

The prefix must touch an ordinary double quote. Accept `c"..."` and `C"..."`,
consistent with Action!'s case-insensitive names. An identifier named `c` remains
legal. Do not add implicit adjacent-literal concatenation in this change.

Decode the payload, then append one NUL byte. There is no leading length byte
and no 255-byte language limit; target object/address limits still apply.
The expression's type is `CSTRING`, pointing at the first payload byte.

Unescaped single-byte characters retain the compiler's existing byte-character
mapping. Characters that cannot be represented as one byte are errors; this
feature does not introduce UTF-8 encoding or Unicode processing. Physical
newlines inside a literal are errors; use escapes.

Ordinary `"Hello"` literals retain their Action! length prefix, doubled-quote
syntax and existing ATASCII escapes. Introducing C-strings must not reinterpret
backslashes in existing programs.

## Escapes

Within a C-string literal, use these case-sensitive escapes:

| Source | Byte | Meaning |
| --- | --- | --- |
| `\n` | `$0A` | Line feed |
| `\r` | `$0D` | Carriage return |
| `\t` | `$09` | Horizontal tab |
| `\b` | `$08` | Backspace |
| `\f` | `$0C` | Form feed |
| `\v` | `$0B` | Vertical tab |
| `\a` | `$07` | Bell |
| `\\` | `$5C` | Backslash |
| `\"` | `$22` | Double quote |
| `\'` | `$27` | Single quote |
| `\?` | `$3F` | Question mark |
| `\0` | `$00` | NUL |
| `\xHH` | `$HH` | Exact byte; exactly two hexadecimal digits |

Unknown, incomplete and malformed escapes are diagnostics. `\0` consumes one
zero, not an octal sequence. `\xHH` deliberately consumes exactly two digits,
so `c"\x41B"` contains `A`, `B`, NUL. General octal escapes, Unicode escapes,
line continuations and Action!'s `\{...}` escapes are outside this literal form.

These escapes specify bytes, not terminal actions. In particular, `\n` always
means `$0A`, matching Exec's [cooked stream](../reference/cooked-console.md); it must
not silently become Atari `$9B`. Use `\x9B` when that exact byte is required.
Whether a device displays a tab or sounds a bell remains device policy.

Embedded NUL is permitted, as in `c"ab\0cd"`. Its backing is six bytes
(`61 62 00 63 64 00`), but its C-string value ends at the first NUL and has length
two. Explicit byte-count I/O can access the complete backing when that is the
intent. The appended terminator is present even when the payload ends in NUL.

## What CSTRING means

Prefer a distinct source type over an alias for `BYTE POINTER`. An alias would
document intent but would not distinguish a string from a binary buffer or an
Action! length-prefixed string. A distinct type adds that distinction without
adding bytes to the value.

Follow the compiler's existing contextual native-type convention: canonical
`SYS.CSTRING`, with an unqualified prelude spelling `CSTRING`, rather than making
the spelling a new unconditional lexer keyword.

The proposed rules are:

- Assigning or passing a `CSTRING` copies its pointer, not its characters.
  Parameters, results and record fields use the normal native pointer layout.
- `text(i)` and `text^` read bytes. Treat `CSTRING` as a read-only view; writable
  storage remains a `BYTE ARRAY` or `BYTE POINTER`. The underlying storage can
  still change through another mutable view.
- `CSTRING(buffer)` explicitly borrows an existing byte buffer. It performs no
  scan or conversion: the caller must supply a reachable NUL and keep the
  storage alive. It does not turn an Action! string into a C-string.
- `BYTE POINTER(text)` is an explicit bridge to existing raw-buffer APIs.
  It performs no copy and does not make literal storage writable. This cast is
  an escape from the read-only view, not a general const-safety guarantee.
- Do not implicitly convert ordinary Action! string literals or arbitrary byte
  pointers to `CSTRING`. A C-string literal is directly assignable to `CSTRING`.
- `CSTRING(0)` is a null pointer, distinct from the non-null `c""`. An API must
  explicitly allow null; do not silently treat null as an empty string.
- Equality compares pointer identity. Text comparison and length are explicit
  operations; assignment and operators do not concatenate or scan strings.
- `SIZEOF(CSTRING)` and `SIZEOF(aCStringVariable)` give the pointer size, not
  the length of the text. Character counts use `SIZE`, not an eight-bit prefix.

This does not provide ownership tracking, automatic lifetime extension, dynamic
bounds checking or proof that an explicitly borrowed buffer is terminated.
Existing bounded validation at Exec API boundaries remains necessary.

## Literal storage and writable arrays

A literal expression has immutable static backing. It remains valid for the
lifetime of its containing program/image, including after the routine using it
returns; unloading that image invalidates its pointers. Literal pooling is
permitted, so pointer identity must not be used as text equality.

Also allow a C-string literal to initialize a byte array:

```action
BYTE ARRAY greeting=c"Hello from disk!\n"
BYTE ARRAY path(64)=c"D1:"
```

Here the declaration creates its own writable array backing. Infer the first
array's extent from the decoded payload plus the terminator. For an explicit
extent, require room for the terminator and zero-fill the remaining capacity.
Scalar CSTRING views are initialized by assignment in a routine or `LET`:
`CSTRING text=c"..."` is explicitly rejected, since bare scalar declarations
follow Action! storage/address initialization rules.

Do not truncate an initializer silently. This is static initialization under
the normal declaration rules, not a runtime string-copy operation.

For example, HELLO keeps the existing counted Write API and sends its newline
in the same call. The command now uses this form:

```action
USE COMMAND
USE CSTRING AS STR

LONGINT FUNC Main()
  LET greeting=c"Hello from disk!\n"
  LET length=STR.strlen(greeting)
  LET count=COMMAND.Write(COMMAND.Output(),BYTE POINTER(greeting),length)
RETURN(IF count=length THEN COMMAND.RETURN_OK ELSE COMMAND.RETURN_ERROR FI)
```

HELLO calls the resident `strlen` once and reuses the length for writing and
checking the result. Its CSTRING variable points to the immutable literal;
the explicit byte-pointer bridge to Write does not copy the text.
`SIZEOF` measures storage: for `path(64)` it returns 64 regardless of the text.

## Small CSTRING module

Ship an allocation-free, compiler-owned `CSTRING` module with `strlen`,
`strnlen`, `strcmp`, `strncmp`, `strchr`, `strlcpy`, `strlcat` and `u32toa`. Use
`USE CSTRING AS STR` to keep the module alias separate from the type spelling.
The public module contains external declarations. Package its single
`CSTRING.IMPL` implementation with the resident system image, alongside Exec,
and expose its functions through the existing checked import mechanism.
Loaded commands carry only their used imports, not another implementation copy.
Calls execute directly in the calling Task's context, without a COP transition,
per-call lookup or kernel policy. Keep the library resident until system exit.

For standalone programs and compiler fixtures, explicitly importing
`CSTRING.IMPL AS STR` includes that same source implementation. This avoids a
new selective-linking feature or compiler module-lookup override. Other small
reusable libraries can use the same resident publication mechanism later;
dynamic library loading/unloading is separate work.

Read-only parameters use `SYS.CSTRING`, except `strnlen` takes a byte pointer so
it can inspect a bounded buffer before the caller knows it is terminated.
Writable destinations are byte pointers with explicit capacities.

Copy and append follow the established strlcpy/strlcat contracts, including the
full destination capacity and attempted-length return. Neither allocates storage
or changes DOS error state. The [implementation plan](../plans/cstring-implementation-plan.md#function-contracts)
defines exact signatures, boundary behavior, packaging and validation.
Allocating and automatically growing strings remain outside this module.

`u32toa(value, destination, capacity)` converts an unsigned 32-bit value to
decimal. It returns the full digit count excluding NUL, writes at most
`capacity-1` digits and terminates when capacity is nonzero. A result at least
capacity signals truncation; capacity zero permits a null destination. Eleven
bytes hold any complete result. The routine uses caller-owned output and a
shared 40-byte decimal-place table, with no allocation or global scratch. WC
uses this resident function and keeps its own separators and newline.

## Exec API use and ABI impact

Text input declarations such as `Open` and `FindName` should eventually accept
`CSTRING`, allowing calls such as `COMMAND.Open(c"STORY.TXT", mode)`. Mutable
output buffers keep their pointer and capacity parameters. `Read` and `Write`
remain byte-count APIs and accept embedded zeros as they do now.

`COMMAND.GetArgStr()` and `PROCESS.GetArgStr()` return a borrowed `CSTRING`.
The [Process contract](../reference/process.md) rejects embedded NUL in argument
payloads and appends the terminating NUL itself. The stored length remains
private for allocation and cleanup; callers use `STR.strlen()` when needed.
The old public `Arguments()` / `ArgumentLength()` pair is removed.

Using a native pointer preserves physical argument widths and record sizes.
It does **not** by itself preserve checked import signatures: actionc hashes
semantic types. Give `CSTRING` a canonical signature identity; when public
providers adopt it, update ABI inputs, generated declarations, manifests and
callers together, advance affected public symbol versions and rebuild commands.
Do not erase the type distinction solely to keep an old signature hash.

Literal support alone does not require changing provider signatures. Neither
step needs another COP service, loader string descriptor or o65 metadata field.
The compact metadata remains eight bytes plus four bytes per import.

## Future near/far pointers

Plan for near/far qualifiers as a general compiler pointer facility, including
`CSTRING`. A near string still contains bytes followed by NUL; only its pointer
representation and addressing contract differ. Do not introduce unrelated
`NEARCSTRING` and `FARCSTRING` types or make three-byte pointers permanent string
semantics. Qualifier spelling belongs in the separate pointer design.

A near data pointer would hold a 16-bit offset within a specified bank; a far
pointer holds the full 24-bit address. Near need not mean bank zero. Its bank
must be defined by the type/address space or a documented calling context, not
whichever DBR value happens to be active. The current native ABI requires DBR=0
at ordinary call boundaries, so upper-bank near addressing needs a compiler and
calling-context contract before Exec can use it.

Near-to-far conversion must supply the defined bank. Far-to-near conversion must
prove or explicitly validate that bank; silently discarding the high byte is
invalid. The design must also specify object bounds, pointer arithmetic, calls,
callbacks and interrupt restoration. A near view of a C-string requires its
terminator to be reachable within that near address domain. `c"..."` alone does
not promise placement in any particular bank.

Start with internal pointers to objects whose bank is known. Keep general Exec
interfaces far initially, since buffers and shared objects can occupy different
banks. Include address-space distinctions in checked signatures when near
parameters are introduced. Do not move objects into scarce bank-zero RAM merely
to shorten pointers; follow the [bank-zero budget](../reference/platform.md#bank-zero-memory-budget).

Also distinguish pointer representation from generated addressing: even a far
pointer can use a cheaper access when the compiler proves the relevant bank and
offset constraints. Measure emitted size and execution cost before choosing
individual migrations. Near/far support remains a separate follow-up and does
not block the initial C-string feature.

## Delivery and cost

Keep this separate from the deferred narrowing of DOS scalar types.

1. **actionc:** implement literal decoding, the source type, array initialization
   and the small CSTRING module as one delivery batch. SemIR owns type/conversion rules;
   NIR carries decoded static bytes, storage identity and mutability. Backends
   emit ordinary data pointers and relocations without reparsing source text.
   Report unsupported targets explicitly until their lowering is available.
2. **Exec816:** pin the compiler, include the library once in the system image,
   publish its checked providers and use C-literals/imports in a small command
   integration batch. Migrate existing public text API declarations and their
   callers in a separate, later ABI slice. Remove redundant mixed-format shell
   helpers once their callers have moved.

Storage cost is payload plus one byte, the same overhead as an Action! length
prefix. A `CSTRING` variable costs one pointer; array initialization needs no
extra CSTRING binding beyond the array's normal representation, nor a duplicate
literal. No implicit heap allocation, conversion buffer or per-Task state is
introduced. Added reserved bank-zero space is **0 fixed bytes and 0 bytes
per Task**, including guards, alignment and unused capacity. The seven routines
cost 3,497 raw / 3,248 optimized code bytes, with no library data objects.
Reported local stack peaks are 12–30 bytes; these are not whole-call-chain bounds.
Their seven provider entries add 228 upper-RAM bytes within the existing
1,664-byte reservation.

Batch implementation edits before validation, following the
[development testing policy](../contributing/testing.md). At the end of the compiler slice,
cover escape bytes and diagnostics, unchanged Action! literals, embedded NUL,
empty/long strings, pointer typing, writable array initialization and raw/optimized
65816 relocation/execution (including a bank boundary), plus the compiler's
required shared-contract checks. Normalize source line endings in text fixtures
without changing binary expectations. Finish the Exec batch with the affected
ABI checks and a small loaded HELLO/path smoke check, not a release matrix after
each edit. Validation evidence is recorded in the implementation plan.
