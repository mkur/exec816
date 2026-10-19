# EDX development port

[Documentation home](../README.md) · [Guest contract](../reference/sdx-services.md) · [Input audit](sdx-edx-audit.json) · [Measured evidence](sdx-edx.json)

The opt-in SDX personality admits the exact EDX.COM from the SHA-pinned SDX 4.51
Toolkit. Its original 6502 code runs in the existing private bank and emulation
context. This is development support for a pinned application, not a general
SDX environment. The earlier audit records original-system evidence separately.

`_RAWCON` binds six functions to an application-owned ATASCII cell buffer. Reads
and all four scrolls operate on that buffer. Dirty rows are sent through public
console requests before keyboard input. The implementation uses the owned DOS
console endpoint; it does not borrow the console worker's private model or open
a competing device binding. Geometry remains fixed for the invocation.

`DOS.ConsoleIO` exposes reusable mode, positioned cell output and scan input to
ordinary native Tasks. Mode changes share the write FIFO. Scan reads share the
existing read ownership and preserve Shift/Control. They bypass cooked editing;
foreground BREAK keeps its existing cancellation route. Retirement restores the
native console mode, including after cancellation. A caller must retain its
buffer until completion. Loader writable bindings now include usable Task stack
payloads, while excluding stack guards and interrupt headroom.

Text mode maps ATASCII directly to screen codes. The bitmap renderer builds
separate even/odd font masks from the pinned OS font, including graphics and
inverse glyphs. It uses the existing bounded text uploader and desktop backing
surface. The GEM font remains available for ordinary native console output.
EDX draws its own inverse caret. An identity-checked bell patch replaces hardware-alias writes with RTS,
preventing guest document RAM corruption. A second patch relocates the absolute
indirect keyboard-dispatch operand to the owning guest D+$87: unlike direct-page
instructions, JMP (absolute) does not add D on the 65816. The fixup preserves
the original tail jump and caller return address.

Fixed, per-Task and private-idle bank-zero reservation changes are **zero bytes**.
Each SDX Session grows from 2,252 to 2,290 bytes (+38), including its row damage
map; heap rounding raises the allocation by 40 bytes. The EDX screen adds
width×height upper-RAM bytes rounded to eight, at most 2,400. The bitmap font
reservation grows by 20,480 VRAM bytes (18,432 populated, including both X
parities). No new Task, stack, direct page or I/O queue is reserved.

The emitted checks are reproducible with:

```sh
python3 tools/prepare_sdx_inputs.py --nomarch /path/to/nomarch
python3 tools/test_sdx_edx.py --output build/sdx-edx/text
python3 tools/test_sdx_edx.py --bitmap --output build/sdx-edx/bitmap
python3 tools/test_console_cells.py --case raw --output build/sdx-edx/console-raw
python3 tools/test_console_cells.py --case opt --output build/sdx-edx/console-opt
python3 tools/test_sdx_arc.py --group a1 --output build/sdx-edx/arc
```

The EDX fixture uses physical keyboard scans to open a file, move to end of
line, insert X, save, exit, reopen and repeat in the second guest slot, checking exact saved bytes and
resource retirement, then cancels a third foreground launch with physical BREAK.
A blank launch saves a new file containing inverse semigraphics and lowercase
text. Caps transitions and Control+Shift qualifiers are checked while inverse
is active. The pinned bridge lacks an INVERSE key alias, so these extra cases
initialize the guest INVFLG at a protected checkpoint; the other keys use actual
POKEY matrix transitions. This instrumentation is not interrupt qualification.
The bitmap fixture also compares the editor's pixels with
an independent OS-font raster. Console bridge checks cover all cell byte values,
local buffers, invalid mode/span requests, successive scan reads and endpoint
ownership in raw and optimized builds. ARC checks include empty and NULL command
lines, listing, overlay failures and successful recovery. Build-local JSON
records retain the actual results, compiler, ROM, emulator and memory map.

These development checks do not qualify every EDX command, maximum document,
filesystem failure, concurrent editor or physical machine. Audible bell, live
resize and Atari HELP-key qualifiers are unsupported. File bytes are preserved;
use ATASCII EOL ($9B) for normal EDX documents. Saving uses ordinary native
truncate/write/close semantics, without atomic replacement or a power-loss
promise. Do not resize an active editor's console.
