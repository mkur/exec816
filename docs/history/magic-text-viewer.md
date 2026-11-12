# Original Text Viewer on MagiC

[Build and launch](../guides/atari-st-reference.md#original-text-viewer-on-magic) ·
[Development evidence](../development/magic-text-viewer.json)

This first port compiles the original `examples/gem-text/text.c` and
`document.c` unchanged for the 68000. It keeps the existing event loop,
incremental replacement, line indexing, row formatting, visible-rectangle
clipping, four-row UPDATE sections and 1 KiB reads. The path helpers are extracted
verbatim from `c/calypsi/file-list.c`; its unused directory scanner is not ported.

The reference uses the pinned MagiC release, Hatari, EmuTOS and TOS/libc SDK from
`toolchain/atari-st-reference.json`. The private desktop launches the viewer and
Counter with MagiC's parallel `shel_write` mode. Counter's application body is
unchanged; its reference startup places the second window below the viewer.
Each process links its own AES context and VDI parameter arrays.
The resident launcher installs the release's US primary keyboard tables through
`Keytbl`, retaining their 384 bytes for the lifetime of both applications.

`text-platform.c` adapts allocation, read-only file handles, metadata and IoErr
to TOS/libc. It uses actual MagiC UPDATE acquisition and software-cursor handling.
The original Exec presentation-completion notifications and preserve request are
inapplicable to this framebuffer/window arrangement, and its extended diagnostic
channel is unavailable. Menu geometry and VDI font selection are established in
the adapter. Shutdown explicitly removes the menu, closes/deletes the window and
closes the virtual workstation. The retained resource report counts adapted
viewer allocations, handles and locks; it is not a complete MagiC heap census.

Documents live on a real read-only FAT12 floppy A:. Hatari's host C: continues to
provide program loading and observation logs, but cannot supply every directory
operation MagiC uses internally. Selecting native A: both in the viewer's paths
and as its current drive makes the original MagiC file selector usable. The
keyboard test waits for the dialog's actual framebuffer before typing; its
Cancel shortcut is Undo. Escape clears the selector field and cancels a pending
load only after returning to the viewer. No kernel, filesystem or graphics driver
is patched.

## Development checks

`python3 tools/prepare_magic_text.py --offline --run` runs emitted optimized
68000 code. It checks the MagX cookie and independent application identities,
loads the 56,746-byte/901-line fixture, drives page and line keys, and compares
the old second text row with the new first row at the pixel level. It opens a
44-byte/two-line replacement through the actual selector, checks Cancel, missing
file and size-limit preservation, cancels a new read, and closes the viewer.
Counter continues updating inactive-window pixels and resumes after viewer exit.
Final adapted allocations, file handles, metadata locks, UPDATE depth, menu,
window and VDI handle all retire.

The existing two-Counter capture is also rerun because the port extends the
shared ST bindings. Its unchanged application bodies retain independent progress,
inactive painting and changed digit pixels. The focused host Counter and shared
reference checks pass. The JSON record retains exact inputs and execution scope.

This is development evidence. It does not establish latency, throughput,
arbitrary occlusion/drag/resize behavior, physical ST operation or Exec hosted
qualification. The first port retains the viewer's 640×240 sizing assumptions
despite the reference's 640×400 display. The OF816 demo is not rebuilt, and no
Exec runtime, ABI, pool or drawing grant changes. Fixed, root/kernel, private idle
and per-public-Task reserved bank-zero deltas are **0 bytes**, including guards,
alignment and unused capacity; Exec VRAM reservations also change by **0 bytes**.
