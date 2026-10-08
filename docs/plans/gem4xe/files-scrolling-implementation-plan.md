# Files scrolling implementation plan

[Design note](files-scrolling-design.md) · [GEM integration](README.md)

Status: planned; follows WG1–WG2.

1. **FS1 — Snapshot and adaptive view.** Replace the eight-entry page state with
   a bounded directory snapshot, retained selection and sixteen reusable rows.
   Update the RSC source and generated fixture expectations. Add size/arrow/slider
   handling and remove the obsolete Next-page path. Commit after focused checks.
2. **FS2 — Desktop integration.** Exercise physical scrolling/resizing and
   application acknowledgment, pixel repair with overlapping windows, refresh
   selection, launcher and shutdown. Update current documentation and record
   optimized emitted-code evidence before committing.

Use the existing `Browser` application and existing drawing/message APIs; no
new generic list framework. Development observers should use exported field
offsets instead of growing the set of unexplained hard-coded offsets. Changes
to observation metadata do not create a public application ABI.

Run the host suite and affected resource/application checks. Keep guards and
heap-return assertions. Report zero fixed/per-Task/private-idle bank-zero
reservation change, upper memory and measured stack margin for each slice.
The final demo refresh follows the dialog milestone and always includes OF816.
