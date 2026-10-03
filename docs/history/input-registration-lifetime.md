# Input registration and lifetime refactor

[Historical records](README.md) · [Implementation plan](../plans/input-registration-lifetime-implementation-plan.md) ·
[Current input contract](../reference/input.md)

IR1–IR5 implement registration and lifetime contracts for native and C input.
Acquire and Release retain full checks. Ordinary operations resolve a live
registration once and trust the caller's storage and lifetime obligations.
Phase-zero letter drains fall from 8.74–8.89 ms to about 0.95 ms charged CPU.
One Return drain still exceeds the 2 ms target; wider console latency goals
remain open.

## Contract and implementation

Take, Pending and route operations omit INPUT memory-table, full lease and
consumer audits in production, including EMPTY. Explicit diagnostic builds
retain those audits in the same implementation. Selection happens during source
generation, so omission holds for raw and optimized compiler output, without a
runtime diagnostic branch. Build provenance records `input_diagnostics`.

Acquire validates configuration, storage and the consumer. Release validates the
original registration and retires capture, notifications, retained events,
routes and Task holds before clearing it. Failed preflight leaves the live
registration intact. The owner must stop shared callers before releasing the
lease or reusing its signal/storage; a matching address does not make a stale
pointer valid after reuse. Take's output is borrowed for that call only.

The C bridge checks the complete huge address before narrowing, using a pure
shape check; native lifecycle calls perform the full audit once. The eight-entry
ABI, configuration version 2, statuses and record sizes are unchanged.

Task exclusion and native IRQ/NMI transactions remain. Acquisition/route/notice
identities, clipping, queue limits, durable loss/BREAK, pending pointer buttons,
BUSY retirement and shutdown coordination remain enforced. No Task, per-event
allocation, kernel service or hot-path reference counter was added. Core Exec,
display and filesystem authority contracts were not migrated by this work.

## Development checks

| Slice | Executed checks and changes |
| --- | --- |
| [IR1](../development/input-registration-ir1.json) | Resolved helpers and separated shape/audit checks; raw/optimized C ABI, keyboard capture and pointer failures. |
| [IR2](../development/input-registration-ir2.json) | Production Take/Pending omit audits; both compiler modes and diagnostic settings, complete huge-pointer rejection, pump and wake checks. |
| [IR3](../development/input-registration-ir3.json) | Route and C lifecycle migration; raw/optimized capture, pointer failures and diagnostic contract cases. Emitted call graphs check all six ordinary operations and lifecycle audits. |
| [IR4](../development/input-registration-ir4.json) | Console signals/focus, bitmap wake boundaries, GEM physical mouse and 25 queue cases per mode, six startup/close cases per mode, failed Release and same/different-address reacquisition. Diagnostic console smoke and an unchanged-image signal replay. |
| [IR5](../development/input-registration-ir5.json) | One final optimized image at three loaded input phases, passive operation profiles on existing C/keyboard/pointer binaries, and an unobserved replay of the final phase-zero image. |

The final working-tree host suite runs 330 tests successfully, with four
historical-source skips; four tests belong to pre-existing cartridge work
outside these commits. Generated interfaces and local documentation links pass checks. Focused
machine-code runs cover guards, native context, bounded completion, ownership
and OS restoration. These are development checks, not full hosted-system or
release qualification.

IR4 repaired two stale diagnostic/oracle hooks: the GEM cursor-fault hook now
requires its actual source boundary, and the text-console completion oracle
uses generated record offsets and the circular cell model. Those repairs do
not alter production input behavior, which is unchanged after IR3.

## Measurements

The [saved baseline](../development/input-registration-baseline.json) and CB4
artifacts were hash-checked and reused without rerunning a baseline. Loaded
runs match compiler, actual ROM/emulator binaries, machine configuration, disk
contents, guest fixture and physical input schedule. Generated workload scripts
differ only in output paths. Extra passive markers do not change the guest.

The configuration remains PAL 800XL, 65C816 ×8, 4 MiB, shadow ROM, VBXE FX 1.26
at `$D600`, ST mouse on port 1 and eight Tasks with physical SDFS traffic.
Action! remains pinned to `f1ff4ce0d16b4705e66d69aad00ca4a7be3e1d08`, without
an override; C uses Calypsi 5.18. IR5 records actual binary hashes, including the
separate shell-paced emulator used for the C ABI fixture.

| Phase-zero single-key drain | Saved CPU | Final CPU | Reduction |
| --- | ---: | ---: | ---: |
| Z | 8.892 ms | 0.949 ms | 89.3% |
| A | 8.735 ms | 0.954 ms | 89.1% |
| Return | 8.594 ms | 2.534 ms | 70.5% |

Every row includes one successful Take and the final EMPTY. Their two Take calls
total 0.495–0.525 ms, down from 6.75–7.61 ms. Ordinary authority audits are absent
from emitted paths and traced drains. Routine spans are nested, not additive.
Charged CPU includes kernel/scheduling/return tails and bus stalls; native
interrupt bodies and time assigned to other Tasks are separate.

In the Return outlier, Pump costs 1.751 ms and its nested Deliver costs 0.998 ms.
The trace enters a VBI dispatch before Decode, executes with kernel DP `$0A00`,
and restores the worker before decoding. That dispatch window contributes
0.900 ms scheduling/return CPU to the conservative service charge, excluding
its native interrupt bodies. Decode itself costs 0.051 ms. The remaining
0.783 ms outside Pump includes the Service exclusion/return path. Return's
8.603 ms elapsed interval also contains 3.260 ms native interrupts and 2.808 ms
off-worker time. This is not remaining INPUT authority validation.

At phases 3,547 and 14,188 base cycles after observed BUSY, Z/A/Return drains
cost 0.949–0.992 ms. The 2 ms goal passes those samples but remains open overall.
BREAK service costs 1.78–3.38 ms across phases, with cancellation routing included;
it is reported separately from the three ordinary-key target samples.

Separate optimized operation probes exercise actual machine code:

| Operation | Charged CPU per call | Scope |
| --- | ---: | --- |
| Native keyboard Take, seeded burst | 0.267–0.690 ms | 65 records across the fixture's burst cases |
| Native keyboard Take, EMPTY after seeded drains | 0.208 ms | Two calls |
| Native keyboard Take, loss / cancellation | 0.252 / 0.230–0.231 ms | Seeded durable notices |
| Native pointer Take, event | 0.372–0.594 ms | 16 calls |
| Native pointer Take, EMPTY / loss | 0.246–1.679 / 0.373–0.393 ms | Eight / six calls |
| C keyboard Take, EMPTY / Pending | 0.290 / 0.281 ms | One call each, including nested native work |
| C pointer Take, initial event / Pending | 0.479 / 0.340 ms | One call each, including nested native work |

These are different fixtures, not matched C before/after comparisons or guaranteed
upper bounds. Seeded loss/burst cases are distinct from physical key capture.
Raw/optimized correctness comes from IR1–IR4; these cost probes use optimized
production code. The evidence also records rejected calls and all individual
operation spans. No drain latency is inferred by dividing total CPU by key count.

| Loaded phase | Raw glyph visible, CB4 → final | Cooked glyph/caret visible, CB4 → final | Final maximum worker CPU |
| --- | ---: | ---: | ---: |
| 0 | 117.04 → 85.12 ms | 136.58 → 74.31 ms | 23.50 ms |
| 3,547 | 112.92 → 85.12 ms | 100.57 → 90.26 ms | 23.50 ms |
| 14,188 | 108.81 → 96.94 ms | 148.44 → 77.37 ms | 23.50 ms |

Visible values are frame-sampled upper bounds, not exact first-pixel times.
Every phase still observes an incorrect frame after 40 ms. Maximum complete
turn elapsed time is 92.87 ms; maximum off-worker delay is 57.89–64.55 ms.
All-owner native interrupt bodies occupy 1.44–1.47 seconds over the respective
complete-turn measurement windows. This includes multiple interrupt sources,
not only mouse sampling. The interactive workload completes 33–34 flood rows
versus CB4's 35, so aggregate totals are not equal-work CPU comparisons.

Public Forbid-entry to matching Permit-entry intervals peak at 32.17 ms across
these runs, versus 31.65 ms in saved phase zero. This observer includes nested
intervals, excludes cold startup and is not an exact measure of kernel state
mutation or uninterrupted Task exclusion across Wait. It does not establish
that full input queues are cheap. The 64-event pump budget remains unchanged;
measuring and decoupling that budget from queue capacity is separate work.

Loaded list launch-to-observed-idle bounds reach 39.55–46.81 ms. Each list retains
one completion query, an IRQ and at least one Wait; no timeout is observed.
SIO timing passes in every phase. ST sampling gaps peak at 268.97 µs, with the
existing approximately 7.9 kHz sampling rate. The unchanged phase-zero image
passes its unobserved functional replay.

The 2 ms service, 4 ms worker, 20 ms scroll and 40 ms visible-input acceptance
goals remain open. Scheduling cost/delay and work between input checks are the
next measured constraints. No scheduler, sampling, draw or drain budget was
changed during this comparison, and isolated scrolling was not remeasured.

## Memory and reproduction

Every slice adds **zero reserved bank-zero bytes**: fixed/root/kernel, each of
the eight public Tasks and private idle, including guards, alignment and unused
capacity. Generated reservations match the established eight-Task layout.
Capture storage, stacks and DPs are unchanged. Loaded stack observations stay
above their interrupt reserves; IR1–IR4 also record diagnostic stack usage.

Optimized INPUT routines occupy 14,758 bytes versus 16,249 in the saved baseline
(1,491 bytes smaller). Diagnostic INPUT occupies 16,674 bytes. INPUT introduces
no additional module data or reserved capture storage. IR5 changes only host
measurement tools, tests and documentation; it adds no guest code/data.

The final loaded XEX is
`70208114013e7b4bd4c4aaf17278de539bac8d688bab5550d3ade5cbae63ce67`
at all three phases and in the replay. Reproduce the loaded observer with
`python3 tools/measure_input_service.py --output build/input-service --phase 0`.
Use `--reuse` for subsequent phases with that build, or `--analyze-only` to
recheck saved artifacts. Comparison requires the archived local baseline files.
`tools/measure_input_operations.py` profiles an existing optimized C, keyboard
or pointer fixture in a fresh output directory using `--fixture`, `--from-build`
and `--output`. Diagnostic builds use the explicit `--input-diagnostics` option
on the native builder and supported input harnesses.
