# AES window application implementation plan

[GEM integration](README.md) · [Design note](aes-window-app-design.md) ·
[Current AES contract](../../reference/aes.md) · [Current display contract](../../reference/display.md)

Status: implemented, 2026-10-07. WA1–WA6 pass development checks;
PI4/HY4 remain open. See the [execution record](../../history/aes-windows.md).

Implement the design in six executable slices, committing after each passing
slice. The result is a resident C counter using ordinary GEM window, VDI and
event calls, followed by a two-instance/native-shell proof and an OF816 demo.
The counter application contains no native desktop drawing protocol.

Use `dcce1b3`, the completed mouse-acceleration work, as the source starting
point and PI3 as the accepted usability baseline. There is no baseline-only
slice and no prerequisite to close PI4/HY4. Keep their existing limits and open
status; this milestone adds desktop functionality.

## Rules for every slice

- Follow the [platform contract](../../reference/platform.md),
  [code style](../../contributing/style.md) and
  [development testing policy](../../contributing/testing.md). Pin the actual
  compiler, C toolchain, ROM and emulator configuration in evidence; document
  local overrides. Do not edit the GEM4XE donor checkout.
- Generate changed Action!/C/assembly ABI definitions from machine-readable
  inputs and rebuild affected callers together. Keep one current interface;
  update reference pages only for behavior implemented by that slice.
- Validate resources at admission and preserve necessary state/ownership
  checks. Do not add repeated hot-path pointer, list or geometry validation.
  Keep driver arbitration in DISPLAY/the adapter and window policy in AES;
  no new kernel selector, priority policy, timer or server Task is planned.
- Report reserved bank-zero delta: target **0 fixed + 0 per public Task + 0
  idle bytes**, including guards, alignment and unused capacity. Report upper
  live/reserved bytes, linked banks, Task slots and requested/measured stacks
  separately. Do not hide a stack-pool enlargement in a build override.
- Run focused host and optimized emitted-code checks. Use small raw/optimized
  cases for changed ABI layouts and C/native bridges; do not duplicate the
  complete GUI workload in raw mode. Interrupt and ownership changes need
  targeted preemption/failure cases. These checks are not full qualification.
- Record evidence under `docs/development` and summarize completed slices in
  a new AES window history page, updating indexes as those files are added.
  Keep large traces, images and intermediates under the development build tree.

## WA1 — Deliver durable GUI messages

Implemented. [Evidence](../../development/aes-windows-wa1.json) covers the GUI
producer, caller delivery, existing messaging/events/registration and both-mode
layout/context probes. Reserved bank-zero delta is zero; four registrations add
368 heap-reserved upper bytes.

Establish the transport before adding window policy.

1. Extend [aes-server.json](../../../abi/aes-server.json), its
   [generator](../../../tools/generate_aes_server.py), private binding records
   and generated layouts for one GUI-only delivery record per registration.
   Preserve all sixteen ordinary `appl_write` records. Define private origin,
   window/open-lifetime metadata and availability separately from GEM words.
2. Extend [aes-messages.c](../../../c/calypsi/aes-messages.c), caller event
   matching and endpoint lifetime handling. Consume GUI records through the
   existing receive port; filter stale GUI lifetimes before freezing readiness,
   recycle through the correct pool and preserve simultaneous message/timer
   semantics. Keep ordinary application messages opaque.
3. Add bounded service pending state and first-pending ordering for redraw,
   close, top and latest move. Publish an immutable record only when available;
   preserve subsequent work independently. Add the atomic recycle-to-service
   wake using the existing directory/service signal and publication holds.
4. Extend cooperative withdrawal/drain for the new record. Neither delete nor
   exit may wait for a message that only the blocked caller could consume.
   Do not allocate delivery storage while posting a close or redraw.

Validation: use the existing [AES runner](../../../tools/test_aes_server.py)
with an emitted service producer and caller. Fill all sixteen ordinary entries,
post GUI work, delay the receiver and verify every pending kind progresses.
Invalidate again while the GUI record is queued; consuming it must not erase
new damage. Cover duplicate coalescing, ordering, recycle/wait races, timer
expiry, close/reopen epochs, exit with queued delivery and partial-init unwind.
Assert no periodic service wake and no message-only call regression.

Exit: bounded GUI delivery survives backpressure without changing ordinary FIFO
capacity or returning event matching to the presenter. No window compatibility
claim yet. Suggested commit: `aes: retain GUI messages until delivery`.

## WA2 — Own GEM windows and hand off redraw work

Implemented. [Evidence](../../development/aes-windows-wa2.json) records window
lifecycle, physical controls, exact outline pixels, visible regions, external
handoff, native regression and ABI checks. Reserved bank-zero delta is zero.

1. Extend the [binding reference manifest](../../../ports/gem4xe/aes-binding-inputs.json)
   and [gem.h](../../../c/include/gem.h) with the selected window calls, fields,
   kinds and messages. Verify the pinned donor declarations, opcode counts,
   signed rectangle conventions and split title pointer. Add named and AESPB
   paths through shared helpers; enlarge the private RPC payload once for the
   required window operations.
2. Add service window records in `lib/aes`, mapping GEM handles to native
   desktop/Layer identities. Implement create/open/close/delete, bounded copied
   titles, top/move, work/current queries and local `wind_calc`. Preserve hidden
   created windows across close; reject unsupported resizing/off-screen geometry
   without mutation. Integrate all remaining-window cleanup into `appl_exit`.
3. Add the external-paint window kind in `lib/desktop` and the explicit damage
   handoff in `lib/display/layers.act`. Generate changed layouts from the
   [Layers](../../../abi/layers.json) and desktop manifests. Complete frame
   drawing and durable work-area invalidation before retiring manager damage;
   never report application pixels painted through ordinary Finish-success.
   Disable app-window copy/move/cache admission explicitly.
4. Publish stable visible work regions and simple query records. Keep Layers
   access in the presenter, enumeration in the caller and snapshots valid under
   `BEG_UPDATE`. Invalidate an iterator after an owner geometry mutation. Convert
   half-open bounds only at the GEM/VDI interfaces.
5. Adapt close/top/title-drag controls to send GEM requests. Commit position and
   stacking only on the app's corresponding call. Preserve native interaction,
   update-lock deferral and already accelerated pointer coordinates.

Validation: extend the [Layers runner](../../../tools/test_layers.py) and
[AES desktop runner](../../../tools/test_aes_desktop.py). Run a C empty-window
client that accepts move/top/close messages. Check reopen, slot exhaustion,
owner exit, full message backpressure, partial/complete occlusion and title
limits. Compare work/border conversions and visible rectangles against an
independent region oracle, including odd pixel positions and zero-area results.
Assert no scene token survives waiting for the app and no damage handoff marks
an app layer eligible for copying. Cover repeated expose/delete while a GUI
record is queued. Preserve native overlap pixels and stack guards.

Exit: ordinary GEM calls control a framed window and deliver redraw obligations;
the application work area is not yet VDI-painted. Suggested commit:
`aes: add application windows and redraw ownership`.

## WA3 — Serialize delegated display access

Implemented. [Evidence](../../development/aes-windows-wa3.json) records two
borrowers, native DMA/pointer contention, exact pixels, both timeout outcomes,
raw/optimized arbitration/context checks and native disk/GUI coexistence.
Bank-zero growth is zero. Native rendering overhead and the revised functional
test hold are recorded explicitly; this does not close PI4/HY4.

This is the ownership gate for direct VDI. Finish it before exposing application
workstation drawing.

1. Extend [display.json](../../../abi/display.json), DISPLAY and the adapter
   with explicit lifetime-owner delegation, access grants, bounded queued
   admission and release. Retain grant owners until revocation completes.
   Define fault/release transitions in the display reference before using them.
   Use existing Exec signaling and short shared-state guards for wait/wake.
2. Route every native renderer entry through the same physical arbiter:
   synchronous and asynchronous drawing, text staging, MEMAC, command-list
   reuse, software cursor, caret, outlines and snapshot work. A native DMA
   submission retains access until its owning presenter completes retirement.
3. Let the presenter try admission without blocking its service loop. Stop new
   conflicting work behind a queued borrower, retire outstanding hardware first
   and signal access changes. Extend AES lock readiness to cover access state;
   do not strand native completion behind an application waiting for admission.
4. Add bounded synchronous borrower operations in a focused C/native fixture.
   Exercise restore/draw/fence/cursor restoration and release between units.
   Keep render state in upper memory and avoid a second physical lease or
   presenter-identity bypass. Coordinate quiescent faults with the lifetime
   owner; do not run presenter teardown as the borrowing Task.

Validation: add focused emitted display tests with two Tasks, forced preemption
at ownership transitions, a delayed borrower, competing native cursor work and
native DMA completion. Assert no overlap of hardware/scratch owners, no lost
wake, bounded waiter progress and complete register/DP restoration. Exercise
revocation while queued, teardown refusal while active, recoverable timeout and
unquiesced reset-required failure. Check native pointer, scrolling and disk
paths after the common arbiter migration. Record maximum owned-unit CPU time
and full stack high-water marks, including bridge and IRQ/NMI reserve.

Exit: shared physical access works independently of GEM drawing. If it requires
waiting for presenter RPC while access is held, or enlarging bank-zero pools,
resolve the design/budget explicitly here. Do not silently substitute per-draw
RPC and declare the direct drawing gate complete. Suggested commit:
`display: serialize delegated renderer access`.

## WA4 — Add private virtual workstations

Implemented. [Evidence](../../development/aes-windows-wa4.json) covers private
workstations, bounded direct drawing, exact pixels, forced preemption, cleanup
and emitted layouts. Both callers fit existing 1 KiB pools with narrow measured
headroom; bank-zero growth is zero.

1. Add `graf_handle`, virtual open/close, the selected attributes, clipping,
   bar and text bindings, with private VDI parameter arrays and a common
   parameter-block dispatcher. Record call counts/defaults in machine-readable
   inputs. Return the full honest workstation inquiry output. Virtual open
   performs no physical open, palette reset or desktop clear.
2. Refactor [hosted-dispatch.inc](../../../ports/gem4xe/hosted/hosted-dispatch.inc)
   and its adapter so the existing rendering backend accepts the admitted
   workstation context. Keep native users on that backend. Select private
   attributes only under physical access; global scratch cannot outlive it.
3. Require update ownership for this initial window drawing profile. Intersect
   the stable visible work region with user clipping for each bounded unit.
   Handle inclusive corners, empty intersections and clipped glyph edges.
   Stream long strings in bounded renderer chunks without silently truncating
   the GEM call; release physical access between chunks and restore context.
4. Return ordinary resource/unsupported/hardware failures through the current
   diagnostic convention. Unwind workstation/grant partial startup and close
   before freeing caller storage. An application never borrows a live stack
   buffer across a completed call.

Validation: two callers alternate distinct pens/clips/text, including preemption
inside backend calls. Compare exact work-area pixels with an independent
expected image and verify frames, occluders and cursor background. Test text
across a chunk boundary, odd-coordinate fills, clip-off, empty clips, unsupported
attributes, failed open and exit without explicit virtual close. Measure both
clients' renderer stack depth and prove they fit the available stack classes
before treating two-instance startup as supported. Assert zero presenter RPCs
for warm attribute and drawing calls, and no ownership unit spanning a complete
large redraw.

Exit: a simple C client directly paints its visible window safely, with isolated
workstation state and measured stack headroom. Suggested commit:
`vdi: add private application workstations`.

## WA5 — Run the counter application through GEM

Implemented. [Evidence](../../development/aes-windows-wa5.json) records two
ordinary GEM counters, exact pixels, physical controls, simultaneous readiness,
partial Task-startup unwind, repeated retirement and separate logical/physical
timing. Existing 1 KiB stacks fit; bank-zero growth is zero.

1. Add a resident C counter example and a separate Exec attachment/startup
   wrapper. Keep the application body restricted to the supported GEM calls.
   Reuse `tools/build_aes_desktop.py` for the emitted fixture; no executable
   loader, resource loader or new application launch service is required.
2. Implement init, title/window/workstation setup and the combined message/timer
   event loop. Handle both returned ready bits, move/top acknowledgments and
   cooperative close. The one-second event wait is a demonstration cadence,
   not a claim of precision clock timing under other messages.
3. Use one redraw helper for `WM_REDRAW` and timer-driven text changes:
   BEG_UPDATE, work query, FIRST/NEXT enumeration, damage intersection, clip,
   fill/text and END_UPDATE. Keep event waits outside all drawing/GUI ownership.
   Keep model updates while covered so exposure renders the latest counter.
4. Unwind every partially completed startup and normal close path. Detach and
   release the Task only after all GUI, delivery, timer and display borrows end.

Validation: emitted end-to-end checks for initial draw, timer update, moved
window, denied/accepted top request, cover/uncover, multiple invalidations while
the app is delayed, simultaneous timer/message readiness and repeated open/exit.
Use exact final framebuffer comparisons and verify the latest model after
exposure. Test allocation/capacity failures without leaked Tasks, ports, records,
locks, windows, grants or workstations. Record logical update-lock duration and
the largest physical access unit separately.

Exit: the example is an ordinary GEM event-loop application rather than a native
retained command client. Suggested commit: `examples: add a GEM counter window`.

## WA6 — Prove coexistence and package the demo

Implemented. [Evidence](../../development/aes-windows-wa6.json) covers the
matched native/counter workload, delayed-client progress, both console repairs,
exact pixels, cleanup, capacity and the extracted OF816 bundle. Bank-zero growth
is zero. Timing and broader compatibility limits remain explicit.

1. Produce an explicit Task/stack/layer admission table for each integration
   scenario. Two counters, native shell and disk/pipeline activity must fit the
   existing eight public slots and stack classes. Replace the native panel in
   the counter demo; exercise panel coexistence separately where needed rather
   than assuming every worker fits at once.
2. Run two differently titled/coloured counter instances. Move/top/close them
   over each other and the scrolling shell, perform the established disk/pipeline
   workload and sustain accelerated pointer input. Delay one app deliberately;
   the other and the service must progress whenever the delayed app owns no
   logical/physical lock. Test orderly service shutdown after client cleanup.
3. Extend the existing timing diagnostics to separate GUI notification delay,
   update-lock wait, physical-access wait, caller drawing CPU and completed
   repaint. Record p50/p95/max and exact pixels for matched native and new loads.
   Investigate new corruption, starvation or hangs here; leave broader latency
   tuning and unchanged PI4/HY4 failures separately recorded.
4. Add an explicit AES-counter selection to [build_demo.py](../../../tools/build_demo.py),
   reusing the production desktop path. Keep the default five-second OF816
   autoboot into the standard shell/prime demo. The optional counter bundle
   includes OF816, matching disk, pinned ROM, licenses, checksums and a short
   guide. Distribute only `exec816-demo.zip`; keep manifests/traces elsewhere.
5. Test the exact extracted ZIP: boot, mount, counter updates, overlap repair,
   physical drag/top/close and disk use. Update current AES/VDI/display/Layers
   references, the application guide, history and roadmap with supported calls,
   measured capacity and remaining limits.

Keep the two pre-existing caret artifacts from the
[mouse-acceleration record](../../history/mouse-acceleration.md) visible in
results. Reproduce them with matched controls if they affect comparison; do not
weaken framebuffer assertions, label a new mismatch pre-existing without
evidence, or describe development checks as hosted qualification.

Exit: two independent GEM applications coexist correctly with native service,
cleanup and the extracted optional demo pass, resource and timing evidence is
recorded, and the documented limited profile matches the executable. Suggested
commit: `demo: package and verify AES window applications`.
