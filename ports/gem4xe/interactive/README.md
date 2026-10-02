# Interactive application

[Port overview](../README.md) ·
[Input implementation plan](../../../docs/plans/gem4xe/input-and-events-implementation-plan.md)

The I4 workload gives the C application and renderer the two existing 2,560-byte
Task pools. Root supervises a cold `D1:DATA.BIN` read. This development launcher
is separate from the G5 computing-peer regression; distribution changes are I7.

The application owns the renderer, its sole client and a reusable keyboard input
lease. Tab cycles a 24-character text field, Count and Exit. Printable keys and
Backspace edit the field; Return activates a button; Escape or BREAK exits.
Count advances the number and the colored indicator. Disk completion leaves the
scene open until explicit exit. There is no AES or physical mouse backend.

`abi/gem-interactive.json` generates the 32-byte control message and 48-byte boot
descriptor for Action! and C. A root-issued nonzero session identifies four
static upper-RAM messages: START/STOP, coalesced progress, DISK_DONE and EXIT.
Each side has two embedded ports sharing one allocated notification bit. Root
creates and retains the application under Forbid; the application retains itself
and root before publishing readiness. Static message declarations explicitly
request even alignment, as required by the Exec message contract.

Root releases console/DOS ownership and authorizes the cold display before START.
The application opens graphics, acquires input and paints the first scene before
replying ready. Failed startup releases its acquired resources before replying.
Exit sets a durable flag and sends the preallocated EXIT message while root can
still be inside DOS. Root settles that call, closes its file, sends DISK_DONE,
collects all its replies, releases its application lease and acknowledges EXIT.
The application settles input and rendering, collects EXIT's reply, and under
Forbid publishes retirement, signals root, releases its final holds and removes
itself. STOP replies acknowledge admission; both exit directions use this same
retirement handshake. The launcher retains all notification storage until then.

A turn drains at most eight input records, eight control messages and one exact
render completion. `GemTryCollect` returns a separate ready flag; an empty port
preserves pending ownership and sequence state. An unexpected message remains
queued and cannot authorize freeing the request. Busy turns yield, and waits
follow observations of every work source without clearing their notifications.

A tile packet has four VDI commands and eight glyphs. Fixed command descriptors
and copied values are written into the owned request before submission. While it
is pending, the application changes only dirty UI state; the next packet captures
that state after collection. Initial painting and longer field redraws span
multiple tiles. The compiler modes remain Calypsi `-O0`/`-O2` and Action! raw/
optimized NIR, without a compiler override.

Calypsi 5.18 emits an incorrect bank relocation for an implicit comparison of a
stored `__far24` pointer with a static symbol. The shared C bridge helper
`ExecSameAddress` normalizes both operands to huge pointers before comparing all
32 bits. `IsListEmpty` also uses it, so embedded upper-bank ports work like heap
ports. Diagnostic probes check equality, a different bank, and a nonzero fourth
byte through emitted code. The helper has no kernel operation or COP selector.

Build with `tools/build_gem_interactive.py --output DIR`, or use
`tools/test_gem_interactive.py --mode raw|opt --output DIR --case keyboard`.
`--replay` uses an existing artifact. Diagnostic resource cases occupy real input
or display ownership, exhaust the allocator, or request a third large Task.
The production build omits those hooks. Checks, maps and transcripts stay outside
any distribution ZIP. Focused development checks do not qualify the hosted system.
