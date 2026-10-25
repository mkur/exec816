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

## RAWCON cells and damage delivery

An open EDX screen binds one 96-byte record in the existing upper bridge bank.
It contains its lease owner, far screen/damage/BREAK pointers, geometry and
thirty precomputed row offsets. Binding prepares the leaf's far instruction
operands while no guest can execute, then publishes ownership last. Unbind
clears only the matching owner; idle BASIC retirement cannot clear EDX's binding.
Close unbinds before restoring console modes or freeing storage. Lease release
also clears ownership.

Bound get/put calls retain the common complete thirteen-byte frame and corrected
JSR PC. They check the physical stack domain, all thirty-two outer DP guard
bytes and foreground BREAK before mutation. Get changes low A and N/Z; put
preserves the saved context and damages only changed cells. Invalid coordinates
detach to ordinary error 156 handling. Guard/domain failures and BREAK retain
their native fatal/cancellation paths. There is one successful cell implementation
in the resident bridge.

The leaf masks IRQs, publishes FAST_CELL with GATE, temporarily selects DBR zero
and borrows four bytes of the suspended native Task's lower DP. A two-byte DBR
setup retires before the four saved scratch bytes; maximum temporary depth is
four bytes, plus a thirteen-byte acknowledge-only NMI frame. NMI acknowledges
and latches throughout the gated interval. Scratch and the complete S are
restored before the common guest restore drains pending work. Only native
detachment publishes a ROM-borrowable anchor; a transient scratch S never does.
No native call arguments are read from the physical guest stack.

Screen Open allocates one 300-byte span array (304 bytes after heap rounding).
Flush submits all nonempty row damage through the public
[`CONCMD_WRITE_CELL_SPANS`](console.md) operation and waits for collection before
the guest can edit its buffers. Idle Flush sends no request. A successful count
or positive BREAK prefix clears only acknowledged whole spans. A negative DOS
return retains all submitted damage because that interface hides device Actual;
replaying positioned cells is safe. A nonzero IoErr remains an error even with
a full count. Retirement frees the packet only after synchronous I/O settles.

These changes add zero reserved bank-zero bytes: fixed, root/kernel, each of
twelve public Tasks and idle, including guards, alignment and unused capacity.
The existing 544-byte guest DP pool and 65,536-byte bridge bank remain fixed.
Console metadata stays 896 bytes; four bytes of spare padding hold vector
progress. Dynamic console Instances still round to 208 bytes. Session payload
grows 2,320→2,324 bytes (allocation 2,320→2,328); embedded BASIC Session grows
2,344→2,348 bytes (allocation 2,344→2,352).
