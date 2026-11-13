# Input-route reuse during paint-only UPDATE

[History](README.md) · [Evidence](../development/gui-route-reuse.json) ·
[Drawing baseline](gui-drawing-baseline.md) ·
[Display ownership](../reference/display.md)

## Change

`BEGIN_UPDATE` and `END_UPDATE` change the shared `mouseOwner` field even when
the caller has no MCTRL hold. Previously, each handoff rebuilt the copied input
routes, recalculated every window's work rectangle and exchanged endpoint holds.
Input routing uses this owner only while `mouseHolds` is nonzero.

`AESSNAPSHOT.Publish` now ignores owner changes in its reuse condition while
`mouseHolds=0`. Existing routes and endpoint holds survive a paint-only handoff.
MCTRL owner/depth, selected window, focus, layout epoch, client count, menu state
and explicit invalidation still control freshness. A zero layout epoch still
forces rebuilding. The private copied owner can remain old while there are no
MCTRL holds; both readers of that field test the hold count first.

Outer UPDATE transitions still mark `AESSTATE.mouseDirty`, and
`AESMOUSE.RefreshSnapshot` still refreshes input eligibility on both transitions.
The service's actual ownership state, queued handoffs, capture and retirement
protocols are unchanged. Window lifetime and endpoint withdrawal explicitly
invalidate the routes. Task preemption, drawing units, application repainting
and public interfaces retain their existing behavior.

This is the first runtime slice after baseline revision `362027c4`. The only
production source change is in `lib/aes/aessnapshot.act`.

## Controlled BEGIN/END result

An optimized native fixture uses the real `AESLOCKS.Attempt` path with two
clients and four windows. Physical readiness is established by the fixture;
there is no renderer, competing Task or physical admission wait. Each owner has
two warmups followed by eight measured BEGIN/END pairs.

| Mean Task CPU per pair | Before, ms | After, ms | Reduction |
| --- | ---: | ---: | ---: |
| Focused client paints | 17.014 | 9.566 | 43.8% |
| Other client paints | 17.430 | 9.838 | 43.6% |

For both owners, each pair still calls Publish twice and refreshes inboxes twice.
Full route rebuilds fall from two to zero, and work-rectangle calculations from
eight to zero. Publication CPU falls from 7.842 to 0.136 ms for the focused
client, and from 7.936 to 0.192 ms for the other client. These figures include
the UPDATE policy and snapshot work rather than just a lock instruction.

## Packaged viewer result

Both packages use the pinned optimized compiler, ROM and PAL 8× 65816/VBXE
configuration from the baseline. All ten application binaries and the C image's
segments are identical. The document, 456×170 work area, 18 visible document
rows and pointer position also match. The loaded scene retains Counter and the
unchanged four-pass GFLOAD disk workload.

Each scene has four alternating page actions and four alternating line actions,
plus an untraced companion for each package. Median physical-key offer to
IRQ-observed completed repaint:

| Scene and action | Before, ms | After, ms | Reduction |
| --- | ---: | ---: | ---: |
| Idle, page | 1221.356 | 1025.851 | 16.0% |
| Idle, line | 1192.791 | 995.145 | 16.6% |
| Counter/disk, page | 2175.631 | 1781.126 | 18.1% |
| Counter/disk, line | 2113.317 | 1839.144 | 13.0% |

Mean viewer CPU falls by 12.5–14.2%. The UPDATE routine portion falls by
31.6–32.5%, accounting for most of the CPU reduction. IRQ time and time waiting
to run remain separately attributed in the evidence; elapsed improvement also
depends on where the shorter work falls in the schedule and disk activity.
Individual loaded actions can still be slower. Four samples do not establish
latency tails, input responsiveness or release qualification.

Every repaint retains seven BEGIN/END pairs, 21 physical grants, 23 hardware
launches, 20 text calls, 31 fences, one bar and 18 document TextRow calls.
There is no retained-pixel scrolling change. All whole-work-area pixel oracles,
boundary no-op, heap return, ownership, stack/domain guards and normal EXIT pass.
Counter advances and disk result bytes match in both loaded packages.

Replay intervals, inter-action gaps, model/first-band/completion edges and
runtime interrupt/switch/gateway counters match exactly. The simulator's global
scheduler clock can have a different origin before BOOT: the original idle pair
differs by a constant 7,296 cycles and the candidate loaded pair by 35,568 cycles.
The evidence records and removes that single offset per run; no individual
sample is aligned or tolerance applied. Candidate idle and original loaded
pairs have zero offset. Scanout timing is outside the measurement boundary;
settled scanout pixels are checked separately.

The idle fixture now closes the startup folder through its physical title and
close gadget. Initial Windows-menu attempts stalled before any measurements.
A fresh original-package idle capture and replay use the same corrected input
sequence, so the historical idle baseline is preserved rather than substituted
into this comparison. The loaded setup and frozen loaded baseline are unchanged.

## Development validation and memory

- The native route fixture passes 546 assertions before and after the change:
  ordinary routing, a different painting client, recursive UPDATE/MCTRL, mixed
  locks, MCTRL selected-window changes, input eligibility, geometry/focus/epoch/
  menu invalidation, endpoint withdrawal with an outstanding reader, and cleanup.
- The optimized public lock suite passes 231 C and four native checks.
- The optimized pointer suite passes 168 C, 25 capture-boundary and five native
  checks, including peer handoff, close/reopen, loss and paint during capture.
- The host suite passes 702 tests with four existing historical-source skips.
- The refreshed OF816 demo passes all 30 ZIP checksums, boot-only content and
  license checks, all 69 recorded SYS file identities and nine on-disk APP
  provider identities. Five-second standard shell/prime autoboot is retained;
  QED was not selected for this package.

The pointer fixture needed its old `item.window.keyRoute` reference updated to
the current `item.keyRoute`. It also needed the existing deferred-paint retirement
wait used by other suites before returning from Main. The original snapshot
code reproduced the former shutdown fault; the repaired fixture exits normally.
Failed pilots, including an incorrect endpoint-hold expectation during fixture
development, remain excluded and identified in the evidence.

Reserved bank-zero change is **zero bytes** for fixed services, root, kernel,
idle and each public Task, including guards, alignment and unused capacity.
Bank-zero budgets, Task pools and runtime reservations match for both the
eight-Task probe and twelve-Task demo. Upper-memory and VRAM reservations are
unchanged. The emitted Publish routine grows by 20 upper-memory code bytes
(4,068 to 4,088); its fixed frame and local stack peak remain 38 and 50 bytes.
No platform or full hosted-system qualification is claimed.

## Reproduction

```sh
python3 tools/test_aes_route_reuse.py --output build/route-reuse-check
python3 tools/test_aes_server.py --suite locks --mode opt --output build/route-locks
python3 tools/test_aes_server.py --suite pointer --mode opt --output build/route-pointer
python3 -m unittest discover -s tests -p 'test_*.py'
python3 tools/build_demo.py --output build/route-demo --gem-desktop --release-compiler
python3 tools/measure_gui_baseline.py --bundle build/route-demo \
  --output build/route-idle --count 4 --observe
```

Repeat the viewer command with a fresh output directory and without `--observe`
for its untraced companion. Add `--load build/gui-baseline/load` to use the frozen
loaded fixture from the baseline; its fixture metadata and hashes are recorded
in the evidence. Before/after capture paths, source and artifact hashes, compiler
settings and separate CPU/IRQ/wait measurements are in the linked JSON.
