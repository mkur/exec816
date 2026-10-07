# Directory listing performance

[Plans index](README.md) · [Roadmap](../roadmap.md) ·
[DOS contract](../reference/dos.md) ·
[Filesystem writes](../reference/filesystem-writes.md) ·
[Development testing policy](../contributing/testing.md)

Status: DL0–DL4 development checks passed; DL5–DL6 pending. Deliver one
executable slice at a time, record its costs and development checks, and commit
before proceeding to the next slice.

Make cached directory listings respond promptly. Reduce repeated computation,
memory copying and output requests while retaining accurate FileInfoBlock
results, filesystem corruption checks and the existing serialized worker.

## Measured baseline

Passive observation of the unmodified `5fd47b6` bitmap preview used the compiler
revision in [actionc.json](../../toolchain/actionc.json), the pinned AltirraOS816
ROM and VBXE emulator, PAL, 8× CPU, 4 MiB RAM and no primes Task. Relevant
filesystem/cache source hashes match the investigated checkout. Local artifacts
are under `build/development/dir-latency`, including `results.json`,
`detailed/results.json`, the probe and hash-verified replay bundles.

| Warm command | Entries | First filename Write | Whole DIR routine |
| --- | ---: | ---: | ---: |
| `DIR` | 5 | 137–140 ms | 735–737 ms |
| `DIR >NIL:` | 5 | 133–136 ms | 492–496 ms |
| `DIR SYS:C` | 17 | 173 ms | 2,513 ms |
| `DIR SYS:C >NIL:` | 17 | 171 ms | 1,298 ms |

All these warm cases had zero block-cache misses and zero physical SIO commands.
Timing starts at ShellDir entry and ends at its final return instruction; typing,
dispatch and prompt redraw are excluded. First bitmap text submission is about
177 ms for root DIR and 225 ms for SYS:C. Submission is not physical scanout.
Nested routine durations are inclusive elapsed guest time and cannot be added
as independent CPU costs.

Before the first root filename, two extent measurements take about 67 ms.
Within the filesystem work, 249 inner-loop software 32-bit multiplications take
22.5 ms; three bytewise map copies take about 20–22 ms. Packet queue waits total
about 7–9 ms. DIR additionally sends three or four separate writes per row.

## Scope and invariants

- Keep the public DOS ABI, output bytes/order and exact `fib_NumBlocks`. Count
  every allocated data sector and map page, including preallocation; file size
  alone cannot supply this count. Preserve sparse regular-file behavior.
- Preserve directory-header checks, map links, sector bounds, protected ancestor
  checks, bounded traversal and errors for malformed media. No mount-time fsck,
  asynchronous enumeration or alternate lightweight FileInfoBlock is added.
- Keep the existing worker, packet lifecycle, BREAK checkpoints and final FIB
  publication. A cache hit still follows the normal cancellation checkpoint.
- Use existing `A816MEMORY.Move`/`Clear` and C-string number conversion. Generic
  compiler/runtime defects belong in actionc, with focused regressions there.
  No new assembly copy loop or command-specific compiler workaround is needed.
- MyDOS retains its traversal policy. Shared block copying and DIR row batching
  also benefit MyDOS. Scheduling, console batching policy and SIO stay unchanged.
- Every slice reserves **0 additional fixed and 0 additional per-Task bank-zero
  bytes**, including alignment, guards and unused capacity. Report actual code,
  upper-RAM allocation and invocation-stack changes separately.

## DL0 — Retain a reproducible baseline

Promote the useful parts of the passive probe into
`tools/measure_dir_performance.py`, reusing the existing demo observer and native
entry/call/return markers. Keep the image uninstrumented. Record source, compiler,
ROM, emulator, image and media hashes, cache settings and measurement boundaries.

Preserve the [compact baseline record](../development/directory-listing-baseline.json) under `docs/development`; large images and
traces stay in the development build directory. The historical preview requires
only the already documented host-observer exception for its missing WORK banner;
fresh builds use the ordinary observer without that exception.

Measure one cold listing followed by repeated warm root and SYS:C listings, with
console and NIL output. Record first filename Write, first text drawing, whole
routine time, cache/SIO counts, extent/map work and row-write counts. Verify the
listing bytes against the media-derived entries. Reuse the captured baseline
where inputs match rather than repeating unrelated boot/command scenarios.

## DL1 — Remove multiplication from the directory slot loop

In [SDFSFILE.Measure](../../lib/spartados/sdfsfile.act), compute the required
payload-sector count once per map page, using the admitted 128/256-byte geometry.
Derive the required prefix within that page once. A zero directory slot then
needs a slot-index comparison, rather than a 32-bit byte-capacity multiplication.
Use widened arithmetic before rounding and preserve the terminal coverage check.

Keep both current scans initially so this arithmetic change is independently
reviewable. Test zero/exact/partial extents, required holes, trailing unused slots
and map transitions at both geometries. The emitted hot loop must have no
long-multiply calls; directory errors and allocation counts must match baseline.

## DL2 — Use bulk memory operations

Replace the byte loop in [SDFS.Cache](../../lib/spartados/sdfs.act) with one
`A816MEMORY.Move` of the actual sector length. Replace the word loop in
[BLOCKCACHE.Copy](../../lib/io/blockcache.act) with a 128-byte Move for each
retained half. Move takes destination before source; retain the wrapper's existing
argument order deliberately. Publish tags only after copying completes.

Use `A816MEMORY.Clear` for the bounded FIB clearing loop in
[FSINFO](../../lib/fs/fsinfo.act). Preserve all reserved bytes and enumeration
cookie publication. Add no buffers, interrupt masks or allocations. Check exact
bytes and guards, including the existing transfer-buffer bank crossing, cache
hit/miss/eviction behavior and one real SIO case through the shared adapter.

## DL3 — Emit one complete DIR row per Write

In [ShellDir](../../examples/shell/shell-commands.inc), build each row in the
existing 128-byte drawing buffer, separate from the FIB in shell scratch. Append
the filename, slash or space/size, and LF using existing bounded string/number
facilities, then call ShellWrite once. The 32-byte FIB name field, decimal size
and separators fit this buffer; retain an explicit capacity check.

Do not call ShellNumber while assembling the row: it also uses this buffer and
writes immediately. Keep first-row streaming, ShellPoll, partial-write/error
policy, causal IoErr and lock cleanup. Do not buffer the whole directory.

Verify byte-identical file/directory rows and ordering, empty directories, maximum
names/sizes, console output, file/NIL redirection and a pipe. Reuse the shell's
output-failure and BREAK checks. Require one output Write per successful row.

## DL4 — Validate and summarize each map in one scan

Have [SDFS.ValidateMap](../../lib/spartados/sdfs.act) retain the allocated-slot
count and first empty slot from its existing validation loop. Two CARD fields
are sufficient. Publish this summary only after successful validation of the
current map for the current cursor/ancestry; clear it when replacing or
invalidating the map. Do not reuse a summary solely because the sector matches.

Measurement adds the map page and allocated slots once, checks the first empty
slot against DL1's required directory prefix, and preserves the final chain
coverage/count checks. It no longer scans all slots a second time. Ordinary file
reads still use the same validation entry and corruption rules.

Run the focused optimized SDFS parser/metadata cases at both sector sizes. Cover
empty, sparse and preallocated files, multi-page maps, directory holes, bad links,
out-of-range/protected sectors and cancellation between pages. Record the shared
upper-RAM delta and the effect on ordinary file reads as well as enumeration.

## DL5 — Cache completed SDFS extent measurements

Add one optional, worker-owned cache of **32 entries**, using simple bounded
lookup and round-robin replacement. One volume incarnation owns the table at a
time; changing volume/generation clears it. No LRU machinery or sector buffers.
Allocate lazily for SDFS measurement; allocation failure uses the normal path.
Keep this accelerator disabled when `CACHE-BLOCKS=0`, without adding a separate
user setting. Release it with the backend workspace.

Match the entry key, start/parent, input length/known/flags and the exact active
ancestry, including depth. Store only completed extent/count/known results and
directory-header dates where measurement supplies them. Names, other metadata,
locks and enumeration cookies still come from the current request. Capture the
input identity before directory measurement replaces snapshot metadata.

Lookup belongs at the backend measurement boundary, before directory-header/map
work. Hits seed the normal measured entry and return DONE through SizeResult;
they do not bypass dispatch availability checks or FIB publication. Misses use
DL1–DL4 and publish a cache entry only after complete successful measurement.
Errors and canceled traversals never publish partial results.

Extend `SDFS.Invalidate` to clear this table. Audit all existing write, namespace,
failure, mount/detach and offline paths. Invalidate before the first physical
mutation submission through [FSWRITEIO](../../lib/fs/fswriteio.act), preserving
its current post-write/error invalidation. Conservatively discard the whole table
on any mutation; no dependency tracking or reliance on mount generation alone.
Retained directory locks must still reflect growth after invalidation. External
media edits without a remount remain outside the existing cache contract.

Budget **at most 2,304 requested bytes** for the table and pending identity/result
bookkeeping, plus its private backend pointer and DL4's four summary bytes.
Include allocator rounding in the build report. There is no per-file, per-Task
or per-mount table. If the emitted layout exceeds this ceiling, simplify fields
before increasing it. Cache-disabled/allocation-failed execution remains correct.

Focused checks must cover warm hits with no measurement map walk, more than 32
distinct entries, both geometries, both volumes, mount-generation reuse, changed
ancestry, and create/extend/truncate/delete/rename/directory-growth invalidation.
Check a populated cache behind an offline bus, a failed mutation, cancellation
before FIB publication and heap restoration on teardown. Reuse current native
DOS/write fixtures; add only the missing cache-specific cases.

## DL6 — Compare the integrated result and record limits

Rebuild the optimized shell/kernel and affected commands with the pinned
toolchain. Compare against DL0 with identical media and configuration; run three
warm repetitions and report medians plus observed ranges. Include one standard
console/MyDOS functional listing and one listing while RUN PRIMES progresses.
These checks do not require a full qualification matrix.

Initial performance targets on the baseline VBXE configuration are at least
2× faster warm root and SYS:C completion, first root filename Write within
75 ms, and first root bitmap text submission within 100 ms. These are targets,
not predictions or hardware qualification. Warm runs must retain zero physical
SIO and block-cache misses. Report NIL timing separately so console costs remain
visible; never weaken correctness or change the workload to meet a target.

Record per-slice and final code/upper-RAM/stack costs, unchanged bank-zero
reservations, completed checks and any missed targets. Put the execution summary
in `docs/history` and compact evidence in `docs/development`; update indexes and
the roadmap. Update reference documentation only for implemented behavior. If a
demo is refreshed, use the required OF816 packaging workflow. Publishing a new
preview and release qualification are separate work.
