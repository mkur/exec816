# Shell startup scripts

The resident shell now assigns `S:` to `SYS:S` and runs optional `S:STARTUP`
and `S:USER` before its first prompt. The current behavior and customization
instructions live in the [shell guide](../guides/shell.md#startup-scripts).
Source lives in [shell-boot.inc](../../examples/shell/shell-boot.inc), using the
existing [EXECUTE helpers](../../examples/shell/shell-execute.inc) and
[command loop](../../examples/shell/shell-session.inc).

## Execution and ownership

The Amiga convention supplies the scripts directory and system/user setup
ordering. STARTUP and USER fit the native filesystems' 8.3 naming limit.
Boot drives the two files sequentially instead of adding nested EXECUTE: there
is still only one active source, read buffer and script record. The default
files contain comments only; neither shell variant starts PRIMES as a result
of this change. OF816 startup and its five-second autoboot remain unchanged.

Startup follows a successful system mount and C: assignment. A missing SYS:S
directory leaves older disks usable. Open suppresses only object-not-found for
the optional files; other assignment/source errors use ordinary diagnostics.
There is no extra Lock/Open preflight. The shared script loop closes the source,
settles command redirection and rearms foreground interaction before the prompt.
An optional missing file preserves the preceding result, including WARN.

Directory, PATH and alias changes survive into the interactive session. USER is
resolved through the current S: assignment, allowing STARTUP to replace it.
ERROR/FAIL or BREAK stops the sequence and leaves a recoverable shell error at
the prompt; diagnostics appear once. EXIT follows ordinary shell shutdown.
Startup does not scan WORK, persist session edits or run again on CD. Script
arguments, substitution, conditions and nesting retain EXECUTE's existing limits.

## Memory and validation

The added S: mapping occupies a previously available assignment slot and an
existing 288-byte upper-RAM AssignInfo allocation. C: and S: therefore occupy
two of four slots. These system-wide mappings intentionally outlive the shell.
No table capacity or reservation grows. The existing 86-byte script record
(88 heap bytes, including its 64-byte read buffer) is reused for one file at a
time, alongside ordinary DOS source-handle allocations. ShellState remains
128 bytes and the shell allocation remains 2,336 bytes.

Matched optimized resident builds grow from 823,562 to 825,616 executable bytes:
**2,054 native bytes**. Initialized non-code segments grow by 25 bytes; the
4 KiB image-data reservation is unchanged. The new StartupFile and BootScripts
helpers have local stack peaks of 26 and 30 bytes. The extracted script loop
retains its 32-byte peak; Open's peak rises from 34 to 38 bytes. Existing stack
reservations remain sufficient in the selected checks. Reserved bank-zero
growth, including guards, alignment and unused capacity, is **0 fixed bytes
and 0 bytes per public Task**. The compiler and ABI pin are unchanged.

The [development evidence](../development/shell-startup.json) records pins,
emitted sizes and selected execution artifacts. These are development checks,
not release or physical-hardware qualification:

- All 396 host tests pass, including recursive packing of the two S: files.
- Eleven optimized native MyDOS boot scenarios cover execution order, C: command
  search, persistent setup, legacy disks, either missing file, WARN continuation
  and retention, errors in either script, a non-directory S target, S remapping
  and physical BREAK in a loaded child. Exact console output checks reject
  duplicate diagnostics and commands after the stopping point.
- The normal ordering/setup scenario also passes on native SDFS. Both backends
  use read-only 256-byte-sector system media; the media hashes stay unchanged.
- Following physical-key commands verify usable input and preserved state.
  Script and temporary stream ownership are empty before the first prompt.
  Final allocation checks explicitly remove C: and S: before measuring the
  baseline, with stack/domain guards and OS restoration assertions retained.
- The ordinary EXECUTE regression passes after extracting the shared loop,
  including its selected read/Close failures, stream cleanup, BREAK and EXIT
  scenarios on MyDOS/SDFS work media.

Default disk sources, the user guides and STORY.TXT include the new setup.
The demo builder already recursively packages and hashes those disk sources.
This slice does not rebuild preview ZIPs or cartridge images.
