# Separate filesystem file and lock objects

Status: O1–O3 complete. Each slice has a separate commit. See the
[measured results](../history/filesystem-objects.md).

Give file handles and locks their own records, retaining a common ownership
header. Keep shared file backing for inherited handles. Then remove read/seek
state from locks. Public DOS calls and opaque handle identities remain unchanged.

## Baseline and final layout

Use the current [length cleanup](../history/filesystem-length.md) as the baseline. It is
committed as `7a2e1fa`. Reuse its matching emitted layouts and images where
applicable.
Freeze the compiler in [toolchain/actionc.json](../../toolchain/actionc.json), stack
checks, emulator/ROM and fixture configuration for size comparisons.

The final representation is:

| Record | Contents |
| --- | --- |
| `FSTYPES.Object` | `DOSOBJECTS.Header`, mount pointer, mount generation |
| `FSTYPES.FileObject` | Common object at offset zero; pointer to `FileBacking` |
| `FSTYPES.LockObject` | Common object at offset zero; `LockState`; enumeration ticket; trailing name |
| `FSBTYPES.LockState` | `Entry`, ancestors, depth |
| `FSTYPES.FileBacking` | Reference count and the existing full read/seek cursor |

`Entry` remains the single definition of metadata, including length. Lock state
is an immutable snapshot. File positions and traversal state belong to backing,
shared only by inherited wrappers; independent Opens still create independent
backings. Keep the current variable-length name trailer in the lock allocation.

Projected sizes, to confirm through the pinned compiler:

| Record/allocation | Current | After O1 | After O2 |
| --- | ---: | ---: | ---: |
| Common object, active bytes | Part of 134-byte combined object | 16 | 16 |
| File wrapper, active bytes | 134 | 20 | 20 |
| File wrapper, rounded heap bytes | 136 | 24 | 24 |
| Independent file, wrapper + backing heap bytes | 248 | 136 | 136 |
| Lock record before name trailer, active bytes | 134 | 130 | 98 |

The expected saving is 112 heap bytes per file wrapper, including inherited
wrappers. Lock savings depend on name length and allocation rounding. Code-size
improvement is a measurement goal, not a promised result.

## O1 — Split file and lock allocations

- Reduce `FSTYPES.Object` to the common prefix. Add `FileObject` and `LockObject`;
  the lock initially retains the existing full `Cursor` to isolate this change.
  Keep `Service.object` and common registry operations typed to the prefix.
- Update `FSREGISTRY`, `FSHANDLER`, `FSDIRECTORY`, `FSRELATIVE`, `FSPACKET`,
  `FSINFO`, `DOSCALLS` and `DOSINHERIT` together. Validate ownership, kind,
  backend and mount generation before accessing a specific payload. A common
  pointer must never be treated as a file merely because it is non-null.
- Make `FSFILES` own file-wrapper/backing allocation and `FSLOCKS` own lock/name
  allocation. Use one small `FSOBJECTS` teardown dispatch for common callers,
  with explicit file and lock branches. It frees wrapper/backing storage;
  existing callers retain their mount-reference responsibilities. No callback
  table, additional payload allocation or compatibility object is needed.
- Make ticket assignment lock-specific, including inherited locks. File opens
  no longer consume an unused enumeration ticket. Preserve mount-generation
  checks and lock ticket exhaustion/stale-cookie behavior.
- Split the current inheritance clone path by kind. Files allocate a small
  wrapper and retain backing; locks copy their state and complete name trailer,
  then receive a fresh ticket. Reset ownership/list links before publication.
  Preserve rollback for allocation, reference-retention and ticket failures.
- Update unpublished-object cleanup in `FSABORT` and open failures. Set the
  object's kind before any failure can reach generic teardown. Remove reliance
  on a lock's unused backing pointer being zero. Allocation/free sizes use the
  selected concrete record and the complete name trailer.
- Update native layout oracles, build provenance and any routine classification
  for `FSOBJECTS`. Update inheritance/cancellation injection hooks if allocation
  sites move: the tests must still reach the intended failures. Several existing
  fixtures assert older 204/140-byte object layouts; migrate those assertions
  rather than retaining obsolete record variants.

Acceptance: no file reserves an inline lock cursor, no lock reserves a backing
pointer, and files retain shared-position behavior across inheritance and either
close order. Failed preparation and cancellation leave heap, mount/backing
references and ownership lists balanced. Wrong-kind handles are rejected before
payload access. Record measured layouts and allocation counts in the commit.

## O2 — Keep only metadata and ancestry in locks

- Add `FSBTYPES.LockState` and replace the lock's full cursor. Remove its byte
  position and 28-byte backend traversal reservation. Leave active file and
  measurement cursors unchanged.
- Update lock creation, cloning, Examine/ExNext, relative lookup, CurrentDir
  and NameFromLock to use the smaller state. Preserve the entry, all 17 ancestor
  slots and depth; enumeration position remains in the caller's FIB cookie.
- Change `FSBACKEND.ValidateBase`, `MYDOS.ValidateBase` and
  `SDFSNAME.ValidateBase` to accept `LockState` directly. Retain their existing
  ancestry, cycle, overlap and parent checks. Do not cast the smaller state to
  `Cursor` or construct a temporary full cursor for validation.
- Recompute the name trailer from `SIZEOF(LockObject)` in allocation, text
  access, cloning and freeing. Check empty/root names, maximum-length names,
  allocation rounding and names spanning a bank boundary.

Acceptance: locks contain no read/seek traversal storage. Relative paths,
inherited current directories, independent enumeration cookies and stale-cookie
rejection retain their behavior. Confirm the projected 98-byte fixed lock record
and name-dependent heap savings.

## O3 — Complete integration and record the savings

- Finish the affected integration cases below, reusing passing evidence from
  O1/O2 when its inputs still match. Cover both filesystem formats.
- Compare resident/library routine bytes with the baseline, excluding changed
  fixture code. Record concrete record sizes, rounded allocations, file-open
  and inherited-wrapper costs, lock-name costs and stack observations. Include
  any new common helper in the code total.
- Confirm unchanged bank-zero and fixed upper-memory reservations. Document
  measured results, source/image hashes, selected checks and remaining release
  qualification in `docs/history/filesystem-objects.md` and a development record.

Acceptance: the two object kinds allocate only their own state; all selected
checks pass with native guards, bounded completion, ownership cleanup and OS
restoration intact. Investigate unexpected code growth before closing the work.

## Focused validation

Follow the [two-tier policy](../contributing/testing.md): test coherent slices, not every edit.
Run host checks for code slices and focused emitted-code cases. Use the default
bank and 128-byte media unless a particular boundary needs another setting.

| Behavior | Starting fixtures and selection |
| --- | --- |
| Record prefixes, kind rejection, named lock allocation/free | `test_dos_lock_names.py --only` selected names, allocation and routing cases; raw/optimized coverage for the new layouts |
| Shared file positions, child-owned wrappers and current-directory snapshots | `test_process_inheritance.py --suite` functional case plus affected rollback cases; reuse each built image |
| Open/lock cancellation before publication | `test_filesystem_active_cancel.py --suite open-allocation,lock-allocation,open-publication,lock-publication` |
| Relative paths, depth and invalid ancestry | `test_dos_relative.py --only` relevant bank-1, depth and corrupt-ancestry cases |
| FIB cookies, metadata and teardown across both backends | Optimized `test_sdfs_dos.py`, plus targeted directory/name cases where the mixed fixture lacks coverage |

Keep failure and layout assertions meaningful: update expected emitted sizes
and offsets, preserve corruption checks, and inject allocation failures at the
new ownership boundaries. Do not run full baud, sector-size, placement or
concurrency matrices for every slice. A demo refresh is separate work and must
include OF816 if requested.

For O1–O3 the reserved bank-zero delta is **0 fixed bytes and 0 bytes per Task**,
including guards, alignment and unused capacity. Keep task stack/DP reservations,
worker count and signals unchanged. All allocation savings are in upper RAM.

## O1 result

The pinned compiler confirms a 16-byte common prefix, 20-byte file wrapper,
130-byte lock record and unchanged 112-byte shared backing. Rounded independent
file storage is 136 bytes (24 + 112), down from 248; inherited wrappers save
112 bytes each. Locks no longer reserve a backing pointer. Their full cursor
is retained until O2. No fixed memory or per-Task reservation changed.

Development checks passed: 236 host tests; raw object routing/layout (29 checks);
optimized canonical names/layout (53), allocation failure at the lock, file
wrapper and file backing (12), inheritance and rollback (395), and all four
open/lock allocation/publication cancellation cases on MyDOS. Inheritance also
checks saturated mount/backing references, lock-ticket exhaustion, file cloning
without a ticket and both parent/child close orders. Artifacts are under
`build/development/fs-objects/o1/`; release qualification remains separate.

## O2 result

Locks now embed a 78-byte `LockState`, giving the projected 98-byte fixed lock
record. Validators accept that state directly, with the same ancestry/overlap
checks. The 110-byte active cursor and 112-byte shared backing are unchanged.
Compared with the baseline, rounded lock storage saves 32 or 40 bytes depending
on name length; fixed and per-Task bank-zero reservation deltas remain zero.

Development checks passed: 236 host tests; raw lock names/layout (58 checks),
including an empty trailer, the maximum name and source/destination bank
boundaries; raw inheritance/rollback (395); optimized relative paths (82),
maximum depth (14), corrupt ancestry (10), and mixed MyDOS/SpartaDOS public DOS
operations (124). Artifacts are under `build/development/fs-objects/o2/`.
The first bank-crossing fixture placement overlapped platform assembly and was
rejected during image validation; its final placement uses free fixture banks.
Production memory reservations were not changed.

## O3 result

Final-source integration passed on both backends, including five cancellation
checkpoints per backend and 1,532 MyDOS directory assertions with stale-cookie
rejection. The nine final-source builds cover 17 native scenarios. The remaining
directory fixture's stale Service-size assertion was updated to 454 bytes.

The matching optimized fixture confirms the allocation savings and a 938-byte
resident/library routine increase (0.30%), fully accounted for by the module
breakdown. Its compiler, platform and complete memory map match the baseline;
fixed and per-Task bank-zero deltas are zero. See the
[development record](../development/filesystem-objects.json) for input/image hashes,
stack observations and per-case evidence. O1 results retain their slice scope;
final-source claims use matching O2/O3 inputs. No demo or release matrix was run.
