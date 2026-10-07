# Directory listing performance

[History index](README.md) · [Implementation plan](../plans/directory-listing-performance-implementation-plan.md) ·
[Baseline evidence](../development/directory-listing-baseline.json) ·
[Development evidence](../development/directory-listing.json) ·
[Filesystem architecture](../architecture/filesystems.md)

DL0–DL6 are implemented and pass development checks. On identical cached media,
the bitmap shell's root DIR drops from 736 ms to a 203 ms median; SYS:C drops
from 2,513 ms to 993 ms. Each row uses one Write. Exact allocation counts,
filesystem validation, output order and cancellation publication are preserved.

## Implementation

DL0 retains the unmodified preview baseline and adds a passive native observer.
DL1 computes directory coverage once per map page with shifts and masks,
removing software multiplication from the slot loop. DL2 uses existing native
Move/Clear operations for map copies, block-cache halves and FIB clearing.
DL3 assembles one bounded DIR row in the existing shell drawing buffer and
streams it through one Write, retaining polls and error/lock cleanup.

DL4 records allocated-slot count and first empty slot during map validation.
Measurement consumes this validated summary instead of scanning every slot
again. It still counts map pages and all allocated payload sectors, including
preallocation, and preserves sparse regular-file behavior. Required directory
holes, bad links, protected sectors and incomplete chains remain errors.

DL5 adds an optional 32-entry cache of completed SpartaDOS measurements to the
serialized filesystem worker. Keys include volume incarnation, entry identity
and exact active ancestry. Names and ordinary metadata come from the current
request. Hits follow the existing cancellation checkpoint before publishing
the FIB. Partial measurements are never stored. Mutation invalidates the whole
table before physical submission; error, offline, mount and teardown paths
invalidate or release it. Zero CACHE-BLOCKS disables it; allocation failure
falls back to measurement. There is no public ABI change or additional Task.
MyDOS benefits from shared bulk copies and row batching without an extent cache.

DL6 rebuilds both OF816 demo variants, compares the final bitmap image with the
retained media, and checks standard-console routing and concurrent primes.
The runtime slices are committed separately in `495fdff`, `77446a4`, `5bb7b35`,
`f2c5523` and `2777155`; the final observer/documentation slice changes no guest code.

## Matched warm measurements

The comparison uses the same 256-byte-sector image with five root entries and
17 commands in SYS:C. Its SHA-256 is
`a87fc518623515fe346c94adf8b6995824fb1210cb4385bea2e399d9687b63fb`.
Both images use optimized actionc
`6510ea1d148c93edea595be8a5afa9630d5a75e3`, the pinned AltirraOS816 ROM,
PAL, native 8× CPU, 4 MiB linear RAM, VBXE and no primes Task. The separate
host compiler build changes Cargo optimization only; compiler source and ABI
remain pinned. Exact image, observer, ROM and machine inputs are in the evidence.

| Warm command | Baseline median / range, ms | Final median / range, ms | Speedup |
| --- | ---: | ---: | ---: |
| `DIR` | 736 / 735–737 | 203 / 200–302 | 3.63× |
| `DIR >NIL:` | 494 / 492–496 | 138 / 138–140 | 3.59× |
| `DIR SYS:C` | 2,513 / single sample | 993 / 992–1,004 | 2.53× |
| `DIR SYS:C >NIL:` | 1,298 / single sample | 402 / 401–408 | 3.23× |

Final results contain three warm repetitions per command. Retained baseline
results contain two root repetitions and one SYS:C repetition for each output
destination. Timing runs from ShellDir entry through its final return, includes
preemption and drawing work, and excludes typing, dispatch and prompt redraw.
The slower third root repetition includes scrolling. All warm runs retain zero
physical SIO, zero block-cache misses and zero extent measurement map walks.
Five or 17 output Writes match the number of rows exactly.

First root filename Write is 39.5 ms median, with a 38.8–40.1 ms range.
A separate passive drawing control on the same image/media records the first
Text, TextCaret or ClippedText submission: 48.2 ms median, 46.5–50.5 ms range.
Submission does not measure physical scanout. All four planned targets pass:
at least 2× faster warm root/SYS:C, first root Write within 75 ms and first
bitmap submission within 100 ms. Cold root/SYS:C listings still require disk
reads and take approximately 1.49/5.05 seconds in this configuration.

## Memory and emitted code

Every slice reserves **zero additional fixed and zero additional per-Task
bank-zero bytes**, including guards, alignment and unused capacity. Task stack
reservations and the existing shell drawing buffer are unchanged.

The shared backend workspace grows from 466 to 470 requested bytes in DL4,
then to 474 in DL5. Allocator rounding changes 472 to 480 bytes. The optional
table requests 2,302 bytes and allocates 2,304, within the 2,304-byte ceiling.
Together these add **2,312 allocated upper-RAM bytes** when the table is present;
without it, only the eight-byte rounded workspace growth remains. There is one
shared table, allocated lazily, with no per-file or per-mount reservation.

| Routine | Baseline code bytes | Final code bytes | Baseline → final local stack peak |
| --- | ---: | ---: | ---: |
| SDFS.Cache | 517 | 537 | 26 → 38 |
| SDFS.ValidateMap | 1,144 | 1,390 | 36 → 38 |
| SDFSFILE.Measure | 2,121 | 2,064 | 38 → 42 |
| BLOCKCACHE.Copy | 179 | 63 | 12 → 12 |
| FSINFO.Clear | 92 | 54 | 10 → 10 |
| ShellDir | 1,995 | 1,352 | 48 → 44 |
| ShellDirRow | — | 1,110 | — → 44 |

The new SDFSEXTENTS module emits 4,466 code bytes. Its largest local stack peak
is 34 bytes in Lookup; fixed frames and individual routine sizes are recorded
in the evidence. Local peaks describe one invocation, not whole call chains.
Native stack/domain guards pass without increasing Task reservations. Both
bitmap manifests retain 18 nonfree upper banks. Whole-image code grows from
797,373 to 820,298 bytes and data from 8,462 to 8,557, but this comparison
includes other work since the preview and is not a DL-only code delta.

## Development checks and limits

The host suite passes all 396 tests. Focused optimized emitted checks cover:

- Both sector geometries, exact counts, sparse/preallocated files, multi-page
  maps, directory holes and malformed/protected links.
- Bulk-copy bytes/guards, cache eviction and real SIO, plus mixed-volume DOS
  operations and unchanged read-only media.
- Bounded names and signed size formatting, empty directories, one Write per
  row, console/NIL/file output and a live DOS pipe. Standard MyDOS file
  redirection is independently compared with all 200 persisted listing bytes.
- Cache identity/ancestry, replacement beyond 32 entries, both volume identities,
  generation changes, allocation failure, zero-cache fallback and heap teardown.
- Create/extend/overwrite/append/truncate/delete/rename and directory growth,
  remount/read-back, cached access behind an offline bus, failed physical writes
  and cancellation immediately before FIB publication.
- Physical foreground BREAK under eight live Tasks, prompt recovery,
  ownership cleanup, stack/domain guards and OS/context restoration.

Fixture maintenance binds the deferred console explicitly, restores the
read-only-handle error assertion, uses the current 4 KiB fixture data arena
and observes row visibility after Write completion. A broader old redirection
fixture stops at an unrelated UNKNOWN-command lookup expectation (218 versus
209); the selected DIR console/NIL/file/pipe cases pass. No production lookup
or transport policy is changed for that fixture.

RUN PRIMES progresses during repeated listings and shuts down normally after
BREAK. This separate control uses fresh media with six root entries and 19
commands. Warm root listings take 506–746 ms and SYS:C 2.36–2.39 seconds;
all have zero SIO/cache misses and one Write per row. These loaded results use
different media and pane/task conditions and are not a matched speedup claim.

Both local packages include OF816, five-second autoboot, pinned ROM/licences,
matching disks and `exec816-demo.zip`. Build products and traces remain under
`build/development/dir-latency/final-bitmap` and `final-standard`; they are not
published. Development checks do not qualify real hardware, alternative ROMs
or a release. Existing transport timing limits remain open. External media
changes without remount remain outside the cache contract.
