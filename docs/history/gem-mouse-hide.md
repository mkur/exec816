# Direct mouse hiding

[History index](README.md) · [Mouse audit](gem-mouse-hide-audit.md) ·
[Pinned inputs and results](../development/gem-mouse-hide.json)

AES `M_OFF` now goes directly through hide accounting to synchronous cursor
restoration. It skips recipient/form selection and leaves pending selection
dirty for input service or a later show/form operation. This follows pinned
MagiC `AESMAIN.S` `gm_hide`, `AESOBJ.S` `mouse_off` and `INPUT.S` `v_hide_c`:
hiding changes counters and removes the old sprite rather than installing a
mouse form.

The shared VBXE mouse apply routine snapshots position, visibility and revision
under its existing Task guard. A visible-to-hidden transition no longer copies,
compares or installs form data. It restores the saved cursor background and
acknowledges the captured revision. The logical target remains owned in the AES
directory; a later show snapshots and installs its current form before drawing.
A later revision published during restoration remains pending. Form applies
while already hidden retain their installation path, as do visible applies,
including custom-form comparison and mask invalidation. Raw VDI calls retain
their native selection policy; their visible-to-hidden transitions share the
same form-copy avoidance.

The existing per-client and aggregate hide counts, UPDATE independence, display
grant, fences, completion/error handling, normal Task preemption and waiter
notification remain in use. No public ABI, application source, platform service,
Task or buffer is added. General guard/wake simplification is outside this slice.

## Focused development checks

The small optimized native cursor-policy fixture passes **55 assertions**.
These include nested/peer hides, retirement, raw VDI depth, force-show behavior,
overflow, form history and completion. Three new checks establish that M_OFF
keeps the current recipient/form and dirty selection intact while returning the
normal success/completion target. Old fixture size expectations are updated to
the existing Request 190, Client 370 and Service 2492 byte layouts; this slice
does not change those types.

A second small optimized fixture executes the production `draw_Mouse` body
with only flush/cursor hardware substituted and real Exec guards. Its **25
assertions** cover a hide without form copies, installation of a custom form
while already hidden, the subsequent show, unchanged visible forms, a late show
revision, a backend fault and an already pending operation. This does not
substitute for real physical ownership/pixel checks.

The loaded MGVIEW check supplies those physical checks. It reuses the unchanged
APP, recompiles only `gem-vbxe.c`, reuses **46 C objects and 10 layout probes**
and relinks the provider, then rebuilds native AES. One down/up pair passes exact
viewport and settled full-scanout pixels, one viewport copy and exposed row per action, no
repaint fallback, three Process lifetimes, ownership/heap restoration and
stack/domain guards. No QED, Counter, application catalog, geometry run, demo
refresh or release qualification is involved. Host checks run **740 tests,
four skipped**.

## Measured result

The same passive mouse observer, document, viewport, clipped pointer at `(639,0)`,
ROM and emulator are used before and after. CPU includes gateway/scheduler
continuation work and bus stalls, with interrupts and other Tasks separate.

| M_OFF | Down before | Down after | Up before | Up after |
| --- | ---: | ---: | ---: | ---: |
| Viewer CPU | 5.928 ms | **3.304 ms** | 5.904 ms | **4.338 ms** |
| Elapsed | 8.034 ms | **3.960 ms** | 8.016 ms | **6.026 ms** |
| Recipient selections | 1 | **0** | 1 | **0** |
| Form copies | 1 | **0** | 1 | **0** |
| Forbid/Permit pairs | 13 | **10** | 13 | **10** |
| Restore submissions / BCBs | 1 / 1 | **1 / 1** | 1 / 1 | **1 / 1** |

Native policy CPU falls from about 0.805 to **0.239 ms**; device-apply CPU falls
from 3.465/3.436 to **1.414/2.438 ms**. The up sample includes ordinary scheduling
and continuation cost within the device's C Task guards, with the same guard
count and no form copy. That cost remains in the total rather than being
presented as a constant 3.3 ms hide. Showing retains one
recipient selection, one form copy and three cursor records, charging about
**5.30 ms CPU**. Both public calls still return success.

Complete-viewport observations are about **120.63/120.42 ms**. These two PAL
samples and one clipped pointer position do not establish an end-to-end latency
improvement or a distribution over cursor positions/forms.

The generated bank-zero budget, runtime reservations and Task pools match the
preceding fixture. Added reserved bank-zero bytes: **0 fixed, root, kernel,
idle and per public Task**, including guards, alignment and unused capacity.
No production static storage is added. Development checks do not qualify the
hosted system.
