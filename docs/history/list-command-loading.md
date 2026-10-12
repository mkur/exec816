# LIST command loading measurements

[History index](README.md) · [Program loading](../reference/program-loading.md) ·
[Listing measurements](spartados-listing-measurements.md) ·
[Development evidence](../development/list-command-loading.json)

This is the frozen pre-refactor profile. The completed
[loader refactor](command-loader-refactor.md) reduces warm loading to
766 ms on SIO and 785 ms on IDE; the original evidence below is retained.

Warm LIST loading takes 1.03 seconds on SIO and 1.04 seconds on IDE even when
every sector is cached. About 72% of that time is inside the loader, with the
rest mostly spent opening and reading the file through DOS. The smallest useful
loader change is to replace PROGRAMPLACE.Copy's byte loop with the existing
A816MEMORY.Move primitive. Wider scalar decoding is the next parser opportunity.

## Warm loading costs

These measurements reuse the optimized standalone VBXE shell and identical LIST
bytes from the [SpartaDOS listing comparison](spartados-listing-measurements.md).
Each transport executes `LIST >NIL:` once with cold caches and three times with
warm caches. OF816, five-second autoboot, PAL 8× CPU, 4 MiB RAM, the pinned
AltirraOS 65816 ROM and transport configuration match that comparison. There is
no primes Task. NIL output keeps console drawing outside the loading question.

The following independent phase medians are rounded to milliseconds. The
complete per-invocation partitions reconcile in the evidence; independently
rounded medians need not add to the median total.

| Loading work | SIO warm ms | IDE warm ms |
| --- | ---: | ---: |
| Current-directory search miss | 37 | 37 |
| Successful Open, two Seeks, two Reads and Close | 247 | 241 |
| Validate o65 profile and source relocations | 243 | 252 |
| Resolve resident imports | 153 | 156 |
| Allocate private image and sections | 5 | 5 |
| Copy executable payload | 134 | 136 |
| Preflight and apply assigned relocations | 197 | 201 |
| Other staging, release and error publication | 10 | 11 |
| **Complete loading** | **1,029** | **1,041** |

Warm load ranges are 1,023–1,029 ms on SIO and 1,040–1,047 ms on IDE. All six
warm invocations have zero physical reads and zero read-cache misses. There
are 231–267 kernel entries during loading, including filesystem and console
Tasks. Cold loading takes 7.63 seconds on the accurately timed SIO disk and
1.20 seconds on IDE, with 34 SIO reads and ten ATA read commands respectively.
Those cold values are single samples and compare different sector geometries.

The successful file path's DOS.Open alone takes 123 ms on SIO and 133 ms on IDE.
Cached payload reading costs another 96/84 ms. Opening includes C: resolution
and file admission; the 37 ms current-directory miss is a separate attempt.
These costs remain a shared DOS/filesystem follow-up rather than evidence that
the cached sector transport is slow.

## Parser and relocation work

The 7,001-byte LIST file contains 5,726 resident text bytes, no initialized data,
848 bytes of BSS, 16 imports and 178 relocation records. Allocation and clearing
are small costs here. The text copy alone costs 134–136 ms because
[PROGRAMPLACE.Copy](../../lib/dos/programplace.act) uses a LONGCARD index,
far-pointer subscripting and a byte assignment for every payload byte.
The pinned actionc runtime's A816MEMORY.Move is already used by
[SDFSFILE.Consume](../../lib/spartados/sdfsfile.act) and supports contiguous spans across banks without
allocation or interrupt masking. Reusing it needs no new public ABI or bank-zero
storage. The measured byte-loop cost is not a promised saving from a replacement.

[O65READ](../../lib/dos/o65read.act) decodes U32 through two U16 calls and U16
through two U8 calls. Every U8 calls Take to check the cursor and advance it.
One successful load makes 549 U32, 1,237 U16, 4,396 U8 and 4,446 Take calls.
Take accounts for 158–165 ms inclusively; U8 accounts for 279–289 ms, already
including those Take calls. U32's 173–178 ms is also nested inside the parent
parser phases. These totals overlap and must not be added to the phase table.

A bounded U16/U32 read can check the complete width once and decode its bytes
directly. That should remove repeated function calls and cursor work throughout
validation, import resolution and relocation. Before changing it, specify and
test truncated-input cursor advancement, returned values and first-error
preservation; the current bytewise reader can advance partially before failing.

The relocation stream is walked four times, taking 372–381 ms together:

1. Locate the exports and validate relocation encoding/order.
2. Validate section and import addends after the compact descriptor is admitted.
3. Preflight assigned destination addresses before patching private storage.
4. Apply the relocations.

The first two walks are included in validation's 243–252 ms; the last two are
the 197–201 ms preflight/application row. Consolidating them is broader than
replacing the copy loop or scalar readers: the passes use information that
becomes available at different stages. Preserve malformed-image rejection and
the rule that no section is patched until placement has passed preflight.

The provider resolver already parses each of the 48 manifest entries once.
It performs 768 name comparisons for the 16 imports. In the IDE sample,
provider String decoding takes 48 ms, direct scalar reads another 43 ms,
name matching 28 ms and resolver instructions roughly 36 ms. The old
per-import manifest parsing issue is fixed; a persistent provider or command
cache is not required for the first loader improvements.

## Validation and reproduction

[The observer](../../tools/measure_list_loading.py) decodes entry/return and
direct JSL call sites from the actual packaged machine image. It pairs calls
by Task direct page, includes interruption and scheduling time, and partitions
direct callees separately from nested reader diagnostics. No guest instructions
or production source are changed. Input preparation and cache invalidation use
the same unmeasured fixture as the listing comparison.

Eight optimized emitted-code invocations pass, with expected loading/search
paths, Write and enumeration counts, zero warm I/O, per-command ownership
cleanup, independent bitmap pixel comparisons, unchanged disk images,
stack/domain guards and final OS screen/cursor/input restoration. Both sessions
exit with zero live Tasks. Development host checks pass all 457 tests, including
three direct-partition observer controls. This scope does not qualify physical
hardware, the standard console or a release.

Reserved bank-zero change is fixed **0**, per-Task **0** and idle **0** bytes,
including guards, alignment and unused capacity. Builds, traces and pixel
captures remain in the development directory; compact evidence retains their
hashes and the measured partitions.

Use the unchanged comparison builds and SIO media prepared by the listing
measurement instructions:

```sh
python3 tools/measure_list_loading.py \
  --bundle build/development/spartados-listing/ide-demo \
  --output build/development/list-loading/ide
python3 tools/measure_list_loading.py \
  --bundle build/development/spartados-listing/sio-demo \
  --media build/development/spartados-listing/sio-matched.atr \
  --output build/development/list-loading/sio
```

Choose fresh output directories for execution. Add `--analyze` to replay the
retained trace, marker and run records without executing another guest session.
