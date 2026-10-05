# ASSIGN logical directories

Status: implemented. The [implementation plan](../plans/assign-implementation-plan.md)
defines the selected semantics; the current interfaces and limits are in the
[ASSIGN reference](../reference/assigns.md), [DOS reference](../reference/dos.md)
and [toolbox guide](../guides/toolbox.md).

DOS ABI revision 7 and program ABI version 11 add `AssignPath` and `GetAssign`.
Four upper-RAM registry slots hold immutable mappings from a logical name to a
validated, canonical physical directory path. A set/replacement publishes a
new record atomically; removal is idempotent. Records survive DOS filesystem
service restart within the same boot but hold no mount or lock references.
`Open`, `Lock`, `CreateDir`, `DeleteFile` and both `Rename` operands expand an
assigned prefix before mount selection. The resolved path is bounded to 255
bytes; a caller-owned buffer lives through the synchronous request. This makes
the same mapping available to the shell, loaded programs and file commands.

The loadable `ASSIGN` command lists, sets, replaces and removes mappings.
Shell PATH retains a validated assigned spelling such as `C:` so a later
replacement redirects command lookup. An explicit `C:HELLO` resolves through
DOS; bare command names still use only CurrentDir and the configured PATH.
There is no implicit `C:` search. A mapping stores one physical directory
snapshot, so chains, multi-directory search, persistent assigns, non-directory
targets and automatic disk-change handling remain unsupported.

## Cost

The optimized 720 KiB demo is compared with the preceding
`build/system-disk-geometry/dd720-sdfs-final` build using the pinned actionc
revision `f1ff4ce0d16b4705e66d69aad00ca4a7be3e1d08`; there was no local
compiler or ABI override. The resident native routine sum rose from 607,887
to 616,788 bytes (**+8,901 bytes**); its XEX rose from 645,642 to 654,789
bytes (**+9,147 bytes**). The loadable `ASSIGN` file adds 3,051 bytes to the
system disk. The provider set grew from 40 to 42; its encoded table uses
1,423 of 1,664 reserved bytes, leaving 241 bytes.

The idle upper-RAM DOS service reservation grows from 96 to 108 bytes for the
four slot pointers (**+12 bytes**). Each occupied assignment allocates a
288-byte record, with four records totaling 1,152 payload bytes plus allocator
overhead. The loadable command has a 288-byte listing record while resident.
The per-Task DOS client context grows from 88 to 94 bytes; the heap rounds
that from 88 to 96, an **8-byte actual increase per context**. Prefix
expansion lazily allocates one 256-byte buffer for a Task that uses an assign,
and `Rename` can need a second 256-byte buffer. Context teardown frees both.
The shell's existing upper-RAM scratch reservation grows by 24 bytes, from
264 to 288. No Task, stack reservation or direct-page allocation was added. Emitted-code
stack checks and guard checks passed on the selected cases, with the existing
Task stack reservations.

An optimized emitted-code trace around `EXEC.Forbid`/`Permit` measured the two
occupied `GetAssign` record copies at 37,285 and 37,041 accelerated CPU cycles,
about 2.63 and 2.61 ms at the pinned 8× PAL CPU rate. Task switching is
excluded during each copy; IRQ and NMI entry remain enabled. The trace used
the same MyDOS registry fixture as the DOS checks, so it measures these
snapshots rather than a worst-case interrupt arrival on physical hardware.

Comparing the two bank-zero maps, including guards, alignment and unused
reserved capacity, gives **0 additional fixed bytes and 0 additional bytes
per public Task**. Both maps retain the earlier `bank-zero-compaction`
comparison of 3,072 runtime bytes for two 1,536-byte larger Task stacks;
ASSIGN adds none of those bytes.

## Development checks

- Generated DOS and program bindings pass `--check`; the host unit suite
  passes 340 tests. The ABI fixture exercises the two new calls in raw and
  optimized emitted code.
- Focused raw and optimized emitted DOS programs exercise capacity,
  replacement/removal, validation and collisions, directory-only targets,
  physical canonical names, nested assignment snapshots, path length failure,
  busy/successful filesystem stop and restart, error contracts and release
  without upper-heap leakage.
- Raw and optimized physical-key shell sessions exercise listing, help,
  replacement, MyDOS and SpartaDOS file writes and reads, directory creation
  and removal, rename, cross-volume rejection, symbolic `C:` PATH lookup,
  command search after reassignment, removal and persisted disk audits.
- `tools/build_demo.py` built the boot XEX, matching 720 KiB system disk,
  work disk and the OF816 package with the pinned AltirraOS ROM and license
  notices. The OF816 development smoke covered both automatic and Forth-command
  handoff into the standard shell. Automatic handoff took 250 PAL frames,
  preserving boot guards and OS state. The archive contains only
  boot/distribution files, the guide, notices and checksums.

These are development-tier checks on the pinned emulator/ROM configuration,
not release or physical-hardware qualification. Concurrent replacement and
forced allocation failure have not been exercised in a focused emitted-code
fixture; they remain validation targets for a broader qualification run.
