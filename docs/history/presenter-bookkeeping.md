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
reservation; the changed routines together shrink by 115 native code bytes.
