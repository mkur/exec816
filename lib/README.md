# Library layout

Sources are grouped by subsystem. Action module names, public interfaces and
procedure boundaries are unchanged by this layout.

OS implementation is GPL-3.0-only. Public Action! declarations, records and
application-side list helpers are MIT-licensed as listed in the
[licence map](../LICENSING.md#mit-public-interfaces-and-examples). A routine being
declared `PUBLIC` does not by itself make its implementation MIT-licensed.

For the runtime relationships behind these directories, read the
[system overview](../docs/architecture/overview.md),
[execution model](../docs/architecture/runtime.md) and
[filesystem architecture](../docs/architecture/filesystems.md).

Follow the [code style guide](../docs/contributing/style.md) for new and changed
handwritten sources; older dense code can be cleaned up as it is touched.

| Directory | Responsibility |
| --- | --- |
| [exec](exec/) | Public Exec API, tasks, scheduling, signals, memory and ports. |
| [dos](dos/) | DOS API, client contexts, streams, cooked input and Process lifetime/inheritance and native o65 validation/loading. |
| [fs](fs/) | Filesystem services, mounts, handlers, packets, files and directories. |
| [console](console/) | Console device, input, display, windows and foreground routing. |
| [mydos](mydos/) | MyDOS on-disk formats, names and file parsing. |
| [spartados](spartados/) | SpartaDOS on-disk formats, names and file parsing. |
| [io](io/) | Device registry, block I/O and SIO transport. |

The public `exec-io-types.inc` remains with the Exec API. Subsystem-specific
`task-*.inc` fragments live with their subsystem and are included by
`exec/taskpolicy.act`; they still belong to the `TASKPOLICY` Action module.
Generated declarations stay alongside their owning sources. Generators support
`--check` at the new locations.

## Building and instrumenting sources

`tools/library_paths.py` supplies all seven compiler module search paths. Generated
modules and test overrides precede these paths. Keep library basenames unique;
directory names do not become Action module namespaces. The ordinary build
entry point remains `tools/native_program.py`; callers do not need to supply
the subsystem paths themselves.

Action `INCLUDE` paths are relative to the including file, so cross-subsystem
includes use explicit relative paths. Build-specific includes remain in the
build output directory. Generators and instrumented test copies use
`read_source()` to preserve static include ownership and select generated
overrides before relocating source text.

Historical qualification JSON retains its original paths and hashes. Validators
translate old flat-library path keys in memory when comparing evidence; this
does not make old evidence current. Exact historical Git/blob verification
continues to use the original paths, and current-source checks still compare
hashes.

This organization changes no executable behavior or memory reservations: fixed
bank-zero delta **0 bytes**, per-task bank-zero delta **0 bytes**, including
guards, alignment and reserved capacity.
