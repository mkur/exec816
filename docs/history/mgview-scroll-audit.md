# MGVIEW scrolling audit

[Port record](mgview-port.md) · [History](README.md) ·
[Measured statistics](../development/mgview-scroll-audit.json)

On 2026-11-15, a small passive audit confirmed that original MGVIEW uses its
copy/exposed-strip path for one-line vertical scrolling. There is no full
repaint fallback. The shared presenter nevertheless consumes substantial CPU
while the viewer's scroll operation is in progress. This makes presenter work
and drawing coordination the next investigation, before changing strip limits.

## Observed response

One physical Ctrl-down and one Ctrl-up were offered to the unchanged loaded
APP. Times are milliseconds of emulated PAL time, including preemption.

| Observation | Down one line | Up one line |
| --- | ---: | ---: |
| Input offered → native keyboard capture | 4.20 | 5.61 |
| Input offered → `set_shift` entry | 13.43 | 15.04 |
| Input offered → first correct top text row observed | 140.53 | 200.21 |
| Input offered → complete correct viewport observed | **220.72** | **200.21** |
| Complete viewport, last mismatch → first match | 205.16–220.72 | 180.98–200.21 |
| Input offered → `set_shift` return | 257.38 | 209.45 |

Pixels are sampled roughly once per PAL frame at native COP boundaries. These
are observed upper bounds, not exact first-pixel timestamps. The top row's
bracket is 120.23–140.53 ms down and 180.98–200.21 ms up. Visible completion can
precede return from cursor restoration and UPDATE release. The opposite copy
directions also change when the top row becomes correct.

## Caller phases

These are inclusive entry-to-return intervals on the viewer Task. CPU charge
includes gateway execution and bus stalls; native IRQ/NMI execution and time on
other Tasks are accounted separately. Nested phases must not be added together.

| Phase | Down elapsed | Down viewer CPU | Up elapsed | Up viewer CPU |
| --- | ---: | ---: | ---: | ---: |
| Complete `set_shift` | **243.95** | **96.70** | **194.41** | **90.00** |
| Begin UPDATE | 36.14 | 9.77 | 28.16 | 7.77 |
| Calculate/publish slider | 24.20 | 7.52 | 6.73 | 5.54 |
| `vro_cpyfm` | **83.13** | **37.64** | **77.20** | **37.10** |
| Exposed-row `_my_draw` | 34.61 | 16.00 | 31.53 | 15.64 |
| Mouse restoration borrow | 7.84 | 3.47 | 3.23 | 2.66 |
| End UPDATE | 24.31 | 8.48 | 8.61 | 7.11 |

The copy interval includes 37.36/31.97 ms running other Tasks and 8.13/8.13 ms
in viewer-context native interrupts (down/up). It is not a measurement of
hardware blitter BUSY time. Even the copy's charged CPU includes setup, polling,
display admissions, fences and kernel calls.

## Drawing path and operation counts

Both directions have the same main path:

| Count per key | Observed |
| --- | ---: |
| `vro_cpyfm` | 1 |
| `_my_draw` | 1 |
| `v_gtext` | 1 |
| `redraw_window` / `update_window` | 0 / 0 |
| AES RPC sequence increment | 0 |
| Successful `VbxeOwnerCopyRect` returns inside copy | 12 |
| Display enter / leave pairs inside copy | 12 |
| `VbxeOwnerFence` calls inside copy | 48 |
| Async blitter-completion IRQ markers inside copy | 0 |

The viewport is 488×200 with an 8×8 font. One line copies 488×192 pixels
(46,848 packed bytes) and reconstructs a 488×8 exposed strip. Independent
pixel comparisons pass before, after and back; an unchanged viewport cannot
pass the navigation check. Scrolling back also needs an extra blank fill for
the shorter exposed line, so complete-operation fill counts differ.

The aligned screen-to-screen S_ONLY route in
[the raster client](../../ports/gem4xe/raster/client.c) reaches
[`GemDrawingCopyBorrow`](../../ports/gem4xe/adapter/gem-vbxe.c). Its limit is
`VBXE_LIST_WORK / width`, capped by `EXEC_VDI_STRIP_ROWS`. The current
[8,192-byte work budget](../../c/include/hardware/vbxe.h) and
[16-row cap](../../c/include/exec816/vdi-unit.h) produce twelve 16-row
admissions. This observation does not imply twelve scheduler switches or
twelve presenter wakes.

Each successful hardware-copy return is observed at its linked caller return
PC, with the JSL target bytes checked and status `DISPLAY_OK`. The
[device operation](../../platform/altirraos/vbxe.c) uses synchronous submission
and polling. It does not use the asynchronous completion-IRQ path here. The
48 fence-call intervals total 16.53/10.87 ms elapsed and 9.15/8.98 ms of viewer
CPU. Those intervals include checks and preemption, not only hardware waiting.

## Where the time goes

Attribution below covers the **whole `set_shift` interval**, including UPDATE
acquisition, rather than only the time for which UPDATE is already owned.
Task CPU and native interrupts sum to the elapsed interval.

| Attribution within `set_shift` | Down | Up |
| --- | ---: | ---: |
| Viewer Task CPU | 96.70 | 90.00 |
| Shared presenter Task CPU | **92.28** | **62.68** |
| Fixture supervisor Task CPU | 11.34 | 6.91 |
| All native interrupts | 43.63 | 34.83 |
| Total elapsed | **243.95** | **194.41** |

The viewer spends 126.21/84.65 ms off CPU. Most of that is presenter execution
and interrupts charged to the presenter context. Counter has no charged CPU
within these two intervals. It advances twice over the wider exercise,
including 60 settling frames afterward; this does not demonstrate Counter
execution inside the drawing scopes.

The fixture supervisor busy-yields while waiting for host instructions. Its
6.91–11.34 ms of charged CPU is artificial contention, so these numbers are not
uncontended desktop latency. Nevertheless, the presenter is the larger peer
cost in both observed actions. Off-CPU time alone does not establish a blocking
call, a lost wakeup or a scheduler defect.

The next small step is to attribute presenter turns and wake reasons during
the already-owned portion of UPDATE: collect/input/settle/paint work and
display readiness retries. [`Display.Leave`](../../lib/display/display-access.inc)
can hand off queued access or signal a blocked owner; the
[presenter loop](../../lib/aes/aessystem.act) contains readiness and settling
work. These are source-level candidates, not a proven cause of every measured
turn. Capture the relevant boundaries before removing wakes or enlarging
drawing quanta. No drawing limits or production behavior changed in this audit.

## Inputs, reproduction and validation scope

The audit reused optimized `build/mgview-dev/smoke` provider, native fixture,
Counter and MGVIEW APPs: **zero builds**, no QED, demo packaging or cold boot.
The 56,746-byte, 901-line `VIEW.TXT` is byte-identical to the earlier MagiC
functional reference, SHA-256
`4e2b4c68e01f9d1fa52811a56536267ab19b90502051a4cba22b4cacddac4ee3`.
The APP is the delivered `432d17cb…` image. Full hashes and machine settings
are in the statistics record.

The pinned machine is AltirraOS 3.44 for 65C816, PAL, CPU multiplier 8, VBXE
FX 1.26 at `$D600`, SIO patches off and accurate disk timing. The ROM and
observer executable hashes are checked. Passive PC history supplies native
IRQ/NMI/scheduler attribution and linked C call boundaries; no guest counters
or timing hooks are inserted. Trace timestamps include eighth-base-cycle
fractions at a 1,773,447.5 Hz base clock.

```sh
python3 tools/measure_mgview.py --cache build/mgview-dev/smoke --output build/mgview-audit
# Recompute the report from the saved capture, without running the guest:
python3 tools/measure_mgview.py --analyze-only
```

The tool requires an existing compatible cache; it never builds missing inputs.
Raw events, sampled pixels and full call spans stay under `build/mgview-audit/`.
The saved capture has 585,918 CPU events and a 39,282,482-byte emulator log.
Its linked marker definition and cached-image identities must match for offline
reanalysis.

Development checks pass: both exact viewport transitions, zero RPC, twelve
successful strip copies per action, unchanged fixture cleanup across four
Process lifetimes, heap checks, stack/domain guards and restored ownership.
Reserved bank-zero deltas are **0 fixed, 0 root, 0 kernel, 0 private idle and
0 per public Task**, including guards, alignment and unused capacity.

These are two directional observations, not a latency distribution, physical
hardware qualification or matched MagiC speed comparison. No no-trace timing
replay, full occlusion/fault matrix or release suite was run.
