# Compiler refresh and Exec816 size comparison

> Historical record: applies to the revisions and profiles described below.
> See the [current documentation](../contributing/building.md) and [history index](README.md).

Measured 2026-09-30 on the standard optimized shell/play image, with eight Task
slots, stack checks enabled, SDFS and the same disk/console configuration. Exec
library, platform, application, ABI and configuration sources are unchanged.
The baseline follows the [DOS simplification](dos-simplification-implementation.md).

## Compiler integration

The old pin was `5f62c9fd`. The new pin is `52747ef6`, merging remote main
`1b072f3b` with the native Move/Fill helper commit `5f62c9fd`. Local actionc main
was advanced to that merge, preserving its pre-existing working-tree changes.
The compiler checkout used for the build is clean and matches the Exec816 pin;
no override is used. These commits have not been pushed.

The native ABI manifest, memory-runtime sources and all exported provider
contracts match the baseline. The compiler improvements cover direct copies,
24-bit arithmetic, expression consumers, forwarding wrappers, address selection,
empty frames and resident pointer values.

## Whole image

| Measure | Before bytes | After bytes | Saved |
| --- | ---: | ---: | ---: |
| Action! routines | 480,535 | 460,048 | 20,487 (4.26%) |
| Loaded segments | 493,521 | 473,034 | 20,487 (4.15%) |
| XEX file | 508,187 | 487,358 | 20,829 (4.10%) |

Loaded storage falls by **20,487 bytes (20.0 KiB, 4.15%)**. Action! code still
occupies **banks 1–8**. The last bank contains 9,795 routine bytes (9.6 KiB),
down from 28,656 (28.0 KiB). No complete code bank is released.

Reserved bank-zero usage remains **24,672 bytes excluding OS reservations**:
10,560 fixed, 2,080 for the root, 1,568 per child slot (seven slots), and 1,056
for idle. The change is **0 fixed / 0 per-Task bytes**, including guards,
alignment and unused reserved capacity.

## Subsystem code

These disjoint groups sum to the Action! routine total. Task policy includes
its DOS/console policy fragments. DOS/command code includes cooked input, pipes,
pipeline coordination and command providers; Process/inheritance is separate.

| Subsystem | Before bytes | After bytes | Saved |
| --- | ---: | ---: | ---: |
| Boot, resident library and generated code | 4,948 | 4,695 | 253 |
| Console | 57,968 | 54,884 | 3,084 |
| DOS and command API | 71,155 | 65,464 | 5,691 |
| Exec services and inspection | 10,559 | 9,914 | 645 |
| Memory and heap | 19,019 | 18,530 | 489 |
| MyDOS | 23,126 | 21,890 | 1,236 |
| Process and inheritance | 21,785 | 21,144 | 641 |
| Program loader | 24,283 | 23,874 | 409 |
| SIO, block I/O and cache | 31,005 | 29,811 | 1,194 |
| Shared filesystem code | 73,486 | 71,271 | 2,215 |
| Shell and demo | 49,986 | 49,648 | 338 |
| SpartaDOS | 31,305 | 29,872 | 1,433 |
| Task/kernel policy | 61,910 | 59,051 | 2,859 |

Using exactly the earlier DOS-report boundary instead, its subtotal falls from
68,994 to **64,172 bytes**, saving 4,822 bytes (7.0%). This alternative subtotal
overlaps the groups above and must not be added to them.

Two small list examples show the effect directly: NewList falls from 133 to
63 bytes; AddHead from 170 to 96 bytes.

## Rebuilt disk commands

| Command file | Before bytes | After bytes |
| --- | ---: | ---: |
| HELLO | 642 | 642 |
| CAT | 2,854 | 2,846 |
| WC | 2,875 | 2,863 |

## Validation and artifacts

Focused native memory tests passed in raw/optimized modes: exact ranges, odd
lengths, overlapping/cross-bank copies, large counts, buffer guards, IRQ/NMI
reentry and record-copy integration. The affected o65 publisher integration
check and all 235 Exec host checks passed.

The rebuilt standard image passed shell boot, SYS: navigation and shared-cache
checks, loaded HELLO, the CAT→WC pipeline, EXIT, heap/ownership cleanup and exact
OS display/input restoration on the existing pinned emulator and ROM. This is
development validation, without a full release matrix or timing qualification.

The refreshed artifacts are `build/demo/program.xex` and `build/demo/sdfs.atr`.
The before-image snapshot is under `build/development/compiler-main-refresh/before/`.
The [machine-readable record](../development/compiler-main-refresh.json) preserves
compiler and Exec revisions, source/artifact hashes, per-module/per-bank sizes,
provider compatibility and validation scope.
