# Finishing short drawing units before switching Tasks

[History](README.md) · [Measurements](../development/drawing-preemption.json) ·
[Earlier cost analysis](dialog-drawing-batches.md) ·
[Display contract](../reference/display.md#delegated-renderer-access)

The experiment has been removed from live code at the user's request. Drawing
units retain normal Task preemption; physical display arbitration still protects
the renderer. The cheaper `Enter`/`OwnerEnter` identity handling remains.

The historical experiment below removed Task switches while a synchronous client
drawing unit held the display. It substantially shortened the longest observed
held interval, but complete dialogs became slightly slower. Its measurements and
packages are retained as evidence, not as the current scheduling contract.

## Scope

The trusted C `drawing_borrow` helper calls `Forbid` before `DisplayEnter` and
`Permit` after `DisplayLeave`. Failed admission also balances Permit. An inherited
Forbid count is preserved. Blocking admission Wait still allows the current
owner and other Tasks to run, restoring the borrower's exclusion on resumption.

Once admitted, the helper finishes its drawing, pointer/outline repair and
synchronous fences before releasing ownership and allowing a pending switch.
IRQ/NMI delivery continues. Callbacks must not wait or issue an AES RPC.
This uses the existing public Exec primitives; no priority, scheduler flag,
selector or kernel policy was added.

The scope is one existing client unit. The dialog still has eight units,
eight borrows, sixteen fences and eight uploads/submissions. Native presenter
units, asynchronous DMA, object traversal and the whole AES UPDATE interval
retain their scheduling behaviour. Generic DisplayEnter/Leave semantics have
not changed.

## Matched results

The unchanged G4BENCH application ran in the exact OF816 demo, at PAL/8x
65816 with VBXE, the same ROM, emulator and compiler pin as RP5. Canvas and
stationary pointer match the earlier captures. Each comparison covers three
batches: 120 dialogs idle and 60 beside Counter. Counter continued advancing.

| Metric | Idle, before → after | Beside Counter, before → after |
| --- | ---: | ---: |
| Reported dialog median | 93 → 97 ms | 112 → 115 ms |
| Cycle-observed whole-dialog mean | 93.087 → 97.296 ms | 112.325 → 115.379 ms |
| Longest known-held interval | **17.147 → 5.275 ms** | **22.814 → 6.309 ms** |
| Off-Task time while held, mean per dialog | **5.476 → 0 ms** | **7.244 → 0 ms** |
| Caller CPU per complete dialog | 50.183 → 51.423 ms | 51.477 → 52.619 ms |

The known-held interval runs from successful Enter return to Leave entry.
It excludes admission/release bookkeeping and is a lower bound on complete
physical ownership duration. All 960 idle and 480 loaded measured intervals
have zero off-Task time. These maxima are observations, not hard scheduling
deadlines; larger supported work units and bounded hardware-fault recovery can
take longer.

Other Tasks still need execution time. In the candidate, the borrowed helper
spends 7.004 ms per idle dialog and 10.409 ms per loaded dialog off-Task **after
Leave returns**. Another 0.167 ms occurs before Enter in the loaded case,
before the initial Forbid has taken effect. Enter/Leave themselves have no
off-Task time in these benchmark runs. The long pauses moved outside ownership;
they did not disappear from whole-operation time.

The two extra calls per unit also cost CPU. Caller time rises by approximately
1.24 ms idle and 1.14 ms loaded. The remaining elapsed increase is time away
from the caller and interrupt time. Logical UPDATE, visibility and service
bookkeeping remain. There is no reason to enlarge drawing batches on the
strength of this experiment alone.

## Focused development checks

- Host suite: 481 cases, four historical-source skips. After the trace-validator
  correction, eight trace tests and four batch-analysis tests passed.
- Optimized emitted borrower fixture: 268 assertions, 48 client units,
  2,788 exact pixels, 458 native units and five asynchronous copies;
  no overlapping renderer access. An injected Yield is deferred, interrupts
  run inside the units, inherited nesting is restored, and closed-grant
  admission failure leaves scheduling permitted. Queued admission still
  switches away while waiting.
- Hardware faults: quiescent timeout returns and cleans up; unquiesced timeout
  retains ownership and enters the expected `$FF93` reset-required park.
  Both have intact guards and no assertion failures.
- Exact packaged-image runs: normal boot, benchmark completion, disk HELLO,
  close/EXIT and ownership restoration passed. Stack guards, the aperture and
  retired startup storage remain intact.
- Two physical Panel presses beside visible Counter matched their button pixels;
  Counter ticked and repainted twice. Samples were 100.3 and 60.1 ms, versus
  the earlier 100.3 and 80.3 ms. This small cohort does not establish an input
  p95 or a general button-latency gain. The focused application-menu pixel and
  preserved-exposure check passed without Files repainting.

This is development evidence, not release or physical-hardware qualification.
Concurrent SIO deadline behaviour was not separately qualified.

The first debug-host compilation exceeded its 600-second limit before guest
execution. Final builds used the clean pinned **release host compiler**, matching
the baseline. The compiler pin did not change and no compiler test suite ran.

The loaded trace initially failed an offline clock check despite a passing guest
run. Its nominal `ticks/50` comparison ignored PAL's actual frame period and
possible preemption inside a clock-read call. The analyzer now checks the saved
tick count against observed VBIs bounded by both clock calls, allowing one
boundary tick for NMI entry versus clock publication. Regression cases cover
both effects. The same capture passed reanalysis; guest code, samples and CPU
attribution were unchanged by this tooling correction.

## Resources and package

Reserved bank-zero growth is **0 fixed bytes, 0 bytes for each of eight public
Task slots, and 0 idle bytes**, including existing guards/alignment/capacity.
Stack reservations, upper static storage and VRAM reservations are unchanged.
Linked executable size grows by **22 bytes**, to 1,272,279 bytes.

The experiment package is `build/drawing-preemption/demo/exec816-demo.zip`,
SHA-256 `55bb1c7e44bac46dca6c44aedfa3317a6449800a6a3f58b62480d38a2c685544`.
It includes OF816's five-second autoboot, matching disks and pinned ROM,
notices, guide and checksums. Build intermediates and traces remain outside it.

```sh
open /Users/michalkurcewicz/action/exec816-public/build/drawing-preemption/demo/launch-altirra.command
```

Rebuild with `tools/build_demo.py --gem-desktop --release-compiler`; capture with
`tools/trace_g4bench.py --bundle DIR --output DIR --load idle` and `--load counter`.
`tools/analyze_dialog_batches.py --trace DIR --output FILE` records both the
known-held interval and the helper's work before Enter and after Leave.

## Removal from live code

The outer Forbid/Permit pair was removed from `drawing_borrow`. Its callbacks
and synchronous fences again allow normal Task preemption while retaining
physical renderer ownership. Short arbitration critical sections, caller-supplied
Forbid nesting and the cheaper `Enter`/`OwnerEnter` identity contract remain.

The removal exposed a missed owner wake in the mixed-renderer fixture, reproduced
on the same emitted image. All 48 borrower units completed without overlap or
assertion failures, but the console worker and its pending writer remained
asleep with physical access free and the arbitration queue empty. The presenter
had deferred output after `Blocked()` without reaching `OwnerEnter()`, so it had
no queued acquisition to wake when the borrower released.

`Blocked()` now publishes an owner wake hint before rechecking a busy borrower.
The final read closes the release-before-subscription race; a release after
subscription supplies a signal that must remain pending until the owner's Wait.
The optimized emitted routine retains both physical-state reads around the hint
store. `Leave` consumes the hint under its existing Forbid section. A queued
owner handoff or quiescent fault already wakes the owner and clears the hint.
This is a notification using the existing owner signal, not a reservation:
an idle presenter cannot acquire the display merely by checking readiness.
Uncontended checks and releases add no kernel call, and the existing FIFO is
unchanged.

The hint adds one byte of upper-memory state. Reserved bank-zero growth remains
**0 fixed bytes, 0 per public Task and 0 idle bytes**, including guards, alignment
and unused capacity. Stack and VRAM reservations do not change.

Focused development checks pass: 483 host cases with four historical skips,
81 optimized native arbitration assertions, and 196 mixed-renderer assertions
covering 48 client units, 463 native units, an asynchronous copy and 2,788 exact
pixels. The trace observes Task switches and interrupts inside drawing units,
with zero overlapping renderer access. Caller Forbid nesting and failed-admission
cleanup pass. Quiescent and reset-required hardware faults pass with intact
guards; normal runs return through the OS boundary with no live Tasks. The
`retirement` section in the measurement record retains the inputs and results.

The previously packaged demos and timing tables above still contain the
experiment. This removal does not refresh those packages or claim new GUI timing.
