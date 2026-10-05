# Multiple-file arguments and LIST patterns

Status: implemented. This completes the third [command and CLI roadmap](../roadmap.md#commands-and-cli)
slice from the [implementation plan](../plans/multiple-file-patterns-implementation-plan.md).
The current public contract is in [command arguments](../reference/command-arguments.md)
and the [toolbox guide](../guides/toolbox.md).

Program ABI version 10 adds one bounded positional string `/M` field to the
resident `ReadArgs` parser. It accepts up to eight items, optionally requires
one with `/A`, and returns a null-terminated three-byte ADDRESS array in caller
storage. The table is reserved only when the first item appears, so an omitted
optional field needs no storage. The generated maximum caller buffer rose from
288 to 315 bytes. Parser errors clear all result slots and occur before command
side effects. All fifteen supplied commands were rebuilt for the new ABI.

CAT now concatenates zero to eight exact named files; zero keeps its borrowed
Input behavior. DELETE requires one to eight exact paths. Both preflight every
empty name before opening or deleting, process names left to right and stop on
the first failure or BREAK. LIST retains exact-directory listing and filters
only a wildcard final component through an iterative ASCII-folding `*`/`?`
matcher. It locks the exact parent, leaves ExNext order intact, rejects wildcard
parents, and reports Object not found when a pattern matches nothing. This
read-only scope avoids the [mount-wide enumeration epoch](../reference/filesystem-writes.md)
that a mutating pattern loop would invalidate.

## Cost

Sizes compare the optimized 720 KiB SDFS demo at the previous system-disk
commit with this slice, using the same pinned compiler revision recorded in
`toolchain/actionc.json` and no local override.

| Component | Before | After | Change |
| --- | ---: | ---: | ---: |
| Resident DOSARGS emitted code | 6,587 B | 7,608 B | +1,021 B |
| CAT o65 file | 2,933 B | 3,600 B | +667 B |
| DELETE o65 file | 1,428 B | 1,767 B | +339 B |
| LIST o65 file | 5,237 B | 6,762 B | +1,525 B |

The optimized `DOSARGS.Decode` local stack peak rose from 46 to 60 bytes,
within the existing Task stack reservation. CAT and DELETE each reserve 27 more
upper-RAM data bytes for the generated argument buffer. LIST reserves 283 more:
27 for arguments and 256 for the parent-path buffer. No persistent parser
object, Task or kernel gateway was added.

The before/after bank-zero reservation maps are identical, including guards,
alignment and unused reserved capacity: **0 additional fixed bytes and 0
additional bytes for each of the eight public Tasks**. The pre-existing
`bank-zero-compaction` comparison still reports 3,072 runtime bytes for two
larger Task stacks (1,536 each); this slice does not change those reservations.

## Development checks

- Host command, disk and package tests: 20 passed; generated program definitions
  passed `--check` and `git diff --check` passed.
- Raw and optimized emitted-code cases: ReadArgs 106 per mode, CAT 21 per mode,
  DELETE 12 per mode, and matcher 13 per mode. Cases include capacity canaries,
  unchanged parser inputs, eight/nine items, lazy optional storage, quoted
  names, empty-name preflight, second-file failures, ordered deletion, BREAK,
  star backtracking, question-mark width and ASCII case folding.
- Packaged optimized SDFS and MyDOS walkthroughs used physical key input,
  writable WORK: disks, real loaded commands, two-stage pipelines and disk
  audits. Both exercised multi-file CAT/DELETE, LIST filters, unmatched and
  invalid parent patterns, then recovered through the ordinary shell path.
- The SDFS OF816 screenshot walkthrough verified the packaged boot XEX and
  measured a 249-PAL-frame autoboot handoff, within the five-second interval.
  Its archive contains 11 distribution entries: boot files, both ATRs, the
  pinned ROM, a short guide, license notices and checksums.

These are development-tier checks with the pinned AltirraOS ROM and emulator.
They do not claim release qualification or physical-hardware coverage. The
OF816 distribution's boot path was exercised with this build.
