# Presenter scheduling and bookkeeping

[Plan](../plans/gem4xe/presenter-bookkeeping-plan.md) · [History](README.md) ·
[Baseline](../development/presenter-bookkeeping-baseline.json)

## PB1: trusted drawing dispatch

The shared bitmap packet is presenter-only. All production drawing calls come
from the resident worker's display, desktop paint, pointer or cache paths;
fixture drawing hooks also execute at worker boundaries. Startup retains the
worker/lifetime check. Dispatch no longer calls `FindTask(NULL)` for each
operation, while binding, failure, status and asynchronous completion checks
remain intact.

The optimized emitted `Run` contains no task lookup and shrinks from 716 to
601 bytes. The exact OF816 package passes the close/New Window observer:
unchanged final pixels, one initial application paint, one explicit Refresh,
cursor/cache-copy completion and normal EXIT. One PAL-sampled observation gives
frame completion 742.2 → 701.8 ms, complete window 1063.0 → 1083.0 ms and close
461.3 → 461.3 ms. These do not establish a whole-window latency improvement.
Raw evidence: `build/presenter-bookkeeping/pb1-frames`.
This is development coverage, not hosted-system or hardware qualification.

PB1 reserves **0 additional bank-zero bytes**: fixed 0, per public Task 0,
idle 0, including guards, alignment and unused capacity. No upper-RAM state,
VRAM allocation, Task, signal or stack reservation is added.

## PB2: readiness queries

Menu, input and widget queries stop at the first decisive condition. Paint
queries share the damage scan after checking lifetime/display readiness, and the
worker reuses a scheduling result only across adjacent queries. Cache startup
invalidates that hint. These hints never authorize a drawing operation; producers'
signal bits survive the final Wait, and local BEGIN still checks queued requests.

The matched optimized package reduces close presenter CPU from 243.8 to 201.9 ms
and observed close completion from 461.3 to 400.9 ms. Menu readiness calls fall
40 → 24 (12.5 → 3.6 ms); input readiness falls 34 → 21 (21.4 → 7.4 ms).
New Window remains 1063.0 ms, with presenter CPU 430.5 → 424.7 ms; its first frame
completes in 702.0 ms. Both have zero settled idle turns, unchanged final pixels,
one initial content paint and normal EXIT. One observed notification turn costs
2.19 ms CPU. These small samples are not percentile measurements.

Development checks: 24 emitted gate assertions; 181 optimized lock assertions,
zero failures, intact guards and cleanup; 489 host tests, four historical skips.
The initial lock build timed out in the debug host compiler; the same frozen
PB2 sources passed with the pinned release compiler. Artifacts are under
`build/presenter-bookkeeping/pb2-frames`, `pb2-gate` and `pb2-locks`.

PB2 adds **0 fixed, 0 per public Task and 0 idle reserved bank-zero bytes**,
including guards/alignment/unused capacity. There is no persistent state or VRAM
increase. The worker's used frame grows 62 → 64 bytes, within its unchanged
reservation; the complete native image shrinks by 117 code bytes.

## PB3: real input notifications

Active input boundaries read the registered presenter's signal bit as a hint and
call `SetSignal` only when it is set. Service retains its sixteen-record budget,
continues a nonempty drain, and independently consumes eligible AES replay.
The worker no longer submits Collect's input bit twice in one turn. Neither an
empty read nor a false hint clears an asynchronously delivered signal.

The optimized pointer fixture passes 21 added boundary assertions: no reads at
unchanged boundaries, arrival after the hint, arrival during drain, arrival after
empty before Wait, budget continuation and replay after mouse-control release.
The controlled sequence consumes 24 fresh records with 24 acceleration calls;
replay does not apply acceleration again. The existing pointer/button ownership,
loss and MCTRL cases also pass, with normal cleanup and intact guards.
Its private synthetic command now counts as pending fixture work, preventing the
AES-only idle shortcut from skipping the test producer. Production scheduling
has no knowledge of that command. Evidence: `build/presenter-bookkeeping/pb3-pointer`.

PB3 adds **0 fixed, 0 per public Task and 0 idle reserved bank-zero bytes**,
including guards/alignment/unused capacity. There is no persistent state, signal,
Task or VRAM increase. The new boundary uses temporary received bits and borrowed
service/owner pointers on the unchanged presenter stack. Production emitted sizes
are recorded with the following integrated package; fixture-only counters and
injection hooks are absent from it.

## PB4: idle cache maintenance

Maintenance first checks the existing repair slots, popup attempt and window
revisions. It only resolves a patch's owner for a ready slot. The settled worker
reuses its scheduling hint if maintenance starts no transfer; a started transfer
forces a fresh scheduling decision. Physical display, scene, pixel validity and
revision checks still precede copying. Every outer END notification remains.

Development checks: the optimized cache fixture passes 220 assertions and all
31 physical phases, including hidden edits, small patches, newly visible sources,
frame-inclusive restores and mixed-owner dropdowns. The packaged window observer
passes exact pixels, exposure, explicit Refresh and shutdown. New Window falls
to 1022.8 ms elapsed and 386.6 ms presenter CPU; close is 401.2/191.6 ms.
New Window input reads fall from 38 (36 empty) to four (two empty); close falls
24 (22 empty) to five (three empty). Both settled observation tails have zero
presenter turns. Evidence: `build/presenter-bookkeeping/pb4-cache` and `pb4-frames`.

The <=2 ms notification target is **still open**: four observed no-transfer
turns cost 2.31–3.75 ms CPU. In the longer cases cache maintenance still checks
an unattempted candidate (about 1.03 ms), but starts no transfer. Do not turn
that candidate into an idle polling loop or change the preservation contract.
Final dialog observations will measure this under repeated UPDATE activity.

PB4 reserves **0 additional bank-zero bytes**: fixed 0, per public Task 0,
idle 0, including guards/alignment/unused capacity. No persistent upper state,
VRAM, signal or Task is added. Cache's used frame grows 34 → 36 bytes; the worker
remains at 64. PB3's production Boundary is 309 native bytes with a 20-byte frame
and 32-byte local stack peak. PB3+PB4 together add 917 native code bytes; stack
reservations and guards remain unchanged.
