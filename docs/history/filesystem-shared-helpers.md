# Shared filesystem helpers

> Historical record: applies to the revisions and profiles described below.
> See the [current documentation](../architecture/filesystems.md) and [history index](README.md).

MyDOS and SpartaDOS now share their 8.3 naming policy and backend-neutral
record/operation bookkeeping. The duplicate routines are removed; callers use
the shared helpers directly.

- [FS83](../../lib/fs/fs83.act) owns character/name checks, component parsing,
  bounded path initialization, candidate selection and ambiguity handling.
  It replaces `MYDOSNAMES` and the equivalent SpartaDOS parser. Match counters
  saturate at two, preserving the distinction between absent, unique and
  ambiguous matches in arbitrarily long supported directories.
- [FSCORE](../../lib/fs/fscore.act) owns entry copies and read/seek initialization
  and successful completion. Operation kind constants live with these helpers;
  each backend still selects its own initial traversal stage.

Root metadata, directory validation, traversal, failure recovery and cancellation
remain backend-specific. MyDOS still checks directory extent overlaps; SpartaDOS
still validates map identities and parent headers. Worker checkpoints and private
progress status values are unchanged. These are ordinary calls, with no new
callback table or public ABI.

Build provenance includes both shared modules. Historical qualification records
retain their original paths and hashes; new MyDOS records include the helpers.

## Size and storage

The matched optimized mixed-filesystem integration builds use compiler
`27119ab2804e795b0bbb067c269826b934271754`, enabled stack checks, eight task slots
and the same 128-byte MyDOS/SpartaDOS media and test program. The baseline includes
the scratch-cache geometry cleanup from commit `79959b1`.

| Emitted code | Before | After | Saved |
| --- | ---: | ---: | ---: |
| Whole integration image, Action! routines | 328,353 B | 325,840 B | **2,513 B** |

The saving includes the new shared helpers. Every module outside the extracted
helpers and their former owners has the same routine-byte total. This measures
the integration image, not a refreshed demo distribution.

Runtime record layouts and allocation sizes are unchanged. Fixed upper-memory
and bank-zero reservations are identical in the two memory maps. Reserved
bank-zero delta: **0 fixed bytes / 0 bytes per task**, including guards,
alignment and unused capacity.

## Development checks

All 236 host tests pass. Focused native checks pass for raw/optimized SpartaDOS
namespace handling, optimized MyDOS metadata, raw MyDOS files, optimized
SpartaDOS files and optimized mixed-volume public DOS integration. They cover
name ambiguity, malformed metadata, read/seek results, ownership cleanup and
intact native guards on 128-byte media. The namespace fixture also retains its
expected arithmetic-fault/guard checks. Release matrices were not rerun.

[Development evidence](../development/filesystem-shared-helpers.json) records
source/image hashes, compiler settings and the code-size comparison. Detailed
artifacts are under `build/development/fs-shared-helpers`.
