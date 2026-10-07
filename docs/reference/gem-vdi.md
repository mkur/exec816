# GEM VDI hosting contracts

[Reference index](README.md) · [Run the workload](../guides/gem-vdi.md) ·
[Drawing record](../history/gem-vdi.md) · [Input record](../history/gem-input.md)

The resident [AES application profile](aes.md) uses direct caller-side VDI
with private virtual workstations. The separate supervised packet workload
below retains its own restricted interface; its packet limits do not constrain
resident `v_gtext` strings.

## Resident application workstations

`graf_handle` returns physical handle 1 and four 8-pixel metrics. It is local,
including AESPB opcode 77. Each registration may open one private workstation
with `v_opnvwk`: pass that physical handle, device 1, solid fill (`work_in[7]=1`),
raster coordinates (`work_in[10]=2`) and text/fill pens 0–15 at words 6 and 9.
Unused line/marker inputs are ignored. Success replaces the handle with 2;
failure sets it to zero. Handles are local to the owning Task. Opening performs
one cold AES delegation exchange and never opens, clears or repalettes hardware.

The 57-word inquiry is generated from [vdi-client.json](../../abi/vdi-client.json).
It describes 640×240, sixteen colours, one fixed 8×8 face and the bar GDP.
Line, marker, polygon, raster-copy, input-device and external-font capabilities
are not advertised. Other supported calls are `v_clsvwk`, `v_bar`, `v_gtext`,
`vs_clip`, `vsf_color`, `vst_color`, `vsf_interior(1)` and `vswr_mode(1)`.
Named calls and `vdi_call(VDIPB *)` share helpers; opcodes/counts are recorded in
the [binding manifest](../../ports/gem4xe/aes-binding-inputs.json).

Attribute changes are caller-local. Drawing requires a shown application window
and `wind_update(BEG_UPDATE)` ownership. Every draw is confined to its published
visible work region, intersected with the private user clip. Clip-off removes
only that user clip. Inclusive signed corners are ordered and widened before
conversion; empty intersections do no hardware work. Text is left-aligned at
the baseline, with top at `y-6`, and uses replace mode. Named strings stream
until their terminator or screen-right exclusion; parameter-block text uses its
explicit word count. Glyph indices are 0–255, a caller obligation. Strings are
not truncated at a fixed call-size limit.

The binding releases [physical access](display.md#delegated-renderer-access)
between at most 16-row fill strips or 32-glyph text chunks. Each admitted unit
selects private attributes, renders through the existing backend, fences,
restores native attributes and overlays, then releases access. Shared parameter
scratch and the 92-byte native-workstation save area remain protected by that
ownership. No warm drawing/attribute call uses presenter RPC, and no physical
unit waits for an AES reply or an application event.

Classic void calls report failures through `ExecAESDiagnostic()`: resource
exhaustion, unsupported operation/attribute, malformed counts, missing update
ownership, or `AES_DISPLAY_ERROR`. Valid pointers and live caller-owned handles
are application responsibilities. Closing releases only the virtual grant,
signal and storage. `appl_exit` also closes an omitted workstation before
retiring the registration. Failure to release ownership prevents disposal.

Private storage is 282 live / 288 heap-reserved upper bytes per workstation,
including its grant and parameter arrays. The AES context is 267 live / 272
reserved bytes. No Task, DP, stack pool, bank-zero reservation, staging page or
VRAM extent is added. See [WA4 evidence](../development/aes-windows-wa4.json) for
emitted layout, preemption, pixel and stack checks. The
[two-counter demo](../guides/aes-applications.md#optional-of816-counter-desktop)
exercises this interface beside native shell/disk work using existing 1 KiB
caller stacks. The [WA6 record](../history/aes-windows.md#wa6--coexistence-and-the-of816-demo)
separates logical update waits, physical access and repaint completion; these
are development results.

## Supervised packet workload

This is the supervised hosting contract for the selected GEM4XE VDI
subset. It uses one renderer Task and one client owned by its supervising Task. It is a private,
rebuilt client/service ABI, not a discoverable resident service or an AES/GEMDOS
environment. [Display ownership](display.md) is a reusable platform interface.
The exact operation numbers, limits and packet offsets are generated from
[gem-vdi.json](../../abi/gem-vdi.json). No new COP selector is allocated.

The fixed mode is 640×240 with sixteen colors and the built-in 8×8 face.
Supported operations are OPEN/CLOSE, clear/update, 2–16-point solid polylines,
solid bars, inclusive clipping, up to 64 glyph indices per text call, line/text/
fill colors 0–15, solid fill interior 1 and replace writing mode 1. Virtual
workstations, raster copies, polygon/contour fill, external fonts, rotation,
markers, AES, GEMDOS, callbacks and dynamic loading are
unsupported. A validated request never silently succeeds as an omitted service.
The interactive application consumes native [keyboard input](input.md) separately
and can request the fixed renderer-owned cursor. Diagnostic injected pointer
events establish button semantics. The application also admits the reusable
ST/port 1 motion and left-button source; see [input](input.md) and the
[demo guide](../guides/gem-vdi.md).

## Service protocol

The renderer is an ordinary Task. Its caller owns the one client and supervisor
stop authority. In the interactive workload that caller is the application;
root supervises disk I/O. Startup passes Task identities directly; the service
is not discoverable by unrelated applications. Create the application and
renderer with 2,560-byte requests before admitting smaller workers. The separate
G5 regression uses a computing peer instead of the application. Retain
participants with public Task leases before publishing the service port.

The current packet revision is 2; old revisions are rejected and callers must
be rebuilt. All fields are little endian. The aligned 156-byte Request begins with the
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
| STOP | Admitted supervisor only, zero commands, exactly 156 bytes; generation/sequence zero. Withdraw admission, finish accepted work, close any live session, release participant leases and acknowledge retirement. |
| CURSOR=5 | Live generation and next sequence, zero commands, exactly 164 bytes. Payload: x/y i16, visible u16 (0/1), reserved u16 zero. Position is the top-left hotspot, x=0–639 and y=0–239, including hidden requests. Fence before success; advance sequence with zero completed_count/reply_words. |

OPEN returns the 45 integer and 12 coordinate words of `work_out`, with the
physical handle implied by the successful generation. The manifest's handle 1
is a client helper convention, never a way to bypass generation validation.
Restrict advertised capabilities to the subset: no input devices, selectable
fonts, rotation, markers, patterned fill or raster operations. The G4 development
corpus records all 57 emitted inquiry words, and its evidence gate checks the
complete expected subset instead of copying upstream capability claims wholesale.

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
`GemTryCollect` collects the exact reply without waiting and returns a separate
ready flag. Empty queues retain ownership and sequence/session state; unexpected
messages stay queued and cannot authorize disposal. `GemPrepareCursor` prepares
the owned packet without submitting it. The application keeps at most one VDI
or cursor packet pending and tracks new dirty state separately.

No request may be accessed by the service once ReplyMsg begins publication.
Normal Task removal is held by leases until close/stop completes. Release the
renderer lease and final notification under the existing Forbid/retirement
protocol; do not leave a pointer to an unretained Task after waking its owner.
Allocation or partial-startup failure unwinds in reverse order before publishing
readiness. There is no forced client kill or timeout-based buffer reclamation.
Startup reserves the supervisor's STOP packet and reply port before readiness.
STOP performs no allocation, including when a drawing reply remains pending;
the client still must collect that exact drawing reply. Failed startup frees
the reserve, and successful shutdown frees it after exact STOP collection.

## Drawing semantics

The operation manifest is an allowlist, including GDP subopcode 1 for `v_bar`.
Reject every other opcode, subopcode, count and attribute value. Colours are VDI
pens 0–15 with the selected GEM palette. Defaults are solid one-pixel lines,
solid fills, pen 1, replace mode, clipping off and the built-in 8×8 face.
Text is at most 64 explicit glyph indices, each 0–255, without a terminator;
empty text is valid. It uses the upstream default left/baseline alignment and
unrotated metrics. Donor keyboard/mouse initialization remains excluded.

Coordinates are signed 16-bit raster positions. Use wide intermediate arithmetic
for clipping and text extents; extreme values must not wrap into visible pixels.
Rectangle corners and clip corners are ordered, bounds are inclusive, and the
screen extent always constrains drawing. Clip-off still supplies two ignored
point pairs for the classic calling convention. An empty intersection draws
nothing. Session open/close cannot appear inside a SUBMIT batch.

The fixed 16×16 black/white arrow starts hidden on every OPEN. The renderer
restores its saved background before scene mutation, then saves and redraws at
the latest accepted position. It clips at screen edges and preserves adjacent
nibbles at odd x positions. Cursor work leaves VDI clipping, pens and text
attributes unchanged. Malformed requests change no cursor, sequence or pixels.
Save/restore/mask phases use fenced blits; a hardware fault follows the same
generation-retirement or reset-required path as drawing.

## Display lease and transitions

The reusable native `DISPLAY` module acquires, releases and queries a display
lease on behalf of the current Task; the hardware adapter supplies completion
fences. It does not add a GEM-specific kernel gateway. The caller supplies a zero-initialized,
address-stable lease record in upper RAM. Its identity and generation are checked
on every operation; copying the record does not create ownership. Records remain opaque; their checked layout is in
[display.json](../../abi/display.json).

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
The console uses the existing signal-based `CONSOLEDRIVER.Stop()` retirement acknowledgment;
no new console completion service is needed.

Use short Forbid sections to test/publish ownership and Task leases. No drawing,
allocation, ROM call, hardware wait or reply occurs while Forbid is held.
The interrupt-side invariant is stronger than IRQ masking: NMI, IRQ, SIO and
other Tasks never read or write MEMAC, VRAM or the driver's pending mapping state.
They may preempt any register write but must return to the same Task context.

The assembly adapter keeps the caller's S and D and preserves the complete
public bridge context. It publishes a pending map in owner-private upper RAM,
disables MEMAC A if necessary, writes BANK_SEL, writes CONTROL, then commits the
software shadow. Between these writes only that Task may resume mapping work;
no asynchronous handler consumes either shadow. The G3 development tests interrupt each boundary with NMI.
Kernel stack switching needs no new private protocol because it never depends
on the mapped aperture. Do not use SEI as a substitute for this invariant.

Support only the cold-boot inactive VBXE baseline in the
[platform pin](../../toolchain/altirra-gem-vdi.json): full FX 1.26, `$D600`,
private 512 KiB VRAM, VBXE interrupts disabled at entry, no shared-memory or
ANTIC fallback. During an owned session the desktop's asynchronous copies and
scrolls use [blitter IRQ completion](display.md#asynchronous-screen-scrolling).
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

[inputs.json](../../ports/gem4xe/inputs.json) pins the donor and toolchain;
[selection.json](../../ports/gem4xe/selection.json) and the patch series define
the extracted renderer. The selected workstation, clipping, line, rectangle,
text and palette code runs through the Exec [backend](../../ports/gem4xe/adapter/README.md).
The donor's low-level hardware/startup code is excluded. The built-in font is
unchanged. There are no printer, CIO font-loading, donor keyboard, legacy context or
full opcode-table dependencies, and no near/TINY/ZWIN reservations.

The mixed eight-Task layout supplies two 2,560-byte large stacks, each including
its 256-byte interrupt reserve. C uses 20 bytes of each Task's existing lower
128-byte DP area. Complete C code/data banks `$0C`/`$0D` reserve 131,072 upper-RAM
bytes. The adapter's 4 KiB staging page is inside that data bank; the CPU aperture
`$8000–$8FFF` is an existing reservation, mapped only during owner transfers.
Protocol storage, leases, driver state and globals remain in upper RAM. Steady
service/client heap allocations total 2,656 rounded bytes, including the
192-byte STOP reserve. The server's upper-RAM record grows by four bytes for
the reply-port pointer. Task stacks and external guards are already in the
platform budget.

[VBXE extents](../../platform/altirraos/vbxe-vram.json) reserve 243,200 bytes of
private VRAM, including screen slack, XDL, the 4,096-byte command arena,
expanded font and strip scratch. Cursor storage at `$37000–$374FF` contains a 256-byte
save area and four 256-byte mask planes, retaining both pixel parities. It reuses the
existing CPU staging page and does not borrow glyph scratch. Two 65,536-byte
[desktop snapshot slots](desktop.md#private-client-snapshots) at `$50000` and
`$60000` include unused capacity. VRAM leaves 281,088 bytes unassigned. CPU and
VRAM reservations are separate.
Fixed, per-public-Task and private-idle bank-zero increments are all zero for
G0–G6 and I0–I7; the existing eight-Task budget includes 56,128 reserved bytes with OS
memory and leaves 9,408 bytes free after startup.

[G4](../development/gem-vdi-g4.json) records the primitive corpus and
[G5](../development/gem-vdi-g5.json) records concurrent physical I/O and failure
cleanup. [G6](../development/gem-vdi-g6.json) records the optional artifact and
standard OF816 controls. These are measured development paths on the pinned
emulator, not a general C stack bound, hardware certification or full hosted
qualification. Calypsi does not add automatic stack checks to these C calls.
[I5](../development/gem-input-i5.json) records cursor pixels and injected gestures;
[I6](../development/gem-input-i6.json) records bounded keyboard latency during
physical SIO, interrupted application/renderer contexts and failure closure.
The current optional artifact is the interactive application described in the guide.
