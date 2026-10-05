# ASSIGN: bounded logical directory names

Status: implemented through A4. The development record is
[ASSIGN logical directories](../history/assign.md). This follows the
[multiple-file and pattern work](../history/multiple-file-patterns.md). Follow
the [DOS contract](../reference/dos.md), [SYS: contract](../reference/sys-volume.md),
[shell PATH contract](../guides/shell.md#path), and
[development testing policy](../contributing/testing.md). The slices below
record the implementation gates; the current contract is in
[ASSIGN](../reference/assigns.md).

## User contract

Provide one loadable `ASSIGN` command and a system-wide DOS mapping table:

```text
ASSIGN DATA: WORK:DATA     Set or replace DATA: with an existing directory
ASSIGN DATA:               Remove DATA:
ASSIGN                     List current assignments
ASSIGN ?                   Show the command template

CAT DATA:NOTES.TXT         Resolve through the assignment
COPY SYS:STORY.TXT DATA:STORY.TXT
```

The command uses the existing `ReadArgsOrHelp` and error/return-code conventions.
`NAME` is required for mutation and must end in one colon; `TARGET` is optional.
No arguments lists assignments in slot order as `DATA: -> D2:DATA` (and prints
nothing when empty). Setting an existing name replaces it; removing an absent
name succeeds. Names compare without ASCII case and are displayed in uppercase.
At most four names may be assigned. An attempt to add a fifth returns
`ERROR_NO_FREE_STORE`; replacement of an existing slot still succeeds.

An assign name has 1–31 legal volume-name bytes before the colon. It may not
collide with `SYS`, `NIL`, `RAW`, `CON`, `CONSOLE`, or **any configured physical
mount name**, including one not currently published in the effective boot
configuration. Reject malformed names
with `ERROR_INVALID_COMPONENT_NAME` and collisions with `ERROR_OBJECT_EXISTS`.
The 31-byte limit follows Exec816's existing mount-label rule; the AmigaOS
`AssignPath` interface uses 30 bytes.
The command accepts no stream or file target: `TARGET` must resolve to an
existing directory on a mounted filesystem. Relative paths and `SYS:` are
allowed as inputs; the assignment stores their canonical physical directory
name after validation. An inaccessible target reports the causal DOS error and
does not alter an earlier mapping.

This uses the [AmigaDOS ASSIGN command's](https://wiki.amigaos.net/wiki/AmigaOS_Manual:_AmigaDOS_Command_Reference)
set/replace, name-only cancellation and no-argument listing behavior. For the
target lifetime it follows the [AmigaOS `AssignPath` approach](https://developer.amigaos3.net/autodocs/dos.library/AssignPath.html):
expand a stored path on each reference and keep no permanent lock. Unlike
AmigaOS `AssignPath`, this first Exec816 slice validates the directory at
assignment time and stores a *physical canonical path*. That avoids retaining
a caller-owned lock or mount across media changes, prevents chains and cycles,
and makes RAM and lookup costs bounded. A later rename/delete of the target can
make the assign fail; remounting a suitable filesystem under the same physical
name can make it work again. There is no automatic disk-change detection.

The table lasts for one Exec boot and survives filesystem-service restart as
names only; a cold boot clears it. Replacing/removing a mapping affects only
future path resolutions. Already-open files and locks retain their normal
mount references. Assigns never pin a mount or change the existing unmount
rules. `MOUNT` continues to list physical volumes only; `NameFromLock`, `CD`
and `PWD` continue to report physical canonical paths. `SYS:` remains the
separate, selected-system-volume alias and cannot be replaced by `ASSIGN`.

`C:` is an ordinary eligible assign name. Explicit `C:HELLO` works once set.
Bare `HELLO` still searches the shell's CurrentDir and configured PATH; there
is no implicit Amiga `C:` search. `PATH ADD C:` and `PATH SET C:` should retain
the symbolic assigned spelling after validating that it is a directory, so
later replacement of `C:` changes command search. Existing physical PATH
entries retain their canonical spelling, and `SYS:` retains its present
special treatment. A removed/unmounted PATH assign yields the normal DOS
lookup error rather than silently selecting another volume.

## DOS interface and routing

Add two public DOS calls, exposed to loaded commands through COMMAND providers:

```text
LONGINT AssignPath(BYTE POINTER name, BYTE POINTER target)
LONGINT GetAssign(CARD index, AssignInfo POINTER info)
```

| Call | Contract |
| --- | --- |
| `AssignPath(name, target)` | `name` is a NUL-terminated label **without** `:`; non-null `target` sets/replaces after validation, null removes. Return `DOSTRUE` on success or `DOSFALSE` with `IoErr`. |
| `GetAssign(index, info)` | For indices 0–3, copy one stable `AssignInfo` snapshot into caller-owned storage; return `DOSTRUE` if occupied, `DOSFALSE` with `IoErr=0` if empty, or `DOSFALSE` with a causal error for invalid index/storage. |

`AssignInfo` is a generated public record with `name[32]` and `target[256]`
NUL-terminated byte arrays (288 bytes total). The command uses one upper-RAM
record for listing. An empty slot clears `info` and returns `DOSFALSE` with
`IoErr=0`. The API clears `IoErr` on success, including idempotent removal.
Invalid index reports `ERROR_BAD_NUMBER`; invalid output storage reports
`ERROR_BAD_NUMBER` without a partial result. Check mapped input and output
ranges before reading or writing them. Keep exact signatures,
record size and native import layouts in `abi/dos.json`; update
`tools/generate_dos.py`, generated DOS bindings, `abi/program.json`, COMMAND
providers and all supplied commands together. Bump the DOS revision and
program version, then rebuild the demo; do not keep an obsolete ABI profile.
Check the provider-manifest capacity in the real linked image before choosing
whether its reservation must grow.

Implement the registry inside DOS, with four upper-RAM slot pointers and one
immutable upper-RAM record per occupied slot. Prepare and allocate a new record
outside `EXEC.Forbid()`, recheck capacity and atomically swap the slot pointer
under Forbid, then
free the old record after leaving Forbid. Readers copy the bounded record under
Forbid before using it, so no caller holds a pointer that replacement can free.
No filesystem call, allocation or I/O runs while forbidden; IRQ/NMI paths do
not access this table. Audit first-publication and concurrent replace/remove
against Task switching, and measure the longest forbidden copy. At full
capacity the four records contain at most 1,152 payload bytes plus 12 pointer
bytes and allocator overhead; ordinary boot without assignments pays only the
pointer table and linked code. Record actual linked/reserved sizes rather than
assuming these payload figures are total heap cost.

`AssignPath` validates the name, then `Lock`/`Examine` the target as a directory,
gets its physical name via `NameFromLock`, and `UnLock`s before publishing.
Preserve the first causal error through cleanup, and publish only after cleanup
succeeds. Validate the canonical name as a physical, bounded path; the stored
record contains no source pointer, lock or mount reference. This also means
`ASSIGN DATA: OTHER:DIR` stores the currently resolved physical directory, not
a dependency on `OTHER:`. A concurrent replacement is serialized only at
publication: the last successful publisher wins, and each reader sees one
complete old or new record.

Add one shared expansion step to `DOSCALLS` **before** `Destination`,
`Configured`, `PathMount` and `Acquire` classify a name. The step validates the
original 255-byte path, copies an assigned prefix to caller-owned upper-RAM
scratch, appends the suffix using one directory separator when needed, and
validates the resulting physical path. `DATA:` resolves to the target directory;
`DATA:FILE` to a child, following the existing slash/component parser. A
result longer than 255 bytes returns `ERROR_LINE_TOO_LONG` before disk I/O;
there is no truncation. Do one prefix expansion only, since stored targets are
physical names. Paths without an assigned prefix retain today's relative,
leading-colon, stream, SYS and physical-volume behavior. An unknown explicit
prefix still returns `ERROR_DEVICE_NOT_MOUNTED`.

The caller's DOS context may lazily own one 256-byte upper-RAM expansion buffer;
Rename needs a second buffer when both names use assigns. Extend context
teardown to free them, and hold each buffer until the synchronous packet has
completed. Admission/allocation failure returns before packet submission or
namespace mutation. Route `Open`, `Lock`, `CreateDir`, `DeleteFile` and both
`Rename` operands through the same step, covering shell redirections, loaded
programs and file commands without shell-only rewriting. Rename retains and
compares resolved mount identities as it does today: same-parent filesystem
limits still apply, and crossing volumes reports `ERROR_RENAME_ACROSS_DEVICES`.
If a mapping changes between the two operand snapshots, mount identity checks
still prevent a cross-volume rename.

## Executable slices

1. **A1 — Registry and public ABI.** Implement `AssignPath`, `GetAssign`,
   generated records/bindings and COMMAND providers. Cover validation,
   physical/configured-name collisions, four/five slots, replacement while
   full, idempotent removal, relative/SYS target canonicalization,
   wrong-type or offline targets, allocation failure, BREAK, cleanup and
   concurrent snapshot/replacement. Run ABI generators with `--check`, host
   checks, and focused raw/optimized emitted-code tests. Prove that no lock or
   mount reference remains after a successful set.
2. **A2 — DOS path routing.** Add bounded expansion and lifetime-managed
   scratch. Exercise exact root and child joins, 255/256-byte boundaries,
   malformed/unknown prefixes, streams, relative paths, SYS and targets named
   through another assign. Use raw and
   optimized emitted DOS tests for read/write via assigns on MyDOS and
   SpartaDOS; all five name-based operations; Rename through physical and
   logical spellings on one mount versus across mounts; open objects across
   replacement/removal; busy/successful unmount, remount and service restart.
   Preserve stack/domain guards, Task ownership, register restoration,
   OS coexistence and bounded completion in the selected fixtures.
3. **A3 — Loadable command and PATH.** Implement the small ASSIGN command and
   preserve a validated logical prefix in shell PATH. Cover listing order,
   exact CLI syntax, parser/help, `C:` command search after reassign, no
   implicit C search, output failure and BREAK. Run focused raw/optimized
   command tests and a physical-key shell session. Update current DOS and
   shell/toolbox references, user guide, documentation indexes and an
   implementation record with unsupported cases.
4. **A4 — Distribution and measured cost.** Rebuild with the pinned compiler
   and ABI inputs in `toolchain/actionc.json`, recording any local override.
   Use `tools/build_demo.py` so the boot XEX, matching disk and OF816/pinned
   AltirraOS ROM with notices stay together. Keep the five-second autoboot to
   the standard shell/prime demo; try `ASSIGN DATA: WORK:DATA`, copy/read/delete
   through `DATA:`, list/remove it, and exercise `C:` with PATH. Publish only
   the normal `exec816-demo.zip` contents. Report linked code growth, provider
   capacity, upper-RAM idle/full/per-Task costs, stack use and reserved
   bank-zero change. Target **0 fixed and 0 per-Task bank-zero bytes**, counting
   guards, alignment and unused reserved capacity; report the measured delta
   even if it is zero. This is development-tier validation, not hosted-system
   or hardware qualification.

Keep this slice to single-target directory assignments. Multi-directory search,
deferred/unvalidated targets, persistent boot assigns, arbitrary device/stream
targets, a RAM filesystem and automatic disk-change handling remain unsupported.
