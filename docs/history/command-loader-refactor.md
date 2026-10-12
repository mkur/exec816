# Command loader refactor

[History index](README.md) · [Implementation plan](../plans/command-loader-refactor-plan.md) ·
[Original loading profile](list-command-loading.md) ·
[Development evidence](../development/command-loader-refactor.json)

The refactor replaces PROGRAMPLACE.Copy's byte loop with the pinned actionc
runtime's A816MEMORY.Move. Complete-width O65 scalar decoding is implemented as a
separate slice. The o65 contract, providers, relocation passes, staging sizes,
section ownership and BSS clearing remain unchanged.

## Bulk copy

The intermediate optimized IDE build loads the same 7,001-byte LIST image
as the frozen baseline. Its warm loading median is 914 ms (911–917 ms),
compared with 1,041 ms (1,040–1,047 ms). The copy phase falls from 136 ms to
6.15 ms. These are measured elapsed times, including interruption and scheduling;
the end-to-end result is measured independently of the copy-phase saving.

PROGRAMPLACE.Copy shrinks from 240 to 118 emitted bytes. Its local stack peak
changes from 14 to 20 bytes because it now calls the runtime primitive. The
runtime uses the calling domain's existing direct-page scratch, preserves
D/DBR/S/I, and requires no new buffer or interrupt masking. Only the admitted
text/data extents are copied; text alignment capacity is not cleared.

The focused optimized fixture compares every copied byte, every source byte
and guards against independently generated host bytes. It covers zero, odd,
even and unaligned copies; source/destination bank crossings; 65,534 through
65,537-byte lengths; and the 131,072-byte text limit in both address directions.
The large buffers are read from a paused Altirra save-state, with their address
mapping cross-checked using debugger reads. This avoids running a guest readback
helper or issuing a debugger request for every word. The fixture completes
across 30 native NMIs. Native stack/domain guards,
ownership and OS/context restoration retain their existing checks.

The reader fixture records the unchanged readers' results before their
implementation changes. Its 30 cases cover complete reads, bank crossings,
all shorter widths, invalid positions, arithmetic wraparound, distinct sticky
errors and repeated reads after failure. The host oracle checks values,
positions, errors and record/input guards rather than duplicating the parser.

The optimized o65 execution fixture also passes 98 checks: 17 provider-binding
regressions, six allocation failures, six loaded Processes, independent Rust
relocation-byte comparisons, BSS initialization and retained image lifetimes.
It uses the unchanged baseline readers for the copy slice. Its obsolete
console bridge is replaced by the pinned paced bridge; deferred-console
bindings, a 6,400-byte upper data arena and buffers in bank $28 bring the
fixture up to the current platform layout. These are test-only placements;
no production reservation changes.

## Scalar readers

U16 and U32 check their complete width once, load bytes with explicit
little-endian widening, and advance the cursor once. Their successful paths
make no U8/Take calls, and U32 makes no U16 calls. The unchanged bytewise fallback
preserves available prefixes, partial advancement and the first error on short
input; a prelatched error returns zero without advancing.

All 30 independent reader cases pass raw and optimized. The optimized corruption
fixture passes 1,124 checks, covering all 344 truncated prefixes, 25 mutations
and two allocation failures. The optimized execution fixture again passes its
98 checks and 17 provider-binding regressions with independent relocated-byte
comparison, initialized data/BSS and six loaded Process lifetimes. Guards,
ownership, native context and OS restoration pass.

The final IDE profile reduces U32 inclusive time from 177 to 58 ms. U16 calls
fall from 1,237 to 139, U8 from 4,396 to 1,922, and Take from 4,446 to 1,972.
These nested timings overlap; their differences must not be summed.

The readers grow from 187/193 to 606/894 emitted bytes: **1,120 extra upper code
bytes**. Their local stack peaks are both 24 bytes, compared with 14/20 before.
This uses existing stack capacity; it reserves no new bank-zero or upper data
storage. The runtime copy wrapper saves 122 code bytes, so the combined change
adds 998 executable bytes to the packaged IDE kernel.

## Combined measurements

Fresh optimized standalone VBXE demos include OF816, the pinned ROM/notices
and five-second autoboot. Their LIST files exactly match the frozen baseline
(SHA-256 `dad6fe0ec38106eb2065055c2ecc70930571047953ef6ed2def303389637e3d1`).
The SIO comparison uses the IDE payloads on a 2,880-sector, 256-byte SDFS disk;
IDE retains its 512-byte partition sectors. The root kernel XEX is refreshed,
while command bytes and directory rows remain matched.

| Warm LIST loading | SIO baseline ms | SIO final ms | IDE baseline ms | IDE final ms |
| --- | ---: | ---: | ---: | ---: |
| Validate input | 243 | 193 | 252 | 201 |
| Resolve providers | 153 | 117 | 156 | 120 |
| Copy text | 134 | 6 | 136 | 6 |
| Preflight/apply relocations | 197 | 154 | 201 | 157 |
| **Complete loading** | **1,029** | **766** | **1,041** | **785** |

Final warm loading ranges are 766–772 ms on SIO and 784.55–784.89 ms on IDE.
The measured total improves by about **25%** on both transports. Cold samples
are 7,415 ms on SIO (34 reads) and 937 ms on IDE (ten ATA read commands).
Those are single samples, with different transport/sector geometry; they are
not a hardware speed comparison. All six warm cases retain zero physical reads
and cache misses.

The visible LIST control passes independent media-derived rows and bitmap pixel
checks, once cold and once warm. Warm total command time is 1,548 ms at the root;
it includes loading, Process launch/wait, enumeration and ordinary console
Writes, and is distinct from the loading-only table. Every command returns its
ownership baseline, media remain unchanged, and all sessions pass native
stack/domain guards and EXIT restoration with zero live Tasks.

The final IDE session's shell slot touches 476 stack bytes (baseline 510);
its largest slot watermark remains 528 bytes in the existing 2,560-byte pool.
The kernel watermark remains 279 bytes. Watermarks are observed lower bounds,
not worst-case stack proofs. Fixed/per-Task/idle reservations are unchanged.
All 457 development host tests pass. This is the development tier; no full
release qualification matrix was run.

DOS staging now makes up a larger share of warm loading: successful Open alone
still costs 123/133 ms on SIO/IDE, and cached payload reads cost 98/88 ms.
The four relocation walks and the provider matching policy remain unchanged.
These shared DOS costs and LIST output batching are separate follow-ups.

## Scope and memory

This is development evidence for the pinned AltirraOS 65816 ROM and emulator.
It does not qualify a release or physical hardware. Each packaged transport
profile executes one cold and three warm `LIST >NIL:` invocations with
OF816 and five-second autoboot. All warm samples retain zero physical reads
and cache misses; per-command ownership, pixel results, unchanged media and
EXIT restoration are checked by the existing listing fixture.

Added bank-zero reservations are fixed **0**, per-Task **0** and idle **0**
bytes, including guards, alignment and unused reserved capacity. The default
eight-slot budget remains 26,848 runtime bytes excluding the OS. No persistent
upper-RAM allocation or public ABI change is introduced.

Builds, logs and traces stay under
`build/development/command-loader-refactor/`; compact evidence records their
hashes. The [original baseline inventory](../development/command-loader-refactor-baseline.json)
remains unchanged.

```sh
python3 tools/test_command_loader_core.py --suite readers --case raw \
  --output build/development/command-loader-refactor/cl2-readers-raw
python3 tools/test_command_loader_core.py --suite readers --case opt \
  --output build/development/command-loader-refactor/cl2-readers-opt
python3 tools/test_o65_validation.py --case opt \
  --output build/development/command-loader-refactor/cl2-validation
python3 tools/test_command_loader_core.py --suite copy --case opt \
  --output build/development/command-loader-refactor/cl1-copy
python3 tools/test_o65_execution.py --case opt \
  --output build/development/command-loader-refactor/cl1-execution
python3 tools/measure_list_loading.py \
  --bundle build/development/command-loader-refactor/cl1-ide-demo \
  --output build/development/command-loader-refactor/cl1-ide
```

Rebuild and compare the combined implementation using the matched-media recipe
in the [listing record](spartados-listing-measurements.md#reproduction), substituting
`build/development/command-loader-refactor` and the `final-*-demo` folders:

```sh
python3 tools/build_demo.py --bitmap-shell-only --format sdfs \
  --sector-bytes 256 --release-compiler \
  --output build/development/command-loader-refactor/final-sio-demo
python3 tools/build_demo.py --bitmap-shell-only --ide-only --release-compiler \
  --output build/development/command-loader-refactor/final-ide-demo
python3 tools/measure_list_loading.py \
  --bundle build/development/command-loader-refactor/final-sio-demo \
  --media build/development/command-loader-refactor/sio-matched.atr \
  --output build/development/command-loader-refactor/final-sio
python3 tools/measure_list_loading.py \
  --bundle build/development/command-loader-refactor/final-ide-demo \
  --output build/development/command-loader-refactor/final-ide
```

Use fresh measurement output directories; add `--analyze` to replay retained
trace/run/marker records. The visible control selects only `('LIST','',False)`
with one warm repeat through `measure_spartados_listing.run`, rather than the
full listing matrix.
