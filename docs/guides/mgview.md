# Original MagiC text viewer

[Guides](README.md) · [Port source](../../ports/magic/mgview/README.md) ·
[Development evidence](../history/mgview-port.md)

In Terminal, run:

```text
RUN C:MGVIEW.APP SYS:MGVIEW.TXT
```

This is the original MagiC MGVIEW application rebuilt for Exec. The existing
Text application remains the default for TXT associations. Running MGVIEW without
arguments exits cleanly; the original helper has no file-selector dialog.

Use cursor keys or the horizontal/vertical scroll gadgets. The original GEM
Home/End and page keycodes are also handled when supplied by the keyboard map.
Digits 0–9 select tab width; 0 displays literal tabs. Ctrl-W cycles the viewer's
documents, Ctrl-U closes one and Ctrl-Q quits. Window move, resize and
full/previous restore work through the ordinary GEM controls. Ctrl-close closes
all documents. Several command-line paths open several windows in one
registration, subject to shared capacity.

The bundled sample is byte-preserved ASCII with CRLF lines. The port also accepts
LF, CR and an unterminated final line. Native ATASCII files use a different
encoding; MGVIEW does not convert them. Embedded NUL becomes a space and displayed
lines are limited to the original 272 columns.

Each file is limited to 65,519 bytes and 16,380 indexed lines, subject to available
memory. Filenames retain the original 127-byte limit; the common command-tail
limit is 255 bytes. Native volume aliases and inherited relative paths apply.
The desktop has four AES registrations and six windows: Desktop and Terminal
leave room for MGVIEW and one Counter. Close unused applications/windows when
capacity is exhausted.

For a small coexistence example, start Counter from the Desk menu and run MGVIEW
from Terminal. Its event loop sleeps until keyboard or window input arrives.
Painting and copy scrolling hold UPDATE while other Tasks retain normal
preemption. The port adds no Task or bank-zero reservation.

Grow/shrink animations, VA_START/AV_STARTED, drag/drop pipes, desktop process
reuse, iconify/uniconify, extra fonts and automatic TXT reassociation are outside
this delivery; the donor's iconify callbacks remain empty.
The development checks cover original-source parsing, loading, scrolling and
ordinary interaction beside Counter; they do not establish release qualification
or a normalized speed comparison with MagiC.

Build just the application with:

```sh
python3 tools/build_mgview.py --output build/mgview
```

The original sources, hashes, licence, native patch and build recipe are retained
under `ports/magic/mgview/`. See the execution record for the small check commands
and paired MagiC/Exec baseline.
