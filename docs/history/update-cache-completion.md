# END_UPDATE cache completion

[GEM plans](../plans/gem4xe/README.md) ·
[Plan](../plans/gem4xe/update-cache-completion-plan.md) ·
[Design](../plans/gem4xe/update-snapshot-reuse-design.md#end_update-cache-completion-addendum) ·
[Previous UPDATE work](update-snapshot-reuse.md)

## EC0 Baseline and regressions

The [EC0 evidence](../development/update-cache-completion-ec0.json) records
738 native assertions, restored heap/ownership and intact guards.

The native snapshot fixture now calls the real `DESKCACHE.EndChange` in fifteen
controlled cohorts, with two warmups and eight measured calls each. It covers
empty and unrelated valid/invalid/pinned slots; either slot and both matching;
held, ready and absent repairs; empty and odd-edged changes; discarded bases,
missing pixels, failed completion and accumulated repairs. Setup uses the cache
lifecycle operations and releases simulated DMA before replacement.

Misses compare every byte of the desktop service, including the scene, windows,
both slots and repairs, and check the discard counter. Matching cases check
transitions and exact expanded repair bounds. The fixture also checks scoped
END for a hidden/iconified owner and verifies that a successful no-slot paint
still publishes readiness, consumes reports and sets a capture candidate.
The existing freshness oracle continues to check all 22 geometry observations.

The real-client cache and lock fixtures cover retained pixels, eviction,
ordinary/scoped/nested UPDATE, local/RPC admission, scheduled peers, inherited
Forbid and cleanup. Their baseline runs reuse the frozen current-runtime images
from the previous UPDATE slice: 224 and 181 C assertions, respectively, plus
four native assertions each. The host suite runs 668 tests, with four expected
historical-source skips.

The unchanged guest corpus is observed with additional native entries at
`DESKCACHE.ClientBounds` and `LAYERCACHE.EndChange`. The latter counts actual
matching slots during each UPDATE, including invalid or pinned matches.
Complete slot and repair bytes are also captured at untimed settled frame
checkpoints. The guest and exposure coverage oracle remain unchanged.

The baseline reproduces all eleven US3 frame digests exactly. Fragmented
Counter tick costs 36.686 ms caller CPU, including 11.302 ms in public END and
2.375 ms across four cache-completion calls. There are **zero matching slots**
in every measured application UPDATE; matching-path cost is therefore checked
in the controlled cohorts and behavior in the retained-pixel fixture.

All 863 production inputs match the final US3 inventory; frozen sources, builds,
observers and raw captures live under `build/update-cache-completion/`.
The older 349-file inventory is not used to establish native GUI provenance.
These are optimized emitted-code development checks, not hosted-system or
hardware qualification. No demo is refreshed.

EC0 reserves **0 additional fixed/root/kernel bank-zero bytes, 0 per public
Task and 0 idle bytes**, including guards, alignment and unused capacity.

Its added records and comparison buffer belong only to the test fixture.

## EC1 Identity-only miss return

The guard checks the two existing identities before `LAYERS.Find`, client
geometry/readiness and rectangle conversion. Any match retains the original
body and both-slot loop. `AESWINDOWSTATE.EndUpdate`, gate/lock policy, cache
layout, compiler and platform inputs are unchanged. Disassembly confirms the
miss returns before the first preparation call.

The [EC1 evidence](../development/update-cache-completion-ec1.json) compares
all fifteen cohorts against EC0. The 738 native assertions pass; all 750 slot
and repair observation bytes and 22 geometry observations match exactly.
The no-slot cohort falls from 0.437 to 0.039 ms caller CPU (91.1% less).
Unrelated valid, invalid and pinned identities also skip all preparation.
Matching-cohort changes range from -0.7% to +3.5%; none exceeds the 5% review
threshold. Either and both-slot completion counts remain identical.
Fresh optimized cache and lock images pass 224 and 181 C assertions plus four
native assertions each. Heap/ownership restore and guards remain intact. The
host suite passes 664 tests with four expected historical-source skips.

Full END still executes for every owned window. In four-window samples,
cache-specific bounds calls fall from four to zero, while all four final
readiness checks remain; BEGIN also retains its four publication checks.
No-slot paint reports still consume journals, publish epoch/readiness and
set capture candidates. Hidden unreported changes retain repaint obligations.

Production changes only `lib/desktop/deskcache.act`: **129 executable bytes
added**, no persistent data, allocation or ABI change. The helper's emitted
34-byte fixed frame and 50-byte local stack peak are unchanged. All complete
bank-zero maps match, with **0 additional fixed/root/kernel bytes, 0 per public
Task and 0 idle bytes**, including guards, alignment and unused capacity.

## EC2 Matched development gate

The [EC2 evidence](../development/update-cache-completion-ec2.json) passes both
gates: lower controlled no-slot END cost and lower fragmented Counter tick CPU.
The repeated controlled fixture reproduces EC1 exactly. Four-window fragmented
native END falls from 5.954 to 4.160 ms (30.1% less).

The unchanged guest runs 67 measured operations after 16 warmups, including
three exposure bursts. It passes 505 assertions and all eleven full-frame
digests match EC0 and US3. All settled slot/repair bytes and pending damage
match. All twelve observed drawing/ownership call-count distributions match
across all nine cohorts. Both sides use the same observer, actionc binary,
Calypsi 5.18, pinned ROM, emulator and machine settings.

Fragmented Counter tick medians:

| Measurement | EC0 | EC2 |
| --- | ---: | ---: |
| Caller CPU | 36.686 ms | 34.426 ms |
| Elapsed | 47.494 ms | 44.812 ms |
| Public END caller CPU | 11.302 ms | 8.773 ms |
| Native END caller CPU | 7.512 ms | 4.992 ms |
| Four cache-completion calls | 2.375 ms | 0.080 ms |
| Presenter CPU | 2.497 ms | 2.497 ms |

Caller CPU improves **6.2%** and elapsed time **5.6%**. Inclusive helper costs
overlap and cannot be added. BEGIN changes from 6.938 to 7.168 ms (+3.3%),
which offsets some END savings in the net result. The four cache bounds calls
disappear and END readiness calls fall from eight to four; the final four
publication checks remain. All measured END calls are local. Counter tick
BEGIN is also local; other cohorts have occasional BEGIN RPC fallback, whose
ranges and caller/presenter costs are recorded separately. No RPC speedup is
claimed.

No caller or elapsed control regresses by more than 5%; zero timer changes
by +0.1% CPU and +0.9% elapsed. The small-object presenter median rises 9.3%
(2.498 to 2.730 ms) as background work overlaps different sample windows.
Its eight samples range from zero to about 188 ms; their total changes from
248.639 to 248.679 ms, only +0.016%. Matching drawing counts, frames and this
aggregate support a scheduling-phase explanation. The evidence retains every
sample; these small cohorts do not establish tail latency.

Exposure delivery also matches exactly: two rectangles in the first burst,
then one in each later burst, with four UPDATE scopes and requested areas
16,128, 16,896 and 16,896 pixels. Each burst exposes 4,608 new pixels.
Burst CPU falls from 44.741 to 41.652 ms; this is not a per-rectangle claim.
Future coalescing changes must still be compared by area and scope count.

The source audit finds only the bounded `deskcache.act` change among 863
production inputs. Native code grows by 129 bytes; data remains 53,013 bytes
and zero-fill 23,451 bytes. C code/data bytes, public layouts and complete
reservation maps match. There is **0 fixed/root/kernel, 0 per public Task and
0 idle bank-zero reservation growth**, including guards, alignment and spare
capacity, and no added upper-RAM record or allocation.

The helper retains its 34-byte fixed frame and 50-byte local stack peak.
The observed matched root stack watermark changes from 740 to 750 bytes in
its existing 1,536-byte reservation, leaving 530 bytes above the 256-byte
interrupt floor. Kernel touched bytes change from 287 to 285; its interrupt
reserve remains untouched. Guards pass and bank ownership restores after
shutdown; the native fixture additionally checks exact `AvailMem` equality.
Watermarks are observations, not worst-case stack proofs.

Raw captures, frozen inputs and evidence recorders are archived under
`build/update-cache-completion/`. EC0 and the earlier US0–US3 records remain
unchanged. EC0–EC2 are complete at the development tier; no full hosted-system
qualification, hardware claim, compiler migration or demo refresh is made.

Fresh functional and measurement commands:

```sh
python3 tools/test_aes_snapshot.py --output build/checks/aes-update
python3 tools/test_aes_server.py --suite cache --output build/checks/aes-cache
python3 tools/test_aes_server.py --suite locks --output build/checks/aes-locks
python3 -m unittest discover -s tests -p 'test_*.py'
python3 tools/measure_aes_update.py --output build/checks/aes-matched
```
