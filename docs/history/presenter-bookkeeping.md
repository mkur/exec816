# Presenter scheduling and bookkeeping

[Plan](../plans/gem4xe/presenter-bookkeeping-plan.md) · [History](README.md) ·
[Baseline](../development/presenter-bookkeeping-baseline.json) ·
[Final measurements](../development/presenter-bookkeeping.json)

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

## PB5: hidden placement before Show

`LAYERS.OrderBelow` places a layer immediately behind a live anchor and shares
`Order`'s private reorder routine. Hidden placement changes no visible regions
or damage; shown placement retains normal invalidation. AES prepares an opening
window below the menu bar before Show. The desktop keeps its bottom placement,
and Focus finds the chrome already ordered. No deferred scene transaction or
second region buffer is introduced.

The optimized emitted Layers fixture passes 1,077 assertions, 128 geometry cases
and 40 scene cases against the independent pixel/rebuild oracle. Coverage
includes hidden placement, shown reordering, no-op/self ordering, invalid IDs
and active-transaction exclusion, with intact guards and normal completion.
The host scene checks were updated for the four added scenarios. Evidence:
`build/presenter-bookkeeping/pb5-layers`. The final package observation below
checks the integrated AES open request and close exposure.

PB5 reserves **0 additional bank-zero bytes**: fixed 0, per public Task 0, idle 0,
including guards/alignment/unused capacity. There is no persistent upper-RAM or
VRAM increase. The Layers fixture leaves 968 bytes above the root Task's stack
floor; all Task and kernel stack reservations are unchanged. Production code
size and presenter stack observations are recorded with PB6's integrated build.

## PB6: final application observations

The final OF816 package contains the production sources committed through
`d29e55c`. Its build banner is `480bd6a-dirty`: it was built once while PB5 was
being checked, and its recorded source hashes match the committed production
tree. All final observations use that same archive, pinned compiler
`05c01f39`, pinned AltirraOS ROM and AltirraBridgeServer. The recorded machine is
800XL/PAL, native 65816 at x8, 64 KiB plus 63 upper banks, VBXE, accurate
generic56k disk timing, no SIO patch/burst/random delay. The JSON records exact
hashes, configuration, observations and limits.

Selected passive boundaries replace the analysis-only trace of every native
routine. CPU charges exclude other Tasks and native interrupts; readiness group
costs use interval unions so nested queries are not counted twice. These are
matched development observations, not hardware results or latency percentiles.

| Window observation | Before PB | After PB |
| --- | ---: | ---: |
| New Window first complete frame | 742.2 ms | 641.6 ms |
| New Window complete contents | 1063.0 ms | 982.7 ms |
| New Window presenter CPU | 430.5 ms | 357.5 ms |
| New Window readiness CPU | 67.7 ms | 35.8 ms |
| New Window visibility rebuilds | 3 | 2 |
| New Window input reads / empty | 38 / 36 | 4 / 2 |
| Uncached close completion | 461.3 ms | 401.2 ms |
| Uncached close presenter CPU | 243.8 ms | 192.0 ms |
| Uncached close readiness CPU | 60.3 ms | 26.7 ms |
| Uncached close input reads / empty | 24 / 22 | 5 / 3 |

The two final New Window rebuilds are dropdown dismissal and **one rebuild
inside AES open**, confirmed by nesting the passive markers. The prepared
placement eliminates the subsequent chrome reorder. Rebuild CPU falls
33.6 → 19.1 ms. Both window operations have zero native-dispatch identity
queries and zero settled idle turns. Before the first application BEGIN,
New Window takes 868.1 → 788.0 ms elapsed and 407.5 → 335.4 ms presenter CPU.
The uncached-close result recovers the approximately 401 ms result preceding
caller-local UPDATE.

The window observer verifies exact final pixels, four cold native frame batches,
two C frame-side calls, one initial content paint, no later changed frame, one
explicit Refresh and exact close exposure. Files icon/list selection and
Shell/SYS focus switching retain their cache restores: zero application paints,
captures or patches on the observed exposures. Summary and pointer coordinates
remain stable. The three settled icon-selection paint intervals are
124.9/124.0/125.2 ms, slightly above the prior approximately 122 ms; list selection
improves 174.7 → 160.3 ms and now completes BEGIN/END locally. All four selection
pairs are local. The no-op navigation case has no paint or UPDATE pair.

Three keyboard and three pointer File/View transitions cause **zero Files
repaints** and reuse all six saved backgrounds, with no background capture or
miss. Popup-content caching remains separate: keyboard transitions have three
popup misses/captures, pointer transitions have one miss and two cached popup
restores. The small transition cohort has medians 320.8/280.9 ms; it does not
establish a dropdown speedup against a newly matched parent capture.

| Repeated drawing, mean traced ms/op | Before PB | After PB |
| --- | ---: | ---: |
| Solid bars | 13.430 | 14.914 |
| Text, even X | 19.546 | 16.873 |
| Text, odd X | 20.073 | 17.410 |
| Clipped text | 22.720 | 22.056 |
| Five-object dialog | 70.430 | 67.195 |

Each row includes three measured batches. Dialog caller CPU stays near
46.7 → 46.9 ms/op while presenter CPU falls 11.3 → 8.4 ms/op. Complete local
UPDATE pairs rise 76/120 → 86/120 for dialogs, 17/150 → 97/150 for even text,
and 0/150 → 81/150 for odd text. Solid bars regress: local pairs fall
113/150 → 6/150 and presenter CPU rises 2.4 → 3.8 ms/op, while caller CPU is
slightly lower. The trace attributes this to more gate-busy RPC fallbacks,
not extra rectangle drawing. Shorter presenter work does not guarantee a local
BEGIN on every timing phase; the policy gate and ordinary preemption are intact.

The three-sample Counter plus console-output case progresses throughout input:
32 console-generation advances, increasing Counter ticks/paints, correct final
desktop pixels, then normal CAT cancellation and shutdown. Button median/max
change 140.1/220.5 → 120.5/180.1 ms. Pointer median is nearly unchanged
(100.1 → 100.3 ms), but the maximum rises 100.3 → 140.2 ms. This bounded cohort
does not establish tail-latency improvement or unchanged worst-case response.
The known Windows-menu focus issue under Counter remains separate; this case
uses the already established direct-title focus route.

### Remaining quiet-turn cost

The **<=2 ms CPU target remains open**. Five final window notification turns
start no transfer and cost 2.31–4.82 ms. Across the measured drawing batches,
634 such turns cost 2.28–5.39 ms, median 4.39 ms. A representative median turn
spends 1.72 ms in readiness queries, 1.64 ms in cache maintenance and 0.57 ms in
Collect. Existing damage and still-ineligible cache-candidate scans remain the
main costs. They do not create a polling loop: the settled window tails have
zero turns. Every successful outer END still notifies the presenter.

### Memory, checks and delivery

All six slices reserve **0 additional bank-zero bytes**: fixed 0, each public
Task 0, idle 0, including guards, alignment and unused capacity. Task pools,
runtime/phase reservations and bank-zero budgets compare equal to the baseline.
Persistent native data stays at 13,530 bytes; no VRAM reservation, queue, Task
or signal is added. Native code grows 2,298 bytes overall, including 1,613 bytes
for PB5's placement helpers. `OrderBelow` uses an 18-byte frame and 30-byte local
stack peak; its shared reorder helper uses 16/30 bytes. The presenter worker
uses a 64-byte frame, within the unchanged stack reservation.

Final package observations leave at least 1,462 bytes above the presenter's
stack floor; the kernel leaves 1,241 bytes untouched from its base, with zero
interrupt-reserve bytes touched. Guards remain intact and normal EXIT completes.
These are observed headroom figures, not worst-case stack bounds.

Development validation: 490 host tests pass with four historical skips; the
changed observer tests pass after the final reporting addition. Focused optimized
emitted coverage includes 24 gate assertions, 181 lock assertions, 145 pointer
assertions plus 21 boundary checks, 220 cache assertions with 31 physical phases,
and 1,077 Layers assertions with 128 geometry/40 scene cases. No full raw/optimized
qualification matrix or hardware qualification was run. Local captures are
under `build/presenter-bookkeeping/final-{frames,keyboard,menu,dialog,load}`.

The demo retains OF816, five-second autoboot, matching media, the pinned ROM,
license notices and checksums. The distribution archive contains only the
boot/runtime files, guide, licenses and checksums; traces/build intermediates
remain outside it. Launch from the repository root:

```sh
build/presenter-bookkeeping/demo/launch-altirra.command
```

Distribution: `build/presenter-bookkeeping/demo/exec816-demo.zip`.
