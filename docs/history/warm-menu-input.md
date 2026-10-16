# Warm menu input

[Implementation plan](../plans/gem4xe/warm-menu-input-plan.md) ·
[Starting analysis](warm-menu-bookkeeping-analysis.md)

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
optimized AES-menu fixture. The latter covers seven pixel phases, title
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

WI2 will record the matched production measurements and demo package here.
