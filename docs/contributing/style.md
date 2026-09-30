# Exec816 code style

Write code that someone learning Exec816 can read without reconstructing its
intent. Use the recent [commands](../../examples/commands/) and
[shell](../../examples/shell/) as the starting point. Some older code still uses
denser formatting or predates `NULL`; it is not the standard to copy.

This guide covers handwritten Action! `.act` and `.inc` files. Apply it to new
code and routines being changed. Keep unrelated cleanup separate; a style
change does not require reformatting the repository. Assembly and host tools
retain their existing language conventions.

## Layout and spacing

- Use two spaces per indentation level, no tabs, and one statement per line.
- Put `IF`, `ELSEIF`, `ELSE`, `FI`, loop delimiters and their bodies on separate
  lines. Avoid packed forms such as `IF failed THEN RETURN FI`.
- Separate declarations from executable code, and separate logical steps with
  a blank line. Give substantial branches space; do not separate every statement.
- Put the routine's final `RETURN` at the left margin, with a blank line before
  it. Early returns remain indented inside their branch. Leave a blank line
  between routines. A routine without declarations has a blank line after its
  signature.
- Retain the compact expression style: `count=length`, `used==+1`,
  `Write(output,buffer,count)`. Use spaces around word operators such as
  `AND`, `OR` and `MOD`.
- Aim for lines around 80 characters. Break long calls after `(` or a comma,
  indenting continuation arguments four spaces beyond the statement. Break
  long conditions at logical boundaries. Do not distort readable declarations
  merely to meet a column limit.

```action
  LET count=COMMAND.Read(input,buffer,BUFFER_SIZE)
  IF count<0 THEN
    RETURN(COMMAND.RETURN_ERROR)
  FI

  IF count=0 THEN
    EXIT
  FI
```

Organize a module as imports/includes, constants, types, storage and routines.
Group related fields and constants; use multiline records when their structure
needs explanation. Keep helpers near their callers, respecting declaration
order. Split large sources by responsibility, as the shell does for its session,
commands, redirection and boot code.

## Names and constants

| Kind | Convention | Examples |
| --- | --- | --- |
| Keywords and modules | Uppercase | `RETURN`, `COMMAND`, `TASKINSPECT` |
| Routines and types | Capitalized words | `ShellConvert`, `FileHandle` |
| Variables and ordinary fields | Lowercase first word | `count`, `readError`, `previousCR` |
| Constants | Uppercase with underscores | `BUFFER_SIZE`, `ERROR_BREAK` |
| Source files | Lowercase; hyphens for fragments | `shell.act`, `shell-session.inc` |

Use names that describe the role. Retain established API names and record-field
prefixes such as `IoErr`, `ln_Succ` and `fib_Size`. Preserve conventional library
spellings such as `STR.strlen`; do not rename interfaces for cosmetic consistency.

Name capacities, modes, states, flags and error codes. Define a buffer's capacity
once and reuse it; derive related sizes rather than repeating numbers. Ordinary
zero tests, increments and simple arithmetic need no artificial `ZERO` or `ONE`.

Put a constant with its owner:

- `COMMAND.RETURN_ERROR`, `COMMAND.ERROR_BREAK` and `COMMAND.MODE_OLDFILE` for
  command results and DOS operations; use the corresponding owning API in
  resident code.
- `ASCII.SPACE`, `ASCII.LF`, `ASCII.NUL` and other shared character names for
  byte classification.
- `SYS.MAXLONGCARD`, `SYS.MAXINT`, `SYS.MININT` and the other system limits for
  numeric bounds.
- Local `CONST` definitions for a command's capacities and private choices.

Use `CONST` for integer ABI values. Use an enum when a distinct type models a
closed set and its consumers accept that type. Do not introduce enum casts into
every API call merely to name a numeric constant. Hexadecimal suits bit masks,
hardware addresses and binary layouts; decimal suits counts and capacities.

## Bindings, types and pointers

Prefer `LET` near first use for a value that will not be reassigned. Give it an
explicit type only when inference does not express the intended type. Keep
mutable counters and state as ordinary declarations before executable statements.
Use a `BEGIN`/`END` block when placing `LET` inside a loop or branch; those
constructs alone do not provide a binding scope.

Choose widths from the required range and ABI. Do not widen every value to
`LONGINT`, or narrow an API value solely to save space. Retain casts that express
signedness, checked narrowing, address arithmetic or an API boundary. Remove
redundant casts. A cast after arithmetic does not widen the arithmetic that
already happened; widen an operand when a wider computation is required.

Use [compiler-supported `NULL`](../history/compiler-null.md) for absent pointers:

```action
  file=NULL
  IF file=NULL THEN
    RETURN(NULL)
  FI
```

Here `file` and the function result have pointer types. Assignments, parameters,
returns and equality comparisons provide that type; `LET value=NULL` does not.
Static pointer values use `[NULL]`. Do not define a local `NULL` constant or
replace typed pointer checks with integer casts. Numeric addresses, counts and
flags still use numeric zero; `ASCII.NUL` is a character, not a pointer.

## Strings and buffers

Use `c"Hello\n"` and `CSTRING` views for ordinary text, names and paths. Use
`USE CSTRING AS STR` in disk commands and the appropriate existing resident
implementation import in resident code. Keep plain Action! strings only where
an interface actually expects a length prefix.

The [HELLO command](../../examples/commands/hello.act) illustrates the usual form:

```action
  LET greeting=c"Hello from disk!\n"
  LET length=STR.strlen(greeting)

  LET count=COMMAND.Write(COMMAND.Output(),BYTE POINTER(greeting),length)

RETURN(IF count=length THEN COMMAND.RETURN_OK ELSE COMMAND.RETURN_ERROR FI)
```

Use `strlen` for terminated text and `strnlen` when the available extent is
bounded. Keep an already known byte count when processing I/O. Use `SIZEOF` for
storage capacity and record size, not the length of a `CSTRING` pointer. Avoid
`SIZEOF(...)-1` as the default way to express text length.

Writable storage remains a `BYTE ARRAY` or `BYTE POINTER`. A `CSTRING` borrows
storage: assigning it does not copy bytes, allocate memory or extend the owner's
lifetime. `BYTE POINTER(text)` bridges a raw-buffer API; it does not make a
literal writable. `NULL` and `c""` are different values.

Use `STR.strlcpy` and `STR.strlcat` for bounded copying and appending; check for
truncation when complete text is required. Keep pointer-and-length operations
for binary data. Emit `\n` for ordinary command output; handle ATASCII conversion
at the interface that requires it. See the [C-string contract](../reference/cstrings.md).

## Control flow and routine comments

Use early returns for invalid input and failed setup, keeping the main path
readable. Keep resource cleanup explicit and reachable on every relevant exit.

Prefer `CASE` when selecting among named values of one command, state or format.
Use `IF` for ranges and conditions involving different values. Align `WHEN`,
`ELSE` and `ESAC` with `CASE`, and separate substantial arms:

```action
  CASE state OF
  WHEN TASKINSPECT.STATE_RUNNING THEN
    label=c"RUNNING "

  WHEN TASKINSPECT.STATE_READY THEN
    label=c"READY   "

  ELSE
    label=c"UNKNOWN "
  ESAC
```

Use an expression `IF` for a short value selection, including a simple return
as in HELLO. Keep longer decisions and operations with side effects in ordinary
statements. Readability matters more than minimizing the line count.

Put a short purpose comment before each nontrivial routine. In examples, also
explain helpers whose names alone do not teach their role. Describe the intent,
result or important contract, rather than narrating assignments and loops:

```action
; Release a file opened by TYPE; borrowed standard input belongs to its caller.
PROC ShellCloseCommandInput()
```

Within a routine, comment reasons, bounds, ownership transfers, synchronization
and surprising hardware constraints. Explain why an error check exists if it
would otherwise be puzzling. Avoid comments such as "increment index".

## Commands, ownership and system boundaries

Disk commands return a named result from `LONGINT FUNC Main()`; use `IoErr` for
the detailed error. Resident entry points and Task procedures keep their own
documented signatures. Use `COMMAND.ReadArgs` for supported structured arguments
and `GetArgStr` when the original argument text is needed. Command arguments
must not consume redirected standard input.

Capture `IoErr()` before another operation can replace it. Preserve the causal
error across output and cleanup. Distinguish owned handles from borrowed standard
streams; only release resources the routine owns. Long-running commands should
honor BREAK at appropriate work boundaries. Follow each I/O API's partial-transfer
contract rather than assuming one call always completes the request.

Reuse shared facilities instead of adding command-local parsing, number
conversion or string libraries. Disk commands import published services rather
than bundling resident implementations. Keep allocation, buffer reuse and
lifetime visible; avoid an abstraction that silently allocates for a simple job.

Style changes must preserve packed record layouts, signedness, evaluation order
and synchronization. Hardware/shared-state code should make ownership and the
protected interval clear. Follow the [platform contract](../reference/platform.md)
for IRQ/NMI, direct-page and bank-zero requirements; formatting is not a reason
to change them.

Edit ABI definitions and generators at their source; do not hand-format generated
files. Follow [repository ownership](../../AGENTS.md) for compiler/runtime changes
and the [two-tier testing policy](testing.md) for validation. Batch related small
edits, check the affected behavior, and do not repeat passing suites without a
reason. Documentation-only work needs content and link checks.
