# Terminal directory notifications and idle polling

[History](README.md) · [Plan](../plans/gem4xe/terminal-idle-polling-plan.md) ·
[Previous measurements](terminal-wake.md)

## TP1 Independent directory watches

Console-view version 5 adds WatchDirectory, TakeDirectoryChange and
UnwatchDirectory through the existing three-ULONG bridge. APP ABI 38 fences the
new capability: older providers reject these APPs before an unsupported operation
could be interpreted as a handle. All 130 import ordinals and the existing
92/76/42-byte public packets remain unchanged.

Four optional directory watches have their own bounded list, independent of the
eight cell subscriptions. Each retains its recipient Task, starts pending with an
initial signal, and coalesces later publications until Take. Take clears only the
pending flag, before metadata reads; it leaves the shared signal untouched.
Unwatch withdraws publisher access before releasing the lease and storage.
External watches prevent service Stop; source destruction does not depend on them.

[TP1 evidence](../development/terminal-idle-tp1.json) records raw and optimized
emitted C/Action bridge checks, including bit 31, two independent Tasks,
allocation/lease failure rollback, capacity, preserved cell slots, pure reads,
coalescing and changes around Take/read/Wait. Both runs check exact heap return,
stack/domain guards, ownership and EXIT. Failure injection replaces only the
watch allocator/Retain calls in a fixture copy. The standalone renderer occupies
one cell slot, leaving seven for the probe. The real public bridge is retained.

A record emits as 22 upper-memory bytes; four allocations cost 96 bytes after
rounding. The emitted list head/count occupy four upper-memory data bytes (a three-byte
pointer and one-byte count). TP1’s JSON bookkeeping estimate said five; the
emitted globals correct that estimate, without changing its heap or reservation
measurements. Complete
`bank_zero_budget`, `task_pools` and `runtime_reservations` match the earlier
eight-Task signal probe: reserved bank-zero growth is **0 fixed, 0 root, 0 kernel,
0 idle and 0 per public Task bytes**, including guards, alignment and unused
capacity. No production reservation grows. The fixture uses an 8 KiB upper data
arena because linking the actual console facade also retains AES globals; the
production GEM profile already reserves 12 KiB. This fixture adjustment does not
reserve guest bank-zero space in production.

Generated definitions and 711 host tests pass, with four existing skips.
These are development checks. Metadata publishers and Terminal admission follow
in TP2; this slice leaves Terminal's polling behavior unchanged.

## TP2 Metadata publishers and Terminal admission

Console LIVE/removal, supported geometry changes and accepted frontend activation
now publish directory invalidations after their state commits. Shell creation,
READY/failure, closing, collection, selection/fallback and controller port
withdrawal do likewise. Queries, painting, ordinary cell output and unchanged
controller turns remain silent. The lower notification core keeps text and
standalone producers independent of the AES facade.

Terminal registers its watch before querying metadata and withdraws it alongside
cell subscriptions before releasing the shared notification bit. Watch-admission
failure follows normal supervised startup rollback. The private record grows by
four bytes to 5,851; the handle is appended at offset 5,847. This slice retains
the 100 ms timer and unconditional metadata refresh.

The raw and optimized startup/teardown probes pass 38 checks each, including
watch admission failure and resource recovery. The shell allocation-failure
fixture passes 145 checks over 19 allocation points; 12 failed creations that
advanced the public identity retain a directory hint. Exact heap return,
Task leases, guards and EXIT pass. Its upper data fixture arena grows from 8 to
12 KiB to hold the linked watch support and test state; production reservations
do not change.

Complete eight-Task probe bank-zero budgets, Task pools and runtime reservation
maps still match the frozen signal probe: **0 fixed, 0 root, 0 kernel, 0 idle and
0 per public Task bytes added**, including guards, alignment and unused capacity.
No production Task, signal bit, upper-memory reservation or VRAM arena is added.

[TP2 evidence](../development/terminal-idle-tp2.json) also records the real GEM
keyboard/session/modal-close scenario. Two native observer Tasks block on their
own directory signals without timers. Creation/retirement and a replacement unit
epoch, plus frontend activation, wake both while the publisher owns UPDATE.
Their counts stay 8/8 during a quiet interval and ordinary ECHO output, then
advance for NEWSHELL/READY, selection and closing/fallback. These are observed
coalesced hints, not a promised event count. Both observers unwatch after port
withdrawal before root finishes. Three exact pixel checkpoints, keyboard editing,
cancelled/confirmed close, ownership, guards and EXIT pass. The focus test now
uses an actual peer layer's bounds, covering both legacy panel/counter and Files
desktops. The host suite passes 711 tests with four existing skips.

## TP3 Event-driven refresh and explicit retries

Terminal consumes directory hints before querying the two metadata services.
Initial/forced refreshes and session actions also invalidate those snapshots.
Cell wakes, redraws and retries use the owned scalar copies. Healthy waits request
messages, buttons and the existing producer signal, without MU_TIMER. Only failed
cell admission or an incomplete selected copy arms a 100 ms retry. An inactive
unacknowledged view does not arm it; successful recovery or closure clears the
reason. A closed selection drains one forced refresh instead of depending on a
timer. Modal close retains its explicit before/after refresh boundaries.

[TP3 evidence](../development/terminal-idle-tp3.json) records 40 refresh-decision
checks and 40 ownership/wait checks in each raw/optimized build. The decision
probe uses the actual platform code with controlled endpoints and real Exec
resources/queued replies. It covers coalesced cell/directory hints, stale bits,
a hint during refresh, bounded capacity retry and release, BUSY and mixed
revisions, inactive pending, source closure/epoch replacement and port withdrawal.
Each retry attempts bounded work without another metadata query; recovery turns
the timer off. Actual bridge capacity and asynchronous publishers are covered by
TP1/TP2 and the real GEM scenario, rather than claimed from these endpoint stubs.

Both untraced and observed keyboard/session/modal-close runs pass. A 2,406.703 ms
quiet interval contains **zero session queries, zero directory reads and zero
Terminal timer arms**. Of 99 completed observed waits, 91 include MU_EXEC from
real view/directory notifications; none includes MU_TIMER. All three pixel
checkpoints, two observers, closing/fallback, watcher withdrawal, ownership,
stack/domain guards and EXIT pass. The first instrumented attempt hit a
30-second host frame-wait limit after NEWSHELL; the retained failed capture is
not counted as passing. A rerun with IRQ/NMI progress markers and a bounded
60-second host wait passes without a runtime change. No cause is inferred.

TP3 changes only the loaded Terminal. The integration fixture reuses an
identical ABI-38 native provider and rebuilds Terminal plus writable SYS; its
original build remains intact. The complete demo will be rebuilt in TP4.

The private Terminal record grows two bytes to 5,853, with metadataDirty/retry at
5,851/5,852. Across TP1–TP3 its rounded allocation grows eight bytes; its watch
uses 24 heap bytes. Complete eight-Task bank-zero maps, pools and runtime
reservations match the frozen probe: **0 fixed, 0 root, 0 kernel, 0 idle and
0 per public Task reserved bytes added**, including guards, alignment and unused
capacity. Fixed upper/VRAM arenas, Task and signal reservations are unchanged.
The host suite passes 711 tests with four existing skips. These are development
checks, not hosted-system qualification.

## TP4 Packaged measurements and delivery

[TP4 evidence](../development/terminal-idle-tp4.json) records the rebuilt OF816
package and the matched viewer cohorts. Runtime sources are `5ea4adf6`; the
frozen before runtime is `4ff5c3e6`. All ten APPs use ABI 38, preserving the
130 import ordinals. Every non-Terminal executable C segment, including the
viewer, and the resident C ELF are byte-identical to the before package.

The compiler, dedicated AltirraOS ROM, PAL/8×/63-high-bank/VBXE FX 1.26 machine,
font, 6,663-byte document, 56×18 viewport, work rectangle and pointer placement
match. Each main scene measures four page and four line actions. Counter/disk
uses the same Counter and frozen four-pass 64 KiB native I/O workload.

| Scene/action | Repaint median before → after, ms | Reduction | Mean viewer CPU before → after, ms |
| --- | ---: | ---: | ---: |
| Idle page | 808.645 → 670.623 | 17.1% | 433.277 → 427.618 |
| Idle line | 832.666 → 671.024 | 19.4% | 433.537 → 425.957 |
| Counter/disk page | 1426.533 → 1064.312 | 25.4% | 476.339 → 464.963 |
| Counter/disk line | 1566.368 → 1086.603 | 30.6% | 477.958 → 465.659 |

Mean completion across eight actions falls **18.3% idle** and **29.5% loaded**.
The viewer CPU reductions are 1.5%/2.5%; the larger latency improvement accompanies
less time waiting to run or waiting for admission. Four samples per operation do
not establish tails or a worst-case bound.

| Mean time per repaint, ms | Idle before | Idle after | Loaded before | Loaded after |
| --- | ---: | ---: | ---: | ---: |
| Viewer CPU | 433.4 | 426.8 | 477.1 | 465.3 |
| IRQ while viewer selected | 94.5 | 92.6 | 152.0 | 162.2 |
| Viewer ready, off CPU | 222.3 | 80.3 | 631.9 | 305.5 |
| Viewer blocked, off CPU | 69.2 | 70.1 | 248.0 | 130.2 |
| Unclassified prefix | 1.6 | 1.2 | 2.6 | 2.1 |
| Total | 821.1 | 671.0 | 1511.5 | 1065.3 |

While the viewer is ready, Terminal/root CPU falls from 134.9/184.1 ms per
idle/loaded repaint to **zero in these windows**; their associated IRQ time
falls from 29.0/63.6 ms to zero. Backend worker CPU rises from 48.0→66.0 ms idle
and 78.6→90.8 ms loaded. Loaded IRQ while the viewer is selected also rises.
CPU and IRQ are separate costs; inclusive source scopes overlap. The measurements
do not attribute every saved millisecond to one peer or predict a general gain.

### Zero polling and preserved work

Both eight-action windows contain zero Terminal session exchanges, directory
scans and timer arms, including zero timer-only metadata queries. Live rosters
retain its watch and independent notification/reply masks. A separate cohort
keeps Terminal behind an unchanged viewer for **2,406.702 ms**: zero session
queries, zero directory scans and zero timer arms, with unchanged viewer pixels.
Its four cleanup actions are outside the matched latency comparison. A final
focused emitted case passes 41 checks with root consuming a fourth watch and
reading Directory while it owns UPDATE, alongside two peer observers. It covers
source creation/destruction, epoch reuse, activation, pure reads and shutdown;
both peers withdraw their watches and all guards/ownership pass. Its fixture
mode stops after these checks, without repeating the keyboard workload.
TP3's real
output/session checks separately establish genuine wakes without timer fallback.

All thirteen drawing-work fields match the frozen before captures: 18 rows,
20 text calls, one bar, 21 grants, 23 hardware launches, five generic submissions
and 31 fences, with unchanged list records/staging work. Seven BEGIN/END pairs
and six physical paint bands remain. Whole-work-area pixels, boundary no-op,
warmed heap return, ownership, guards and EXIT pass. Counter advances and
persisted disk bytes match.

Both identical-package untraced companions reproduce every relative timing edge,
inter-action gap, sample counter and pixel hash exactly. Both global clock-origin
offsets are zero. All four main runs cold-boot the extracted package and retain
the five-second/250-frame OF816 autoboot. New samples observe all six paints
increments; the two old loaded samples with five retain the existing documented
late-counter-store interpretation. Viewer code and actual drawing work are
unchanged. Completion still means IRQ-observed dirty clear after fences and
END_UPDATE; scanout is checked separately.

The wider loaded capture exceeded the drawing reader's 256 MiB input limit.
The original capture and reader-failure result remain intact. The
[reanalysis tool](../../tools/reanalyze_viewer_drawing.py) derives an input with
all used drawing sites, scheduler/interrupt boundaries and original clock
endpoints: 342,221,488→115,457,040 bytes. Drawing CPU/IRQ/ready/blocked budgets
reconcile with the full wait audit. The same reduction on idle reproduces its
original drawing records exactly. `completed-results.json` records the resolved
loaded reader failure. No guest instruction, capture point, input timing or
completion criterion changed; the observer stayed frozen across the cohorts.

### Memory and package

Complete `bank_zero_budget`, `task_pools`, `runtime_reservations`, image-data,
upper-reservation and console-storage maps match the before demo. Reserved
bank-zero growth is **0 fixed, 0 root, 0 kernel, 0 idle and 0 per public Task
bytes**, including guards, alignment and unused capacity. Fixed upper-memory
and VRAM arenas grow by zero. There is no additional production Task or signal.

Private costs remain a 22-byte watch/24-byte rounded allocation (96 bytes for
four), four bytes of list bookkeeping, and six added Terminal bytes
(eight rounded allocation bytes). Native routine payload grows 3,631 bytes.
Terminal executable C grows 19,618→20,824 bytes; its APP grows 22,680→23,930 bytes,
with the same 66,473-byte separated image span. Code payload is separate from
fixed arena reservations. Observed Terminal stack use changes 830→821 bytes idle
and 901→900 loaded in its 1,312-byte pool, leaving 235/156 untouched bytes above
the 256-byte interrupt reserve. Watermarks are lower bounds, not worst-case proof.

The ZIP/SYS audit passes 30 checksums, all 69 SYS file identities and nine disk
APP identities; the tenth APP is the RAM desktop. OF816, matching pinned ROM,
license notices, writable combined SYS, WORK, MD5/ARC/EDX and overlays are retained.
The ZIP contains boot files, guide, licenses and checksums; development files stay
outside it. ZIP SHA-256:
`06975e1221b3740460d29ffac4d96c67f9a0ce7ba02cfd6032b54db42a7317cc`.

```sh
python3 tools/build_demo.py --output build/terminal-idle/demo --gem-desktop --release-compiler
python3 tools/trace_viewer_waits.py --bundle build/terminal-idle/demo --output build/idle-observed --count 4 --observe --drawing
python3 tools/trace_viewer_waits.py --bundle build/terminal-idle/demo --output build/idle-replay --count 4
python3 tools/trace_viewer_waits.py --bundle build/terminal-idle/demo --output build/loaded-observed --count 4 --load build/gui-baseline/load --observe --drawing
python3 tools/trace_viewer_waits.py --bundle build/terminal-idle/demo --output build/loaded-replay --count 4 --load build/gui-baseline/load
python3 tools/reanalyze_viewer_drawing.py --output build/loaded-observed
python3 tools/build_terminal_directory_probe.py --output build/update-owner-build --probe-only
python3 tools/test_terminal_directory.py --build build/update-owner-build --output build/update-owner --probe-only
python3 tools/check_terminal_idle.py --bundle build/terminal-idle/demo --output build/quiet-viewer
python3 tools/audit_gem_demo.py --bundle build/terminal-idle/demo --output build/package-audit.json
```

Use fresh capture directories. Launch with
`build/terminal-idle/demo/launch-altirra.command`; distribute
`build/terminal-idle/demo/exec816-demo.zip`. Host checks pass 711 tests with four
existing skips; generated definitions and local links pass. These are focused
development results. QED and full release/hosted-system/hardware qualification
remain separate.
