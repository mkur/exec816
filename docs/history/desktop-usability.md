# Desktop usability

[Implementation plan](../plans/gem4xe/desktop-usability-refactor-plan.md) ·
[Current desktop contract](../reference/aes.md#small-gem-desktop) ·
[Development evidence](../development/desktop-usability.json)

All five planned refinements are implemented. New folder windows use 456×196
outer bounds and a 432×164 work area, fitting four columns and four complete
rows with the existing sixteen visible objects. Resizing remains adaptive.
`RAM:` opens the existing writable RAM filesystem. Its memory-chip artwork
uses the established palette and CICON format. Eight desktop icons fit at a
28-pixel vertical pitch; their centres move twelve pixels left. The widest
label still has four pixels of left margin. The native console window is now
named `Shell`, also used by the active caption and Windows menu.

Delete confirmation uses the existing seven-object form as a small framed
overlay within its owning folder. It adds no window slot or event loop. A
single name appears below `Delete file?` or `Delete folder?`; multiple selections
show file/folder counts. Only folder selections show `Empty folders only`.
Cancel is the outlined default, with an underline for keyboard focus; inversion
indicates a held mouse press. Releasing outside clears the press. Tab/Space
activates the focused button, Return defaults to Cancel, and Escape dismisses
without navigating. Existing DOS error 216 produces `Folder is not empty`.
There is no recursive deletion or pre-delete descendant scan.

The folder remains visible behind the overlay and redraws on exposure. Other
applications remain usable. The same object pool is restored before subsequent
copy/replace/progress forms. Button focus and press updates draw only the
affected buttons. Other dialog types retain their previous presentation;
iconification remains outside this work.

## Development checks

Both focused walkthroughs passed against the same extracted OF816 ZIP:

- `--usability`: 4×4 grid and desktop bounds; physical RAM icon opening; GUI copy
  into RAM followed by loaded `CMP`; default Cancel, held press and outside
  release, Escape, Tab/Space deletion; mixed file/empty-folder deletion;
  nonempty-folder failure; resized and list-view confirmations. Counter keeps
  ticking and Shell accepts `TASKS` while confirmation is pending. Switching
  back restores the overlay correctly without consuming another window slot.
- `--compact-files`: independent full-scene pixels for icon/list selection,
  resize, full/restore, scrolling, exposure and close; Parent/Escape and Refresh
  menu/keyboard paths; root no-op, virtual parent, upward reveal and parent
  exclusion from mutation operations.

Both complete loaded `HELLO` and orderly `EXIT` with intact stack/domain guards.
The minimum observed ordinary-Task headroom is 167 bytes above the guarded floor;
idle headroom is 121 bytes. These are observations from the selected runs, not
worst-case stack bounds. Emitted application layout probes match the host
observers. Host checks pass 455 tests with four existing skips. No compiler
suite, full qualification matrix or real-hardware test was run.

## Memory and distribution

| Storage | Bytes | Change from the compact Counter baseline |
| --- | ---: | ---: |
| Desktop APP file | 74,816 | +3,987 |
| Files APP file | 52,806 | +3,858 |
| DESKTOP.RSC | 7,606 | +548 |
| Desktop record | 2,414 | +62 upper-memory bytes |
| Browser record | 4,041 | 0 |
| Folder OBJECT pool | 552 | 0 |

Fixed, per-Task and idle reserved bank-zero changes are all **zero**, counting
guards, alignment and unused capacity. Generated reservation, Task-pool and
bank-zero-budget records match the preceding compact Counter demo. No Task,
signal, timer, VRAM reservation or public ABI is added. The selection bitmap,
256-entry snapshot capacity and 16 KiB copy buffer are unchanged.

The resident image is rebuilt for the Shell title. Packaging uses
`tools/build_demo.py`, including its monitor refresh for the final application
binaries. The compiler revision remains the pinned
`81dd7dc53377c772602cc09992bdf2a694b4a43b`, using the release host compiler at
that same revision. OF816, five-second autoboot, the pinned AltirraOS ROM,
matching system/WORK disks, guide, notices and checksums are included.

The 606,184-byte ZIP contains 23 distribution files, with intermediates and
test output kept outside it. Exact inputs, hashes, machine configuration and
selected results are retained in the linked evidence. Launch from the repository:

```sh
./build/desktop-usability/demo/launch-altirra.command
```

The distribution is `build/desktop-usability/demo/exec816-demo.zip`.
