# CG2: icon directories at 640×240

[Roadmap](../../roadmap.md#colour-gem-desktop-roadmap) · [Plan](colour-files-plan.md)

Extend Files in place. Keep its 256-entry snapshot, reusable visible OBJECTs,
navigation, editing and DOS helpers. An icon view lays out compact 104×40 cells;
list view retains twelve-pixel rows. Resize computes the column/row capacity
once, bounded by the existing visible-object pool. Scrolling advances grid rows
and selection exposes its cell. Repaint the old/new selection only; directory
changes and view changes redraw the work area. Use three compiled stock icon
planes with per-cell labels and ICONBLKs, avoiding one bitmap allocation per file.

Menus add View choices for Icons/List and Name/Directory order, using standard
`menu_icheck`. A directory information line reports total file bytes and items;
the title shows the path. Standard INFO/WF_INFO and FULLER/WM_FULLED extend the
existing frame/gesture pipeline. The application remembers restore bounds and
acknowledges full-size requests. Horizontal scrolling is unnecessary for a grid
that reflows or the existing clipped-name list; its gadgets remain deferred.

Use 32×20 bitmap images plus the 8-pixel label in a 32-pixel OBJECT. This
keeps each icon update in the existing one-unit widget path; a 36-pixel object
would otherwise need three 16-row strips. The 40-pixel grid pitch keeps spacing.

Double-clicks use capture-time button transitions, their Exec tick and a small
spatial tolerance (four pixels per axis, 25 captured VBI ticks: 500ms PAL /
417ms NTSC). Keep immediate first-click feedback: requests for up to two
clicks return each accepted edge with a count of one or two, rather than waiting
to see whether a second press will arrive. This is a deliberate latency-oriented
departure from delayed GEM click aggregation. The application opens on count two
only when the same selected object receives a completed press/release. Loss,
native gestures, a different window and an expired interval reset the sequence.
No extra event queue, polling timer or signal is needed.

Correct tree and handle use remains the caller's responsibility. Resource
admission remains cold. New geometry uses shared generated constants. Store
labels, information strings and icon state in upper memory; add no Task, bank-zero
reservation or framebuffer. Actual stack margins and code/data costs are measured
before packaging. The existing Files launch lifetime remains until CG4.
