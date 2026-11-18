# Migrate MagiC MGEDIT to Exec

[GEM plans](README.md) · [MGEDIT audit](../../history/mgedit-port-audit.md) ·
[GEM architecture guidance](../../contributing/README.md#gem-architecture-guidance) ·
[Development testing policy](../../contributing/testing.md)

**Status** — ME0–ME3 implemented at development scope. ME4 ports the named
document workflow after review of its buffer and alert ownership choices.
Commit each passing slice.
[Execution record](../../history/mgedit-migration.md)

## Target workflow

Rebuild Atari `MGEDIT.APP` from its original sources. The core milestone opens
an existing native file, edits and selects multiline text, scrolls both axes,
saves to the existing path, and handles Save, Discard and Cancel on close. Its
windows must work alongside MGVIEW on the same AES. The interactive milestone
adds New, Open and Save As from the menu, including saving an untitled document.
Clipboard, Preferences, fonts and desktop integration have their own acceptance
gates. These workflows establish the viewer/editor scope of GEM coverage.

Preserve MagiC's responsibilities. MGEDIT owns each document buffer, window,
menu and file operation. The `EDITOBJC` engine owns edit state, layout, caret,
selection and scroll behavior. AES draws a `G_EDIT` object using its window's
visibility. Keep normal Exec Task preemption, independent input delivery and
existing UPDATE and display ownership. Use GEM4XE as the graphics reference and
reuse the current native GEMDOS, loader, memory and C lifetime services.
[MagiC model](../../architecture/magic.md) ·
[AES contract](../../reference/aes.md) · [VDI contract](../../reference/gem-vdi.md) ·
[GEMDOS compatibility](../../reference/gemdos-compatibility.md)

## Decisions at the relevant slice

| Before | Proposed choice for review | Alternative and consequence |
| --- | --- | --- |
| ME1 | Put the reusable `edit_*` contract in the existing C816 AES provider, with native C bindings and `G_EDIT` type 37 in the object dispatcher. Run its paint routine inside AES's admitted drawing context. Keep the document buffer in the APP and editor state in upper memory, owned by its AES registration and released on detach before the buffer is swept. | Link the engine from source in each APP and add a drawing boundary through which AES calls the APP. That duplicates engine code, requires a callback lifetime contract, and needs a way to paint within the existing grant. The current public AES and VDI calls reject reentry from an active object draw. |
| ME4 | Use an explicit single-bank buffer capacity with edit headroom and a NUL byte. Keep MagiC's contiguous caller-owned buffer and verify the 16-bit line and pixel calculations independently of capacity. | Preserve the donor's 65,536-byte growth reserve with `MEMF_LINEAR`. This needs cross-bank compiler and library checks, allocator lifetime integration, and adequate contiguous upper RAM. Exec already provides that allocation mechanism. |
| ME4 | Use the existing `form_alert` outside UPDATE/MCTRL for the modified-close prompt. Keep the document live and resume its close operation after the result. | Match MagiC's prompt inside the handler's UPDATE scope. Exec's alert currently rejects held locks, so this would require a reusable form ownership change and checks on manager and input progress. |
| ME5 | Convert a stock RSC variant reproducibly, preserving tree and item indices, text and actions. Use a supported representation for the About bitmap and translate the visual flags/states. | Implement generic BITBLK/`G_IMAGE`, 3D flags and relevant object states so stock resources load with their visuals. This widens resource admission and painting and needs its own pixel checks. |
| ME5 | Keep the first app workflow tied to a shown document. Resolve windowless New/Open before accepting no-argument launch and last-document close. | Follow MagiC's menu-only flow with a desktop policy that can select an app menu without a shown window. Starting with an untitled document and returning to a launcher after last close would be a smaller visible adaptation. |
| ME6 | Preserve MagiC's modeless `fslx_*` lifecycle using the reusable native selector internals and paths. | A modal `fsel_exinput` bridge can deliver Open and Save As sooner. It changes the event flow, requires entry outside UPDATE/MCTRL, and prevents interaction with the same app's documents while the selector runs. |

Confirm departures before their dependent slice. For each choice, record the
pinned donor behavior, the affected contract and the storage or coordination
cost. The fixed C816 AES provider is already part of the loader. The deferred
common C runtime sharing work is independent of ME1. A newly exposed platform
gap needs a description of the required semantics and the public Exec services
considered before proposing a general change.
[C816 loading](../../reference/c-program-loading.md) ·
[C runtime lifetime](../../reference/c-runtime.md#entry-and-lifetime) ·
[Linear allocation](../../reference/memory.md) ·
[Resident runtime backlog](README.md#gem-b3-resident-c-runtime-code)

## ME0 — Pin and reduce the test client

- Use MagiC revision `28cfdd29aa16fef692cc287bad3046b44ddcce3d`. Record original
  bytes and hashes for the MGEDIT application, the `EDITOBJC` C sources and
  headers, the 68k line-scan reference, `TST_APP/EDIT` and selected resources.
  Retain upstream notices and record the source encoding, native patches and
  build recipe following the MGVIEW port.
- Use `TST_APP/EDIT` as the behavioral reference for object creation, buffer
  attachment, open and event dispatch. The stock test client loads
  `edit.rsc`, opens a `wdlg_*` host and calls an older `edit_evnt` signature.
  Use a compiled one-object tree and a normal GEM window for the first native
  fixture. Use the pinned `MT_EDIT.H` contract called by MGEDIT for event/error
  fields. Confirm the first integration and fixture scope with ME1.
- **Gate** — provenance and ABI inventory are reproducible from tracked inputs.
  Map `edit_*` operations to the donor's AES 210–217 calls and record the subset
  each slice exposes.
  Record the current compiler/provider identity and a matching small APP
  fixture to reuse in later development checks.

[Atari reference pin](../../../toolchain/atari-st-reference.json) ·
[MagiC test client](https://gitlab.com/AndreasK/Atari-Mac-MagiC-Sources/-/tree/28cfdd29aa16fef692cc287bad3046b44ddcce3d/MagiC/EXTENSIO/EDIT_SLB/TST_APP/EDIT) ·
[MGVIEW source handling](../../../ports/magic/mgview/README.md)

## ME1 — Show one edit object

- Bring up `edit_create`, buffer attachment, open/close/delete and `G_EDIT`
  drawing in the approved placement. Translate the donor's `WORD`, `LONG`,
  huge pointer and line-scan boundaries explicitly. Use the current fixed 8×8
  face and the donor's tab and mixed CR/LF line layout. Keep VDI attributes
  local to the caller and edit state local to the object.
- Use the normal `objc_draw` dispatch inside the established visible-work
  clip. Use the standard workstation and display grant for the object and
  retire its references before releasing the APP buffer. Check allocation and
  `wind_open` results before publishing the object to the event loop.
- **Gate** — the optimized loaded fixture paints two or more lines in one
  window. Cover exposure under an overlapping window, failed creation and
  close/reopen with ordinary AES and C backing cleanup. Check emitted pointer
  or packed-layout behavior in a small raw and optimized probe when needed.

## ME2 — Edit text and draw the caret and selection

- Add the required `edit_evnt` key path, caret and dirty access, selection
  state and current buffer length. Preserve the donor's insertion/deletion,
  line split/join and byte conventions. Keep capacity checks at the buffer
  mutation boundary. A full buffer keeps its prior text, caret and terminator.
- Preserve MagiC's XOR caret and selection behavior. Check the existing
  destination-invert raster operation and GEM4XE's packed-pixel XOR path for
  both X parities. Use the proven operation through the existing draw context,
  including a one-pixel vertical caret. If the primitives fall short, propose
  the reusable graphics operation before adding it.
- **Gate** — a short typing sequence yields the expected bytes and dirty
  state. Test split/join, capacity refusal, caret and range inversion at both
  X parities, and redraw through an obscured selection. Unchanged neighbors
  and balanced cursor state are part of the pixel check.

## ME3 — Scroll and select with the pointer

- Wire `edit_resized`, scroll queries and `edit_scroll` to the existing window
  geometry and scrollbar calls. Preserve MagiC's visible-rectangle traversal,
  overlap-safe copy and exposed-strip redraw on both axes. Start at the donor's
  operation boundaries and reuse `vro_cpyfm` and the current paint path.
- Port left-button selection and timed drag autoscroll. Wait before acquiring
  UPDATE in the outer loop. Inside the drag handler preserve the donor's
  release/motion/timer ordering and release DISPLAY before waiting. Use the
  delivered window identities for key and button records, and cancel on
  recoverable input loss or withdrawal of the target route.
- **Gate** — compare line and page scrolls with direct redraw pixels, including
  repeated horizontal scroll and resize. Exercise drag/autoscroll, release and
  input loss with a small peer APP. Verify the peer runs and input still arrives
  while SCRENMGR waits on the editor's UPDATE.

## ME4 — Load and save a named document in MGEDIT

- Port the donor's `MGEDIT.C` and `MGEDWIND.C` document branches and native
  startup. Reuse GRECT adapters, APP arguments, `Fopen`/`Fcntl(FSTAT)`/`Fread`
  and `Fcreate`/`Fwrite`/`Fclose`. Use the approved buffer policy, checked size
  arithmetic and native paths. Bound path/title copies and leave room for the
  dirty marker. Test the file data as binary bytes.
- Preserve the existing-path Save and modified-close flow. Clear dirty only
  after the full write and successful close. Keep a failed Save dirty and
  open. Use the donor's three prompt choices through the approved alert
  boundary. Preserve the application's close order for the editor, buffer and
  window. Stop and final retirement use existing runtime lifetime rules.
  Resolve any change to MagiC's UPDATE scope for I/O separately.
- **Gate** — launch the loaded MGEDIT with a path, edit, save, close and reopen
  it with exact expected bytes. Exercise Save, Discard and Cancel plus a short
  write or terminal close failure. Open a second document and verify redraw and
  routing while switching between MGEDIT and a matching MGVIEW build.

## ME5 — Load the menu and handle New and Quit

- Use the approved resource and desktop policy. Preserve original tree/item
  indices and menu dispatch. Route About through a supported native form,
  retaining the real close and error paths. Introduce New and the correct
  no-argument and last-window behaviors for the selected policy. Keep file
  operations that depend on ME6 unavailable in this slice.
- **Gate** — verify the resource loads and is withdrawn before free. Select
  New, About, Save and Quit from the correct focused menu and verify dirty
  cancellation across two documents. Test focus changes and last-window close.

## ME6 — Modeless Open and Save As

- Reuse native directory enumeration, file filtering, selector rendering and
  form resources under the approved lifecycle. Preserve `fslx_*` event-loop
  dispatch and native path rules. Keep the destination document and a validated
  selected range alive while Save As is pending. Cancel or defer conflicting
  edits or window retirement according to the chosen MagiC mapping.
- **Gate** — open an existing file, save a new document, Save As for a named
  document and save a selection. Verify Cancel, failure and a close attempt
  during a selector session. With the modeless contract, a second document
  continues to receive its own redraw and permitted input.

## ME7 and later — Feature parity slices

| Slice | Feature and reuse | Acceptance |
| --- | --- | --- |
| ME7 | Cut, Copy and Paste using MagiC's `scrp_read` and `SCRAP.TXT` roles over native DOS. Review a shared AES scrap location and its lifecycle before adopting it. | Transfer text between two app instances. Exercise a failed write without losing the selected text and an oversized paste without changing the destination. |
| ME8 | Windowed Preferences, palette and settings using the `wdlg_*` and `form_popup` flows. Reuse existing object/form and popup rendering where the contracts match. Decide the native `MGEDIT.INF` path before enabling persistence. | Change colors and tab width, cancel and reopen Preferences, and recover saved settings on restart. A document in another window continues to redraw. |
| ME9 | Font chooser and editor font metrics. Determine the required VDI/GDOS subset from the donor and review the reusable font contract. | Select a second supported font and verify glyphs, caret, selection, tab spacing and scroll metrics after the change. |
| ME10 | Remaining desktop and visual features. Review `VA_START`/`AV_STARTED`, `AP_TERM`, and grow/shrink animations individually against the native launch and desktop contracts. | Validate each selected behavior with actual desktop and window interactions. Record remaining MagiC gaps against their original calls. |

## Development evidence and delivery

Use one optimized emitted-code scenario for the feature touched in each slice,
with the specific failure or ownership case above. Reuse the compatible boot
fixture, provider and existing APPs whenever their inputs match. An APP ABI
change requires a matching provider and rebuilt APPs used in that check. Use
the small Counter fixture for scheduler progress and MGVIEW for editor/viewer
coexistence. Keep routine builds free of QED and release matrices.

Record the tested behavior, APP and provider bytes, upper-memory costs per
document and registration, measured stack headroom and reserved bank-zero
delta per slice. Target zero added reserved bank-zero bytes and use existing
Task pools. Report a measured shortfall before expanding them. If a demo is
requested, use the standard OF816 packaging path and include the approved
resource variant and donor notices.
[Testing policy](../../contributing/testing.md) ·
[Bank-zero budget](../../reference/platform.md#bank-zero-memory-budget)
