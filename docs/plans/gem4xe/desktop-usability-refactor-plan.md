# Desktop usability refactor plan

[GEM plans](README.md) · [Current desktop behaviour](../../reference/aes.md)

Status: all five items implemented and development-checked. See the
[implementation record](../../history/desktop-usability.md) for executable
checks, memory costs and the refreshed OF816 demo. Iconification remains a
separate design and implementation plan.

## 1 Files default grid

Show four columns and four complete rows of icons by default: sixteen visible
items. Tighten excess spacing and modestly enlarge the default folder window
if needed. Preserve readable filenames, the top summary and scroll controls
within the 640×240 desktop. Retain adaptive layout when the user resizes a
window; the default target does not impose four columns on smaller windows.

## 2 RAM desktop icon

Expose the existing `RAM:` filesystem alongside `SYS:` and `WORK:` with a
distinct RAM-disk icon in the current restrained palette. Double-click opens
its folder window, and it is available as a writable copy destination through
the existing file-operation flow. Adjust desktop icon spacing or placement
to fit the additional icon within the screen.

## 3 Compact contextual delete confirmation

Replace the current full-folder-window confirmation with a small framed
dialog over its owning folder. Leave out scrollbars and resize controls.
Keep other applications usable while the confirmation is pending, and
restore the folder view and focus when it finishes.

- For a single file, ask `Delete file LONG.TXT?` using the selected name.
- For multiple selections, show the file and folder counts.
- Use `Delete` and `Cancel` buttons. Keep Cancel as the keyboard default,
  indicated by an outline; reserve the inverted state for an actual press.
- Show the empty-folder restriction only when folders are selected. Ensure
  the wording and selected names fit without the current clipped heading.
- Report `Folder is not empty` when that operation fails for a nonempty
  directory, using the existing DOS result rather than adding a descendant
  scan before every deletion.

The former heading, `Delete (empty folders only)?`, was shared even by ordinary
file selections. It described the retained limitation: one `DeleteFile` call
per selected entry, supporting files and empty directories. Recursive
deletion is a separate functional task and is outside this presentation
change. See the [current deletion contract](../../reference/aes.md) and
[DOS operations](../../reference/dos.md).

Use classic GEM confirmation forms as the visual reference while preserving
Exec816 multitasking. The Atari desktop's Delete Folders/Items confirmation
is described in the [Falcon manual, pages 5-14–5-15](https://www.atariworld.org/files/docs/Atari_Falcon030_Manual_en.pdf#page=116).
Reuse existing GEM objects, dialog support and event handling; avoid a new
dialog framework or additional validation layers.

## 4 Shorter Shell name

Rename the displayed `Exec816 Shell` title to `Shell`. Use the same name in
the window title, active-application label and Windows menu entry wherever
the shell is identified.

## 5 Smaller left desktop margin

Move the desktop icon column slightly left to reclaim the excess padding at
the screen edge. Move icons and their centred labels together, keeping enough
margin for the widest label and its selection outline to remain fully visible.
Coordinate the placement with the additional `RAM:` icon from item 2.

## Validation

Check the 4×4 default grid and resized layouts, opening and copying to `RAM:`,
and single-file, multiple-selection, empty-folder and nonempty-folder delete
cases. Check Cancel, keyboard activation, readable text, exposure restoration
and continued interaction with other applications. Check consistent `Shell`
naming across the title and menus, and check that the shifted desktop column
keeps labels and selection outlines visible with matching click targets.
Use focused development
checks and report any reserved bank-zero change; no new reservation is
proposed by this task list.
