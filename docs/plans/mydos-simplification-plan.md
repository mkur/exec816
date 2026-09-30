# MyDOS simplification implementation plan

Status: M1–M4 complete. See the [implementation record](../history/mydos-simplification.md).

Make MyDOS use the common filesystem records directly, eliminating the state
translation introduced when the second backend was added. Deliver four executable
slices, with a separate commit and a short size/check record for each slice.

## Scope and baseline

Preserve the read-only DOS API, supported MyDOS media, filename matching,
directory traversal, Read/Seek results, cancellation and error behavior. Keep
the bounded parser steps: the filesystem worker owns I/O waits and cancellation
checkpoints. Retain corruption checks and cycle detection.

This work changes Exec816 source. Compiler optimization, compiler-pin updates,
SpartaDOS algorithm changes, filesystem writes, shared filename-parser extraction
and play-image refresh are separate work. Apply the [style guide](../contributing/style.md)
to changed routines without broad unrelated formatting.

The reviewed optimized image, built with the recorded local compiler override
`dab630a6` and stack checks enabled, contains:

| MyDOS component | Code bytes |
| --- | ---: |
| Metadata and path walking (`MYDOS`) | 8,589 |
| File operations (`MYDOSFILE`) | 9,853 |
| Name handling (`MYDOSNAMES`) | 1,851 |
| Common-record adapter (`FSMYDOS`) | 10,302 |
| Total | 30,595 |

Within those totals, the seven record-conversion helpers occupy 4,736 bytes;
the six blocking/convenience routines occupy 1,939 bytes. These are overlapping
subtotals of the table, not additional costs or guaranteed net savings. Parts
of FSMYDOS contain necessary behavior that will move into the backend.

Before M1, capture a reproducible baseline from the current source. Use the
[pinned compiler](../../toolchain/actionc.json) by default; if continuing with the
local optimized compiler, record its exact revision and override explicitly.
Use the same compiler, build configuration and fixture bytes for all before/after
measurements. Do not compare different compiler revisions as source savings.

## Final representation

| State | Single owner after the refactor |
| --- | --- |
| Block volume, root, format and mounted status | `FSBTYPES.Volume` |
| MyDOS VTOC bounds, bitmap extent and marker | Small private MyDOS volume record |
| Current/found entry, path, ancestors, errors and requested sector | `FSBTYPES.Workspace` |
| Entry metadata, ancestors, position, length and known-length flag | `FSBTYPES.Cursor` |
| Sector-chain position, trailer state and cycle-detection counters | Private record inside `Cursor.storage` |
| Read/seek parameters, progress, result and stage | `FSBTYPES.Operation` |

Preserve the current opaque MyDOS entry key: raw disk flags in bits 8..15 and
the directory ordinal in bits 0..7. Common `Entry.flags` continues to contain
only DIR/PROTECTED; trailer decoding must get the raw format flag and ordinal
from the key. Keep declared sector counts distinct from discovered byte lengths.
MyDOS entries retain zero timestamps and unknown lengths until measured.

No second workspace, mirrored cursor metadata or private operation record
remains. Keep the explicit two-format dispatcher; introduce no driver registry,
callback framework, extra worker or per-file sector buffer.

## M1 — Separate test drivers from the production parser

- Capture code totals, record sizes and allocation counts before changes.
- Move the synchronous `Mount`, `GetEntry`, `Resolve`, `BeginResolve`,
  `ReadPhysical` and `MYDOSFILE.Run` convenience logic into test support where
  it is needed. Production retains the existing bounded Begin/Continue calls.
- Update the metadata/file fixtures to drive the production steps, preserving
  sector request accounting, I/O errors and completion limits.
- If the existing runners cannot select a bounded development subset, add that
  selection without removing the full suite or relaxing its assertions.

Acceptance: production no longer emits these test-driving routines. Existing
metadata and file behavior passes focused raw/optimized emitted-code cases;
the independent disk fixtures are unchanged.

## M2 — Operate on common records and delete the adapter

- Change MyDOS metadata, name-component parsing and file operations to accept
  `FSBTYPES` records. Make this a single coherent migration of callers and tests;
  do not introduce a parallel parser or compatibility API.
- Reduce private types to MyDOS volume details and sector-chain state. Keep
  the existing 92-byte cursor reservation during this slice to separate behavior
  changes from shared storage sizing.
- Decode entries directly into the common entry. Initialize fields previously
  set by `ExportEntry`, including key, normalized flags, known length and dates.
- Update common operation/cursor fields directly. Explicitly preserve
  `neededSector` publication, byte position on failure, partial-read cancellation,
  length discovery and all existing step result meanings.
- Move volume allocation, measurement and directory-base validation from
  FSMYDOS to the appropriate MyDOS metadata/file module. Route FSBACKEND directly
  to those routines; remove FSMYDOS, the conversion helpers and obsolete types.
- Remove the MyDOS workspace allocation/free path. Update startup rollback
  injection for the remaining allocation sites; remove the obsolete
  `backend-work` failure case because that allocation no longer exists.
- Update fixtures that inspect or corrupt raw flags, ordinals and private chain
  fields to use the new representation while retaining their behavioral checks.
  Audit module lists, packaging rules and source transformations for old names.

Acceptance: no Push/Pull, Import/Export, mirrored operation or duplicated
workspace remains. MyDOS read/seek/metadata results and failure positions match
the baseline. Startup failure releases every resource still acquired.

## M3 — Reclaim unused record capacity

- Remove the unused MyDOS workspace-state pointer from the common workspace.
  Leave unrelated SpartaDOS naming and behavior alone.
- Replace `storage(92)` with a named capacity sufficient for the measured MyDOS
  chain record and SpartaDOS map cursor. Check both emitted layouts against it
  without creating circular module dependencies.
- Derive private allocation sizes with `SIZEOF`. Update affected size assertions,
  fixture allocations and frees together; rebuild all internal consumers.
- Record actual reductions per filesystem workspace, mounted MyDOS volume and
  open file/lock, plus embedded cursors in service and SpartaDOS state. Count
  allocation rounding separately from active field bytes.

Acceptance: no live private record exceeds its reservation; interleaved handles
retain independent state. Focused MyDOS and SpartaDOS cases pass after rebuilding
the shared layouts, with clean ownership and intact guards.

## M4 — Verify integration and publish the measurements

- Run focused public-DOS coverage for MyDOS open/read/seek, enumeration and
  relative paths, then cancellation/reuse and a mixed MyDOS/SpartaDOS mount case.
- Compare one fixed 8 KiB read with matching media, SIO speed and cache state.
  Record logical sector requests and physical reads; use a warm-cache run to
  expose CPU overhead. Do not infer loader performance from this read test.
- Recompile the standard system with the frozen compiler/configuration and
  report whole-image code, MyDOS code and common-filesystem code separately.
  Moving code into shared modules must not masquerade as a size reduction.
- Record RAM/allocation changes, stack bounds, bank usage, selected checks and
  pending release qualification in `docs/history/mydos-simplification.md`.

Acceptance: lower aggregate production code and upper-RAM usage, preserved DOS
behavior, no added sector reads for the selected workload, no guard/headroom
regression, and no resource leak. Investigate any unexpected regression before
declaring the refactor complete. Do not promise a specific KiB reduction before
measuring the final code.

## Development checks and memory budget

Follow the [two-tier testing policy](../contributing/testing.md). Test coherent slices rather
than every edit; reuse passing results until their inputs change. Run the host
suite for code slices and focused raw/optimized native coverage. Existing
starting points are `test_mydos.py`, `test_mydos_files.py`, `test_dos_startup.py`,
`test_dos_relative.py`, `test_filesystem_active_cancel.py` and `test_sdfs_dos.py`
under `tools/`. Select affected cases, not every runner's full matrix.

Across the slices cover 128/256-byte trailers, the 10/16-bit link flag and file
ordinal, fragmented and greater-than-64-KiB files, directory ancestry, EOF,
seek-from-end length discovery, malformed/cyclic chains, I/O failure,
cancellation after partial progress, and handle reuse. Preserve existing
register/stack/domain, ownership, bounded-completion and OS-restoration checks.
The full baud/bank/concurrency matrix remains a release activity.

For M1–M4 the planned reserved bank-zero delta is **0 fixed bytes and 0 bytes per
task**, including guards, alignment and unused capacity. All removed records
and reduced allocations are in upper RAM. Do not shrink task stack or DP
reservations as part of this work; report their unchanged budget per slice.
