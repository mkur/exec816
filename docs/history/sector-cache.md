# Sector read cache

> Historical record: applies to the revisions and profiles described below.
> See the [current documentation](../architecture/sector-cache.md) and [history index](README.md).

The filesystem adapter keeps recently read sectors in upper RAM, shared by
MyDOS and SDFS, all mounts and all open handles. File closes and command exits
preserve the cache. It defaults to **512 blocks of 128 bytes: 64 KiB payload**.
A 256-byte sector occupies two blocks; a hit requires both halves.

Change `cache_blocks` in `config/kernel.json` when building, or cancel the
OF816 countdown and enter:

```forth
decimal
512 CACHE-BLOCKS!    \ 64 KiB; the default
CACHE-BLOCKS@ .
EXEC816
```

Zero retains only the original scratch-sector buffer. Other accepted values
are powers of two from 16 through 2048. The request is captured before Task
admission and applies to the boot session. If allocation fails, partial storage
is freed, the shell reports the fallback, and ordinary disk operations continue.
See [OF816 boot](../guides/boot-monitor.md) and the [boot contract](../reference/platform.md#boot-service-settings).

A four-way set-associative table limits lookup to four tags per block and uses
round-robin replacement. Collisions can evict data before nominal capacity is
full. Successful exact-length reads populate it; failures do not. Detach and
transport errors drop the affected volume. A reset-required/offline SIO bus
drops all retained blocks and still prevents filesystem access to cached data.
Keep mounted media unchanged until unmount/remount; there is no automatic
media-change detection, prefetch, write support or write-back.

## Memory cost

At the default capacity, upper RAM holds:

| Storage | Reserved bytes |
| --- | ---: |
| Payload | 65,536 |
| 512 twelve-byte tags | 6,144 |
| Per-set replacement indices | 128 |
| Adapter | 72 (66 used; previously 40 reserved) |
| Captured boot settings | 4 |

The payload/tag allocations add 71,808 bytes. Adapter growth and captured
settings add 36 more. There are no per-file or per-Task cache allocations.
The existing 256-byte transfer buffer remains. The optimized cache routines
occupy 5,292 upper code bytes; total emitted routine growth including boot and
integration changes is 8,283 bytes against the pre-cache standard image.

Bank-zero reservation growth is **0 fixed bytes, 0 bytes per Task**. The
standard eight-slot image still reserves 61,536 runtime bytes including the OS,
guards, alignment and unused capacity (24,672 excluding OS). Fixed runtime
storage is 10,560 bytes; the root slot reserves 2,080, each other public slot
1,568, and idle 1,056. Loading reserves 57,232 bytes including OS. OF816 continues
borrowing its existing 3,424 bytes until handoff.

## Measured behavior

On the pinned AltirraOS/Altirra emulator profile (8× CPU, PAL, SDFS with
128-byte sectors, Generic 57.6 kbaud), the same image and disk gave:

| 8 KiB `Read`, one busy CPU Task | Guest seconds | Wire reads |
| --- | ---: | ---: |
| Larger cache disabled | 7.641 | 66 |
| Default cache, cold data | 7.621 | 66 |
| Default cache, repeated after Close/Open | **0.662** | **0** |

All 8,192 bytes matched on both reads. The CPU worker completed 137 work rounds
during the warm read. Cold timing differs by about one PAL tick; this single
comparison does not establish a cold speedup. The retained read is about 11.5×
faster. Allocation, opening, closing and verification are outside the timing.

The standard shell image ran the same command sequence with its prime Task
active. These rows compare the later, fully primed sequence with caching
disabled versus enabled:

| Command | Disabled seconds / reads | Warm seconds / reads |
| --- | ---: | ---: |
| `HELLO` | 1.941 / 10 | **0.493 / 0** |
| `CAT STORY.TXT` | 7.042 / 37 | **2.446 / 0** |
| `WC <STORY.TXT` | 4.848 / 33 | **0.883 / 0** |
| `CAT STORY.TXT \| WC` | 9.440 / 64 | **1.961 / 0** |

The first HELLO was 1.755 s cold and its immediate repeat 0.487 s warm.
Command timing covers dispatch through load, execution and unload; typing,
redirection setup, prompt rendering and debugger pauses are excluded. Display
output and loader CPU work remain: warm HELLO still spends about 0.15 s inside
`PROGRAM.Load`, and warm CAT includes printing 24 lines. No eviction occurred
in this working set; the core fixture separately exercises forced collisions.

Free memory at the prompt is **311,208 bytes** with the default cache versus
383,016 disabled, exactly the 71,808-byte payload/tag allocation difference.
The largest contiguous linear block is 311,168 bytes with the cache. Startup,
a first command sequence and repeated commands/pipeline return to the same
memory baseline; final EXIT restores bank ownership and the OS. The pipeline
uses seven of the eight Task slots.

See the [measurement record](../development/sector-cache-measurements.json) for
pinned inputs, exact timings, wire counts, cache counters and trace hashes.
These are guest timings on that emulator profile, not hardware qualification.

## Development checks

The [boot record](../development/sector-cache-boot.json),
[cache fixture](../development/sector-cache-core.json) and
[OF816 record](../development/sector-cache-of816.json) cover real startup and
raw/optimized cache behavior. The core fixture verifies every returned byte,
full capacity across a bank boundary, 128/256-byte sectors and partial-half
misses, eviction, multiple mounts, remounts, failure/cancellation, zero capacity,
allocation rollback, guards and complete cleanup.

A warm filesystem cancellation case preserves the causal BREAK result and
cursor. The offline case warms D1 before a short D8 response, verifies that D1
cannot serve retained bytes through the offline bus, and checks that every tag
was invalidated. No extra worker checkpoint was needed: existing operation
checkpoints and ordinary preemption cover hits.

The host suite passes 231 checks. The required shared compiler checks exposed
two stale baseline expectations: the native snapshot still uses the old DP
locations and the NIR corpus count expects 362 successes where 363 pass.
The focused SIZE regression, NIR snapshots/sweep and remaining compiler test
targets pass. Full release and physical-hardware qualification remain separate.

The [refreshed play-image record](../development/sector-cache-play.json) records the
clean source build and final artifact hashes. Boot `build/demo/program.xex` or
`build/of816/of816-exec.xex` with the matching `sdfs.atr` in D1. The final OF816
bundle passed default autoboot and manual 128-block configuration into the
standard shell, HELLO, CAT/WC and EXIT, plus guard/ownership/OS restoration and
both monitor exit cases.
