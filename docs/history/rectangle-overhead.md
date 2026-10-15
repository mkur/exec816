# Rectangle overhead

[Plan](../plans/gem4xe/rectangle-overhead-plan.md) ·
[Measurements](../development/rectangle-overhead.json) ·
[Physical entry follow-up](../development/display-ownership-entry.json) ·
[Display contract](../reference/display.md)

## RP1: reserve actual drawing units

The presenter no longer reserves physical display access for an entire service
turn. Existing `GemDrawing*` entries protect pointer/caret/outline operations,
text and frame batches, widget callbacks, cache copies and completion retirement.
Each callback and its command list remain protected through the fence. Widget
continuations flush and clear strip redirection before releasing; borrowers do
not use their retained private VRAM strip. Native BUSY retains pending work;
the existing owner queue/wake retries it. Async launch retains the DMA pin and
Poll can retire it while a borrower waits. No kernel, scheduling or IRQ change.

The matching current parent uses the icon-cache package from `3ff76d7`, rather
than the older pre-merge measurement. Its untraced rectangle batch median is
24.4 ms. Passive captures measure 24.080 → 21.358 ms elapsed per rectangle;
presenter CPU falls 9.692 → 7.800 ms. The candidate capture observes no owner
entry/drop during these idle rectangle intervals: CPU-only service no longer
reserves the renderer. These are three batch averages, not latency percentiles.
Loaded results and final untraced comparison follow in RP5.

Development checks: 66 optimized arbitration assertions including nesting,
FIFO/BUSY retry, DMA pin and fault revocation; two renderer borrowers beside
native output/pointer work, 48 completed borrows, one asynchronous copy, zero
overlap and 2,788 checked pixels; quiescent and unquiesced fault cleanup. The
fixture now observes both async scroll and CopyStart (the current console uses
the latter). Its first run failed the obsolete scroll-only copy counter, with
pixels and ownership intact. Six passive-trace host tests pass. The packaged
rectangle run cancels later rows with Escape, closes normally, runs HELLO and
returns through EXIT with guards intact. No full qualification claim.

Reserved bank-zero delta: **0 fixed, 0 for each of eight public Tasks, 0 idle**,
including guards/alignment/spare capacity. Upper static data and VRAM reservations
are unchanged; linked executable bytes fall by 275. No stack capacity changes;
observed headroom above the interrupt reserve is at least 313 bytes for active
application Tasks, 1,427 for the presenter and 194 for idle in this capture.

## RP2: changed-only mouse snapshots

One presenter-owned `AESSTATE.mouseDirty` byte replaces unconditional all-client
publication. The state module holds it so inbox/window publication can invalidate
it without introducing cyclic module dependencies. Pointer/button samples,
release after capture, loss/recovery, registration, inbox open/close, focus,
scene visibility and outer UPDATE/MCTRL transitions invalidate it. Menu state
only invalidates on a changed value. Nested lock counts retain the existing
publication boundaries without recopying unchanged snapshots.

The ordinary idle trace improves 21.358 → 20.054 ms per rectangle. Refresh is
still called at synchronization boundaries, but its CPU drops 1.902 → 0.532 ms
per rectangle; actual per-client Snapshot calls drop 3.953 → 1.000. Presenter
CPU falls 7.800 → 6.818 ms. The remaining two-client publications correspond to
the existing outer Begin/End lock transitions, not idle service passes.

Development: 145 optimized pointer assertions pass, including new stationary
focus checks, nested UPDATE/MCTRL, queued handoff, capture/release, loss recovery
and window reopening. The normal packaged rectangle run, cancellation, HELLO,
guards and EXIT pass. The independent lock-queue fixture times out after 118
checks with no assertion failures on RP2, RP1 and the original `3ff76d7`
parent using the same C fixture. This pre-existing fixture limitation is not a
passing lock qualification. The repaired Counter baseline completes at 27.8 ms/rectangle,
with visible progress, normal app closure and EXIT.

Reserved bank-zero delta: **0 fixed, 0 per public Task, 0 idle**, including all
reserved capacity. Static upper RAM grows by **1 byte**; linked executable bytes
increase by 818. VRAM and all stack reservations are unchanged.

## RP3: direct rectangle bindings

Named `v_bar` and `vsf_color` now call the shared internal operations directly.
Generic parameter-block calls retain their count/handle checks and output
semantics without copying rectangle/control arrays into workstation scratch.
Rectangle normalization uses LONG coordinates and one user-clipped area feeds
both damage reporting and visible fragments. Covered changes are still reported;
physical fragments, cursor handling and completion remain synchronous.

The idle capture measures **3.809 → 3.320 ms CPU per `v_bar`** and
**9.699 → 8.790 ms benchmark Task CPU per rectangle**. Mean elapsed time is
20.091 ms versus 20.054 after RP2: this capture does not demonstrate an additional
end-to-end gain. The presenter executes more work in that scheduling phase
(7.759 versus 6.818 ms/rectangle). Final untraced batches follow in RP5.
One upload/submit and a mean of three solid records remain: one at even X and
five at odd X, 21/105 bytes, with the existing encoder unchanged.

Development checks use explicit named/PB single-pixel, reversed and clipped
pairs, wide signed endpoints, multi-client/private scratch preemption and
covered/exposed pixels. The VDI oracle was updated for the current snapped X,
11-row title/work offset and menu geometry. The added test originally used a
mutable points-array expression; Calypsi 5.18's emitted listing read the old
right coordinate instead of the just-written left coordinate. Explicit constant
case coordinates make the fixture inputs unambiguous; production drawing code
and compiler pins were not changed to accommodate this test construction.
The VDI fixture passes 421 assertions and all six pixel comparisons; the
existing hidden/partial/failed-paint cache fixture passes 220 assertions.
Six passive-trace host tests and normal package cancellation/EXIT also pass.

Reserved bank-zero delta: **0 fixed, 0 per public Task, 0 idle**. Static upper
RAM, VRAM and stack capacities are unchanged. Linked executable bytes grow by
354; direct bindings trade some code duplication for less caller work.

## RP4: measured UPDATE limit

The passive observer now also records Submit, PutMsg/GetMsg/Wait, dispatch,
eligibility, reply, snapshot and cache transition boundaries. No guest timing
instrumentation or production UPDATE change was added. Values below are per
rectangle, amortized over the unchanged four-rectangle UPDATE group.

| UPDATE component | CPU ms | Elapsed ms |
| --- | ---: | ---: |
| Both `wind_update` calls, inclusive | 1.651 | 9.841 |
| Caller preparation/result handling, excluding message primitives | 0.759 | — |
| Caller PutMsg/GetMsg/Wait, combined | 0.893 | — |
| Presenter request pump, inclusive | 2.183 | — |
| Intake/dispatch outside lock processing and reply | 0.205 | — |
| Lock eligibility | 0.030 | — |
| Begin/End window processing, inclusive | 0.846 | — |
| Drawing snapshot publication, within Begin | 0.272 | — |
| Cache BeginChange/EndChange, within window processing | 0.152 | — |
| Reply, within presenter pump | 0.505 | — |

Nested rows overlap and must not be added. The client spends 7.845 ms off CPU
inside the two UPDATE calls, including server execution; this is not hardware
BUSY time. PutMsg can switch Tasks before returning, and Wait sleeps until reply.
Their wall intervals therefore include execution elsewhere. The entire sample
also contains 5.576 ms/rectangle of presenter CPU outside the measured request
pump; changing small snapshot scans cannot remove all that service work.

No additional production edit is justified in this slice. Eligibility already
runs once per outer acquisition, and window Sync has a revision early return
(0.026 ms/rectangle). Begin must invalidate content/certification even when
nothing visible is drawn; End consumes completion and failure reports. The
existing scene revision does not establish that every caller window's drawing
snapshot, update count and paint epoch can be reused. Skipping publication
would need a new validity contract for at most 0.272 ms/rectangle in this trace.
The remaining message validation is outside this slice's selected window/lock
bookkeeping scope. A future measured service-loop or message-path change can
address larger costs independently, with input latency checks.

The six trace-parser host tests pass. RP3's 220 cache assertions cover the
unchanged hidden/partial/failure rules; RP1's mixed borrowing/native output and
RP2's 145 pointer/lock assertions cover the unchanged handoff semantics. The
standalone lock-queue timeout remains explicitly unqualified as described above.
Reserved bank-zero, code, upper RAM, VRAM and stack-capacity deltas are all zero.

## RP5: ordinary application and desktop results

All final checks boot the exact OF816 ZIP. The parent and candidate use the
same ROM hash, emulator binary, compiler pin, PAL/8× CPU/VBXE configuration,
accurate SIO and benchmark canvas/pointer. Per-process ROM registration IDs
vary; the actual ROM bytes match. No guest benchmark changes, priority changes,
larger UPDATE groups, hidden pointer or drawing-only substitute were used.

| Ordinary rectangles | Parent batch averages (ms/op) | Candidate batch averages (ms/op) | Median change |
| --- | --- | --- | --- |
| Idle desktop | 24.6, 24.4, 22.8 | 20.0, 20.0, 20.0 | 24.4 → **20.0**, 18.0% lower |
| Beside Counter | 28.0, 27.6, 27.8 | 22.8, 22.6, 22.6 | 27.8 → **22.6**, 18.7% lower |

Each batch contains 100 rectangles. Counter progresses visibly, later benchmark
rows cancel with Escape, the apps close normally, HELLO runs and EXIT restores
the OS. These are medians of batch averages, not individual-operation p95s.
The roughly 12 ms idle objective is **not reached**.

The passive matched-parent comparison explains the partial gain: DisplayEnter
falls **4.954 → 1.012 ms elapsed**, including a fall in off-Task time from
3.644 → 0.100 ms. `v_bar` falls 11.676 → 5.171 ms elapsed. However, amortized
UPDATE elapsed rises 7.166 → 9.841 ms while its caller CPU is nearly unchanged
(1.602 → 1.651 ms). Scheduling and service work have shifted into the exchanges;
the reduction in drawing admission does not translate one-for-one into complete
application throughput. The native request pump itself remains about 2.2 ms CPU
per rectangle. These inclusive intervals overlap.

Files observations use a new folder window with stock icons already cached:

| New Window milestone | Parent | Candidate |
| --- | ---: | ---: |
| Complete frame | 822.263 ms | 742.183 ms |
| Complete window | 1243.625 ms | 1143.336 ms |

This is one observation per build, sampled once per PAL frame, not a cold-boot
or p95 claim. The client paints once, does not redraw after completion, and an
explicit Refresh still paints exactly once. Closing the folder does not alter
uncovered desktop icon pixels. Icon/list selection matches a complete repaint;
unchanged summaries and pointer pixels stay stable. Shell/SYS focus restoration
preserves selection without client repaint or cache capture/patch. Boundary
cursor input does no repaint; keyboard scrolling paints once.

The small matched input cohort gives individual whole-region completion times:

| Input | Parent samples (ms) | Candidate samples (ms) |
| --- | --- | --- |
| Panel button beside live Counter | 80.3, 120.2 | 100.3, 80.3 |
| File menu opening | 200.6, 200.6 | 180.4, 180.6 |
| File → View switch | 220.5, 220.5 | 200.6, 200.6 |
| File row highlight | 60.1, 60.4 | 60.1, 60.1 |
| Repeated pointer File/View switches | 300.9, 280.9 | 300.9, 280.7 |

Two samples do not establish a latency distribution or a reliable button gain.
Warm repeated headings are essentially unchanged. Menu Escape restores the
preserved Files pixels without repaint. Counter advances two ticks/paints during
the candidate button cohort and its visible digits change. Independent complete
scene pixels, guards and normal EXIT pass. The Panel observer needed the same
compact-frame geometry correction as the VDI oracle; its initial old-geometry
comparison failed, not the repaired pixel check.

Development scope: focused optimized ownership, mixed rendering/fault, pointer,
VDI and cache fixtures; trace host tests; ordinary rectangle rows and the small
physical desktop cohorts above. The pre-existing standalone lock-queue timeout
remains an explicit limitation. No full hosted-system, hardware or HY4/PI4
qualification is claimed. Raw compiler matrices were not needed for unchanged
ABI/layout and kernel semantics.

Cumulative reservations: **0 bank-zero bytes fixed, 0 per public Task, 0 idle**,
including guards/alignment/spare capacity; **0 VRAM bytes** and no stack-capacity
changes. Upper static data grows by one byte to 13,529. Linked executable bytes
grow by 897 to 1,272,257. Final observed headroom above the interrupt reserve is
at least 210 bytes for application Tasks, 1,452 for the presenter, 117 for idle
and 991 for the kernel across these package runs; all guards remain intact.

The package is `build/rp5/demo/exec816-demo.zip`, SHA-256
`e147eb25f9a3b8d873998a33cb882bae1c232d3f99ad7833e13243f9d155425a`.
It contains OF816's five-second autoboot, matching system/work disks and ROM,
license notices, a short guide and checksums. It was built from `a6d8654` with
only host measurement tooling uncommitted, hence the `-dirty` banner; production
sources have not changed since RP3. Large logs/intermediates remain in `build/`.

Launch locally:

```sh
open /Users/michalkurcewicz/action/exec816-public/build/rp5/demo/launch-altirra.command
```

## Follow-up: five-object dialog

The unchanged complete five-row benchmark was run on the same archived parent
and RP5 packages, first idle and then beside Counter. Benchmark source hashes,
donor/adapters, compiler, emulator, ROM, machine settings, canvas and pointer
match. These runs reuse the packages above without rebuilding them. Raw results
are in `build/rp-dialog/{parent,candidate}/g4bench-{idle,counter}.json`; the
linked measurement record retains their hashes and dialog samples.

| Five-object dialog | Parent batches (ms/op) | RP5 batches (ms/op) | Median change |
| --- | --- | --- | --- |
| Idle desktop | 106, 108, 109 | 92.5, 93, 93 | 108 → **93**, 13.9% lower |
| Beside Counter | 133, 130, 131 | 111, 112, 113 | 131 → **112**, 14.5% lower |

One operation draws the complete five-object tree through `objc_draw`, with an
UPDATE pair, visibility checks and event polling for each dialog. Preparation,
warmup, report rendering and disk writes are outside the timed interval. This
is application throughput including scheduling, not a measurement of button
feedback or isolated blitter speed. The results are medians of three batch
averages, not p95s. The existing two-second calibration uses 20 dialogs per
batch for the parent and both Counter runs, and 40 for the faster idle candidate;
the same twenty-position sequence repeats. The PAL clock is 50 Hz.

The gain extends beyond rectangles: the presenter ownership and mouse snapshot
changes also serve object drawing. RP3's direct named `v_bar` binding is not
used by the timed dialog: `objc_draw` reaches `WidgetFill`/`GemWidgetFill`
directly. Object traversal, per-object/strip display borrowing, fills and text
remain, and the dialog has one UPDATE exchange per operation rather than
amortizing it over four rectangles. These code-path observations explain why
the workloads need not improve equally; these elapsed samples do not attribute
the saved time to individual functions. They also do not establish a matched
speed ratio against the original GEM4XE benchmark.

Development scope: all five rows completed in all four package runs; Counter
advanced during both loaded runs. Reports saved, apps closed normally, HELLO
ran and EXIT returned with no live Tasks and intact guards. No production code,
ABI, stack capacity, VRAM or bank-zero reservations changed in this follow-up
(0 fixed, 0 per public Task, 0 idle bank-zero bytes).

## Physical entry: trust the admitted caller

`DISPLAY.Enter` and `OwnerEnter` no longer call `EXEC.FindTask(NULL)` to
recheck the drawing caller's identity. Admission still retains the borrower
and lifetime owner. Using one's own live grant, and calling owner operations
only from the owner, are caller obligations. State/generation checks, FIFO
handoff, Forbid/Permit, DMA pins, revocation and fault handling are unchanged.
The C bindings and the separate short-unit preemption experiment are unchanged
by this follow-up.

The same optimized arbitration fixture runs before and after the change, with
eight successful uncontended root-Task acquisitions added to its existing
contention, nesting, DMA and fault cases. The obsolete foreign-caller rejection
assertion is removed. All **81 assertions** pass with intact guards, Task
ownership cleanup and OS restoration.

| Native operation | Before, mean CPU | After, mean CPU |
| --- | ---: | ---: |
| Enter | 0.706 ms | 0.146 ms |
| Leave | 0.147 ms | 0.149 ms |
| Enter + Leave | 0.852 ms | 0.295 ms |

This is a **65% reduction in native pair overhead** on the pinned PAL/8x
configuration. The eight baseline `FindTask` calls consume 4.387 ms CPU in
total; the candidate makes none inside borrower or owner entry. These native
routine measurements exclude the C/Action bridge, drawing and AES UPDATE;
they do not establish a new whole-dialog or UI latency result. Owner-entry
timings in the evidence mix successful, nested, BUSY and no-owner calls and
must not be read as an uncontended average.

The desktop-background observer previously broke at the removed lookup.
It now observes the drawing bridge through a test-only bank-zero trampoline
in existing diagnostic scratch. Observed runs add two JMLs per drawing call;
unobserved runs do not install it. Registers, flags and stack semantics are
preserved. This observation cost is separate from the native timings above.

The two native entry routines shrink by **214 code bytes**. Fixed bank-zero,
each public Task, idle, upper static data and VRAM reservation deltas are all
**zero**, including guards, alignment and unused reserved capacity. These are
development checks, not release or real-hardware qualification.

## Physical entry: packaged GUI follow-up

The refreshed OF816 demo is built from clean commit `9926859`. Its comparison
baseline is the earlier `50e4b16-dirty` drawing-preemption experiment package,
not RP5: both builds retain the same short-unit Forbid/Permit wrapper. The C
renderer ELF, G4BENCH and Desktop application bytes, system disk, compiler pin,
ROM, emulator configuration and memory reservations match. The measurements use
the same PAL/8x machine; raw traces and intermediates remain in `build/`.
The [physical-entry evidence](../development/display-ownership-entry.json)
records the hashes and commands under `gui_followup`.

The unchanged dialog benchmark uses the same canvas and stationary pointer.
Its existing baseline capture is compared with one new idle run, each covering
three measured batches and 120 dialogs:

| Dialog metric | Before | After |
| --- | ---: | ---: |
| Reported median of batch averages | 97 ms | 90 ms |
| Cycle-observed whole-operation mean | 97.296 ms | 90.339 ms |
| Caller CPU per operation | 51.423 ms | 46.749 ms |
| DisplayEnter + DisplayLeave CPU, including C bindings | 7.539 ms | 2.990 ms |
| `objc_draw` elapsed mean | 50.104 ms | 40.955 ms |
| Presenter CPU per operation | 28.739 ms | 27.659 ms |

The redundant identity lookup accounts for most of the caller CPU reduction:
ownership bookkeeping falls by 4.549 ms per dialog, about 60%. Rendering,
command construction and upload CPU are essentially unchanged. There are still
eight borrows, sixteen renderer fences, eight uploads/submissions and fourteen
solid fills per dialog. The longest known-held interval remains about 5.27 ms,
with no off-Task time in any of the 960 measured held intervals per build.
This preserves the scheduling experiment; it does not enlarge drawing batches.

The improvement reaches whole-operation time, but logical UPDATE still consumes
31.550 ms elapsed per dialog, including 23.521 ms away from the caller. Presenter
CPU is part of that off-Task execution and other off-Task intervals, not extra
time to add to the whole-operation result. These benchmark figures are not
button-feedback latency or input p95.

Files has one fresh New Window observation per package, with stock icons already
cached and the same `SYS:` listing. Completion is sampled once per PAL frame:

| New Window metric | Before | After |
| --- | ---: | ---: |
| Complete frame | 741.931 ms | 762.139 ms |
| Complete window | 1143.084 ms | 1123.131 ms |
| CPU inside the four frame calls | 45.644 ms | 43.061 ms |

Frame CPU is lower, but the visible completion times move by one PAL frame in
opposite directions. This small check does **not establish a reliable Files
opening-latency improvement**. The complete-frame milestone includes delays
before and between frame calls; it is not just frame-renderer execution time.
Both runs use four native frame calls, two C frame batches and 130 frame blitter
records. Initial content paints once, remains unchanged for the following 80
sampled frames, and explicit Refresh paints exactly once with matching pixels.
The warmup close leaves uncovered desktop icons unchanged.

All five benchmark rows complete, the report saves, disk HELLO runs, and normal
close/EXIT passes. Both Files runs also return normally. Guards remain intact
and no Tasks remain live after EXIT. Development checks only: no new loaded
benchmark, compiler suite, broad system matrix or hardware qualification ran.
Reserved bank-zero delta remains **0 fixed bytes, 0 per public Task and 0 idle
bytes**, including guards/alignment/spare capacity; stack and VRAM reservations
are unchanged.

The refreshed package is `build/display-entry-gui/demo/exec816-demo.zip`, SHA-256
`c43ffd5a75bb2b3362c1720088dd87d11dfced241cda8e4f41b0df1a1a591f0a`.
It includes OF816's five-second autoboot, matching disks and pinned ROM,
licenses, guide and verified checksums; build artifacts stay outside the ZIP.

```sh
open /Users/michalkurcewicz/action/exec816-public/build/display-entry-gui/demo/launch-altirra.command
```
