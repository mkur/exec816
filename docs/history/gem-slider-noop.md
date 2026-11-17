# Unchanged slider completion

[History index](README.md) · [Pre-copy audit](gem-pre-copy-audit.md) ·
[Measurements and inputs](../development/gem-slider-noop.json)

Equal slider setters now return through UPDATE release without general
publication, menu reconciliation or exposure completion. This follows pinned
MagiC `AESWIN.S` `ws_slend` / `ws_endsw`: with Smart Redraw enabled, an equal
normalized value goes directly to `update_0`. The existing native frame routine
already recognizes equality; this slice completes that return through the
caller-facing AES wrapper.

`AESLOCAL.Policy` reports a private unchanged-slider outcome only after a
successful frame result with no change and no retained caller wait. `Call`
converts that outcome to the ordinary handled result, then uses its common
scope-release path. The four slider fields share this branch. The request's
successful result survives, and normal final-release notification/Yield policy
still belongs to the existing UPDATE service. Changed values, errors and
retained continuations retain their completion paths. No public ABI, request
field, application code, renderer or platform service changes.

## Focused development check

Only optimized native AES is rebuilt from the frozen EU5 MGVIEW fixture. Its
resident C provider and APP are reused byte for byte, with their recorded input
hashes checked. The existing passive pre-copy observer runs the down/up pair
and three Process lifetimes. It verifies the emitted code's public result and
scope boundaries, not just the source branch.

| Equal `WF_VSLSIZE` | Before down/up | After down/up |
| --- | ---: | ---: |
| Viewer CPU | 4.367 / 4.367 ms | **2.870 / 2.875 ms** |
| Elapsed | 5.293 / 5.293 ms | **3.441 / 3.491 ms** |
| General publication calls | 1 / 1 | **0 / 0** |
| Input snapshot publication checks | 2 / 2 | **0 / 0** |
| Exposure, menu reconciliation and scene completion calls, each | 1 / 1 | **0 / 0** |
| Temporary UPDATE scope boundaries | 2 / 2 | **2 / 2** |

Both equal calls return public handled/result values of **1**. Neither mutates
thumb geometry nor paints. Both changed position calls retain one selected-axis
update, one selected paint, their publication/completion path and successful
public results. All three native UPDATE Attempts still succeed per scroll;
there are no Obtain waits. This loaded pair observes vertical size equality and
position changes; it is not a new four-field or failure qualification matrix.

Whole pre-copy CPU falls from **35.803/36.341 to 34.300/34.757 ms**; elapsed
falls from **44.981/48.292 to 43.118/46.401 ms**. The first small reduction is
therefore visible in its enclosing CPU interval. Observed complete-viewport
latency is **120.28/119.95 ms**, versus 120.50/140.23 ms before; these two PAL
observations do not establish a latency distribution or an end-to-end gain.

Exact viewport pixels, one viewport copy, one exposed-row draw, no repaint
fallback, unchanged pointer position, ownership/heap restoration and
stack/domain guards pass. The settled full scanout is identical to the audit.
Host checks run **738 tests, four skipped**. No QED, Counter, application/provider
build, geometry run, demo refresh or release matrix is performed.

The generated bank-zero budget, runtime reservations and all Task pools match
EU5. Added reserved bank-zero bytes: **0 fixed, root, kernel, idle and per public
Task**, including guards, alignment and unused capacity. The private outcome is
an immediate constant; no new runtime record or static storage is introduced.
These development checks do not qualify the hosted system.
