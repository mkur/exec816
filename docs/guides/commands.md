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
