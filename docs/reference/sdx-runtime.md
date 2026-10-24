# Resident SDX and FastBasic guests

[Reference index](README.md) · [Service ABI](sdx-services.md) ·
[FastBasic sessions](fastbasic.md) · [Implementation evidence](../history/sdx-resident-stack.md)

Two loaded Images retain independent guest banks and aligned direct pages.
Exactly one SDX/FastBasic invocation owns physical page one. Its lease lasts
through native services, input/device waits, preemption and cancellation cleanup.
Other native Tasks continue to run. A second invocation reports primary 20 and
native error 202 before frame construction, console changes or guest mutation.
Process creation itself can succeed; this failure is the runner's normal result.

An idle persistent BASIC Process releases that lease after output, diagnostics,
native I/O and resumable frames retire, before replying. Its private memory,
channels and Process remain. The next Run acquires a fresh invocation frame;
busy Run preserves data. Restart and Quit while parked never borrow page one.
An INPUT, PAUSE or debugger-style live wait cannot park.

## Physical frames and ROM entry

Guests retain `E=1`, `M=X=1`, their private D and guest PBR/DBR. The generated
13-byte frame preserves hidden B, X/Y, D, DBR, status and PC. The saved S points
below the live frame. Native continuations use their existing Task stacks.
Service and interrupt transitions do not copy whole pages. Trap/overlay
unwinds may move one 13-byte frame under the transition gate.

The lifetime lease, current CPU owner, complete borrow anchor, ROM depth and
entry gate are separate fields in the existing upper bridge bank. Short stores
under IRQ masking publish ownership and frames; NMI acknowledges/latches during
incomplete transitions. Stable service/wait phases permit native scheduling.
Guest restore retains the existing partial-pop reconstruction and early
emulation-stub bank classification. No Task dispatch crosses a live ROM activation.

Runtime ROM entry uses the complete anchor when a guest is suspended. Already
nested ROM work preserves its current page-one S. With no frame, the controlled
OS top applies. The pinned ROM's COP `$00` and VBI paths enter emulation mode;
passing a native Task stack through unchanged is unsupported.

Require `anchor - 128 >= $0110` before borrowing, hence anchor at least `$0190`.
The `$0100–$010F` lower guard remains reserved. The budget includes the wrapper,
COP/native-to-emulation entry, ordinary VBI, one nested CIO VBI, owned/ROM IRQ
entry and acknowledge-only NMI. Nested CIO VBI uses a small emulation frame and
only enters while S is in page one; deeper or transitional NMIs defer. It keeps
ROM clock-dependent scrolling working. Native SIO continues to exclude ROM
serial service while it owns the hardware. Another ROM or third-party interrupt
chain requires a new audit.

The pinned BASIC parser stores grammar backtracking records in a 256-byte
private-bank buffer, with three bytes of bookkeeping and at most 63 live states.
It checks CPU state at `$01A4` and action entry at `$01A7` after three temporary
saves. Excessive grammar depth reports parse result 306 (`too long`); errors
unwind before printing. ARCADD checks
saved S at `$01A0` on each recursive Huffman entry, preserving the replaced
store and guest registers/status on success. A deeper entry returns SDX 158;
ordinary terminal mutation cleanup preserves the old archive. These are bounded
resource failures, not page-copy fallback modes. Source assumptions, conservative
envelopes and the stack-entry inventory are recorded with the implementation.

## RAWCON presentation

EDX owns its fixed ATASCII cell buffer and inverse software caret. Each row has
an empty span or first/end changed columns. Unchanged writes create no damage;
clear and scroll mark their affected rows. Flush sends counted spans through
public `DOS.ConsoleIO(WRITE_CELLS)` in row order before returning a key. Damage
clears only after a complete successful write. Failed/short writes retain it;
retirement restores ordinary console modes.

Cell get/put use a bounded native path. Every service boundary still checks all
32 DP guard bytes and foreground BREAK. The Process-owned foreground scope is
borrowed once per invocation; its pending byte is observed at every boundary.
Blocking console/DOS work stays outside the entry gate. The measured p95 target
of 100 ms is still open; development results do not qualify the hosted system.

## Memory

Reserved bank-zero growth is **0 bytes**: fixed, root/kernel, all twelve public
Tasks and idle, including guards, alignment and spare capacity. Keep the existing
544-byte fixed DP reservation (two 256-byte pages and two outer 16-byte guards).
Page one remains part of the OS reservation. The upper bridge bank remains
64 KiB reserved; two context records shrink from 512 to 16 bytes each and the
old host page image disappears. This does not release the reserved bank.

RAWCON replaces 30 dirty bytes with 60 span bytes. SDX Session grows from
2,290 to 2,320 bytes; the eight-byte heap allocation grows from 2,296 to 2,320
bytes. Each retained BASIC Session embeds that guest state and grows by 30 bytes.
The parser adds 259 bytes of private guest BSS. Heap alignment and changed code
also affect BASIC's available program storage; the emitted engine map supplies
the actual heap start. No parser storage is added to bank zero.
