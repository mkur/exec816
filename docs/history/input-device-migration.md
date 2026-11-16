# input.device migration

[History](README.md) · [Current interface](../reference/input-device.md) ·
[Migration plan](../plans/input-device-migration-plan.md) ·
[Acceptance data](../development/input-device-im8.json)

Implemented through IM0–IM8 on 2026-11-16. These are development checks on emitted
optimized code, with the small public layout/access probe also checked raw.
This is not hosted-system or release qualification. No QED, application catalog,
demo package or release matrix was built for this migration.

The input Task owns INPUT acquisition, consumption and release. Native bounded
handlers translate/copy records and publish readiness without UPDATE, scene
access or drawing. Standard Atari text links no AES/DESK routines and needs no
VBXE device. GEM handlers use held routing snapshots; menu/drag interpretation
and cursor rendering remain in the selected frontend. Retained manager presses
carry window identity/epoch and endpoint holds. Withdrawal, endpoint exit and
overflow release those holds and cancel the incomplete sequence.

The frontend and console backend remain separate from capture. This adapts
MagiC's independent input role using ordinary Exec Tasks, messages, signals,
Task leases and short publication guards. No new specialized kernel operation
or scheduler policy was added. The current AESSYSTEM loop remains in the frontend;
SCRENMGR SM3/SM4's caller-drawing, scene-reader and physical-retirement work is
still outstanding.

## Executed checks

| Boundary | Focused result |
| --- | --- |
| Public wire/layout/access | Raw and optimized 17-assertion native probe, plus Calypsi layout checks |
| Controls/lifetime | 35 assertions: attach prefix unwind, cancellation before/after commit, reply collection, detach during system stop and service restart |
| Keyboard handoff | 59 assertions: physical keys/Ctrl-C/BREAK, queued detach, different handler on the same resident Task, new source generation and all sixteen route slots |
| Relative pointer | 10 assertions with physical ST motion and button edges |
| Native client | 13 assertions, including shared quick route control from a peer Task |
| Console ingress | 20 assertions for copied delivery, translation, overflow and stop admission |
| Atari text | 16 assertions: cooked/raw reads, Ctrl-C, output/scroll, close, heap equality and exact saved-screen/hardware restoration; zero GUI routines and no VBXE |
| Text focus/relocation | 13 stages and 50 assertions, exact pixels, captured focus, loss, close/reuse and exact saved OS restoration |
| Manager targets | 37 assertions while a manager sleeps on UPDATE: key/button inbox delivery, MCTRL, target pins, withdrawal/endpoint close, overflow and clean reclamation |
| GEM integration | Two ordinary Counters; 19 native assertions, pointer-busy startup rollback/retry, input and console writes during UPDATE ownership, and inbox delivery while drawing waits for a display grant |
| Host | 718 tests, five expected historical skips |

The focus check caught a copied-frontend error: showing a hidden console at a
new position dirtied the source model, so unchanged leading cells were omitted.
Show now invalidates the frontend's private copy. The test also waits for copied
backend delivery and checks the actual claim snapshot, rather than an earlier
boot-screen sample.

The tests use the [compiler pin](../../toolchain/actionc.json) at
`05c01f39ff3beef97af0e65b0a16666f5a1bd805` and the
[pinned Altirra configuration](../../toolchain/altirra-gem-vdi.json), dedicated
AltirraOS 65816 ROM and bridge hashes recorded with the evidence. Native context,
stack/domain guards, bounded completion and final ownership tables passed.
Pre-existing frame-setter work was present during these development checks and
was left untouched. The GEM image predates only the separately checked standalone
Show fix; Show is unavailable in GUI mode.

## Resource ledger

Fixed, root, kernel, private-idle and per-public-Task reserved bank-zero deltas
are **0 bytes**, including guards, alignment and unused capacity. The existing
eight-public-pool map is unchanged. Three selected service Tasks replace the
former combined two-service arrangement: input, backend and frontend. This
occupies one additional ordinary pool, **1,600 bytes**: 1,312 stack, 256 DP and
32 guard bytes. The GUI frontend retains its existing 2,848-byte large pool.
Root plus two Counters occupies six public pools; private idle stays separate.

The resident input arena adds **1,024 reserved upper-RAM bytes**. It includes
32 bytes for name/device metadata, a 122-byte service record, four 96-byte
bindings, two 92-byte sources and 302 bytes of layout slack. The service record
includes a reserved 62-byte Task object; the worker uses Exec's existing managed
Task metadata. None of that unused capacity is counted as a reservation saving.

Each native client owns 133 bytes before heap overhead: 56-byte client state
including its quick request, 27-byte port and 50-byte control request. GEM uses
keyboard and pointer handles. Manager targets add **192 upper-heap bytes per
GUI service**: sixteen 12-byte records, including alignment. Text has no AES
allocation. No VRAM map or drawing limit changed.

Observed GUI peaks were input **410/1,312** stack bytes, frontend **800/2,560**,
backend **161/1,312**, and kernel **287/1,536**. These retain their interrupt
headroom and guards; the observations do not justify shrinking reservations.
The small text fixture uses its own 1,536-byte pool profile, recorded separately.

## Passive timing

The observer inserts no guest instructions. IRQ/NMI time and off-Task time are
separate from conservative charged CPU, which includes called code and bus
stalls. The controlled workload includes startup, motion, intentional ownership
waits and teardown; it is not a scroll benchmark.

| Span | Samples | Median charged CPU | Maximum charged CPU |
| --- | ---: | ---: | ---: |
| Keyboard handler | 2 | 1.261 ms | 1.261 ms |
| Pointer handler | 114 | 5.431 ms | 9.229 ms |
| Control loop, including empty checks | 96 | 0.244 ms | 7.661 ms |

The input Task entered no drain turn during a **401 ms idle interval**. The two
keyboard publications reached their handlers in **3.24–4.20 ms** and their inboxes
in **4.50–5.46 ms** after native notification. Pointer elapsed time reached
66.54 ms, including up to 58.58 ms off-Task; it must not be described as isolated
handler CPU. Pointer records can coalesce, so their recorded notification delay
starts at the latest preceding notification rather than the oldest movement.
Nested spans must not be added. This evidence establishes independent progress;
it does not establish a scrolling-speed improvement.

Direct ordinary C handler callbacks, forced consumer-exit/unload recovery, live
text/GEM switching and the future VBXE text-mode renderer remain unsupported.
The existing standalone bitmap selection remains; this migration adds no new
renderer or final SCRENMGR implementation.
