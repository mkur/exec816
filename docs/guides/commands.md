# Write a disk command

[Guides](README.md) · [Build prerequisites](../contributing/building.md)

Disk commands use the small `COMMAND` interface and a `LONGINT FUNC Main()` entry.
Return a named command status; set IoErr when there is a secondary cause to report.
There is no separate SetResult call.

## Start with HELLO

The complete example is [hello.act](../../examples/commands/hello.act):

```action
MODULE HELLO

USE COMMAND
USE CSTRING AS STR

; Write one greeting through the command's selected output stream.
LONGINT FUNC Main()

  LET greeting=c"Hello from disk!\n"
  LET length=STR.strlen(greeting)

  LET count=COMMAND.Write(COMMAND.Output(),BYTE POINTER(greeting),length)

RETURN(IF count=length THEN COMMAND.RETURN_OK ELSE COMMAND.RETURN_ERROR FI)

ENDMODULE
```

Output is selected by the parent: the same code works on the console, NIL or a
pipe. Write is counted binary I/O; strlen excludes the C-string terminator. The
[CSTRING library](../reference/cstrings.md) is resident, so each command imports
its used routines rather than carrying another library implementation.

Build it from the repository root:

```sh
python3 tools/build_command.py examples/commands/hello.act -o build/commands/HELLO
```

This produces the o65 command and companion reports, not a new disk image.
The [demo builder](../contributing/building.md#build-the-demo) compiles and bundles
HELLO, CAT and WC with the matching resident providers. Rebuild the resident image
and commands together when their ABI changes.

## Arguments, input and errors

`COMMAND.GetArgStr()` borrows the Process's NUL-terminated argument string.
Use [ReadArgs](../reference/command-arguments.md) for supported positional
arguments instead of writing a separate filename parser in every command.
Its result slots and decoding storage belong to the caller.

Use Input/Output for selected streams and explicit Open/Close for owned files.
Honor byte counts, EOF and partial-transfer errors. Report failure through
`COMMAND.RETURN_ERROR` and the named errors in COMMAND; preserve a causal IoErr
across cleanup. Long CPU loops can inspect `COMMAND.BreakPending()` so foreground
BREAK does not depend on entering a blocking read.

[CAT](../../examples/commands/cat.act) demonstrates file/stream copying and
[WC](../../examples/commands/wc.act) demonstrates arguments, bounded buffers,
BREAK checks and numeric output. Follow the [style guide](../contributing/style.md).

## Scope

COMMAND is a bounded set of checked resident imports, not the complete resident
Exec API. See the [loading contract](../reference/program-loading.md) for supported
imports and the [Process contract](../reference/process.md) for lifetime, inherited
handles and result collection. For broader Exec experiments, start with the
[standalone message example](messages.md).

## Shared toolbox services

The [toolbox](toolbox.md) uses these resident COMMAND imports:

- `WriteAll(handle, buffer, length)` returns DOS true after the entire counted
  write, or false with IoErr. It handles short writes and BREAK, preserving a
  committed-prefix error. Zero length is a no-op; negative lengths fail.
- `ReaderInit(reader, handle)` initializes a caller-owned `COMMAND.Reader` and
  borrows the handle. Pass the record address as BYTE POINTER. It allocates
  nothing and never closes the handle.
- `ReadByte(reader)` returns 0..255, -1 for EOF or -2 for error. Committed bytes
  precede a saved read error. `reader.error` retains that pending cause; an early
  consumer must check it before claiming success.
- `ReadLine(reader, buffer, capacity)` returns a counted payload excluding its
  delimiter, -2 for EOF or -1 for error. Empty lines return zero.
  `reader.terminated` indicates a present delimiter. It handles CRLF across reads,
  CR, LF and ATASCII EOL. Payloads are binary-safe and not NUL-terminated.
  Capacity exhaustion is an error, never a truncated successful line.
- Lock/UnLock/Examine/ExNext publish existing DOS directory operations using
  opaque BYTE POINTER identities and the generated `COMMAND.FileInfoBlock`.
- IsInteractive/OpenConsole/ConsoleInfo expose the
  [foreground console contract](../reference/dos.md#foreground-console-access).

DOS transfer buffers and reader storage must be in caller-owned upper RAM.
Use command globals (private to the loaded image) for I/O scratch; local arrays
on the native bank-zero stack cannot be passed to DOS Read/Write. Do not modify its cursor fields after
initialization, share it between Tasks, or mix buffered and direct reads from its
handle. Prefetching advances the underlying cursor beyond consumed bytes.
Arguments and buffers must remain valid for each synchronous call; these helpers
do not provide memory isolation for arbitrary machine code.

The examples' `command-common.inc` shares opening/cleanup and output presentation
policy. The argument parser, buffered I/O and numeric formatting themselves remain
single resident implementations. New interfaces are generated from
`abi/program.json`; rebuild the resident system and all commands together.
