# One owner for length metadata

> Historical record: applies to the revisions and profiles described below.
> See the [current documentation](../architecture/filesystems.md) and [history index](README.md).

`FSBTYPES.Entry.length` and `Entry.known` now own the byte extent. A cursor
embeds that entry and adds traversal state; its duplicate `length` and `known`
fields are removed. Read, seek, EOF checks and length discovery use the same
entry. MyDOS still learns a nonempty file's exact length only after validating
the terminal chain sector. Unknown length remains distinct from an empty file.

SpartaDOS directory caching uses `state.directory.entry.length`. The separate
`directoryLength` field and repeated writes to three length fields are removed.
The initial 23-byte header read has an unknown extent and is bounded by its
request; a validated header supplies the true length and sets `known`. Cached
directory reads and bounds checks then use that entry. The length stored in a
subdirectory's parent row remains untrusted, as before.

Measurement returns a complete result in the supplied cursor's `entry`, including
length and allocated-sector count. File-info publication reads that one entry;
`FSINFO.Fill` no longer accepts a separate size argument. This also removes the
SpartaDOS accounting copy back into the lookup workspace. MyDOS initializes a
complete directory result when reusing a measurement cursor previously used for
a file. DOS continues to report directory `fib_Size` as zero.

Lookup workspaces and read-only lock snapshots still contain entries for their
own operations. Opening or measuring an entry copies it into the cursor that
owns the operation; those snapshots do not compete with the active cursor's
length. This change introduces no global inode table or additional allocation.
Public DOS interfaces are unchanged; internal cursor layouts require rebuilding
resident code and its fixtures together.

## Cost and validation

The pinned compiler emits these layouts; heap allocations round to eight bytes:

| Record | Active bytes before → after | Heap bytes before → after |
| --- | ---: | ---: |
| Cursor | 116 → 110 | 120 → 112 |
| File backing | 118 → 112 | 120 → 112 |
| Object, before any lock-name trailer | 140 → 134 | 144 → 136 |
| Filesystem service | 460 → 454 | 464 → 456 |
| SpartaDOS backend state | 476 → 466 | 480 → 472 |

The service and backend state together save 16 heap bytes. An independent open
file's object and backing save another 16 bytes; wrappers sharing a backing save
8 bytes each. Lock allocations also include variable-length names, so their
rounded saving depends on the name. Reserved bank-zero delta is **0 fixed bytes
and 0 bytes per Task**, including guards, alignment and unused capacity. Fixed
memory maps are unchanged.

Against `6686db3`, resident/library Action! routines in the optimized mixed-volume
fixture shrink from **312,489 to 312,372 bytes**, saving **117 bytes**. This excludes
the fixture module, whose new regression checks add test code. Compiler
`27119ab2804e795b0bbb067c269826b934271754`, stack guards, mount geometry and other
build settings match the baseline. No demo rebuild was requested.

Development checks passed: 236 host tests; raw MyDOS files; optimized SpartaDOS
files, namespace and mixed-volume public DOS operations; cancellation during
directory accounting and publication. Added checks cover read/seek length
discovery, reusing a measurement cursor for a directory, an initially unknown
SpartaDOS header extent and its cached reuse, and public Examine results for
both backends. Native guards and ownership cleanup pass; the namespace fixture
also retains its expected arithmetic-fault check. Release matrices were not run.

[Development evidence](../development/filesystem-length.json) records sizes,
source hashes and results under `build/development/fs-length/`.
