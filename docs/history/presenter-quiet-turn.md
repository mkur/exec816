# Presenter quiet turn implementation record

[Implementation plan](../plans/gem4xe/presenter-quiet-turn-plan.md) ·
[PB6 baseline](presenter-bookkeeping.md) ·
[Measurements](../development/presenter-quiet-turn.json)

## QT1 Conditional signal collection

The resident worker reuses its established Task pointer to check for pending
collection bits. Empty collection returns the bits already consumed by Wait;
nonempty collection still uses the public atomic SetSignal acknowledgement.
Request and unrelated bits retain their original handling. There is no change
to END notifications, the policy gate or preemption.

Development checks: 490 host tests passed with four historical skips; the
optimized production-routine signal probe passed 38 assertions, the real text
worker wake/stop/restart fixture passed 179, and the AES gate fixture passed 24.
The signal probe injects arrivals after both empty and nonempty hints and checks
that unrelated bits survive. It also verifies sixteen empty calls perform no
acknowledgement. Their combined elapsed time is 0.398 ms with fixture hooks;
this is not a whole-presenter performance result.

Local evidence: `build/presenter-quiet-turn/qt1-{signals,wake,gate}`. The signal
probe now extracts the production routine instead of retaining the old copied
implementation. The worker probe was updated for the current shared final Wait.

Reserved bank-zero delta: fixed **0 bytes**, each public Task **0 bytes**, idle
Task **0 bytes**, including guards, alignment and unused capacity. No persistent
state, VRAM or stack/DP reservation was added. Combined production code/data
and hosted stack measurements follow in QT4. No full qualification was run.

## QT2 Event-driven window cache inspection

The desktop cache now retains a six-bit candidate mask and the last observed
visibility rebuild. Native changes, completed manager paint and accepted AES
paint reports rearm the affected window; a visibility rebuild reconsiders the
window set. Each inspection consumes its bit, including rejected and already
attempted candidates. Common display/scene blocking leaves candidates pending.
Revision checks, repairs, popup precedence and the one-transfer limit remain.

Development checks: the optimized AES cache fixture passes 32 physical phases,
including full/partial repaint, hidden changes, frame recapture, move/exposure,
two-slot eviction, deletion/reuse and mixed-policy menu restoration. Four
settled states each receive twelve additional real presenter signals: none
causes another candidate geometry inspection. A full paint report without an
explicit changed rectangle produces a current image. Exact client/frame pixels,
unpinned settled storage, guards and normal return pass. The host suite again
passes 490 tests with four historical skips. Evidence:
`build/presenter-quiet-turn/qt2-cache`.

Reserved bank-zero delta: fixed **0 bytes**, each public Task **0 bytes**, idle
Task **0 bytes**. The five new upper-RAM state bytes consume four additional
allocated bytes because the candidate byte fills existing padding. No new VRAM,
DP or stack reservation. Emitted END bookkeeping grows by 111 code bytes with
its local stack peak unchanged at 70 bytes; combined timing follows in QT4.

## QT3 Layers-owned visible-damage readiness

Layers maintains one bit per slot, including the background, for manager damage
intersecting current visibility. Marking damage, rebuilding visibility, paint
retirement, deletion and saved-scene restoration update it. Already-runnable
layers need no new intersection scan when more damage is added. External repaint
obligations remain separate. The presenter's no-damage query now reads the word
after its existing paint-token and lock checks.

The intersection predicate moved into Layers. Mutating paths carry resolved slot
indices instead of searching again for every mark. No global Layers state was
added. The generated Scene and enclosing desktop Service layouts were rebuilt
together, and the current reference documents the read-only summary.

Development checks: 1,255 optimized Layers assertions with 128 geometry and 40
scene cases; an independent intersection oracle covers both sides of painting,
all nine bits, fully covered damage, later exposure, saved-image subtraction,
external handoff, failed completion and slot reuse. The small bank-crossing
layout/transaction probe passes 127 assertions in each of raw and optimized
modes. The 490-test host run found the expected desktop Service size change;
after correcting that assertion, all five affected desktop contract tests pass.
Generators and diff checks pass. Local evidence:
`build/presenter-quiet-turn/qt3-{layers,layout-raw,layout-opt}`.

Reserved bank-zero delta: fixed **0 bytes**, each public Task **0 bytes**, idle
Task **0 bytes**, including guards and unused capacity. Scene grows 9,184 to
9,186 bytes and desktop Service 18,716 to 18,718 bytes in upper RAM, including
alignment. No new per-Task state, VRAM or DP/stack reservation. The Layers/Regions
fixture reports 35,879 code bytes, no mutable globals and a maximum local stack
peak of 56 bytes. These fixture sizes are not a whole-demo code delta.

The integrated demo build found one remaining unqualified call to the moved
damage predicate. Commit `b797535` corrects that presenter call site; the final
package and observations below include it.

## QT4 Combined measurements

The production commits are `bf7e1d9`, `10ceeaa`, `2e70f8e` and `b797535`.
The final package uses the same compiler (`05c01f39`), ROM, emulator pin,
machine configuration, disk file set and disk timing as PB6. Applications and
native consumers were rebuilt together for Layers ABI 12. The configuration
remains 800XL/PAL, 65816 x8, 64 KiB plus 63 upper banks, VBXE and accurate
generic56k disk timing, without SIO patching, burst or random delays.

Passive markers change no guest code or storage. CPU is the existing
conservative Task charge, including kernel calls, scheduling/return overhead
and bus stalls; native IRQ/NMI bodies and other Tasks are accounted separately.
Nested readiness costs use interval unions. The no-transfer classifier is
unchanged: the quiet branch runs and Cache returns zero. Event-driven rechecks
remain in that population.

| No-transfer drawing-cohort turns | PB6 | QT4 |
| --- | ---: | ---: |
| Count | 634 | 639 |
| Minimum presenter CPU | 2.278 ms | 1.611 ms |
| Median presenter CPU | 4.394 ms | 1.757 ms |
| Maximum presenter CPU | 5.389 ms | 2.771 ms |
| Turns above 2 ms | 634 | 18 |

The median falls **60%**. A representative median turn spends 1.216 ms in
readiness checks, 0.063 ms in Cache and 0.015 ms in Collect; PB6 spent
1.723, 1.640 and 0.568 ms respectively. The no-damage query falls from about
0.56 to 0.05 ms. The 639 final no-transfer turns contain **zero SetSignal
calls, cache candidate inspections or damage-intersection scans**.

The **strict <=2 ms CPU target remains open**. The 18 longer benchmark turns
still carry scheduling/return charges within the observed routine boundaries;
the worst includes 1.159 ms in Offer, normally about 0.15 ms. No additional
cache or damage scan explains those tails. The separate window cohort has six
no-transfer turns at 1.65–2.75 ms, median 1.74 ms. Its longest turn does inspect
a newly armed cache candidate, consuming about 1.08 ms in Cache. Settled window
tails still have zero turns: no polling loop was introduced.

| Drawing workload, mean traced ms/op | PB6 | QT4 |
| --- | ---: | ---: |
| Solid bars | 14.914 | 11.651 |
| Text, even X | 16.873 | 15.014 |
| Text, odd X | 17.410 | 15.117 |
| Clipped text | 22.056 | 21.254 |
| Five-object dialog | 67.195 | 60.518 |

All rows retain three measured batches. Solid-bar complete local UPDATE pairs
recover **6/150 to 133/150**; even text reaches 150/150, odd text 148/150 and
dialogs 118/120 instead of 86/120. Dialog presenter CPU falls 8.43 to 2.71 ms/op,
while caller CPU changes 46.9 to 47.1 ms/op. Mean caller-local END CPU changes
5.61 to 5.63 ms for dialogs; the other rows change by about 0.03–0.18 ms.
The gain is not simply work transferred to END. The gate, every outer END wake
and ordinary preemption remain intact.

| Window observation | PB6 | QT4 |
| --- | ---: | ---: |
| New Window complete frame | 641.6 ms | 641.6 ms |
| New Window complete contents | 982.7 ms | 1002.6 ms |
| New Window presenter CPU | 357.5 ms | 365.5 ms |
| New Window readiness CPU | 35.8 ms | 29.1 ms |
| Uncached close completion | 401.2 ms | 361.2 ms |
| Uncached close presenter CPU | 192.0 ms | 165.1 ms |
| Uncached close readiness CPU | 26.7 ms | 12.1 ms |

New Window does **not** improve. It retains two visibility rebuilds, including
one inside prepared AES open, four native frame batches and two C frame-side
calls. Rebuild CPU increases 19.07 to 20.78 ms; mutation-side summary upkeep
is real work. Cache maintenance also rises 5.37 to 8.36 ms in that opening
interval. Before the first application BEGIN, presenter CPU is almost unchanged
at 335.4 versus 335.9 ms. These savings target repeated settled queries rather
than the initial drawing path. Exact final pixels, one initial content paint,
one explicit Refresh, unchanged settled pixels and exact close exposure pass.

Files icon selection remains local and preserves its summary and pointer
position, but takes about 130 ms versus 124–125 ms. Caller drawing CPU remains
about 99 ms; the increase is off-task time. List selection improves 160.3 to
147.3 ms. The no-op case has no paint or UPDATE pair. Shell/Files exposures use
cache restores with zero application paints, captures or patches. One sampled
list-selection frame contains a temporary pointer-image change; final pixels
and coordinates are correct. This does not establish flicker elimination.

Three keyboard and three pointer File/View switches cause zero Files repaints,
six saved-background restores and no background captures or misses. Popup
content keeps the same three keyboard misses, one pointer miss and two pointer
hits. Median response is effectively unchanged at about 321/281 ms. The
keyboard maximum rises one PAL frame, 361 to 381 ms; these small cohorts do
not establish percentiles.

With Counter and sustained CAT output, the three button samples have median/max
100.3/120.3 ms, versus 120.5/180.1 ms in PB6. Pointer median stays near 100.3 ms
and maximum changes 140.2 to 100.4 ms. Counter ticks/paints progress and console
generation advances 34 times, followed by normal CAT cancellation and EXIT.
The WORK load bytes match PB6. The established direct-title focus route avoids
the separate known Windows-menu issue under Counter. This is a bounded progress
check, not a throughput or tail-latency qualification.

The final New Window/close and Files selection/focus runs were repeated because
opening and icon selection showed small regressions. Both repeats reproduce
the recorded timings, call counts and pixel/preservation observations exactly;
guards remain intact and EXIT completes normally. Evidence is in
`build/presenter-quiet-turn/repeat-{frames,keyboard}`. No other cohorts were
repeated and the existing PB6 baseline was reused.

### Memory, validation and delivery

Every slice reserves **0 additional bank-zero bytes**: fixed 0, each public
Task 0 and idle 0, counting guards, alignment and unused capacity. The generated
memory manifest matches PB6 exactly. No Task, stack/DP reservation, signal,
queue, timer or VRAM reservation was added. QT4 adds only passive host markers
and records.

Integrated native code grows 1,082,683 to 1,085,814 bytes (**+3,131**). Native
data entries total 13,530 to 13,535 bytes; the new cache globals occupy four
additional placed bytes because one byte fills existing alignment padding.
The desktop Service layout grows by the two-byte Scene field. The END
routine retains its 70-byte local stack peak. Final package runs leave at least
1,469 bytes above the presenter's stack floor and 1,237 bytes untouched from
the kernel stack base, with zero interrupt-reserve use. These are observations,
not worst-case stack bounds. All guards are intact and all runs finish with
zero live Tasks.

Development validation comprises 490 host tests (four historical skips), the
focused emitted checks recorded for QT1–QT3, and the packaged frame, Files,
menu, drawing and loaded-input runs. The full qualification matrix was not run.
Evidence is under `build/presenter-quiet-turn/qt*` and
`build/presenter-quiet-turn/final-{frames,keyboard,menu,dialog,load}`.

The final ZIP includes OF816, five-second autoboot, matching media, the pinned
ROM and license notices. All 22 distribution checksums were verified. Traces,
manifests and build intermediates stay outside the archive. Launch from the
repository root:

```sh
build/presenter-quiet-turn/demo/launch-altirra.command
```

Distribution: `build/presenter-quiet-turn/demo/exec816-demo.zip`.
SHA-256: `2f3e94b4f3bb3e166638a6d40067475b5d7756adbd80e327ebdb25a8eac96408`.
