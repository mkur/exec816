# Warm menu input

[Implementation plan](../plans/gem4xe/warm-menu-input-plan.md) ·
[Starting analysis](warm-menu-bookkeeping-analysis.md) ·
[Measurements](../development/warm-menu-input.json)

## WI1 Same-turn advancement and empty paint selection

`CONSOLEINPUT.Service` advances menus once after a bounded drain that consumed
events. It records the retained-input hint first, while a newly requested
heading still blocks input. This preserves queued keys if the advancement
clears that block. Empty/blocked drains add no advancement attempt; pointer,
widget, drag and focus ordering stays unchanged.

`DESKPAINT.Pump` returns before candidate selection when the Layers visible-damage
summary is empty and no paint token is active. Active paint continuation and
retirement still run. No damage flag, quota or synchronization protocol was
added.

Development checks pass: nine focused host observer/accounting checks and the
optimized AES-menu fixture (321 AES checks, zero failures, four native checks).
The latter covers seven pixel phases, title
continuation/failure, cached replacement, queued input injected into both copy
phases, Escape/loss/outside clicks, ordinary-paint fairness, native menus and
cleanup. Artifacts: `build/warm-menu-input/wi1-menus`, with adjacent host and
fixture logs. No raw or release qualification matrix ran.

The two emitted routines grow by 73 bytes combined. `CONSOLEINPUT.Service`'s
fixed frame grows 12 → 14 bytes (local stack peak 18 → 20); `DESKPAINT.Pump`
stays at a 52-byte fixed frame (local peak 66). These are local allocations,
not whole-call-chain bounds. Reserved bank-zero delta is **0 fixed, 0 per
public Task, 0 idle bytes**, including guards, alignment and unused capacity.
Scene, DP, stack, VRAM and upper-memory reservations are unchanged.

## WI2 Matched production measurements

The clean `426f3f8a` package uses the same compiler revision/executable, emulator,
ROM bytes and PAL/65816x8/VBXE/63-bank configuration as the preserved CG3
baseline. The original passive observer and all 36 actions are unchanged.
ROM-path-derived firmware identifiers are the only machine-setting differences.
All transfer counters match; no timed action repaints Files or performs disk I/O.

Each complete keyboard switch reaches menu advancement before the next policy
offer. The intervening offer and empty paint call are gone:

| Keyboard sample | Key return → advancement, before | After |
| --- | ---: | ---: |
| 0 | 7.008 ms | 0.084 ms |
| 1 | 7.916 ms | 0.083 ms |
| 2 | 7.007 ms | 0.133 ms |

The last after-sample includes 0.043 ms of interrupt time. All three have zero
off-presenter time in this interval. The representative old empty paint call
cost 1.613 ms CPU and lay **inside** the old advancement delay; do not add those
savings. Across the historical sampled windows, empty-return paint calls now
cost at most 0.040 ms, versus 1.644 ms before. Those windows have different
completion endpoints in some actions, so their aggregate cost is not a matched
per-operation saving.

Three-sample medians, with the same endpoint for each before/after pair:

| Action and endpoint | Elapsed before → after | Presenter CPU before → after |
| --- | ---: | ---: |
| Cached opening, historical sampled area | 140.454 → 120.244 ms | 84.118 → 78.899 ms |
| Highlight | 60.122 → 60.123 ms | 25.561 → 17.943 ms |
| File → View, historical sampled area | 100.288 → 100.288 ms | 65.074 → 59.390 ms |
| Dismiss | 100.288 → 100.288 ms | 64.324 → 58.607 ms |
| Keyboard, complete popup and headings | 100.288 → 100.288 ms | 66.378 → 60.274 ms |
| Pointer burst, complete popup and headings | 140.454 → 140.203 ms | 95.633 → 96.422 ms |

Keyboard CPU through title retirement falls **59.234 → 53.089 ms**; CPU after
retirement remains about **7.14 → 7.18 ms**. Median title retirement advances
**78.124 → 71.431 ms** from the stimulus. This is a real reduction in foreground
work, but the complete pixels still fall in the same roughly **80–100 ms**
last-nonmatch/first-match bracket. Do not claim a complete-switch frame gain.
The roughly 20 ms opening improvement uses the historical cropped endpoint,
which excludes headings and top popup rows. Three observations do not establish
p95 or a universal latency bound.

Pointer behavior remains comparable. Its route already advanced in the input
turn; these changes target keyboard ordering. In the third pointer sample the
heading crossing occurs 10.7 ms later after the stimulus, increasing total CPU
before crossing. CPU from crossing to complete feedback is 72.989 → 72.235 ms
in that pair; its response bracket is 88.075–108.032 → 77.415–97.372 ms. Retain
the individual crossing and frame samples rather than treating the whole
stimulus CPU increase as a popup-rendering regression or claiming a general
pointer improvement. Native controls remain in their previous sampled response
ranges. The uncached Desk popup still takes about 181 ms at its historical
endpoint; visibility rebuilding and renderer work were not changed here.

For the representative complete keyboard switch, the saved-popup scene commit
still consumes **16.470 → 16.472 ms CPU**. That remains a separate potential
follow-up. The new code removes input-turn delay and empty selection work;
it does not make that commit optional.

## Checks, resources and package

The production trace passes Counter progress during 30 application and 30
native highlights, normal EXIT, zero-live-Task cleanup and intact guards.
OF816 autoboot remains 249 PAL frames. All 22 archive checksums verify; build
intermediates and measurements stay outside the ZIP. This is development
coverage, with the WI1 fixture above; no raw or release/hardware qualification
matrix ran.

Native Action code grows **1,095,444 → 1,095,517 bytes** (+73), and native data
stays 13,544 bytes. C text/data/BSS stay **222,330 / 20,773 / 23 bytes**. The
memory reservation manifest is byte-for-byte unchanged: **0 fixed bank-zero
bytes, 0 per public Task, 0 idle**, including guards, alignment and unused
capacity. No Scene, DP, stack, VRAM or upper-memory reservation grows.

Observed presenter stack use changes **835 → 838 of 2,560 bytes**, leaving
1,466 above the floor. Kernel use changes 293 → 295 of 1,536; idle stays
129/512. These workload observations are not whole-program stack bounds.

Artifacts:

- `build/warm-menu-input/demo/exec816-demo.zip`
- `build/warm-menu-input/demo/launch-altirra.command`
- `build/warm-menu-input/menus` (passive development capture)

The ZIP includes OF816 boot, matching disks, pinned ROM, guide, notices and
checksums. SHA-256:
`141353a19a6b88a3506932294c7ee2cf145e073ad01770e65435f1d9cbfe117e`.

Launch from the repository:

```sh
./build/warm-menu-input/demo/launch-altirra.command
```
