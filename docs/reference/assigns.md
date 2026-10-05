# ASSIGN logical directory names

`ASSIGN NAME: directory` publishes one system-wide logical prefix for an
existing directory. For example, after `ASSIGN DATA: WORK:DATA`, ordinary DOS
calls resolve `DATA:NOTES.TXT` beneath the validated `WORK:DATA` directory.
`ASSIGN NAME:` removes a mapping; `ASSIGN` lists occupied slots. Names ignore
ASCII case, use the existing 1–31-byte volume-label spelling, and may not
replace `SYS:`, a stream name or any configured physical mount name. Four
assignments can exist at once. Standard shell startup assigns `C:` to `SYS:C`,
using one slot and leaving three for other names. It is an ordinary replaceable,
removable assignment, visible in `ASSIGN` output. Its target is the selected
system drive's canonical `C` directory, such as `D2:C`.

DOS `AssignPath(name, target)` takes the name **without** its colon. A null
target removes it; a non-null target must resolve to a directory. It returns
`DOSTRUE` or `DOSFALSE` with `IoErr`. `GetAssign(index, info)` copies an occupied
slot 0–3 into a caller-owned `AssignInfo` record (32-byte name, 256-byte target).
An empty slot returns `DOSFALSE` with `IoErr=0` and clears the record. Invalid
indices or storage report `ERROR_BAD_NUMBER`. Loaded COMMAND programs receive
equivalent imports; their `GetAssign` buffer is a byte pointer to the generated
record. Exact signatures and layouts are generated from [dos.json](../../abi/dos.json)
and [program.json](../../abi/program.json).

Assignment validates `Lock`, `Examine`, `NameFromLock` and `UnLock` before
publication. It stores the physical canonical directory path, never a caller's
lock or mount reference. A target supplied through another assign is reduced
to its current physical path. Replacement/removal affects new resolutions;
open files and locks keep their original mount references. A successful
unmount leaves the mapping text in place, but lookups fail until a suitable
physical mount is available again. The table survives filesystem-service
restart within one Exec boot and clears on cold boot.

One assigned prefix is expanded before DOS classifies `Open`, `Lock`,
`CreateDir`, `DeleteFile` and either `Rename` operand. Relative paths, initial
colon, streams, physical mounts and the selected `SYS:` alias keep their
existing rules. A joined path is limited to 255 bytes; overflow reports
`ERROR_LINE_TOO_LONG`. `NameFromLock`, `CD` and `PWD` report physical names.
`MOUNT` lists physical volumes, while `ASSIGN` lists logical mappings. Existing
Rename same-parent and same-mount restrictions still apply.

The shell searches bare commands in CurrentDir and its own PATH, initially
`C:`. Explicit `C:HELLO` uses DOS resolution. A validated
`PATH SET C:` or `PATH ADD C:` retains the logical spelling, so replacing `C:`
changes later command search. An unavailable assigned PATH entry reports its
normal DOS error. `PATH RESET` restores the `C:` search entry without changing
the assignment; `PATH CLEAR` leaves only CurrentDir lookup.

Assignments are single-directory and non-persistent. There are no multi-target
search lists, deferred/unvalidated targets, arbitrary device or stream targets,
RAM: filesystem, or automatic disk-change detection. This intentionally uses
path-based resolution without the permanent lock of a regular Amiga ASSIGN;
see the [implementation plan](../plans/assign-implementation-plan.md) for the
bounded lifetime and memory rationale.
