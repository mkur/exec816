# Multiple-file arguments and simple LIST patterns

Status: implemented. This is the third [command and CLI roadmap](../roadmap.md#commands-and-cli)
slice. The current [argument contract](../reference/command-arguments.md) and
[filesystem mutation contract](../reference/filesystem-writes.md) are the starting
points. The [development record](../history/multiple-file-patterns.md) gives
the emitted-code, packaged-demo and memory results. Matching stays in loadable
commands; the shell passes argument spelling through as it did before.

## Public behavior

Extend the shared `ReadArgs` template with one positional string `/M` field.
It may combine with `/A` and must be the last positional field; keyword and
switch fields may follow it. `/M` does not combine with `/K`, `/N` or `/S`.
At most eight values are accepted. A populated result slot points into caller
storage to a null-terminated array of three-byte `ADDRESS` values; each points
to one decoded, NUL-terminated string in the same storage. An omitted optional
`/M` slot is zero. `/A/M` requires at least one item. The caller owns the
storage for the result lifetime. Increase the generated storage bound by the
nine-address table; keep the provider allocation-free and the result-slot
capacity measured in template fields. This semantic extension increments the
program ABI version and rebuilds all supplied commands.

The existing scanner still separates spaces/tabs, decodes whole-token quotes
and the two quoted `*` escapes, and does not expand patterns. A quoted empty
item is present and counts toward the eight-item limit. Template validation
precedes argument decoding. Decode errors win at their source position; the
ninth `/M` item returns `ERROR_TOO_MANY_ARGS`, insufficient caller storage
returns `ERROR_BUFFER_OVERFLOW`, and missing required values return
`ERROR_REQUIRED_ARG_MISSING`. Every supplied result slot is cleared on
failure. These errors occur before command side effects.

`CAT [FILE ...]` concatenates up to eight exact files in argument order. With
no file it reads borrowed Input as today. `DELETE FILE ...` requires one to
eight exact paths and deletes in argument order. Both commands reject any
decoded empty filename before opening or deleting anything. Neither expands
`*` or `?`; duplicates remain separate items. Once file work begins, stop at
the first Open/read/write/Close or Delete error, retain its IoErr and leave
already completed output or deletions intact. Check BREAK between files and
preserve borrowed-versus-owned stream cleanup.

`LIST` retains its exact-directory behavior. If the final path component
contains `*` or `?`, resolve its parent directory and filter each ExNext name
through one shared command-level matcher. `*` matches zero or more bytes and
`?` exactly one; ASCII letters compare without case. Match files and
subdirectories, in filesystem enumeration order, with `NAMES/S` affecting only
presentation. Patterns in a parent component are unsupported and return
`ERROR_BAD_ARGUMENTS` before Lock. An unmatched pattern returns
`ERROR_OBJECT_NOT_FOUND` with no output. An exact empty directory still
succeeds with no output. Quotes group an argument but do not disable matching;
the sole unquoted `?` remains the existing help request, while `LIST "?"`
matches a one-character name. There is no sorting, recursion, shell expansion
or pattern support for mutating commands. LIST never mutates a volume, so it
does not invalidate its own ExNext epoch.

Error order is: parser/template error, command filename or pattern preflight,
Lock/Examine, then left-to-right enumeration or file operations. BREAK and
transport errors stop work at the point observed. A partial output stream or
earlier successful deletion is not rolled back.

## Executable slices

1. Add `/M` validation and decoding to `DOSARGS`, generate the bounded result
   table size from `abi/program.json`, increment the ABI version, and update the
   current command-argument reference. Exercise raw and optimized emitted code
   for absent/required values, order, quotes, eight/nine items, short storage,
   canaries, error precedence and unchanged input.
2. Migrate CAT and DELETE to `/M`. Extend their focused raw/optimized command
   fixtures for exact names, empty preflight, failure after a successful item,
   BREAK, partial transfers, first-error retention and owned-handle cleanup.
3. Add the bounded iterative matcher and LIST final-component split. Cover
   `*`, `?`, mixed case, volume/parent prefixes, directories, NAMES, empty and
   unmatched results, invalid parent patterns, output failure and BREAK in
   emitted code. Keep the matcher in the loadable command source.
4. Refresh the OF816 demo using `tools/build_demo.py` and exercise the new
   commands with physical keys against the packaged system and writable WORK
   disks. Run host/generator checks, the focused emitted-code fixtures, and
   the relevant demo walkthrough. Record executable size, upper-RAM data,
   provider capacity, stack observations and the reserved bank-zero change.
   Target **0 fixed and 0 per-Task bank-zero bytes**, counting guards,
   alignment and unused capacity. This is development-tier validation, not a
   release qualification matrix.

Update the current command/toolbox guides, the implementation record and
relevant documentation indexes with the final behavior and unsupported cases.
