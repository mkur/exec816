# MGVIEW presenter work and wake reasons

[Scrolling audit](mgview-scroll-audit.md) · [History](README.md) ·
[Statistics](../development/mgview-presenter-audit.json)

On 2026-11-15, an expanded passive trace identified repeated **mouse
presentation** as the largest presenter cost during MGVIEW's UPDATE. Native
window painting is nearly idle. A retained drawing-changed hint repeatedly
admits the mouse path, which does not consume that hint. This is a smaller
next fix than changing copy-strip limits. This audit changes host tools and
documentation only.

## Scope and CPU attribution

The owned interval starts when `ExecAESBeginUpdate` returns and ends at entry
to the END `wind_update` call. MGVIEW already owns UPDATE throughout that
interval. BEGIN and END execution are excluded. This is narrower than the
earlier whole-`set_shift` interval, which includes acquiring and releasing it.

| Measurement, milliseconds | Down | Up |
| --- | ---: | ---: |
| Already-owned UPDATE interval, elapsed | 183.38 | 157.52 |
| Presenter CPU in that interval | **63.47** | **48.53** |
| Inclusive `DESKINPUT.Present` CPU | **39.26** | **36.04** |
| Nested `CONSOLEBITMAP.Run` CPU | 24.04 | 23.54 |
| Inclusive `DESKINPUT.Service` CPU | 7.19 | 1.52 |
| Native paint-pump CPU | 0.18 | 0.14 |
| Exclusive scene-admission phase CPU | 8.90 | 0.51 |
| Exclusive scheduling/readiness phase CPU | 4.00 | 3.66 |

Inclusive routine charges overlap: the bitmap call is inside mouse presentation,
and scene reclaim can dispatch deferred input. Do not add these rows. The
statistics also partition all presenter CPU into disjoint outer phases, with
clipped calls at the interval boundaries and IRQ/NMI execution kept separate.

`DESKPAINT.Pump`, `DESKPAINT.Ready`, `AESHOST.Pump` and `DESKHOST.Runnable`
return zero at every observed completion in the owned interval. The pump runs
four times down and three times up, without advancing window painting or
admitting an AES message. UPDATE does not keep the presenter asleep: input,
cursor handling, scene coordination and readiness work still execute normally.

## Why the presenter runs

Signal arguments are recovered from the emitted Action! call packet's observed
PHA instructions. The packet widths and linked JSL instructions are checked.
The common presenter target is `$021594`, identified from the scene-release
path, and its CPU direct page is `$1300`. Signal producers below run on the
viewer Task, `$1200`.

| Presenter-target signal posts inside owned UPDATE | Mask | Down | Up |
| --- | --- | ---: | ---: |
| `AESGATE.Release`: scene release / waiting presenter | `$00080000` | 3 | 2 |
| `DISPLAY.Leave`: subscribed display-readiness observer | `$00010000` | 3 | 1 |
| `DISPLAY.Next`: queued lifetime-owner handoff | `$00010000` | 0 | 1 |

These are executed signal posts, not inferred wakes from copy-strip counts.
The display bit is shared with the backend completion wake; the sender sites
above establish these posts as arbitration notifications. The copy itself is
synchronous and has no asynchronous completion-IRQ marker.

| Wait returns observed inside owned UPDATE | Down | Up |
| --- | ---: | ---: |
| Main-loop Wait, scene/AES bit | 2 | 1 |
| Scene-reclaim Wait, scene/AES bit | 1 | 0 |
| Main-loop Wait, display bit | 3 | 2 |
| Main-loop voluntary Yield calls | 0 | 0 |

Up's final main-loop Wait returns after the owned interval, so it is excluded
from the return counts even though it overlaps the interval. Signals are hints:
posts, consumed bits and scheduling turns need not correspond one-to-one.

Six presenter turns intersect the down interval, including two that take the
quiet notification/cache branch. Four intersect up, with no quiet branch.
The first and last intersecting turns can be partial; these are not counts of
complete turns or kernel Task switches. The presenter also executes two/one
`DISPLAY.Next` borrower-wake posts down/up, targeting the viewer, rather than
itself. Client mouse-completion signals from `AESWAIT.Signal` likewise are not
presenter wakes.

This resolves the earlier ambiguity: both caller scene releases and subscribed
display-readiness notifications bring the presenter back. It does **not** wake
once for every one of the twelve copy strips.

## Repeated mouse work

Inside the owned interval, the saved trace already contains caller-return
markers for the cursor decisions in
[`DESKINPUT.Present`](../../lib/desktop/deskinput.act):

| Observed completion inside interval | Down | Up |
| --- | ---: | ---: |
| `CONSOLEBITMAP.Changed()` returns 1 | 8 | 8 |
| `CONSOLEBITMAP.Changed()` returns 0 | 0 | 0 |
| Following `AESCURSOR.Pending()` check | 0 | 0 |
| Console C mouse operation returns `DISPLAY_OK` | 7 | 8 |
| Console C mouse operation returns `DISPLAY_BUSY` | 0 | 1 |

The changed hint short-circuits the subsequent pending-revision test. The
console switch's linked JSL to `GemDrawingMouse`, followed by its return PC,
independently confirms the mouse operation and status. One down bitmap call
starts inside this interval and returns afterward; CPU is clipped, and that
return is excluded from the table.

The source explains the repeated hint. In
[`CONSOLEBITMAP`](../../lib/console/consolebitmap.act), drawing and `Drawn()`
set `drawingChanged=1`. `Present()` uses that hint to call `Mouse()`.
`Mouse()` calls `Run(OP_MOUSE)` without consuming it, whereas `Cursor()`
clears it after `Run(OP_POINTER)`. With AES installed, `Present()` selects
the `Mouse()` path. Its repeated successful returns therefore leave the
changed condition true for the next check.

The trace confirms repeated submissions, not a full hardware cursor repaint
on every call. The C mouse path may find unchanged physical state; each call
still crosses the ordinary C bridge, renderer arbitration and scene
suspend/resume. In the owned interval the presenter has only two observed
`VbxeOwnerFence` calls and one `VbxeOwnerSubmit` per direction, far fewer than
its mouse submissions. The charged mouse CPU is not pure blitter time.

The next implementation slice should consume the drawing-changed hint for the
AES mouse path. Consume only the old notification, preserve a new draw that
arrives while the C call or scene resume is running, and rearm on BUSY. Keep
cursor revisions, visibility completion and ordinary Task preemption intact.
Then repeat this same two-key capture and compare pixels, mouse-call counts,
viewer response and presenter CPU. No strip-size, scheduler or wake-policy
change is justified as part of that fix.

## Reproduction and validation

```sh
python3 tools/measure_mgview.py --presenter --output build/mgview-presenter-audit
# Analyze the saved capture without running the guest:
python3 tools/measure_mgview.py --output build/mgview-presenter-audit --analyze-only
```

The tool reuses the same optimized MGVIEW, Counter, provider and native fixture
as the preceding audit. ROM and observer executable hashes, machine settings,
APP identities and linked markers are checked. Native code, APPs, physical-key
sequence, document and viewport are unchanged. The expanded trace reproduces
both viewport timings (220.72/200.21 ms), caller phase charges and completed
pixel hashes **exactly**, despite selecting additional passive PCs.

The capture has 797,615 CPU events and a 53,466,411-byte log. Full spans and
events remain in `build/mgview-presenter-audit/`; compact inputs, counts and
charges are committed in the statistics record. Signal posts without decoded
target arguments are retained in the full record but excluded from the
presenter-target table. Native procedures have no meaningful return value;
only documented BYTE getters' return histograms have semantic meaning here.

Development checks pass: two exact viewport transitions, one copy and one
text-row draw per key, zero AES RPC, unchanged twelve-strip copy path,
four fixture Process lifetimes, heap checks, intact stack/domain guards and
restored ownership. Counter advances twice over the wider run including its
post-settle period. It has no charged CPU inside the measured scroll scopes.

There were **zero builds**, no QED, demo packaging or cold boot. Reserved
bank-zero deltas are **0 fixed, 0 root, 0 kernel, 0 private idle and 0 per
public Task**, including guards, alignment and unused capacity. These remain
two diagnostic samples with a busy-yielding fixture supervisor, not release
qualification, a latency distribution or a matched MagiC speed comparison.
