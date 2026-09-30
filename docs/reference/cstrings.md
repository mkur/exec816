# C-string literals and CSTRING

[Reference index](README.md) · [Command example](../guides/commands.md)

CSTRING is implemented by the pinned actionc compiler and its small resident
library. Exec owns the API declarations and callers that use it.

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
[DOS paths](streams.md). Action! literals still carry a length
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
legal. Implicit adjacent-literal concatenation is unsupported.

Decode the payload, then append one NUL byte. There is no leading length byte
and no 255-byte language limit; target object/address limits still apply.
The expression's type is `CSTRING`, pointing at the first payload byte.

Unescaped single-byte characters retain the compiler's existing byte-character
mapping. Characters that cannot be represented as one byte are errors; this
feature does not introduce UTF-8 encoding or Unicode processing. Physical
newlines inside a literal are errors; use escapes.

Ordinary `"Hello"` literals retain their Action! length prefix, doubled-quote
syntax and existing ATASCII escapes. C-string syntax does not reinterpret backslashes in ordinary literals.

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
means `$0A`, matching Exec's [cooked stream](cooked-console.md); it must
not silently become Atari `$9B`. Use `\x9B` when that exact byte is required.
Whether a device displays a tab or sounds a bell remains device policy.

Embedded NUL is permitted, as in `c"ab\0cd"`. Its backing is six bytes
(`61 62 00 63 64 00`), but its C-string value ends at the first NUL and has length
two. Explicit byte-count I/O can access the complete backing when that is the
intent. The appended terminator is present even when the payload ends in NUL.

## What CSTRING means

`CSTRING` is a distinct source type, not an alias for `BYTE POINTER`. It
distinguishes terminated text from binary buffers without adding storage.

The canonical type is `SYS.CSTRING`, available as unqualified `CSTRING` through
the compiler prelude.

The rules are:

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

A C-string literal can also initialize a byte array:

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

The allocation-free, compiler-owned `CSTRING` module provides `strlen`,
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

| Routine | Result |
| --- | --- |
| `strlen(text)` | SIZE byte count before NUL. |
| `strnlen(bytes, maximum)` | SIZE bounded count; return maximum if no NUL is found. |
| `strcmp(left, right)` / `strncmp(left, right, maximum)` | INT less than, equal to or greater than zero for bytewise order; the bounded form examines at most maximum bytes. |
| `strchr(text, value)` | Borrowed CSTRING at the first match or NULL; searching for NUL finds the terminator. |
| `strlcpy(destination, source, capacity)` | SIZE source length, excluding NUL. |
| `strlcat(destination, source, capacity)` | SIZE attempted combined length, excluding NUL. |
| `u32toa(value, destination, capacity)` | SIZE full decimal digit count, excluding NUL. |

Inputs must remain valid for the scan; these calls do not validate arbitrary
addresses. strcmp/strncmp compare text; CSTRING equality compares addresses.

Copy and append follow the established strlcpy/strlcat contracts, including the
full destination capacity and attempted-length return. Neither allocates storage
or changes DOS error state. Pass the complete destination capacity including room for NUL.
A return value at least that capacity reports truncation. strlcpy returns the
source length; strlcat returns the attempted combined length and searches for
the existing terminator only within capacity. If none is found it leaves the
buffer unchanged and returns capacity plus source length. Buffers must not
overlap. A zero capacity permits a null destination.
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
The [Process contract](process.md) rejects embedded NUL in argument
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

Near/far pointers and further public text-signature migration remain on the
[roadmap](../roadmap.md#deferred-api-and-compiler-work). The
[original design](../history/cstrings-design.md) and
[implementation plan](../plans/cstring-implementation-plan.md) retain rationale
and development records.
