# Cheap directory metadata refactor plan

[Implementation plans](README.md) · [Roadmap](../roadmap.md) ·
[DOS contract](../reference/dos.md) · [MyDOS](../reference/mydos.md) ·
[Filesystem writes](../reference/filesystem-writes.md) ·
[Testing policy](../contributing/testing.md)

Status: DM0–DM4 complete at the development tier; each slice committed.
[Implementation record](../history/directory-metadata.md) ·
[Compact evidence](../development/directory-metadata-final.json).

Make ordinary Examine and ExNext return directory metadata without measuring
each selected file's chain. MyDOS provides a sector count and therefore a byte
upper bound; SpartaDOS stores an exact byte length; RAM already knows its length.
Expose which quantities are exact and keep a single explicit ExamineExact call
for applications that need measured lengths or allocated-block counts.
This replaces the proposed MyDOS length cache follow-up to the completed
[MP0–MP6 performance work](../history/mydos-performance.md).

## Metadata contract

Keep the existing Examine/ExNext signatures and 260-byte FileInfoBlock size.
Replace the final two reserved bytes with `CARD fib_InfoFlags` at offset 258,
leaving `fib_Reserved(30)` at offset 228. The private enumeration cookie stays
at the beginning of that reserved area. Check its emitted size against the
30-byte capacity rather than assuming it fits.

Define these constants in [abi/dos.json](../../abi/dos.json) and generate the
Action!, COMMAND and C definitions:

| Flag | Value | Meaning |
| --- | ---: | --- |
| FIB_SIZE_EXACT | 1 | fib_Size is an exact byte length. |
| FIB_SIZE_BOUND | 2 | fib_Size is a byte upper bound, not EOF. |
| FIB_BLOCKS_EXACT | 4 | fib_NumBlocks is the format's exact allocated-sector count. |

The two size flags are mutually exclusive. An unavailable quantity is -1 with
its validity flags clear. A valid empty size is zero with FIB_SIZE_EXACT set.
Directory byte size remains zero with FIB_SIZE_EXACT, as in the current API;
allocated-sector counts describe storage separately.

| Ordinary metadata result | fib_Size | fib_NumBlocks |
| --- | --- | --- |
| MyDOS regular file | `count * (sectorBytes - 3)`, FIB_SIZE_BOUND | Directory sector count, FIB_BLOCKS_EXACT |
| MyDOS legacy zero-count/zero-start empty file | 0, FIB_SIZE_EXACT | 0, FIB_BLOCKS_EXACT |
| MyDOS directory | 0, FIB_SIZE_EXACT | 8, FIB_BLOCKS_EXACT |
| SpartaDOS regular file | Stored byte length, FIB_SIZE_EXACT | -1, unavailable without map measurement |
| SpartaDOS directory | 0, FIB_SIZE_EXACT | -1, unavailable without map measurement |
| RAM file or directory | Known byte length or directory zero, FIB_SIZE_EXACT | 0, FIB_BLOCKS_EXACT; RAM has no disk sectors |

MyDOS may publish an exact length already supplied by a live, admitted writer
lease; it must not scan or add a persistent cache to obtain one. A one-sector
file is not necessarily empty. Widen the bound multiplication before evaluating
it, including a 65,535-sector directory count. The bound describes a structurally
valid directory entry; it does not certify that its file chain is valid.

Add `ExamineExact(lock, info)` with the same argument/result shapes as Examine.
It uses the existing bounded measurement path and returns exact byte sizes and
block counts, or the current causal error. It initializes enumeration like
Examine; subsequent ExNext calls still use ordinary cheap metadata. No
ExNextExact, mode stored in the cookie, global setting or parallel metadata
record is needed. An application needing exact information about one listed
file locks that file and calls ExamineExact with a separate FIB.

Register one distinct public DOS packet action and propagate the call through
the native DOS binding, loaded COMMAND provider and C bridge/import table.
Increment their relevant ABI revisions/versions and rebuild callers together.
This deliberately changes Exec816's current exact-FIB default to accommodate
metadata that MyDOS can supply cheaply. Keep the Amiga-shaped calls and normal
owned-lock/packet semantics; document this Exec816 extension explicitly.

## Scope and invariants

- Ordinary metadata reads only the directory sectors/maps needed for lookup or
  enumeration. It performs no selected-file payload/map measurement and no
  extra child-directory walk solely to count blocks.
- Preserve live-object, mount, lease, directory-entry and initial-reference
  admission, ancestry, enumeration-cookie identity/epoch and normal I/O errors.
  Establish metadata once and reuse existing admission helpers.
- Chain/trailer/cycle/count errors beyond the directory record are discovered
  by Read, Seek, ExamineExact or mutation preflight. Cheap listing is not a
  file-integrity check; retain these corruption regressions on those operations.
- Keep the final cancellation checkpoint and complete FIB publication. Failed
  queries leave the prior result/cookie intact, subject to the existing
  end-of-enumeration cookie rule. Preserve interleaved FIBs and mutation epochs.
- Keep internal `Entry.length`/`known` exact-only. Calculate upper bounds for
  public metadata; never install them as cursor length, EOF or a write position.
- Read discovers exact EOF from validated trailers. Seek(END) measures only
  when needed. Writable Open/Delete/Truncate keep selected-chain preflight,
  reservation/publication ordering and failure/offline policy.
- Keep the existing SDFS extent cache for explicit measurements. Do not extend
  it for MyDOS or add another cache. Removing/lazily allocating that cache and
  consolidating buffers remain separate work.

## DM0 Baseline and caller inventory

Freeze the current production revision, pinned compiler/ROM/emulator, media,
cache setting, code sizes, FIB layout and observer definitions. Reuse the
[MP6 results](../development/mydos-performance-final.json) where inputs match.
Keep large artifacts under `build/directory-metadata`; use existing operation
and directory measurement runners rather than a new benchmark framework.

Inventory native and loaded commands, shared pattern selection, FIND, shell
current-directory/destination checks, C FileScan, GEM Files/file selectors and
the text loader. Classify each use as names/types, display, capacity bound or
explicit exact measurement. Inventory tests that currently assume every
ExNext result contains an exact size and allocated count.

Acceptance: reproducible listing baseline and a complete caller migration list,
including generated bindings and existing corruption expectations.

## DM1 Information flags and explicit exact queries

Update the machine-readable FIB layout/constants and add ExamineExact. Regenerate
DOS/COMMAND/C definitions, provider/import identities and layout checks; edit
handwritten bridge implementations through their owning source/generator.
Append the C call-table/import entry and update its capacity/binding checks.
Verify the COMMAND provider still fits its existing reservation.

Retain the existing measurement path for all queries during this foundation
slice. Publish truthful exact flags with completed results, then write the cookie
without touching fib_InfoFlags. ExamineExact uses that same measurement path.
No persistent request mode or extra service/workspace field is needed.

Run generator/host checks and one small raw/optimized Action!/C interface probe:
FIB size/offsets, cookie capacity, flag access, exact-query call/result shape,
far FIB guards and failed-query preservation. Rebuild a loaded command and C
caller through their real bindings. Ordinary functional checks stay optimized.

Acceptance: one current ABI, truthful flags, working explicit exact queries and
unchanged enumeration behavior before switching the default in DM3.

## DM2 Prepare commands and GEM callers

Teach resident DIR and loadable LIST to print exact byte lengths as before and
bounds as `NAME <=2530`. Display an unavailable size as `?`. LIST NAMES remains
name-only. Keep one DIR Write per row, existing bounded row/scratch storage,
streaming order, BREAK and cleanup. Neither command requests exact measurements.

Pattern selection, FIND, COPY destination checks and GUI scans use names/types;
they must not request lengths or allocated counts. Keep existing FIB/caller
storage and shared scan helpers. Do not add a size field to GUI entry snapshots.

The bounded text loader may reject a file early only when an exact size exceeds
its cap. A MyDOS bound above the cap is inconclusive. Retain its counted reads,
capacity/line limits and extra one-byte EOF probe at capacity, which distinguish
a fitting file from an oversized one without an initial size scan.

Extend focused command/text-loader fixtures for exact, bounded and unavailable
metadata. Include an actual file at the loader's capacity whose sector-derived
bound exceeds it, and one byte beyond capacity. Preserve the previous document
and release all handles/locks on failure. Audit every production fib_Size and
fib_NumBlocks consumer; use flags before treating a value as exact.

Acceptance: callers handle the new metadata states truthfully while the kernel
still supplies exact results. This prevents an intermediate commit from printing
an upper bound as an exact size or rejecting a fitting text file.

## DM3 Switch ordinary queries to directory metadata

Split metadata selection from measurement in
[FSDIRECTORY](../../lib/fs/fsdirectory.act). Ordinary Examine/ExNext copy fresh
decoded metadata into the existing result entry and publish availability flags.
Only ExamineExact enters FSBACKEND.Measure/its resumable continuation. Keep
directory-resolution steps required for lookup and ancestry; omit measurement
of each child merely to produce listing fields.

For MyDOS, reuse initial-file admission without fetching its payload, recognize
the accepted legacy empty form and calculate the wide bound for the public FIB.
For SDFS, use the recorded file length and leave allocated counts unavailable;
do not infer them from length, since sparse/preallocated files and map sectors
make that incorrect. For RAM, publish existing node metadata. Exact queries keep
the existing format-specific measurement/corruption paths.

Update native directory/write fixtures to check ordinary metadata availability
and use a separate file lock/FIB for explicit exact assertions. Preserve live
writer visibility, interleaved enumeration, copied/stale cookies, remount and
mutation invalidation. Cover 128/256-byte MyDOS, SDFS SIO/512-byte IDE, RAM,
zero/partial/short sectors, maximum bound arithmetic and a corrupt later chain:
listing can succeed, but ExamineExact/Read/mutation preflight must still fail.
Exercise BREAK before publication and a failed directory read through the real
adapter, checking unchanged results, exact reply collection and guards.

Acceptance: ordinary MyDOS enumeration has zero selected-file chain visits and
no payload reads. Ordinary SDFS enumeration does not measure each selected
file's map chain. Explicit exact results and file I/O remain unchanged.

## DM4 Measurements and documentation

Repeat matched cold/warm directory workloads with the same media, cache and
observers. Adapt expected metadata/output bytes to the deliberate API change;
keep measurement boundaries and counter definitions fixed. Distinguish historical
comparisons from freshly matched runs when fixture inputs differ.

Record time to first row, total frames, directory versus selected-file fetches,
chain visits, gateway/output calls, cache hits, physical I/O and emitted code
bytes. Check ordinary and explicit exact queries separately, plus one bounded
COPY/read/Seek(END) regression. Require zero selected-file measurement work for
ordinary listings and measured reduction in warm MyDOS listing cost. Do not
promise an overall speed factor before measuring output and packet costs.

Update DOS/MyDOS/SDFS/RAM and loading references, shell output documentation,
the roadmap and indexes. Preserve historical exact-FIB qualification records;
add new compact development evidence and an implementation record. Run host,
generator, documentation/link and only affected emitted-code checks not already
covered by passing slices. Demo refreshes and release qualification are separate.

## Storage and validation budget

Target **0 additional fixed / 0 per-Task / 0 idle reserved bank-zero bytes**,
including guards, alignment and unused capacity. The FIB remains 260 bytes;
metadata flags reuse reserved capacity. Keep Task/DP/stack pools, backend records,
cache capacity, sector buffers and transfer staging unchanged. Add no per-file,
per-mount or per-entry allocation. Report any upper-RAM growth from the appended
C binding slot, including alignment, and actual native code/stack observations.

Use development checks per slice: host/generator checks and focused optimized
machine-code behavior. Raw/optimized coverage is limited to DM1's changed layout
and language bridges. Preserve pinned inputs, runtime/domain guards, register
restoration, ownership cleanup and bounded completion. Plan-only edits require
content/link checks; this plan makes no new executable qualification claim.
