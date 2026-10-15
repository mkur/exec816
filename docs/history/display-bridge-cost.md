# Physical display C/Action bridge cost

[History index](README.md) · [Display contract](../reference/display.md) ·
[Machine-readable evidence](../development/display-bridge-cost.json)

The remaining bridge costs about **35 microseconds per client ownership call**.
An uncontended Enter/Leave pair costs **0.365 ms CPU**, of which **0.070 ms
(19.2%)** is C/Action bridging and **0.295 ms** is native ownership work.

This measures the optimized code corresponding to `8b39fc8`, after removing the
short-unit preemption experiment and fixing the missed presenter wake. The
redundant caller-identity lookups remain removed. Production code is unchanged
by this measurement.

## Client ownership

The existing mixed-renderer fixture executes 48 successful drawing borrows from
two C Tasks beside native console/pointer work. Of these, 40 admissions never
call Wait and 32 releases send no wake signal. There are **29 matched pairs**
meeting both conditions. Failed admission and contended paths are recorded
separately.

All table values are mean charged CPU in microseconds:

| Layer | Enter, 40 uncontended calls | Leave, 32 releases without a wake | Matched pair, 29 pairs |
| --- | ---: | ---: | ---: |
| C binding and argument packet | 10.966 | 11.022 | 22.052 |
| Assembly marshalling and dispatch | 12.899 | 12.520 | 25.598 |
| Action wrapper | 11.318 | 11.053 | 22.300 |
| **Bridge subtotal** | **35.182** | **34.595** | **69.949** |
| Native ownership | 145.379 | 149.880 | 295.142 |
| **Total** | **180.561** | **184.475** | **365.091** |

The pair column uses the same 29 acquisitions and releases, so it is not the
sum of the two independently selected call means. Pair medians are **366.165 us
total** and **68.863 us bridge**. The bridge mean across all 48 successful pairs,
including contention, is similar at **70.163 us**. Waiting and wake/queue work
account for the long ownership calls; they do not belong to the bridge.

The C binding constructs the six-byte argument packet and its pointer, computes
the table offset and restores its stack. `_DisplayCall` aligns the stack, copies
arguments into the native calling convention, dispatches through the bound
table and restores the C stack. `CDisplayEnter`/`CDisplayLeave` then narrow the
pointer and call the native routine. Their generated code includes normal stack
bounds checks, argument copying and another frame. These wrappers do not repeat
a caller-identity lookup.

## Presenter calls

The presenter uses the same assembly dispatcher. `DisplayOwnerEnter` binds
directly to the native routine, so it has no intermediate Action wrapper.

| Successful OwnerEnter path | Calls | Total CPU | Bridge CPU | Native CPU |
| --- | ---: | ---: | ---: | ---: |
| No delegated clients | 342 | 37.924 us | 25.824 us | 12.100 us |
| Delegated clients present | 156 | 171.126 us | 29.825 us | 141.301 us |

Bridging dominates the very short owner-only path. With borrowers admitted,
native arbitration costs more. OwnerEnd also traverses the bridge; its 497
successful calls average **31.291 us bridge CPU**. These calls mix delegate
counts and DMA states, so their total time is not a single uncontended benchmark.

## Implication

For the existing eight-borrow dialog, the measured client bridge represents
about **0.560 ms CPU per dialog**. This is an upper bound from removing the
entire bridge, not a predicted speedup: specialized bindings would still need
some ABI conversion and calls. A thin Enter/Leave binding could remove packet
construction and the extra Action wrapper, but cannot remove the native
arbitration cost by itself. Native ownership remains the larger part of this
path; AES UPDATE messaging and rendering are outside these measurements.

No new whole-dialog timing, Files opening latency or input p95 is claimed.
The previously packaged GUI benchmark still predates the preemption removal.

## Method and checks

`tools/measure_display_bridge.py` replays the existing optimized display-borrow
image and adds passive emulator PC observations. It changes no guest bytes.
Boundaries come from linked C listings and decoded native instructions; returns
match the full stack pointer and Task direct page, including tail calls.
Each layer is the exclusive difference between nested spans of the **same
invocation**, including their return instructions. The outer caller's JSL and
argument preparation are outside the public-entry measurement.

The existing scheduler timeline separates charged Task CPU, native interrupt
time and time running another Task. Charged CPU uses the same conservative
interrupt boundary convention as the GUI traces. Successful admissions calling
Wait and releases calling Signal are kept separate from the uncontended group.

Inputs are the pinned Action compiler, Calypsi 5.18, dedicated AltirraOS ROM,
PAL/8x 65816, VBXE and 63 high banks; exact hashes and configuration are in the
evidence. The fixture passes 196 assertions, 48 borrower units, 463 native
units, one asynchronous copy and 2,788 exact pixels with zero overlapping
renderer access. Normal OS return, intact guards and zero live Tasks pass.
The host suite passes 487 tests with four historical-source skips, including
focused accounting checks for nested CPU/interrupt/wait attribution and pairs.

This is development evidence. There is no compiler rebuild, demo refresh, full
qualification matrix or real-hardware qualification. Reserved bank-zero delta
is **0 fixed bytes, 0 per public Task and 0 idle bytes**, including guards,
alignment and unused capacity. Upper RAM, stack and VRAM reservations are
unchanged.

Reproduce using the existing optimized fixture (or first build it with
`tools/test_display_borrow.py` and the pinned release host compiler):

```sh
python3 tools/measure_display_bridge.py \
  --from-build build/drawing-preemption-removal/fixed/borrow \
  --output build/display-bridge-cost
```

Add `--replay` to reanalyze the saved capture without running the guest again.
Raw spans, the trace and fixture reports stay in the development directory.
