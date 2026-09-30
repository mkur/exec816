# Command arguments implementation

Based on [the design note](../reference/command-arguments.md). Keep this to one
resident DOS helper, without allocation or a new kernel call. Two compiler
correctness fixes discovered by the focused tests are listed below.

## 1. Parser and public contract

- Add `COMMAND.ReadArgs(template, values, valueCapacity, storage,
  storageCapacity)`: LONGINT result, -1 success / 0 failure, with IoErr.
- Use CSTRING for the template, ADDRESS POINTER for result slots, and BYTE
  POINTER for storage; both capacities are CARD. Slots hold three-byte string
  addresses. The pinned compiler does not support CSTRING POINTER; consumers
  can view a populated slot as `CSTRING(BYTE POINTER(values(0)))`.
- Generate limits (eight fields, 255-byte template/text) and shared DOS errors.
  Implement bounded template validation and decoding with caller-owned storage.
  Clear every supplied slot on failure; no source modification or truncation.
- Template labels use ASCII letters, digits and underscore, with a letter or
  underscore first. Only an optional `/A` (case insensitive) is supported.

## 2. Resident integration and command migration

- Export one checked native provider in the existing program ABI.
- Replace CAT's private Filename parser with `c"FILE"`; keep its path buffer.
  A present empty filename is ERROR_INVALID_COMPONENT_NAME.
- Have WC use an empty template; keep ECHOARGS's raw GetArgStr behavior.
- Teach the shell's existing scanner to accept tabs alongside spaces, retaining
  its pipe/redirection handling and original quoted argument spelling.

## 3. Focused development validation and cost

- Run host contracts/generator checks and raw/optimized emitted parser cases:
  templates, required/extra values, quotes/escapes, limits, exact/short buffers,
  unchanged source, null-on-failure, canaries and separate callers.
- Run the focused CAT/WC stream fixtures and shell argument handoff checks.
- Extend the resident-library fixture with ReadArgs imports and two live callers;
  check relocation, signature rejection, independent storage and cleanup.
- Record code/metadata/stack costs and reserved bank-zero delta. No release
  matrix or play-image refresh is part of this slice.

Reserved bank-zero target for every slice: **0 fixed bytes / 0 per Task**,
including guards, alignment and unused reserved capacity.

## Compiler prerequisite discovered during validation

The far-memory canary fixture exposed two existing compiler defects: ADDRESS/
SIZE inline arrays disagreed with pointer indexing about the element stride,
and a cast around pointer arithmetic could lose the bank byte because semantic
analysis labelled the intermediate expression CARD. Fix these in actionc, with
focused regressions, and pin the clean revision. No Exec-specific compiler rules
or new language feature are involved.

## Implementation and development results

Slices 1–3 are implemented. CAT uses `FILE`; WC uses an empty template.
ECHOARGS retains GetArgStr. Errors and limits come from the ABI JSON inputs.
No parser routines are copied into either command.

These results used compiler `4293d5cc` (after `d3e91900`), subsequently included
in the [upstream compiler merge](../history/compiler-upstream-merge.md).
Reproducible prerequisites:
[array stride fix](../../toolchain/patches/actionc-array-stride.patch), then
[pointer-expression fix](../../toolchain/patches/actionc-pointer-expressions.patch).
Focused compiler checks include the CSTRING and embedded-array regressions, NIR
snapshots and the 51-fixture sweep. The required complete compiler suite is
also passed once for these shared semantic changes (3,550 tests).

Exec development checks on the pinned paced AltirraOS 65816 profile:

- 216 host tests and DOS/Process/program generated-definition checks passed.
- Raw and optimized: 65 parser cases, 17 CAT stream cases and 16 WC cases each.
  Parser results and canaries live in upper RAM, exercising full-width addresses.
- Raw and optimized: 109 resident-library/import/lifetime checks each. Two loaded
  callers retain independent decoded strings across suspension; changing their
  original text does not change those strings. Bad name/version/signature imports
  fail cleanly, and all owned memory is returned.
- Optimized shell: 74 cases / 356 checks, including real quoted/escaped argument
  tails passed into CAT's template, tab separators and redirection removal.
- CAT and WC compact-o65 builds pass in both modes and import the helper.

| Cost | Raw | Optimized |
| --- | ---: | ---: |
| Resident parser + public wrapper, bytes | 4,693 | 4,311 |
| Largest parser fixed frame, bytes | 34 | 36 |
| Public wrapper fixed frame / local stack peak, bytes | 28 / 50 | 28 / 50 |
| Loaded test callers' observed stack high-water, bytes | 458 | 425 |
| CAT file, bytes | 4,478 | 3,756 |
| WC file, bytes | 3,756 | 3,995 |

The provider entry adds **34 bytes**: EPV2 is now 733 bytes inside the unchanged
1,664-byte upper-RAM reservation. Parser code has no mutable static storage.
CAT keeps its 256-byte path buffer and adds a three-byte result slot; its emitted
Main fixed frame is 32 raw / 30 optimized bytes (including compiler storage).
WC needs no argument slots or decoding buffer.

The stack observations cover the whole loaded fixture, including I/O and
scheduling, rather than attributing all stack use to parsing. All guards and
OS/context restoration checks pass; the two callers retain 310 raw / 343
optimized untouched bytes above their reserved interrupt floor. Reserved
bank-zero delta is **0 fixed bytes / 0 per Task**, including guards, alignment
and unused capacity. No arena or Task stack reservation was enlarged.

Detailed provenance and measurements: [development record](../development/command-arguments.json).
These are development checks; no complete Exec release matrix or play-image
refresh was run.

Status: implementation and development checks complete.
