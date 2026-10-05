# Hosted VDI renderer backend

[Port index](../README.md) · [Service protocol](../service/README.md) ·
[Display ownership](../../../docs/reference/display.md)

`GemVbxeBackend` connects the supervised G2 service to the selected GEM primitives
and the bounded AltirraOS VBXE driver. Pass its address to `GemServiceStart`.
There is one renderer instance per linked image; only the retained service worker
may enter it. This remains a private hosted interface, with no kernel selector.
The launcher establishes the pinned inactive display baseline and installs the
C display bridge before starting the service. Close and stop text services before
opening graphics, as required by the display contract.

Open acquires VBXE, binds the fixed device, initializes attributes and the GEM
palette, expands the linked font, clears the screen and enables presentation.
Its 57-word reply advertises the frozen subset. Each command reaches the selected
VDI dispatcher only after the service validates the entire batch. The service
fences every command before counting it or returning its outputs. Close drains
work, unbinds the renderer and restores the OS display through the G3 driver.

The donor device's window pointers refer to a private 4,096-byte upper-RAM staging
page. Changing pages flushes the previous page through checked VRAM transfers;
issuing a blit flushes and invalidates it first. The driver closes MEMAC before
returning. The selected fill, glyph expansion and clipped-raster algorithms remain
upstream code. The adapter queues records in one 4,096-byte upper-RAM construction arena.
It drains at 64 records or 8,192 estimated bus accesses, before CPU staging
reads/writes or scratch reuse, and at the command's final fence. `blit_pending`
reports retained work; `blit_start` and `blit_run` both complete the bounded list
synchronously. Long rectangles are split into at most sixteen-row chunks,
further reduced by the work budget. Synchronous lists leave VBXE IRQs disabled;
the asynchronous scroll path below owns completion IRQs. No second aperture is enabled.
The driver validates each full list and inserts chaining itself. A failed
submission latches the command fault; a partially flushed VDI command is not
reported complete.

`gem-drawing.h` exposes the same device, font and palette through ordinary
`DISPLAY_*` calls. `GemDrawingOpen` returns the existing 57-word workstation
description; fill uses half-open pixel bounds, and text uses top-left 8×8 cells
with explicit foreground/background pens. Text must fit completely on screen.
The CPU string must not overlap the mapped `$8000–$8FFF` aperture.
An empty valid rectangle or string does not draw. Every successful operation
in this original synchronous group fences before returning. Build with `GEM_DRAWING_ONLY` to omit service policy while sharing drawing and pointer
policy; the caller must own the display. There remains one drawing session per
image, shared with the service when linked together. This is a C interface;
calling it from Action! requires the separately tested language bridge in B6.

Copy, Fill, Text and Fence each check the display owner once at public entry.
Their internal drain, transfer and fence helpers reuse admission within that
invocation, retaining full driver argument/list validation. Every independent
service command, cursor, fence and close callback also admits its owner before
mutating shared renderer state. Open initializes cursor state only after acquiring
the display. Admission never survives a return or becomes a session-wide cache.

`GemDrawingCopy` fences preceding drawing and calls the shared
[`VbxeCopyRect`](../../../docs/reference/display.md#bitmap-rectangle-copies)
operation. It accepts explicit VRAM surfaces and preserves opaque pixels in
overlapping copies. The descriptor remains immutable until the call returns.
The GEM service does not advertise an additional VDI opcode for this operation.

`GemDrawingScrollStart`, `GemDrawingCopyStart` and `GemDrawingPoll` expose the driver's
[asynchronous screen scroll](../../../docs/reference/display.md#asynchronous-screen-scrolling)
with a logical GEM background pen. Source Y minus destination Y selects an
upward shift in multiples of eight pixels and the matching exposed fill height.
Start fences prior queued work, validates
the complete copy/fill and returns its ID after launch. Poll performs one
completion check. A second start returns BUSY until completion is consumed.
Ordinary Copy/Fill/Text/Fence and Close retain synchronous completion and finish
pending hardware work before dependent access. The caller remains the sole
drawing owner; this adds no renderer Task or service opcode.
`GemDrawingCompletionMask` exposes the display driver's owned signal. A retained
VBXE IRQ producer and independent sixteen-VBI-tick watchdog wake that owner;
it then calls Poll to consume the matching durable result. The driver releases
the binding and signal only after settling DMA. See the
[display contract](../../../docs/reference/display.md).

Fully visible nonzero-ink glyphs use one nibble-stencil command. Hardware-zero
ink retains the inverse-mask AND path, and clipped glyphs retain the staged
pixel path. Empty glyphs skip ink after the opaque background fill. Private
preinitialized records avoid repeated generic rectangle setup, while submission
still validates the whole list. The maintained fourth extraction patch supplies
these changes. The 256-byte ink cache and 21-byte template fit inside the
existing C bank reservations; B2 adds no bank-zero or VRAM reservation.

Even-X `GemDrawingText` runs use a driver-generated list instead of repeating
the generic device and list-validation path for every glyph. The driver checks
the entire CPU string, screen rectangle, colours and 256-glyph atlas before
submitting any prefix. A private native uploader writes one background fill and
up to 32 fixed 8×8 glyph records directly into the existing command arena. This
uses at most 33 records, 693 arena bytes and 5,120 blitter bus accesses per batch,
within the existing limits. Every field, including chain termination, is written
anew; hardware-zero ink uses inverse-mask AND and other ink uses the stencil.
The operation fences every batch before reusing the arena or returning.

`GemDrawingTextFill` draws a nonempty even-X text run followed by a small fill
rectangle, with one owner admission. The rectangle requires even X and width,
nonzero dimensions, screen bounds and at most 3,072 pixels. All arguments are
checked before drawing; the fill is appended only to the final text batch.
That list uses at most 34 records, 714 arena bytes and 8,192 bus accesses within
the existing work budget. The console uses this synchronous operation for its
last dirty span and new underline caret, avoiding a second call and launch.

The fifth extraction patch connects the ordinary text entry to this path. Odd-X
text and VDI opcode 8 retain their existing device glyph path. Public raw-list
submission still validates every supplied record. No cached admission, new Task,
bank-zero reservation, extra arena or completion API is introduced. The uploader
uses call-clobbered Task DP scratch `$80–$99`; its 25-byte packet layout is checked
through emitted C, and its source reads carry across CPU bank boundaries.
The uploader packet grows by nine bytes on the existing Task stack. Reserved
bank-zero storage, per-Task stacks, DP, guards and alignment remain unchanged
(0 bytes).

Because donor callbacks return void, the backend latches the first hardware
error. Further callbacks cannot touch hardware, and the service fence reports
`GEM_DEVICE_FAULT`. The service preserves only the completed prefix, invalidates
the session and closes it. Recovery that has already released the display is
safe to close again at the backend boundary. Failure to quiesce remains the
G3 reset-required path, which never returns a normal reply. A later open rebuilds
the complete font, palette and default workstation state.

The patch series separates storage/subset adaptation, wide-coordinate arithmetic
fixes, and the hosted window substitution. Signed 16-bit inputs use wide text
placement and Bresenham error/count calculations. Text cells wholly outside the
screen are rejected before narrowing to device coordinates. Lines preserve the
original pixel phase while stepping at most 65,536 points per segment. This is
bounded correctness, not a frame-rate guarantee.

G4 reserves zero additional bank-zero bytes: fixed, each public Task, and idle.
The existing whole C code/data banks remain reserved (131,072 bytes including
unused capacity); staging consumes 4,096 bytes within the data bank. B1 adds 4,096 construction bytes inside the existing data bank. VRAM now
reserves 111,872 bytes including padding: screen 81,920, XDL 256, BCB 4,096,
font masks 20,480 (18,432 used), glyph scratch 4,096 and cursor storage 1,280. These reservations are
separate from CPU RAM. The test's 76,800-byte CPU readback allocation, font copy
and borrowed observer scratch are diagnostics, not production renderer storage.

Run the development corpus with:

```sh
python3 tools/test_gem_render.py --mode raw --output build/gem-vdi/g4-raw
python3 tools/test_gem_render.py --mode opt --output build/gem-vdi/g4-opt
python3 tools/test_gem_drawing.py --mode opt --output build/bitmap-console/drawing
```

Use `--production-control` in a separate directory for original hardware status
reads; snapshot/guard observers remain explicit test instrumentation. `--replay`
reuses that directory's emitted image. Results include byte-for-byte agreement
with the pinned upstream model and an independent pixel model, all glyphs/pens,
clipping and coordinate limits, packet bank boundaries, invalid-batch atomicity,
completed-prefix fault handling, reopening, font/palette data and visible scanout.
A real NMI is observed inside selected font code. The bulk CPU readback observer
borrows and restores unused `$6000–$6FFF` and the profile's diagnostic code scratch
at a paused NMI entry; IRQ/NMI are masked for that copy, so it does not qualify
preemption. Normal rendering remains preemptible. Stack peaks are measured paths,
not compiler-enforced whole-program bounds.

[G4 evidence](../../../docs/development/gem-vdi-g4.json) records the executed
scope. Combining this renderer with a computing peer, physical SDFS traffic,
console transitions and the broader service failure matrix is recorded by G5.
The [input implementation](../../../docs/history/gem-input.md) adds a supervised
keyboard application and renderer-owned cursor. The fixed arrow uses 256-byte
save and both even/odd AND/OR planes at `$37000–$374FF`. Hide/restore
precedes each scene mutation; fence saves and redraws without changing VDI
attributes. CPU staging is reused only after flushing; glyph scratch stays separate.
I5 checks exact odd/even/edge pixels, stationary redraws, reopen and each fault phase.
AES, physical mouse input, virtual workstations, external fonts, raster copies
and dynamic loading remain unsupported. The standard OF816 demo is separate.
