# Minimal VDI hosting contracts

[Implementation plan](minimal-vdi-implementation-plan.md) · [Port inputs](../../../ports/gem4xe/README.md)

These are the frozen G0 implementation contracts, not available public services.
G1 extraction and the [G2 private service](../../../ports/gem4xe/service/README.md)
are implemented. G3–G5 must establish hardware and integration behavior before
these contracts move into reference documentation.
The exact operation numbers, limits and packet offsets are in
[gem-vdi.json](../../../abi/gem-vdi.json). No new COP selector is allocated.

## Service protocol

The renderer is an ordinary Task. Root owns the one client and the supervisor
stop authority. Startup passes their Task identities directly; this first
service is not discoverable by unrelated applications. Create the renderer and
computing peer with 2,560-byte requests before admitting smaller workers. Retain
participants with public Task leases before publishing the service port.

All fields are little endian. The aligned 156-byte Request begins with the
16-byte Exec Message. Its trailing 57-word output array is large enough for the
classic workstation response. Up to 16 twelve-byte Command records follow it;
their read-only coordinate and integer arrays follow the entire command table.
The table and arrays together occupy at most 2,048 bytes. The largest allocation
is therefore 2,204 bytes. All packet storage belongs to one allocated upper-RAM
extent within one CPU bank. Reject other placements before publication; the
receiver independently validates the packet length and every referenced extent.

`mn_Length` and `total_bytes` must agree and cover the entire allocation submitted
to the service. An offset is relative to the start of that allocation, is even,
and names data after the complete command table. Empty arrays require offset
zero. Nonempty arrays may share read-only input bytes, but cannot overlap the
header, command table or reply storage. Widen arithmetic before multiplying a
point count by four, adding offsets, or checking the 24-bit address range.
Flags and reserved words are zero. A caller must provide a valid Exec Message
and reply port even when testing a malformed service header; this protocol is
not memory isolation against arbitrary invalid pointers in a shared address space.

| Service | Input and successful reply |
| --- | --- |
| OPEN | Session 0, sequence 1, exactly one `v_opnwk` descriptor with the fixed eleven-word work-in in the manifest. Acquire presentation and initialize defaults before replying with a nonzero generation, handle 1 and workstation output. A second open returns BUSY. |
| SUBMIT | Live generation and next sequence, 1–16 supported commands. Validate the complete batch before execution. Return the completed count and outputs in command order after hardware completion. |
| CLOSE | Live generation and next sequence, zero commands, exactly 156 bytes. Drain accepted drawing, restore presentation and invalidate the session before replying. This implements the hosted `v_clswk` helper. |
| STOP | Root supervisor only, zero commands, exactly 156 bytes; generation/sequence zero. Withdraw admission, finish accepted work, close any live session, release participant leases and acknowledge retirement. |

OPEN returns the 45 integer and 12 coordinate words of `work_out`, with the
physical handle implied by the successful generation. The manifest's handle 1
is a client helper convention, never a way to bypass generation validation.
Restrict advertised capabilities to the subset: no input devices, selectable
fonts, rotation, markers, patterned fill or raster operations. G4 must check the
emitted inquiry values against the operation manifest instead of copying upstream
capability claims wholesale.

SUBMIT replies contain one word for each successful colour, interior or writing
mode setter, in command order; other supported drawing calls produce no words.
`reply_words` and `completed_count` describe only valid output. On validation
failure both are zero, with no attribute, pixel or sequence mutation. On an
execution failure they describe the completed prefix; pixels from the failing
command may already have changed. A hardware failure retires the generation.
Both `v_updwk` and successful batch completion include a hardware fence.

Use increasing 32-bit generations, never zero and never reused during a service
lifetime. Refuse a new session with EXHAUSTED before wrap. Sequences begin with
OPEN at 1 and advance only for accepted requests; reject stale/out-of-order
values with BAD_SESSION. Reserve the last sequence for CLOSE, so wrap cannot
prevent cleanup. STOP remains possible after exhaustion or orderly device-fault
recovery. Malformed/unsupported packets leave the session usable; an unknown
or stale generation never addresses its replacement.

The client keeps its packet immutable and its storage/reply port live from
PutMsg until GetMsg removes that exact reply. Exec owns the message linkage;
the receiver may write only result, completion/output counts, reply words and
the OPEN generation. Synchronous helpers use submit/collect internally and expose
failure through a status accessor, including classic void-return calls. The
supervisor can instead submit, perform Action! DOS I/O, then collect; no request
borrows a C activation that has already returned.

No request may be accessed by the service once ReplyMsg begins publication.
Normal Task removal is held by leases until close/stop completes. Release the
renderer lease and final notification under the existing Forbid/retirement
protocol; do not leave a pointer to an unretained Task after waking its owner.
Allocation or partial-startup failure unwinds in reverse order before publishing
readiness. There is no forced client kill or timeout-based buffer reclamation.

## Drawing semantics

The operation manifest is an allowlist, including GDP subopcode 1 for `v_bar`.
Reject every other opcode, subopcode, count and attribute value. Colours are VDI
pens 0–15 with the selected GEM palette. Defaults are solid one-pixel lines,
solid fills, pen 1, replace mode, clipping off and the built-in 8×8 face.
Text is at most 64 explicit glyph indices, each 0–255, without a terminator;
empty text is valid. It uses the upstream default left/baseline alignment and
unrotated metrics. Physical keyboard, mouse and cursor initialization are absent.

Coordinates are signed 16-bit raster positions. Use wide intermediate arithmetic
for clipping and text extents; extreme values must not wrap into visible pixels.
Rectangle corners and clip corners are ordered, bounds are inclusive, and the
screen extent always constrains drawing. Clip-off still supplies two ignored
point pairs for the classic calling convention. An empty intersection draws
nothing. Session open/close cannot appear inside a SUBMIT batch.

## Display lease and transitions

Implement a reusable native `DISPLAY` module, not a GEM-specific kernel gateway.
Its public operations will acquire, release and query completion of a display
lease on behalf of the current Task. The caller supplies a zero-initialized,
address-stable lease record in upper RAM. Its identity and generation are checked
on every operation; copying the record does not create ownership. Records remain
opaque until G3 determines their checked ABI layout.

The shared state is FREE, ACQUIRING, ACTIVE, RELEASING or FAULTED, with one retained
owner. Acquisition returns OK, BUSY, UNSUPPORTED, NO_MEMORY or INVALID_OWNER and
never waits for a live owner to disappear. No recursive acquisition is supported.
Failures before hardware mutation unwind to FREE. Once mutation begins, rollback
must restore the snapshot before publishing FREE; an unquiesced engine leaves
FAULTED, retains the owner/storage and requires the controlled platform reset path.

The console and graphics adapter must use this same state. Console shutdown
acknowledges release only after its worker has stopped presentation and input
production and restored the OS state it owns. Root closes all text handles,
releases its DOS context and waits for this acknowledgement before graphics
acquisition. A new console open while graphics owns presentation fails with BUSY.
G3 adds a public bounded completion notification if the console lacks one.

Use short Forbid sections to test/publish ownership and Task leases. No drawing,
allocation, ROM call, hardware wait or reply occurs while Forbid is held.
The interrupt-side invariant is stronger than IRQ masking: NMI, IRQ, SIO and
other Tasks never read or write MEMAC, VRAM or the driver's pending mapping state.
They may preempt any register write but must return to the same Task context.

The assembly adapter keeps the caller's S and D and preserves the complete
public bridge context. It publishes a pending map in owner-private upper RAM,
disables MEMAC A if necessary, writes BANK_SEL, writes CONTROL, then commits the
software shadow. Between these writes only that Task may resume mapping work;
no asynchronous handler consumes either shadow. G3 injects NMI at each boundary.
Kernel stack switching needs no new private protocol because it never depends
on the mapped aperture. Do not use SEI as a substitute for this invariant.

Support only the cold-boot inactive VBXE baseline in the
[platform pin](../../../toolchain/altirra-gem-vdi.json): full FX 1.26, `$D600`,
private 512 KiB VRAM, no VBXE interrupts, no shared-memory or ANTIC fallback.
Version reads do not prove inactivity. The launcher establishes the boot
precondition; software tracks all later writes. An unknown previous graphics
owner is UNSUPPORTED. Keep software shadows for write-only registers and snapshot
the OS display list, DMA and other state the adapter actually changes.

Before changing/reusing scratch, replying, reading pixels or releasing the
display, fence the blitter. Every internal busy and VCOUNT loop has a wrap-safe
Exec-tick deadline below half the tick range. On timeout stop/reset the engine,
verify quiescence, disable XDL and mappings, then restore OS shadows/registers
before making FREE visible. If quiescence cannot be established, do not free
DMA storage, release ownership or claim a clean return to the OS.

## Source boundary and memory

[inputs.json](../../../ports/gem4xe/inputs.json) fixes the donor files and their
roles. Extract the selected dispatcher/workstation, clipping, line, rectangle,
text and palette code from `vdi.c`; extract only built-in face initialization
from `font.c`. Adapt `dev_vbxe.c` and `vbxe.c` to the display lease/fence, and retain
the pinned generated `font8x8.c` unchanged with its notices. Rewrite the small
host boundary headers for huge-data pointers and upper-RAM scratch. Reference-only
files explain removed dependencies; they are never compiled to satisfy symbols.

Remove the full opcode tables, virtual workstation/context ownership, printer,
CIO font loading, keyboard/cursor paths, fill-pattern and trigonometric tables.
Unsupported operations return explicit errors at dispatch, not fake service stubs.
G1 must prove the selected link has no remaining near/TINY/ZWIN reservations or
hidden startup calls. Keep the upstream extraction and platform patch separate.

G0 adds no production allocation or bank-zero reservation. Subsequent slices
reuse the two 2,560-byte pools and the existing 4 KiB CPU aperture. Keep protocol
storage, driver state, font data and runtime globals in validated upper RAM.
G1 records complete CPU placement; G3 records VRAM extents and slack separately.
The donor's BCB comment says 1 KiB, but `MAX_BCB=12` uses 252 bytes at `$30100`,
before cursor storage at `$30200`; validate actual extents instead of importing
that comment as an overlapping reservation. The
[G1 record](../../development/gem-vdi-g1.json) measures the recording-device call
chain; hardware drawing stack measurements remain pending.
