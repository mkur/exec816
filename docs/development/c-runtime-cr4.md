# Shared C runtime: QED acceptance

[Current contract](../reference/c-runtime.md) ·
[Implementation plan](../plans/c-runtime-implementation-plan.md) ·
[Execution record](c-runtime-cr4.json)

CR0–CR4 pass development checks. QED uses the common allocation, argument,
descriptor, FILE, errno and termination implementation. Its remaining native
adapters provide GEMDOS names, document storage and editor transaction policy.
GemARC and refreshed distribution acceptance remain CR5 work.

The selected optimized checks cover native text allocation, files/stdio, Stop
and Task admission; save-transaction edge cases; real Open/edit/Save/Save As,
cancel, failed writes, uncertain Close and failed publication; Stop during
older-backup cleanup; and twelve edit/New cycles beside an ordinary GUI peer.
Closed-image audits check persisted document, backup and retained recovery bytes.
A focused runtime pair also checks independent state, callbacks, streams and
exact ownership restoration during concurrent execution. The host suite passes
665 tests. These checks do not constitute full hosted-system qualification.

The QED comparison uses a prior production build whose selected native sources,
patches, selection and Calypsi runtime manifest match the 0.2.3 baseline. QED
was a separate artifact and was absent from that release's core demo ZIP.
The execution record preserves the matched inputs and identities.

| QED metric | Baseline | Common runtime | Change |
| --- | ---: | ---: | ---: |
| Code bytes | 116,860 | 119,070 | +2,210 |
| Initialized bytes | 2,774 | 2,804 | +30 |
| BSS bytes | 24,628 | 24,945 | +317 |
| Image span | 182,396 | 184,606 | +2,210 |
| Serialized APP | 134,754 | 137,254 | +2,500 |
| Rounded loader backing | 247,936 | 250,144 | +2,208 |
| Declared Task stack, including interrupt reserve | 2,560 | 2,560 | 0 |

Both loader capacities above use the actual eight-byte heap alignment; older
layout reports rounded that accounting field to four. New reports derive the
alignment from the heap ABI. Prefixes increase from QED's former 12 to the common
16 bytes; heap rounding remains separate. The common argv allocation is also
owned until RELEASE. Detailed counters and stack observations are in the record.

All eight APPs in the original core ZIP were compared with their rebuilt
versions. Serialized growth ranges from 9,310 bytes for Counter to 13,918 for
BASIC. APP builds now disable the Calypsi cross-call and interprocedural
cross-jump optimizations required by the nonlocal termination boundary; QED
already used those options. CR3 started/stopped all nine rebuilt applications,
including the RAM-installed desktop, with guards and interrupt reserves intact.

Reserved bank-zero growth is **0 fixed, 0 root/kernel, 0 per public Task and
0 private idle bytes**, counting guards, alignment and unused capacity. Existing
small-stack and QED admission requirements remain unchanged. Runtime tables,
allocation prefixes and loader backing are upper-memory costs.
