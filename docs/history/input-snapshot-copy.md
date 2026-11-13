# Empty input route copies

[History](README.md) · [Plan](../plans/gem4xe/input-snapshot-copy-plan.md) ·
[IC1 baseline](../development/input-snapshot-copy-ic1.json) ·
[IC2 evidence](../development/input-snapshot-copy-ic2.json) ·
[Earlier route reuse](gui-route-reuse.md) · [AES contract](../reference/aes.md)

## Implementation

`AESSNAPSHOT.Default` now tests a published slot's endpoint before copying its
46-byte `WindowRoute`. An empty slot clears only the caller's endpoint and
returns zero. A populated slot still copies the complete record and takes one
temporary endpoint hold. A live client without a focused window remains a
successful lookup. The endpoint check, copy and hold share the existing Forbid
guard with publication and withdrawal.

Successful callers still drop their temporary hold exactly once. Other output
fields are unspecified after failure; the production refresh/loss callers and
the scene observer already inspect them only on success. No publication pointer
escapes. The successful path returns its established result without testing the
copied endpoint a second time.

The only production change is in `lib/aes/aessnapshot.act`. Both outer UPDATE
transitions still refresh input eligibility, and populated inboxes still receive
the full latest sample. Capture replacement, MCTRL, notification, loss and
retirement semantics retain their existing implementation. There is no new
cache, compact record, ABI, kernel operation or drawing boundary.

## Focused measurements

IC1, commit `8ea50407`, froze the extended probe on the unchanged `41802444`
runtime. IC2 uses the same workload, observer, pinned optimized release compiler
and machine. Each cohort discards two warmups and measures eight repetitions.
Sweep costs include the four lookups, successful Drops and loop bookkeeping;
actual copy calls are observed separately at their emitted JSL and successor.

| Populated defaults | Sweep CPU before, ms | After, ms | Full copies before → after |
| --- | ---: | ---: | ---: |
| Zero | 0.907 | 0.622 | 4 → 0 |
| One | 1.153 | 0.832 | 4 → 1 |
| Two | 1.297 | 1.031 | 4 → 2 |
| Four | 1.581 | 1.469 | 4 → 4 |

The two-client sweep uses **20.5% less Task CPU**. The fully populated control
also improves, so the added early test causes no measured control regression.
The route size comes from emitted SIZEOF, rather than a new public layout.

| Paint-only BEGIN/END pair | Mean CPU before, ms | After, ms | Reduction |
| --- | ---: | ---: | ---: |
| Focused client | 9.368 | 9.188 | 1.9% |
| Other painting client | 9.784 | 9.450 | 3.4% |

Each pair still performs two input refreshes and no route reconstruction.
Default copies fall from eight to four, or 368 to 184 bytes. Both live-client
lookups per refresh succeed, including the unfocused client's window-zero
default. Input refresh itself includes endpoint holds, sample copying,
eligibility and notifications; route copying was only a small part of that
remaining work. The two-owner probe establishes no physical admission or
contention latency: it uses one caller with established physical readiness.

## Packaged viewer

The frozen previous package uses the same production sources as `41802444`.
Its idle observer matches the current observer exactly. For the loaded capture,
the only script difference is the unused idle startup-folder close branch;
ASTs match with that branch removed. The before-capture audit is retained in
the evidence. All ten APP binaries and the C image's segments match the rebuilt
package. Compiler, machine, ROM, document and work geometry are unchanged.

Each scene measures four page and four line actions. The CPU and completion
columns have different meanings: means describe viewer CPU, while medians
describe physical-key offer to IRQ-observed completed repaint.

| Scene/action | Mean viewer CPU before → after, ms | Repaint median before → after, ms |
| --- | ---: | ---: |
| Idle page | 439.071 → 436.191 | 1025.851 → 1063.645 |
| Idle line | 438.100 → 436.964 | 995.145 → 1007.523 |
| Counter/disk page | 481.135 → 478.235 | 1781.126 → 1844.849 |
| Counter/disk line | 472.639 → 471.917 | 1839.144 → 1777.739 |

Viewer CPU falls by **0.15–0.66%**. Repaint medians are mixed: three increase,
while the loaded line median decreases. This small change does not establish
consistent visible latency improvement. For example, mean idle page time rises
33.0 ms despite 2.9 ms less CPU; runnable off-CPU time rises 35.8 ms. The evidence
keeps CPU, IRQ, blocked, runnable and unclassified-prefix costs separate. Four
deterministic actions per operation do not establish latency tails.

Observed and untraced timings match exactly after a single recorded global
scheduler-clock origin alignment: zero for both new scene pairs and the old
idle pair, 35,568 cycles for the old loaded pair. All relative edges, gaps and
interrupt/switch/gateway counters match. Every repaint keeps 18 document rows,
20 text calls, one bar, 21 grants, 23 launches, five generic submissions and
31 fences. Retained-pixel scrolling and drawing units are unchanged.

All twelve new whole-work-area checkpoints match the independent oracle,
77,520 pixels each. Boundary no-op, exact warmed heap return, stack/domain
guards, ownership and EXIT pass. Counter advances and persisted disk result
bytes match. These are completed-repaint observations; scanout timing is
excluded and settled scanout pixels are checked separately.

The rebuilt package passes 30 ZIP checksums, boot/guide/licenses-only content
checks, all 69 recorded SYS file identities and nine on-disk APP identities.
OF816, matching pinned ROM, five-second standard shell/prime autoboot, writable
SYS and MD5/ARC/EDX plus notices are retained. QED was not selected.

## Validation and resource cost

Both native runs pass 838 assertions: the original routing/UPDATE/MCTRL cases,
empty output after populated storage, complete successful route values and hold
balances, a live client without a focused window, withdrawal while a reader
holds an endpoint, final-reader release and reuse with another endpoint/epoch.
The zero/one/two/four populated cohorts all return the expected hit counts.
Heap return, stack/domain guards, ownership and normal EXIT pass.

The optimized lock fixture passes 231 C and four native checks. The pointer
fixture passes 168 C, 25 capture-boundary and five native checks. The host suite
passes 702 tests with four existing historical-source skips. This is development
testing with unchanged layout and ABI; no raw matrix or release qualification
is inferred.

The Default routine grows from 361 to 385 upper-memory code bytes. Its fixed
frame remains eight bytes and local stack peak remains 20 bytes. Complete
eight-Task probe and twelve-Task demo bank-zero maps are compared in the
evidence: reserved growth is **zero bytes** for fixed services, root, kernel,
idle and each public Task, including guards, alignment and unused capacity.
Upper-memory and VRAM reservations are unchanged.

## Reproduction

```sh
python3 tools/test_aes_route_reuse.py --output build/input-copy-check
python3 tools/test_aes_server.py --suite locks --mode opt --output build/input-copy-locks
python3 tools/test_aes_server.py --suite pointer --mode opt --output build/input-copy-pointer
python3 -m unittest discover -s tests -p 'test_*.py'
python3 tools/build_demo.py --output build/input-copy-demo --gem-desktop --release-compiler
```

Use the existing `tools/measure_gui_baseline.py` with fresh observed and untraced
output directories for the idle scene and the unchanged
`build/gui-baseline/load` Counter/disk fixture. The evidence identifies the exact
packages, source/observer inputs, sample counts, CPU/IRQ/wait split, artifacts
and matching replay checks. Full hosted-system/hardware qualification and QED
remain outside this slice.
