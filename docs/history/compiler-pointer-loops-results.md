# Native pointer-loop implementation results

> Historical record: applies to the revisions and profiles described below.
> See the [current documentation](../contributing/building.md) and [history index](README.md).

Implemented in actionc on `feature/native-pointer-loops`; the original integration used
`1f5049e9472fe80dfccae2fdea13e16e32ea1792`. This completes the
[pointer-loop plan](../plans/compiler-pointer-loops-plan.md). The FindName source,
three-byte pointer representation, native ABI v2 and stack-check setting are
unchanged. Shared NIR was not modified.

The [frameless follow-up](#frameless-follow-up) below records the newer compiler
pin and targeted measurements. The whole-demo figures refer to the original
integration above.

## Compiler slices

| Slice | Commit | Change |
| --- | --- | --- |
| P1 | `07a40487` | Coalesce complete pointer homes across casts and CFG edges. |
| P2 | `05134102` | Keep admitted call-free pointer loops in the existing resident DP pool. |
| P3 | `6f399627` | Update dying pointers in place and capture a dying base before replacing it. |
| P4 | `d61ae5e1` | Prove edge A/N/Z outputs unused before omitting their saves and repairs. |
| Validation | `dbba9c75`, `1f5049e9` | Extend boundary coverage and record the backend results. |

All allocations use typed operations and CFG liveness, with whole-routine
fallback when capacity, effects or emission proofs are unsuitable. Pointer
writes, calls and unmodelled scratch effects retain their existing strategies.
No routine names or record layouts participate in eligibility.

P4 checks machine liveness on the actual selected CFG, including backedges,
then checks a fresh analysis after replay. Live or unknown accumulator/flag
observations reject the proposal. Cyclic pointer copies retain complete
three-byte capture storage; protected machine state and A16 edge boundaries
remain intact. This adds no emitted-byte peephole pass.

## Measured result

The generic lookup fixture reproduces the original Exec816 FindName listing.
VM cycles measure routine entry through RTL with the same inputs and placement,
including checked entry and teardown. These are CPU-test timings, not SIO or
whole-command timings.

| Optimized lookup | Original | P1 | P2 | P3 | P4/final |
| --- | ---: | ---: | ---: | ---: | ---: |
| Code bytes | 381 | 332 | 278 | 252 | 228 |
| Fixed frame bytes | 26 | 20 | 6 | 4 | 4 |
| First match, `alpha`, VM cycles | 2,092 | 1,772 | 1,198 | 1,016 | 944 |
| Later match, `alphabet`, VM cycles | 4,692 | 3,902 | 2,590 | 2,130 | 1,968 |

FindName is **40.2% smaller**, with **54.9% fewer cycles** on the first-match
workload. The raw fixture remains 322 bytes with an 18-byte frame. The optimized
fixture enforces the final code, frame and first-match cycle budgets.

| Steady matching, nonzero character path | Original | Final |
| --- | ---: | ---: |
| Instructions | 67 | 32 |
| Stack-relative instructions | 35 | 2 |
| REP/SEP instructions | 13 | 9 |
| String-byte reads | 3 | 3 |

These path counts are static counts from the emitted listings. `$A0–$A2` holds
the left cursor, `$A3–$A5` the right cursor, and `$A6–$A8` the current node.
Successor and name temporaries reuse these homes when lifetimes permit. Both
cursor steps write their final DP homes directly. The two remaining stack
instructions capture and compare a character, rather than move pointers.
The repeated character read remains; eliminating it needs a separate
nonvolatile memory-effect proof. Conservative width requests remain where the
existing predecessor proof does not authorize omission.

## Whole demo

Summed Action! routine code fell from **460,048 to 459,313 bytes**, a reduction
of **735 bytes**. Twenty-six routines became smaller and two more reduced only
their frames; no routine grew in code or frame size. Compiled Action! code still
occupies banks `$01–$08`; the imported runtime remains in `$0F`.

| Representative routine | Code before → after | Frame before → after |
| --- | ---: | ---: |
| EXECLISTS.FindName | 381 → 228 | 26 → 4 |
| EXECLISTS.NewList | 63 → 63 | 0 → 0 |
| EXECLISTS.AddHead | 96 → 96 | 0 → 0 |
| EXECLISTS.RemHead | 167 → 167 | 12 → 12 |
| DOSOBJECTS.Find | 267 → 213 | 12 → 4 |
| CSTRING_IMPL.StrLen | 140 → 140 | 8 → 8 |
| CSTRING_IMPL.StrCmp | 230 → 230 | 10 → 10 |
| CSTRING_IMPL.StrChr | 162 → 150 | 14 → 14 |

Every slice, including integration, adds **0 fixed / 0 per-Task reserved
bank-zero bytes**. This includes guards, alignment and unused capacity. Smaller
invocation frames do not shrink the reserved Task stack pools.

The rebuilt distribution is `build/demo/exec816-demo.zip` (149,260 bytes). It
contains the OF816 boot XEX, matching SDFS system disk, pinned AltirraOS ROM,
short guide, licenses and checksums. All seven ZIP entries and payload checksums
were verified against the tested bundle. The native payload XEX is 486,617 bytes.

## Validation and limits

Development checks passed:

- Pointer lookup in raw/optimized modes: empty/single/multiple nodes, unnamed
  nodes, empty names, prefix mismatches, long common prefixes, resumed searches,
  aliased names, unaligned fields and bank-crossing strings.
- Generic cursor wrap/carry/borrow, live old values, whole-home capacity and
  fallback, swaps/cycles, malformed allocations and observed A/hidden-B/NZ
  rejection. The existing affected pointer/o65 tests also passed.
- Two Task domains plus IRQ-domain reentrant traversal, IRQ at every reached
  instruction, nested NMI and seeded schedules; full context/DP/stack guards.
- 342 native library tests (341 in the broad run plus the updated DP-admission
  assertion), 86 root native/ABI/image/o65/CLI integration tests, and five
  Exec816 frame-map host tests. Optional inventory tests were ignored.
- Exec816 `named-raw` and `named-opt` on the pinned IRQ-corrected Altirra bridge
  and AltirraOS ROM. The candidate was recorded as a local compiler override
  before moving the pin; subsequent compiler changes only updated a unit
  assertion and documentation.
- The standard OF816 demo smoke, including autoboot, shell commands, SYS: and
  D1:/D2: selection, and `CAT | WC`, on the pinned paced emulator profile.

The full debug native runtime suite was run once: **332 passed, 12 failed,
6 ignored**. All 12 failures were reproduced independently on the original
`52747ef6` compiler pin. They are in accumulator forwarding, captured byte
returns, home analysis, integer casts, o65, parameter comparisons/forwarding,
preemption, replay and state tracking. Most assert obsolete code shapes,
counts or DP offsets; one o65 context fixture has an unresolved interface name.
They remain a separate release gate. This result is focused development
validation, not a passing full-backend or hosted release qualification.

Retained local evidence is under `build/development/pointer-loops/`, including
before/after listings, maps and logs; named-list reports are in
`build/lists-tests/`. The final focused native provenance manifest is
`build/actionc-pointer-loops/tools/native65816-runtime-tests/target/qualification/run-cvlnzuge/manifest.json`.
The OF816 report is `build/demo/of816/results.json`.

## Frameless follow-up

Exec816 now pins actionc `70d59b96906e6c1f8a5688dadf1274a1dbda5770`. The compiler
places byte temporaries after complete pointer slots in the existing resident
DP pool, retaining stack fallback under pressure. Byte comparisons and their
adjacent-load optimization accept those homes. Compiler and Exec816 frame-map
validation reject out-of-range slots, byte/pointer overlap, calls and mixing
with the separate word-resident profile.

| Optimized FindName | Previous pin | New pin |
| --- | ---: | ---: |
| Code bytes | 228 | 189 |
| Fixed frame / local stack peak | 4 / 4 | 0 / 0 |
| First-match VM cycles | 944 | 889 |
| Later-match VM cycles | 1,968 | 1,895 |

Pointer homes remain at `$A0–$A8`. Byte home classes use `$A9–$AB`; after
comparison fusion only `$A9` needs memory traffic. No local stack writes,
allocation, teardown or stack-limit reads remain. Incoming arguments and the
return address remain on the caller's stack. The existing zero-frame rule
removes the entry guard; stack checks remain enabled globally. FindName source,
ABI and reserved bank-zero memory are unchanged: **0 fixed / 0 per Task bytes**,
including alignment, guards and unused capacity.

Development validation covers the compiler allocator and selector, image-map
round trips and corruptions, raw/optimized lookup and materialized comparisons,
DP exhaustion, byte and pointer boundaries, stack guards, and IRQ/NMI with two
Tasks and reentrant IRQ traversal. The optimized traversal is interrupted at
all 68 reached Task/instruction sites; raw covers 114. The Exec816 host suite
passes 236 tests. `named-raw` and `named-opt` pass with the clean new compiler
pin, AltirraOS ROM and IRQ-corrected emulator recorded in `toolchain/altirra-1m.json`.
The optimized Exec816 image independently confirms the 189-byte, zero-frame
FindName result. Existing full-backend release failures were not rerun.

Evidence is under `build/development/frameless-findname/`. The latest native
runtime provenance is
`build/actionc-pointer-loops/tools/native65816-runtime-tests/target/qualification/run-ncnewnyf/manifest.json`.
The existing OF816 demo distribution has not been rebuilt for this follow-up;
the refreshed pin applies to subsequent builds.
