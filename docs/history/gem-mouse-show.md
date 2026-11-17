# Cached built-in cursor shows

[History index](README.md) · [Direct hiding](gem-mouse-hide.md) ·
[Pinned inputs and results](../development/gem-mouse-show.json)

Showing an unchanged built-in cursor no longer copies the 76-byte mouse form.
The VBXE adapter snapshots its kind with position, visibility and revision under
the existing Task guard. If the kind matches the cached built-in, its MFORM
payload is unused: rendering already has the built-in selection. Existing mask
preparation, save/draw commands and completion still run when required.

Changed built-ins and all custom forms retain their full snapshot, comparison
and installation paths, including mask invalidation. Hide accounting, recipient
selection, display admission/fences, waiter notification and Task preemption
are unchanged. Actual hiding still avoids form work through the preceding
slice's direct transition. No public ABI, application code or platform service
changes.

This follows MagiC revision `28cfdd29aa16fef692cc287bad3046b44ddcce3d`:
`AESMAIN.S` `gm_show` changes the application count and calls `mouse_on`;
`AESOBJ.S` `mouse_on` changes the aggregate count and calls VDI on the visibility
transition; `INPUT.S` `v_show_c` draws through the retained `mouse_buffer`.
Ordinary showing does not install a mouse form again. Exec retains its guards,
copied targets and physical grant because other Tasks can preempt the caller.

## Focused development checks

The optimized production-body device fixture now passes **42 assertions**.
The preceding 25 hide/form/busy/fault cases remain. New cases cover showing and
reapplying the same built-in without copying irrelevant payload, a changed
built-in following its original installation path, and a late custom-form
publication after the kind-only snapshot. Completion acknowledges the captured
revision and the later apply installs the new custom form.

Only flush/cursor hardware is substituted in that small fixture; its Task
guards execute through Exec. A loaded MGVIEW down/up pair checks real physical
ownership and pixels. It reuses the APP and unaffected C objects, recompiles
only `gem-vbxe.c`, relinks the provider and rebuilds the native fixture. No QED,
Counter, catalog, geometry run, demo refresh or release matrix is involved.

The loaded pair passes exact viewport and settled full-scanout pixels, one
viewport copy and exposed-row draw per action, no repaint fallback, unchanged
pointer position, three Process lifetimes, ownership/heap restoration and
stack/domain guards. Host checks pass **740 tests, four skipped**. The native
cursor-policy fixture is not rerun because that code is unchanged in this slice.

## Measured result

The same passive mouse observer, document, viewport, clipped pointer at `(639,0)`,
ROM and emulator are used before and after. Inclusive routine measurements
overlap; Task CPU includes bus stalls and gateway/scheduler continuation work.

| M_ON | Down before | Down after | Up before | Up after |
| --- | ---: | ---: | ---: | ---: |
| Viewer CPU | 5.297 ms | **4.281 ms** | 5.301 ms | **4.282 ms** |
| Elapsed | 6.398 ms | **5.160 ms** | 6.444 ms | **5.160 ms** |
| Full form copies | 1 | **0** | 1 | **0** |
| Recipient selections | 1 | **1** | 1 | **1** |
| Forbid/Permit pairs | 13 | **13** | 13 | **13** |
| Cursor submissions / BCBs | 1 / 3 | **1 / 3** | 1 / 3 | **1 / 3** |

Device-apply CPU falls from **2.844/2.836 to 1.828/1.832 ms**. The surrounding
selection, coordination and completion paths remain separate work. Hiding still
has no form-copy or recipient-selection call and restores through one BCB.
Both public mouse calls return success. Display grants, fences and total raw
submission counts per scroll are unchanged.

Complete-viewport observations remain about **120.28/120.62 ms**. These two PAL
samples establish the local reduction in the observed show calls; they do not
establish an end-to-end latency gain or a distribution over positions/forms.

The generated bank-zero budget, runtime reservations and Task pools match the
preceding fixture. Added reserved bank-zero bytes: **0 fixed, root, kernel,
idle and per public Task**, including guards, alignment and unused capacity.
C direct-page workspace remains **23 bytes**. No new production static storage
or scratch capacity is added. These development checks do not qualify the hosted
system.

