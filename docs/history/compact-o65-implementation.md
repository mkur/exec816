# Compact o65 metadata

> Historical record: applies to the revisions and profiles described below.
> See the [current documentation](../guides/README.md) and [history index](README.md).

This historical slice introduced `actionc.o65.compact.v1`. Current builds use
[compact v3 with native ABI v2](direct-page-partition.md). The file carries an eight-byte
profile/ABI header and one four-byte signature per import, using the existing
o65 import names and relocation stream. Runtime stack guards remain enabled.
The [format and validation boundary](../reference/program-loading.md) are the public
contract; complete compiler proofs remain in host `.profile.json` records.

| Command | Previous file | Compact file | Metadata trailer | Reduction |
| --- | ---: | ---: | ---: | ---: |
| HELLO | 2,359 B | 1,314 B | 28 B | 44.3% |
| CAT | 7,759 B | 4,692 B | 56 B | 39.5% |
| WC | 6,538 B | 4,449 B | 44 B | 32.0% |

These are actual optimized compiler outputs. Code and data payloads keep their
existing representation. Routine/object maps, full import ABI descriptions and
duplicate relocation proofs are removed from the file; the remaining trailer
is excluded from resident text. The loader allocates only its validation record
and import table. Allocation-failure coverage therefore falls from four to two
validation allocations, and from eight to six for the full execution fixture.

The native provider manifest uses `EPV2`, with names, addresses, extents and
32-bit signatures. Its payload falls from 1,250 to 480 bytes. Host packaging still
checks complete physical provider shapes and retains them in `providers.json`.
The existing 1,664-byte reserved capacity is unchanged.

Compiler support is committed as `a62ee9e7`, based on the previous `47cd55b2`
pin, and recorded in [toolchain/actionc.json](../../toolchain/actionc.json).
The [compiler patch](../../toolchain/patches/actionc-compact-o65.patch) is retained
locally; no upstream push or general compiler qualification is implied.
The compiler's existing detailed profiles remain available to its other
consumers. Exec has one current loader profile; commands and kernel must be
rebuilt together.

Reserved bank-zero delta: **0 fixed bytes / 0 bytes per Task**, including
alignment, guards and unused capacity. Staging, validation and loaded images
continue to use the existing upper heap. The text alignment policy is unchanged.

## Focused validation

The compiler's `mir65816_o65` and `actionc_65816_o65_cli` targets cover compact
admission, standard split-address carries, relocation equivalence, truncation,
metadata versions, unsupported import contracts, report contents and protected
output paths. Raw and optimized compilation, LF and CRLF inputs are exercised.
The existing detailed-profile tests remain in those targets. All 19 tests pass.

The 19 host checks cover generated program policy, native package/frame maps
and disk builders. The program generator check, changed Python syntax and local
document links pass. A real MyDOS package contains five compiled commands and
nine Atari files, with every host JSON report outside the volume. HELLO, CAT,
WC and ECHOARGS are rebuilt under `build/compact-o65/commands`.

The native validator passes 1,355 optimized and 1,388 raw assertions, including
all 423/434 truncated prefixes, 23 corrupt-field mutations per mode, unchanged
source bytes and both allocation failures. Execution passes 98 assertions per
mode, comparing relocation bytes at two placements with the Rust reference,
checking 17 provider cases, two independent instances, six allocation failures,
retained ownership, unload/reload, stack/domain guards and OS restoration.
Optimized execution uses kernel bank 1; raw execution uses bank 3.

The optimized validator retains its recorded development compiler override.
The committed compiler contains the same format code; subsequent validation and
execution use the clean new pin. The simplified ASCII-only provider name reader
is exercised by both clean-pin execution cases. Full transport release matrices
and general compiler qualification remain separate.

The original fully raw multi-bank fixture ran its first instance successfully,
then correctly returned DOS error 103 at its second placement. Its resident
kernel occupies one more bank than the optimized kernel, leaving only banks
10–12 contiguous. The deliberate 65,536-byte gap plus the raw command's
166,685-byte aligned backing exceeds those 196,608 bytes, before metadata.
This is a fixture capacity limit. The multi-bank runner now uses the production
optimized kernel for both command modes, retaining the two distinct placement
assertion. Raw-loader coverage remains in the separate validation/execution
fixtures. The allocator and reserved memory policy were not changed.

Multi-bank execution now passes for raw and optimized commands: each has over
64 KiB of executable text and runs at two distinct bank-aligned addresses.
Both deliberate overflow runs reach the resident fault handler and retain the
live Image. Exact compiler inputs, ROM/emulator identity, native results and the
capacity diagnosis are retained in
[compact-o65.json](../development/compact-o65.json). This records six passing
native builds and eight sessions, plus the separately diagnosed capacity case.
