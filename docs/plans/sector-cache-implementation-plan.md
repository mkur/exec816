# Sector cache implementation plan

Status: C1–C4 implemented in separate slices. See the
[implementation and measurements](../architecture/sector-cache.md),
[boot evidence](../development/sector-cache-boot.json),
[cache evidence](../development/sector-cache-core.json),
[OF816 checks](../development/sector-cache-of816.json) and
[measurement record](../development/sector-cache-measurements.json).
Development checks pass; full release qualification remains separate. Follow
the [platform contract](../reference/platform.md) and [testing policy](../contributing/testing.md).

## Outcome

Keep recently read disk sectors in **64 KiB of upper-RAM payload storage** by
default. Repeated command loads and file reads should avoid SIO for retained
sectors, including directory and allocation-map sectors. Loading, relocation
and program initialization still run normally.

The existing [block adapter](../../lib/io/blockio.act) retains one sector. Expand
this boundary, shared by MyDOS and SpartaDOS, and keep its existing asynchronous
miss path. The filesystem worker owns the cache; no new worker or COP operation
is needed. Implementation exposed an unsigned SIZE multiplication defect; its
general fix and focused regression live in actionc (`bcabe0a4`).

## Capacity and boot setting

Use a numeric boot parameter, `cache_blocks`, counting **128-byte blocks**.
This makes the memory cost independent of disk geometry: a 128-byte sector
occupies one block, and a 256-byte sector occupies two. Short boot sectors use
one block. Call these blocks rather than sectors in configuration and commands
to avoid implying that every physical sector has the same size.

| `cache_blocks` | Payload capacity | Meaning |
| --- | --- | --- |
| 0 | 0 | Disable the larger cache; retain the existing one-sector buffer. |
| 128 | 16 KiB | Smaller-memory setup. |
| 256 | 32 KiB | Intermediate setup. |
| **512** | **64 KiB** | Default: room for 512 short sectors or 256 full-size sectors. |
| 1024 | 128 KiB | Optional larger cache. |
| 2048 | 256 KiB | Initial upper limit, subject to available RAM. |

Accept zero or a power of two from 16 through 2048. This permits cheap masked
indexing and bounds allocation and validation. Capacity is payload, not total
memory usage; tags and control state are additional.

The setting is fixed for the boot session. The direct XEX path initializes the
default; OF816 may override it before handing control to Exec. No persistent
settings store or runtime resizing is required.

Proposed Forth interface, available only after slice C3:

```forth
decimal
512 CACHE-BLOCKS!    \ request 64 KiB
CACHE-BLOCKS@ .      \ print the requested block count
EXEC816
```

`0 CACHE-BLOCKS!` disables the larger cache. The setter checks the full Forth
cell before narrowing it, reports invalid values and preserves the previous
setting. The getter reports the request, since allocation happens after Exec
starts. Leaving the five-second countdown alone uses the default.

## Boot handoff

Introduce one small, documented boot record shared by the direct loader and
OF816. An eight-byte first version is sufficient: a two-byte magic, one-byte
version, one-byte size, two-byte `cache_blocks`, one-byte `system_drive`, and
one reserved zero byte. The [SYS: plan](sys-volume-implementation-plan.md)
shares this record and defines the system-drive field.
Define the wire layout once in a machine-readable ABI file and generate the
assembly, Action! and packaging definitions. Use explicit little-endian fields.

Place it in proven unused space inside the existing 256-byte boot-state
reservation. Check the placement against loader work fields and all supported
layouts. Initialize defaults **after** the loader clears that area during its
first INITAD; entering `loader_start` after the monitor must preserve overrides.

Native startup validates and copies the record into owned upper-RAM settings
before any relevant bootstrap storage can be reused. No pointer into the Forth
dictionary or borrowed stacks survives handoff. Invalid records or values use
the build default and retain a diagnostic status. The OF packager obtains the
record location/version from generated image metadata and rejects incompatible
images instead of guessing an address.

This plan implements cache capacity. System-drive selection and `SYS:` follow
the linked plan, reusing the common boot plumbing; `RAM:` remains separate.

## Cache behavior and cost

- Allocate one cache when the filesystem adapter starts, shared across its
  mounts and all file handles. Keep it across ordinary file closes and command
  exits. A program image itself is not retained by this cache.
- Keep the existing 256-byte transfer/scratch buffer and its caller contract.
  Copy cache hits into it; read misses into it through the existing SIO path,
  then populate the cache after successful, exact-length completion.
- Store payload in 128-byte blocks. Use a small four-way set-associative tag
  table: hash the volume identity, sector and half-sector into a set, examine
  at most four candidates, and replace entries round-robin. This avoids a scan
  of hundreds of entries on every read and avoids linked LRU maintenance.
- Tags identify the attached volume, mount generation, physical sector and
  half-sector. Geometry/profile remain immutable within that volume lifetime.
  A 256-byte hit requires both halves; a missing half triggers one complete
  physical-sector read. Publish both halves only after the complete successful
  transfer, without allowing the second insertion to evict the first.
- Allocate payload with `MEMF_UPPER | MEMF_LINEAR`, using wide size/address
  arithmetic across bank boundaries. Tags and adapter state also live in upper
  RAM. Clear validity metadata rather than clearing 64 KiB of unused payload.
- Target at most 8 KiB of tags, replacement state and added adapter/configuration
  storage at the default capacity. Record actual sizes, allocator rounding and
  code growth in C2. The existing scratch buffer remains an additional 256 bytes.
- If either cache allocation fails, free partial allocations and keep the
  existing one-sector behavior. Record requested/effective capacity and report
  the fallback once when the filesystem starts. Do not fail boot or silently
  consume bank-zero memory. Free everything on adapter teardown.

Hash collisions may evict blocks before the nominal payload capacity is full.
Measure the intended command working set before accepting the replacement/hash
choice; do not promise that every collection of files smaller than 64 KiB fits.

Keep synchronization under the existing single-worker ownership. Cache hits
must still pass normal request, mount and cancellation checks. Preserve bounded
filesystem progress and BREAK handling when warm reads no longer wait on SIO;
add a bounded worker checkpoint only if existing operation checkpoints are
insufficient. Interrupt handlers never access the cache.

## Invalidation

Distinguish invalidating the current scratch-buffer contents from dropping
stored blocks. In particular, reusing scratch space for `OpenDevice` must not
flush unrelated cached volumes.

Invalidate a volume's blocks before detach/free and on transport failure.
An unsafe/offline SIO bus invalidates all affected mounts and prevents cache
hits from bypassing their unavailable state. Failed, short or cancelled reads
never publish data. Keep derived filesystem-cache invalidation consistent with
the [existing lifecycle contract](../reference/dos.md).

Preserve the requirement that media remain unchanged while mounted, including
through raw SIO clients. A controlled disk replacement requires unmount/remount
and a new generation. This cache does not detect external media changes.
Write support must add invalidation/update rules before it is enabled; this
milestone is read-only, without prefetch or write-back.

## Implementation slices

### C1 — Boot configuration

Complete: the direct loader initializes the record, Task startup validates and
captures it, and build metadata carries its layout/defaults. The host suite
passed 230 checks. Ten real-loader cases passed in each of raw and optimized
code, covering defaults, overrides, malformed records and independent captured
settings, with normal context/guard/ownership and OS-restoration checks.

Add the boot-record ABI, generated definitions, build default and image metadata.
Connect direct-loader initialization and native validation/copying. Document the
public handoff contract in the platform documentation. Keep filesystem behavior
unchanged until C2.

Development checks: generated definitions and host layout/validation checks;
one focused native fixture for default, zero, valid override, malformed record
and out-of-range value, including preservation through loader entry.

Bank-zero reservation delta: **0 fixed bytes, 0 bytes per Task**. The eight-byte
record consumes existing reserved capacity, including its reserved zero byte.

### C2 — Shared read cache

Add a small private cache module behind `BLOCKIO`, update adapter records and
all affected callers, and pass the captured setting through filesystem startup.
Implement allocation, lookup, replacement, successful fill, invalidation and
cleanup together. Retain the single current block-adapter interface and its
immediate-hit/prepared-miss behavior.

Extend the focused block fixture in raw and optimized emitted code. Cover warm
hits without wire requests, collisions/eviction, 128/256-byte sectors and short
boot sectors, mixed volumes, remount/address reuse, failed/short/cancelled fills,
zero capacity and allocation rollback. Include a payload crossing a bank
boundary. Verify unchanged data, guards, ownership and cleanup. Use an affected
filesystem cancellation/progress case to cover an entirely warm read.

Bank-zero reservation delta: **0 fixed bytes, 0 bytes per Task**. Payload and
metadata are upper-RAM allocations; no task slots or stack/DP arenas are added.

### C3 — OF816 configuration words

Implement `CACHE-BLOCKS!` and `CACHE-BLOCKS@` in the local platform dictionary,
using the generated boot contract. Keep the countdown and `EXEC816` flow.
Document both cache-disabled and default-capacity examples, with no upstream
Forth modifications or general parameter parser.

Extend the existing OF smoke fixture with one default autoboot and one cancelled
countdown/set/get/manual-boot route. Verify the effective kernel setting, invalid
input preserving the old value, guarded handoff and ordinary shell operation.

Bank-zero reservation delta: **0 fixed bytes, 0 bytes per Task**. Keep new word
logic in the upper-RAM dictionary and any adapter changes within its current
code/state limit; packaging must continue enforcing that limit.

### C4 — Measure and refresh the images

Reuse the isolated 8 KiB read and command-loading measurements. On identical
ROM/emulator/media/SIO profiles, compare larger-cache disabled, enabled cold,
and enabled warm runs. Count actual wire reads as well as elapsed time. Use
fresh startup/remount for cold measurements; closing a file does not clear the
cache. Include repeated HELLO and a HELLO/CAT/WC sequence, with a background
task, to show both reuse and remaining loader CPU costs.

Acceptance: exact output in every mode; zero wire reads on a repeated read whose
required sectors remain cached; measured warm command improvement; no persistent
allocation growth; working BREAK and background-task progress. Explain any cold
regression or unexpected collision misses before accepting the implementation.

Refresh the standard and OF play bundles. Run the focused shell/pipeline/EXIT
smoke with the default cache and record requested/effective capacity, total
memory cost, free memory and pinned inputs. Confirm enough heap remains for the
existing CAT/WC pipeline and prime task. Full release matrices remain separate.

Bank-zero reservation delta: **0 fixed bytes, 0 bytes per Task**. Report actual
reserved totals including guards, alignment and unused capacity for the final
image. If fitting the implementation would require enlarging a bank-zero arena,
revise and justify that budget before making the change.
