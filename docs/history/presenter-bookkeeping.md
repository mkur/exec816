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
