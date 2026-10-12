# SpartaDOS listing measurements

[History index](README.md) · [Directory metadata](directory-metadata.md) ·
[Development evidence](../development/spartados-listing.json) ·
[Measurement tool](../../tools/measure_spartados_listing.py)

Cached SpartaDOS listings have similar latency on IDE and SIO. Resident DIR
lists eight root entries in about 309 ms and 20 commands in 750–767 ms. Loaded
LIST takes 1.77–1.80 seconds and 2.86–2.94 seconds respectively. Its command
loading and three/four output Writes per row explain much of the difference.
These are development measurements of the standalone VBXE shell.

## Inputs and timing boundaries

Both builds use production sources at `dbadb418`, optimized actionc revision
`6510ea1d148c93edea595be8a5afa9630d5a75e3`, Calypsi 5.18, the pinned AltirraOS
3.44 for 65C816 ROM, PAL, an 8× native CPU, 4 MiB linear RAM, an 80×30 VBXE
console and no primes Task. `tools/build_demo.py` builds the matching commands,
OF816 boot image, ROM/licences and distribution ZIP. Five-second autoboot and
the exact packaged kernel execute in both sessions.

The IDE fixture uses native 512-byte sectors, the pinned IDE Plus BIOS 2.1,
revision E controller and a solid-state disk model. SIO uses 256-byte sectors
and the GENERIC57600 profile, with accurate disk timing enabled. Both disable
SIO acceleration patches, burst I/O and random delays. Their 720 KiB system
filesystems contain identical payload bytes in all 41 files, independently
audited for allocation ownership. Root entry order, types and displayed lengths
match, including `EXEC816.XEX`; SYS:C contains the same 20 commands. The sector
layouts differ, so the cold results compare complete configurations rather
than isolating the transport alone.

Each command/output combination has one cold sample followed by three warm
repetitions. Cold invalidates all 512 read-cache tags, sector scratch and SDFS
map/directory/extent identities at an idle prompt. The volume and current
directory lock stay admitted. Warm repeats the identical command after CLS.
No filesystem mutation occurs. There are 64 measured invocations altogether,
including console and NIL output; all 48 warm invocations have zero physical
reads and zero cache misses.

Timing starts at ShellOneCommand entry and ends at its final RTL. It includes
parsing, redirection, directory lookup, LIST loading/launch/wait, output and
command cleanup. Typing and prompt redraw are outside the interval. The empty
cooked-line buffer is prefilled while paused; a physical Return uses ordinary
cooked input draining and shell dispatch. A separate physical-typing control
on the identical IDE image gives a warm root DIR median of 310.48 ms versus
308.62 ms with prefilled input, with overlapping ranges.

Passive markers observe existing instructions and the shared DOSCALLS
implementations reached by both resident and loaded commands. They add no guest
counters. Bridge clock values are aligned to the observer's unwrapped 32-bit
epoch. Routine durations include preemption and can overlap; they are not
exclusive CPU costs. Kernel-call counts include every Task during the interval.

## Console listing times

Warm figures are medians of three repetitions; ranges are in parentheses.
All values are milliseconds.

| Command | Rows | SIO cold | SIO warm | IDE cold | IDE warm |
| --- | ---: | ---: | ---: | ---: | ---: |
| DIR | 8 | 1,326 | 308 (307–310) | 351 | 309 (309–310) |
| DIR SYS:C | 20 | 1,545 | 750 (746–750) | 813 | 767 (766–769) |
| LIST | 8 | 8,400 | 1,773 (1,763–1,774) | 1,957 | 1,799 (1,799–1,809) |
| LIST SYS:C | 20 | 9,381 | 2,865 (2,864–2,866) | 3,074 | 2,942 (2,935–2,948) |

Cold DIR issues two SIO reads or two ATA read commands at root; SYS:C requires
five SIO reads or four ATA read commands. Cold LIST issues 34 SIO reads or ten
ATA read commands, including loading its 7,001-byte command image. ATA commands
can transfer several sectors. Cold SIO timings include rotational phase; a
single cold observation is not a stable latency estimate. For example, cold
DIR SYS:C to NIL is slower than console output despite identical read counts.

The first completed row includes its newline/caret painting. Its last
synchronous bitmap text return bounds completion in the framebuffer, before
the row-ending Write returns. This measures fenced drawing, not monitor
scanout; complete settled screens are independently compared with expected
pixels after every invocation.

| Command | SIO cold first row | SIO warm first row | IDE cold first row | IDE warm first row |
| --- | ---: | ---: | ---: | ---: |
| DIR | 1,077 | 61 | 102 | 62 |
| DIR SYS:C | 689 | 116 | 178 | 135 |
| LIST | 7,803 | 1,172 | 1,353 | 1,194 |
| LIST SYS:C | 7,761 | 1,247 | 1,414 | 1,290 |

## Remaining costs

NIL controls retain the same enumeration and number of public Write calls.
Their warm medians isolate much of the console-related elapsed time without
requiring disk I/O.

| Command to NIL | SIO warm, ms | IDE warm, ms |
| --- | ---: | ---: |
| DIR | 208 | 210 |
| DIR SYS:C | 470 | 494 |
| LIST | 1,392 | 1,431 |
| LIST SYS:C | 1,791 | 1,842 |

| Console command | Writes | SIO / IDE warm kernel calls | SIO / IDE loading, ms | SIO / IDE Write time, ms | SIO / IDE metadata time, ms |
| --- | ---: | ---: | ---: | ---: | ---: |
| DIR | 8 | 714 / 694 | 0 / 0 | 117 / 115 | 121 / 121 |
| DIR SYS:C | 20 | 1,497 / 1,504 | 0 / 0 | 294 / 295 | 287 / 283 |
| LIST | 28 | 1,779 / 1,734 | 1,030 / 1,042 | 387 / 403 | 150 / 154 |
| LIST SYS:C | 80 | 3,826 / 3,848 | 1,048 / 1,070 | 1,114 / 1,144 | 280 / 312 |

Loading covers two PROGRAMFILE.Load attempts: the current-directory search
miss and the successful C: lookup/load. Each LIST invocation loads and links
its image again, even with all sectors cached. Only about 230–280 kernel calls
occur during that roughly one-second phase. Its CPU work deserves a separate
loader profile before deciding whether to retain command images.

The [subsequent LIST loading profile](list-command-loading.md) attributes about
72% of warm loading to validation, binding, relocation and copying. It identifies
the payload byte loop and repeated scalar-reader bounds checks as small follow-ups.

LIST emits the name, separator or directory slash, size and newline through
separate Writes. For the 20-file command directory, output accounts for about
1.1 seconds and 2,200–2,260 kernel calls, versus roughly 0.29 seconds and
620–650 calls for DIR. Batching LIST rows through one public Write is the
clearest small follow-up; its existing directory scratch buffer can be
evaluated for reuse after Lock completes.

Both commands make ten metadata calls for root and 22 for SYS:C: Examine,
ExNext for each row and the final exhaustion query. Ordinary listing invokes
neither file/directory extent measurement nor the completed-extent cache.
That cache remains unallocated throughout both runs. Warm SYS:C DIR validates
two required directory maps, costing roughly 16 ms on SIO and 29 ms on IDE
in one representative repetition. That is a smaller cost than public metadata
request handling and output. These measurements do not justify another cache.

## Validation and memory

Development checks pass: 64 optimized emitted-code measurement cases,
media-derived output order/types/exact sizes, expected metadata/Write counts,
independent bitmap pixel comparisons, unchanged SYS/WORK media, allocation
audits, per-invocation ownership cleanup, stack/domain guards and final OS
screen/cursor/input restoration. EXIT leaves zero live Tasks. Six focused host
observer controls and the complete 454-test host suite pass.

Guest runtime sources, ABI, buffers and reservations are unchanged. Additional
reserved bank-zero bytes are fixed **0**, per-Task **0** and idle **0**, including
guards, alignment and unused capacity. Large build products, traces and pixel
captures remain under `build/development/spartados-listing`; the compact
evidence retains hashes, inputs, counters and timings. This is not release
qualification, a standard-console measurement or a real-hardware claim.

## Reproduction

Build fresh standalone bitmap demos from the recorded source revision:

```sh
python3 tools/build_demo.py --bitmap-shell-only --format sdfs \
  --sector-bytes 256 --release-compiler --output build/development/spartados-listing/sio-demo
python3 tools/build_demo.py --bitmap-shell-only --ide-only \
  --release-compiler --output build/development/spartados-listing/ide-demo
```

Reformat the IDE demo's payloads as comparison SIO media. This includes the
otherwise IDE-only root XEX so all displayed rows match:

```sh
python3 - <<'PY'
import sys
from pathlib import Path
sys.path.insert(0, 'tools')
from make_data_disk import make
root = Path('build/development/spartados-listing')
make(root/'sio-matched.atr', root/'ide-demo/media',
     binary_names={'EXEC816.XEX'} | {'C/'+p.name for p in (root/'ide-demo/media/C').iterdir()},
     filesystem='sdfs', sector_bytes=256, sectors=2880, label='SYS')
PY
python3 tools/measure_spartados_listing.py \
  --bundle build/development/spartados-listing/sio-demo \
  --media build/development/spartados-listing/sio-matched.atr \
  --output build/development/spartados-listing/sio-final
python3 tools/measure_spartados_listing.py \
  --bundle build/development/spartados-listing/ide-demo \
  --output build/development/spartados-listing/ide-final
```

Use a fresh output directory for each execution. `--analyze` replays retained
run/marker/trace files without guest execution; repeat `--media` for the SIO
comparison. `--physical-input` types every character for an input control.
