# Commands for writable filesystems

Status: implemented. See the [development record](../history/write-commands.md)
and [command guide](../guides/toolbox.md#writable-files). This follows the completed
[filesystem writers](../reference/filesystem-writes.md) and
[first toolbox](command-toolbox-implementation-plan.md).

## Scope and behavior

Ship five loadable commands using the current COMMAND imports and argument
parser. Keep Amiga-style names/templates and Unix counted-stream behavior.
No new resident library provider, kernel operation or argument syntax is needed.

| Command | Template | Behavior |
| --- | --- | --- |
| COPY | `FROM/A,TO/A,APPEND/S` | Copy one named input to one exact destination filename. Create/truncate by default; APPEND opens or creates without truncation and seeks to EOF. |
| TEE | `FILE/A,APPEND/S` | Copy selected Input to the named file and selected Output. Create/truncate by default; APPEND preserves existing content. |
| DELETE | `FILE/A` | Delete one file or empty directory. |
| RENAME | `FROM/A,TO/A` | Rename one entry within its current directory, without replacing an existing entry. |
| MAKEDIR | `NAME/A` | Create one directory under an existing parent, then release the returned lock. |

Use ReadArgsOrHelp for every command; `?` must never open a data file or consume
Input. Reject explicit empty names before doing work. Successful commands return
OK and IoErr zero; errors return ERROR with the first causal error. Honor BREAK
before opening/mutating and between transfer chunks. Retain filesystem commit
and final-Close cancellation semantics.

COPY opens its source before its destination. The filesystem's reader/writer
exclusion then rejects copying onto the same object, including aliases, before
truncating it. A missing input must not create/truncate the target. COPY accepts
an exact target filename; it does not infer a basename from a directory target.

COPY and TEE preserve every byte, including binary/ATASCII data. Share a small
command-side transfer routine and use resident WriteAll for partial output.
Keep a 512-byte upper-RAM buffer per running transfer command. TEE writes the
file first, then Output, and stops on the first failure; its destinations are
not an atomic pair. A short read's causal error wins over a later output error.
Close each owned handle exactly once, including terminal Close failure, and
never close borrowed Input/Output. Partial output may remain after failure or
BREAK; destructive Open is not rolled back.

Multiple filenames, wildcard expansion, recursive operations, parent creation,
directory-target COPY, cross-directory moves, metadata preservation and atomic
replacement remain deferred. No shell aliases or new built-ins are required.

## Executable slices

1. Implement the five commands and their shared command-side transfer policy.
   Exercise actual command bodies in raw/optimized emitted code against
   controlled streams: binary bytes, short transfers, read/write/open/seek/close
   errors, BREAK, empty names, help, cleanup and error precedence.
2. Load the real commands through the shell on writable MyDOS and SpartaDOS.
   Cover copy/append, TEE and pipelines, same-object protection through aliases,
   directories, collisions, nonempty deletion, read-only rejection and a usable
   prompt after failure. Audit persisted contents and allocation independently.
3. Add the commands to the standard demo, update guides/help text, and package
   with tools/build_demo.py. Keep OF816's five-second shell/prime autoboot,
   read-only SYS and disposable writable WORK. Check media capacity explicitly.
4. Record source/toolchain/media hashes, selected development tests and measured
   command/stack/storage costs; commit the completed implementation and record.

Use the [development testing tier](../contributing/testing.md): host tests,
focused raw/optimized emitted checks, loaded commands on both formats and the
packaged OF816 walkthrough. Do not rerun unrelated release matrices or claim
physical-device/release qualification. Keep the pinned compiler and ROM.

Target **zero additional fixed and per-Task bank-zero reservations**, including
guards, alignment and unused capacity. Commands use existing Task slots and
upper-RAM loaded images; measure their code/data and observed stack costs.
The distributable ZIP contains boot files, both disks, the ROM, guide, notices
and checksums; test output and manifests stay in the development directory.
