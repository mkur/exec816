# Window gadgets implementation plan

[Design note](window-gadgets-design.md) · [GEM integration](README.md)

Status: implementation in progress.

| Slice | Change | Development gate |
| --- | --- | --- |
| WG1 | Generated constants/layouts, kind-aware work geometry, Layers bounds changes, slider fields and complete frame rendering | Host/generator checks, focused shared-layout probes, optimized window API/geometry cases |
| WG2 | Size, thumb, arrow and track gestures using existing capture and GUI messages | Physical request/acknowledgment, cancellation, clipping/pixel checks and cleanup |

Commit each executable passing slice. Keep current fixed-window behavior and
native console geometry. Rebuild all shared-layout consumers together; do not
retain an older protocol. Record upper data/heap, frame work and stack margins
separately from the required **zero fixed/per-Task/private-idle bank-zero delta**.

WG1 edits `abi/aes-server.json`, `abi/desktop.json` and their generators,
`AESWINDOW`, `AESWINDOWSTATE`, caller window bindings, `DESKGEOMETRY`, Layers
and frame composition. Cache thumb pixels when geometry or slider state changes.
Extend the existing window fixture rather than creating another desktop engine.

WG2 extends the present gesture continuation. Publish requests after release,
without holding scene ownership across the caller wait. Preserve top-first,
loss/Escape and close/retirement handling. Add independent expected geometry
and physical observations to the window test, plus a bounded frame pixel check.

Update the AES/desktop contracts and indexes as behavior lands. Record actual
tests and limits in `docs/history/window-gadgets.md` with compact evidence in
`docs/development/`. Packaging follows the Files and editable-dialog milestones
so the distributed desktop includes useful callers of the new facilities.
