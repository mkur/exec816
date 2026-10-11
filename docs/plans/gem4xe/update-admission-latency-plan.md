# AES UPDATE admission latency implementation plan

[GEM plans](README.md) · [Viewer measurements](../../history/text-viewer-performance.md) ·
[AES contract](../../reference/aes.md) · [Display ownership](../../reference/display.md)

Status: UA1 is implemented and committed. UA2 has no accepted production
candidate: all nine trials miss at least one input, cancellation or stack gate.
UA3 retains the comparison evidence, but its acceptance/package gate remains
open. The production renderer, application code and memory map are restored to
TVP4. No gate or tolerance is waived. See the execution record for the retained
experimental patches and the measured cancellation phases.
Implement UA1–UA3 as small executable slices, checking and committing each
before continuing. Follow the
[execution record](../../history/update-admission-latency.md).

Shorten the waits surrounding `wind_update(BEG_UPDATE)` while preserving input
response and fair access to the desktop. Extend the existing viewer diagnostics,
identify the largest avoidable delay, and make one focused production change.
Application APIs, lock semantics and renderer bounds remain unchanged.

## Starting evidence

Use the completed TVP4 implementation at `bf02f88` and its
[retained evidence](../../development/text-viewer-performance.json). The tested
OF816 ZIP has SHA-256
`5366248c6df85bfddf793c345f3001bbb1dc8bc44ad46e140a4ec39b9c66191f`.
There is no new full baseline milestone. Preserve those records and reuse the
pinned machine, compiler, media, window geometry and offered input sequences.

| Current software milestone | Median | p95 |
| --- | ---: | ---: |
| Page completion | 942.6 ms | 964.7 ms |
| Page first changed band | 178.6 ms | 525.9 ms |
| Line completion | 940.5 ms | 960.4 ms |
| Line first changed band | 191.4 ms | 524.7 ms |
| Panel raise and action | 981.0 ms | 1222.9 ms |
| Panel gesture through completed repaint | 538.3 ms | 781.8 ms |

One traced page spends 282.8 ms on viewer CPU, 60.0 ms in interrupts, 433.9 ms
blocked off CPU and 110.5 ms runnable off CPU. Its second UPDATE acquisition
takes 343.3 ms; UPDATE holds range from 62.1 to 97.8 ms. These are individual
observations, not percentiles. The 544.4 ms off-CPU total is not all lock waiting,
and the 343.3 ms call does not by itself identify a slow lock owner.

The current path has two distinct forms of ownership. AES arbitrates the
logical UPDATE lock, publishes the visible-region snapshot and replies to the
caller. Each subsequent VDI unit separately enters the physical display arbiter.
The presenter may still hold physical access after replying, until `OwnerDrop`
or asynchronous completion retires it. Measure both boundaries.

## Slice sequence

| Slice | Deliverable | Gate |
| --- | --- | --- |
| UA1 | Explain UPDATE admission and handoff delays | Reconciled attribution and unchanged-image replay |
| UA2 | Remove the largest measured avoidable delay | Preserved ownership/fairness and improved measured latency |
| UA3 | Matched desktop comparison and OF816 package | Input/cancellation checks, pixels, resources and reported targets |

## UA1 Attribute the waits

Extend [`text_performance_trace.py`](../../../tools/text_performance_trace.py)
and [`measure_text_viewer.py`](../../../tools/measure_text_viewer.py), reusing the
existing scheduler and presenter work-unit observers from the
[latency diagnostics](../../guides/aes-latency-diagnostics.md). Trace only a few
representative page and loaded-Panel intervals, including the long acquisition;
retain the 256 MiB trace cap. Add focused host parser checks for the new
attribution, rather than another profiling framework.

For each BEGIN and matching END, correlate the request address, sequence and
client/Task identity through these boundaries:

1. Caller submission, presenter dequeue and lock request/queue insertion.
2. Eligibility changes, acquisition and visible-region snapshot publication.
3. Reply, caller readiness/selection and `wind_update` return.
4. First drawing `DisplayEnter`, physical admission and synchronous completion;
   track the presenter's `OwnerDrop` and any outstanding hardware pin separately.

Split BEGIN elapsed time into intake delay, time admitted but ineligible,
eligible-to-grant service delay, snapshot/reply work and caller resumption.
Overlay each interval with charged CPU, IRQ/NMI and runnable/blocked time for
the relevant Task; these are alternate views, not quantities to add together.
Track logical lock lifetime through presenter-side END processing separately
from application drawing time and the END call's own reply delay.

Inspect the actual blockers in
[`aeslocks.act`](../../../lib/aes/aeslocks.act): UPDATE/mouse owner, physical
button ownership, queue order, pending window mutation, busy scene, display
access, console DMA/batch state and drag outline. Record owner identity and
active operation (paint, console text/scroll, move/cache, window/menu mutation).
Preserve overlapping blockers; do not charge the same elapsed interval twice.
Where eligibility transitions cannot be resolved exactly, report observation
bounds instead of attributing the whole gap to a guessed cause.

Use passive checked emitted-instruction markers and existing state. Validate
call/return stack matching and relocated APP identity; missing markers fail
analysis. Do not add production polling or timing counters. Replay the selected
intervals without detailed tracing, requiring matching input, model, completion,
pixels and cleanup. Record the dominant cause and selected UA2 change before
editing production code.

Establish UA3's fixed-offset cancellation cases and their unchanged-image
results here as well. Append that workload after the existing timing cohorts
so it does not change their offered sequence.

Commit: `Attribute AES UPDATE admission and display handoff waits`.

## UA2 Shorten the measured delay

Make the smallest change supported by UA1. The main source locations are
[`aeshost.act`](../../../lib/aes/aeshost.act),
[`aescore.act`](../../../lib/aes/aescore.act),
[`deskhost.act`](../../../lib/desktop/deskhost.act) and
[`consoledriver.act`](../../../lib/console/consoledriver.act).

| Observed cause | Candidate change |
| --- | --- |
| Eligible request waits for a late settlement pass | Settle at the relevant existing completion boundary, before unrelated optional work or sleep. |
| Fresh native work delays an already queued lock | Correct the pending-acquisition gate or service ordering while letting admitted work retire. |
| Reply is followed by unnecessary physical-owner retention | Drop access at a safe completed-unit boundary, preserving nesting, DMA pins and borrower FIFO. |
| One admitted operation dominates the wait | Reduce its measured work within the existing transaction lifetime. |

These are alternatives to select from, not a list of speculative changes.
If several edits are necessary, separate and measure them before combining.
An application legitimately holding UPDATE, or a runnable Task awaiting CPU,
must remain visible in the result. Smaller presenter steps alone do not shorten
a scene token held across the entire repaint. Changing that token's lifetime
requires a separate damage/publication design and is outside this plan.

Preserve recursive UPDATE/MCTRL holds, try-acquire behavior, arrival order among
eligible callers, the existing owner-upgrade exception, and exit cleanup.
Publish the snapshot and ownership before replying/signaling. Keep pending-lock
gates that prevent continuous native output from starving applications, and
verify that repeated application locks still allow native controls/output to
advance. Settlement does not admit additional requests or renew turn budgets.

Retain four total native/AES admissions per turn, the late AES opportunity,
input-service boundaries and bounded console/paint work. A new handoff boundary
must be outside an active C callback and borrowed console view, with complete
scratch publication and correct scene/display ownership. Preserve DMA retirement,
overlay repair, fault recovery, ordinary signal waits and lost-wakeup handling.
Blocked work must sleep; avoid adding unconditional Yield, periodic wakeups or
longer interrupt/Forbid sections.

Keep the viewer's four-row bands and VDI's 32-glyph/16-row physical units, plus
the 64-record/8192-work blitter ceilings. Caller-owned pointers and admitted
geometry remain caller responsibilities; add no repeated validation layer.
Kernel priorities, new kernel services, timer/I/O changes, raster-copy scrolling
and a general redraw redesign are separate work.

Run the host suite and focused optimized emitted checks: AES locks; affected
presenter intake/order and pending-before-Wait cases; actual desktop exclusion
and resumed input; continuous console progress and cancellation. Reuse
`test_aes_server.py` (`locks` and affected `intake` cases),
`test_aes_desktop.py` and `test_console_fairness.py`. If physical arbitration
changes, add the affected `test_display_access.py` / `test_display_borrow.py`
cases, including queued grant retirement and fault cleanup. Select relevant
cases rather than rerunning every desktop suite.

Commit only a demonstrated latency improvement with preserved semantics.
Commit: `Shorten AES UPDATE admission at completed presenter work boundaries`
(adjust the title to the measured fix).

## UA3 Compare input response and package the result

Repeat the existing three-run cohorts: 30 completed page actions, 30 line
actions and 30 loaded Panel transactions. Preserve both raise/action and
gesture-only timing, first changed content, model and full-damage completion.
Add BEGIN/END distributions, total acquisition time per page and the longest
attributed waits; do not add component percentiles. Keep offered/completed
counts and any backlog or timeout. Detailed traces explain selected intervals;
unobserved runs supply the comparison distributions.

Compare every production candidate against both TVP4 and its immediate
predecessor. Retain the existing **20.05 ms** tolerance for IRQ-sampled UI
milestones. Determine any finer passive-marker tolerance on unchanged-image
replays in UA1, before candidate measurements. Require a repeatable reduction
in the identified avoidable wait and improved page median/p95, with no
reproducible worsening of first-content or Panel median/p95 beyond tolerance.
Do not excuse an intermediate input regression by comparing only with the
older, slower TVP1 image. Repeat an inconclusive affected pair with equal offered
work; preserve focus routing and distinguish required raise clicks from gestures.

Add a bounded cancellation comparison to the existing runner. Offer viewer
Escape/Stop and shell BREAK at preselected guest-clock offsets from an explicit
workload-start boundary, independently of repaint or Panel completion. Freeze
the offsets on the unchanged image in UA1, including active loading and console
output. Record delivery, observed stop/cancel, I/O retirement and return to idle,
along with work progress at the offer. Require correct document retention,
bounded completion and no reproducible latency regression. Report small case
sets individually; do not manufacture a p95 from a handful of cancellations.
The previous 1015.3 versus 282.4 ms CAT cleanup observations remain historical,
not this comparison's baseline.

Build with `tools/build_demo.py --gem-desktop`, retaining OF816's five-second
autoboot, startup applications, matching disks/ROM and notices. Check the exact
ZIP with the focused viewer and Files workflows through EXIT, plus the loaded
Panel/cancellation cases. Require pixel correctness after resize, cover/exposure
and model replacement during painting; guard/ownership/heap return; counter
progress; idle sleep; and restored OS state. Software completion remains
separate from scanout, and transient flicker remains a separate qualification.

Record results in `docs/history/update-admission-latency.md` and
`docs/development/update-admission-latency.json`, linking the existing TVP4
evidence instead of rewriting it. Retain hashes, selected work intervals,
original and candidate distributions, failed trials and resource costs. Update
this plan, the indexes and roadmap. The earlier twofold page objective remains
**640.8 ms median / 660.8 ms p95** against TVP1; report it as open if missed.
These development checks do not close HY4/PI4 or qualify real hardware.

Commit: `Record UPDATE admission latency and the tested OF816 desktop`.

## Resource and validation rules

Target **0 additional reserved bank-zero bytes fixed, 0 per public Task and
0 private idle** in every slice, including guards, alignment and unused capacity.
Reuse the existing presenter and storage. Report code, upper-RAM and VRAM deltas;
no new buffer or VRAM reservation is planned. Preserve 128 bytes of ordinary-task
headroom above the 256-byte floor; TVP4's measured minimum is 156 bytes. A needed
stack increase requires explicit accounting and focused checks, not a broad
refactor solely to preserve the current size.

Follow the [development testing tier](../../contributing/testing.md) and
[platform contract](../../reference/platform.md). Use the pinned compiler inputs;
small raw/optimized probes are needed only for changed ABI/layout/bridge behavior
or suspected compiler defects. Edit generated code through its generator and
leave the upstream GEM4XE checkout untouched. Preparing this plan changes no
executable code or memory reservations; content and local-link checks suffice.
