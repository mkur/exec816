# HELLO and CAT size analysis

> Historical record: applies to the revisions and profiles described below.
> See the [current documentation](../guides/README.md) and [history index](README.md).

Measured 2026-09-25 at Exec816 `bbb8f2c72ad238201e83528a5ad90cc4f95e7b39`.
This examines the loadable [HELLO](../../examples/commands/hello.act) and
[CAT](../../examples/commands/cat.act), not the hosted kernel examples.
The [measurement snapshot](../development/command-size-analysis.json) records
compiler revisions, source/artifact hashes, and raw/optimized measurements.

## Packaged commands

All sizes below are bytes. These are the optimized files in the D6 demo bundle,
built with the pinned compiler `47cd55b2dac510922949832332b7a2c3220885be`.

| File component | HELLO | CAT |
| --- | ---: | ---: |
| Machine code, including stack guards | 929 | 3,889 |
| Initialized data | 18 | 0 |
| Compiler/loader descriptor | 1,073 | 3,123 |
| Other o65 framing, imports, relocations and exports | 339 | 747 |
| **Total file** | **2,359** | **7,759** |
| BSS, additional RAM but no file payload | 0 | 772 |

Metadata accounts for 60% of HELLO and 50% of CAT on disk. There is no embedded
copy of Exec, DOS, or the command library. COMMAND declares external providers;
the emitted bodies are just HELLO.Main and CAT.Filename/Copy/Main. Unused
external declarations are already omitted from the import table.

HELLO contains two writes, two Output calls, and two error-reporting paths: eight
static call sites. CAT has 21 call sites and does substantially more than a copy
loop: bounded filename parsing, quotes/escapes, file opening, short writes,
BREAK handling, preservation of causal errors and conditional close. Its BSS is
the 512-byte buffer, 256-byte path and four-byte failure value. Removing these
behaviors would change the command rather than improve compilation.

Recognized stack-guard sequences occupy 243 bytes in HELLO (nine sequences) and
648 in CAT (24). Subtracting those ranges leaves 686 and 3,241 code bytes. This is
an attribution measure, **not a built guard-free release size**: frame-entry
guards also perform stack arithmetic that an unchecked prologue still needs.
The current o65 build path emits guards and supplies no stack-check disable
option; unchecked commands also need an explicit loader/provider policy change.
Guard removal is a separate release-policy slice, consistent with the release
budget excluding debug guards.

## Rebuilding with the current compiler

The local override was actionc `7b078ea157e8986b0bfcfa281ea6312abf4d9bd3`.
The Exec pin was not changed.

| Compiler / mode | HELLO file | HELLO code | CAT file | CAT code |
| --- | ---: | ---: | ---: | ---: |
| Pinned / raw | 2,443 | 1,013 | 8,394 | 4,666 |
| Pinned / optimized | 2,359 | 929 | 7,759 | 3,889 |
| Current / raw | 2,443 | 1,013 | 8,342 | 4,614 |
| Current / optimized | 2,359 | 929 | 7,403 | 3,749 |

HELLO is byte-identical with the current compiler. CAT improves by 356 file bytes
(4.6%): 140 code bytes, 192 descriptor bytes and 24 ordinary relocation bytes.
The descriptor saving comes from twelve fewer relocation proofs.

| Optimized routine | Pinned code | Current code | Current fixed frame |
| --- | ---: | ---: | ---: |
| HELLO.Main | 929 | 929 | 16 |
| CAT.Filename | 1,136 | 1,136 | 20 |
| CAT.Copy | 1,608 | 1,485 | 24 |
| CAT.Main | 1,145 | 1,128 | 22 |

The pin predates the native 32-bit Add/Sub and constant-store work. Updating it
will recover the measured CAT saving after appropriate integration validation,
but will not address HELLO's remaining overhead.

## Compiler opportunities

### 1. Fold static addresses and constant byte indices

In the current optimized HELLO listing, producing `@greeting(1)` occupies **81
bytes** at `$01005A..$0100AB` (end exclusive). It materializes the symbol into
direct-page scratch, copies it to a stack temporary, copies it back, constructs
a three-byte constant one, adds it bytewise, and copies the result to another
stack temporary.

A direct symbolic address plus relocation addend can initialize the same final
three-byte home with three immediate loads and stores. Including the initial
SEP, that local sequence is 14 bytes: a **67-byte local opportunity**, not yet an
implemented whole-program saving. It needs no access to the array contents.

Likewise, the two `greeting(0)` reads and their LONGINT conversions occupy 88 and
90 bytes. Both rebuild an address and add zero before loading one byte. Use a
direct relocatable BYTE load, then zero extension. Preserve both reads: greeting
is mutable, so its initializer does not justify reusing the value across Write.
Even plain `@newline` takes 28 bytes through scratch and a stack temporary.

This slice can preserve exact memory access width, count and ordering. It does
not depend on proving that an arbitrary pointer supports wider memory accesses.
Prefer target address selection over introducing new source semantics in MIR.

### 2. Use Y for CARD-indexed byte access

CAT.Filename contains five `text(index)` reads and two `path(used)` stores.
Current code repeatedly builds a full effective pointer and performs a
three-byte carry chain for the CARD index. A stride-one BYTE access can use a
captured base pointer with the CARD index in Y and long-indirect indexed
addressing. Preserve 24-bit effective-address behavior, bank-crossing semantics,
the exact BYTE access, and call barriers. Handle reads and stores in separate
slices if that makes verification simpler.

This targets the 1,136-byte Filename routine that recent arithmetic work did
not shrink. It also has consumers throughout DOS and the kernel.

### 3. Signed tests and small call cleanup

CAT's captured LONGINT values still have opportunities in sign/ordered tests
such as `count<0` and `written<=0`. Native tests of private captured values can
be developed independently of alias-sensitive memory widening.

Native-width argument copies already exist, including word-plus-byte handling
of three-byte arguments. The remaining issue is scheduling: the current pass
chooses widths one argument at a time. Batching private low-word copies across
adjacent pointer arguments could amortize mode changes, provided the homes do
not overlap. This needs measurement before prioritizing it above address work.

Call cleanup also preserves A with TAY/TYA even for void calls. HELLO's two
SetResult sites demonstrate a small, bounded opportunity to omit that pair
when no result is captured. Do not treat necessary captures across calls as
automatically redundant.

For context, outside recognized guard ranges the current optimized binaries
contain 202/962 bytes of stack-relative instructions and 68/382 bytes of REP/SEP
in HELLO/CAT respectively. These categories explain where the code goes; they
are not promises that those instructions can all be removed.

## File-format overhead

| Descriptor component | HELLO | CAT, pinned |
| --- | ---: | ---: |
| Header and vector counts | 36 | 36 |
| Routine records/contracts | 88 | 274 |
| Object records | 97 | 134 |
| Import records/contracts | 388 | 919 |
| Relocation proofs | 464 | 1,760 |
| **Total** | **1,073** | **3,123** |

Each relocation has a 16-byte proof in addition to its ordinary o65 relocation
entry. There are 29 proofs in HELLO and 110 in packaged CAT. The format also
repeats ABI contract strings. Debug-name characters account for only 70 and 123
bytes, so stripping names alone will not resolve the metadata cost.

A compact profile could encode ABI identities once, shorten repeated contracts,
and reduce redundant relocation representation while preserving validation.
This is separate compiler/loader format work. The existing v2 profile already
has another purpose; any compact profile needs an explicitly defined version.

## Loaded RAM: the largest independent problem

[PROGRAMPLACE.Allocate](../../lib/dos/programplace.act) requests `textBytes+$ffff`
and rounds the usable text address up to a 64 KiB boundary. The complete backing
allocation stays live until unload. Alignment preserves the compiler's routine
bank placement, but costs approximately one extra bank per command.

| Retained allocation accounting | HELLO | CAT, pinned |
| --- | ---: | ---: |
| Text + initialized data + BSS | 2,020 | 7,784 |
| Image allocation payload, including alignment and header | **67,616** | **73,376** |
| Target with exact aligned text allocation | 2,080 | 7,840 |

The first two rows describe the current policy. The third is an accounting
target, not an implemented measurement. It saves 65,536 bytes for each of these
images after eight-byte allocation rounding. Current-compiler CAT still retains
73,040 bytes under the existing policy.

These totals include rounded text backing, data, BSS and the 48-byte rounded
Image record. They exclude allocator metadata, Process/DOS objects, inherited
streams, copied arguments, file staging, validation temporaries and task
stack/direct-page resources. The packaged CAT figure agrees with the existing
[D6 report](demo-implementation.md).

The cleanest RAM slice is an alignment-aware allocation operation within the
existing Exec heap/ownership model. Do not simply return the prefix/suffix with
FreeMem: the [system allocation contract](../reference/memory.md) requires
the original pointer and requested size and excludes partial system frees.
Allocation failure, fragmentation and exact unload ownership need coverage.

The descriptor itself also remains in loaded text. Discarding it could save
another 1,073/3,123 bytes, but needs a stronger contract: current validation
excludes descriptor relocation sites while permitting section-relative targets
within the full text extent. Prove/reject references into metadata before
shortening retained text. This is not merely changing the allocation length.

## Suggested order and validation scope

1. Compiler: constant symbol-plus-offset addresses, then direct constant-index
   BYTE accesses. These are the clearest small code-size slices.
2. Compiler: CARD-indexed BYTE loads and stores using Y.
3. Exec: exact aligned text allocation, as an independent RAM priority.
4. Compiler: captured signed tests and void-call cleanup; measure argument-piece
   scheduling before choosing a larger scheduling pass.
5. Format: compact contracts/proofs and explicitly discardable load metadata.
6. Release policy: unchecked command emission and compatible loader contracts.

This analysis rebuilt both commands in raw and optimized modes with both
compilers. Pinned optimized outputs were byte-identical to the packaged files;
manifest hashes matched the command sources, COMMAND interface, compiler binary
and packaged artifacts. Independent format decoding reconciled every file byte.
Diagnostic fixed-address links provided disassembly and instruction-based guard
recognition; their code sizes matched the o65 routine totals. Those diagnostic
links use placeholder provider addresses and were not executed.

No compiler, loader, command source or toolchain pin was changed. No runtime or
full Exec qualification was run. Local listings and detailed measurements are
under ignored `build/command-size-analysis/`; the compact snapshot linked above
preserves the results without checking in generated binaries.
