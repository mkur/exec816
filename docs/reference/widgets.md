# Hosted AES widgets

[Desktop](desktop.md) · [Source port](../../ports/gem4xe/aes/README.md) ·
[Implementation plan](../plans/gem4xe/aes-widgets-implementation-plan.md)

The native widget interface is an ordinary desktop content lane. It ports
selected GEM4XE object and form code, without full AES compatibility. The
presenter retains copied trees; applications own stable request and payload
storage until exact reply collection. No application pointer or callback is
kept in a retained tree. Retained transactions and desktop painting are implemented; event-driven
interaction follows in AW4.

Open with `CONTENT_WIDGETS`; the content kind is immutable. Set `request.window`,
`payload` and `bytes` for these operations:

| Operation | Payload and result |
| --- | --- |
| SET_TREE | Exactly one 1,800-byte `WIDGETTYPES.Tree`; validate and atomically install a copied tree, cancel old interaction, assign a new nonzero epoch and revision 1, and damage the client. Failure preserves the previous tree. |
| UPDATE_WIDGETS | Exactly one 1,132-byte `Update`; match epoch and expected revision, validate all assignments, then commit the batch and its visual damage together. |
| READ_WIDGET_STATE | A writable 140-byte `Snapshot`; return epoch, revision, count, focused index and object flags/states. |

These operations share the existing content lane with REPLACE. Use the generated
[widget ABI](../../abi/widgets.json) and [desktop ABI](../../abi/desktop.json),
and rebuild callers when either changes. Payloads must occupy supported upper
RAM within one CPU bank. Storage is checked at public admission; trusted paint
and input do not perform per-object writable-range checks.

Trees contain at most 32 objects, eight hierarchy levels and 1,024 bytes of
NUL-terminated strings. Labels are at most 63 glyphs from the existing GEM 8×8
font. Specifications for G_STRING/G_BUTTON are offsets into the packet's text
array. G_BOX/G_IBOX use GEM packed colour/border specifications: only hollow or
solid interiors and inward borders 0–3 are accepted. Buttons retain the donor's
outward border: one pixel, plus one for EXIT and one for DEFAULT. All visual
extents fit their parent and the client, including borders and labels.

Only buttons accept SELECTED/DISABLED and selection/default/exit/radio flags.
DEFAULT requires EXIT; EXIT controls cannot retain selection. Radio buttons are
exclusive among siblings of the same parent. HIDETREE and LASTOB are supported;
indirect specifications, user callbacks, editable fields and other types,
flags or decorations are rejected. Parent-return sibling links are terminators;
admission rejects cycles, duplicate parents, unreachable nodes and excessive
depth before entering donor walks.

Updates contain at most eight distinct objects and absolute assignments for
state, label or subtree visibility. Geometry and topology change through
SET_TREE. Labels specify an offset and length excluding their required NUL;
the complete resulting strings must fit retained capacity. Hiding the root
through UPDATE_WIDGETS is unsupported. Invalid batches have no partial effects.
No-op assignments neither increment the revision nor damage pixels. A changed
batch cancels an armed gesture and moves invalid keyboard focus to the first
eligible object. Damage includes changed visual bounds and old/new focus.

STALE rejects an outdated epoch or revision; read current state before retrying.
Epoch and revision never wrap to reusable identities. EXHAUSTED preserves the
old model and permits close/retirement. Old-epoch queued widget events are
discarded; applications must also reject old notifications already collected.
Semantic event records reserve epoch, revision, object and resulting state;
physical event production is connected in AW4.

Each admitted widget window reserves 4,096 upper-RAM bytes, including unused
capacity. The current C context occupies 2,200 bytes. One shared 2,200-byte
staging context prepares replacement and updates; replacement does not allocate
a second per-window block. CLOSE releases the block after the Layers token
retires. There are still four window slots, eight public Task pools, one display
owner and the existing 2,560-byte presenter stack. Reserved bank-zero growth is
zero for fixed/root/kernel, every public Task and private idle, including guards,
alignment and spare capacity. Widgets add no VRAM reservation.

Painting reconstructs the damaged client background and intersecting objects
in tree order. The presenter admits at most four objects and sixteen scanlines
per turn and services input between continuations. One Layers token freezes the
model across these turns. Occluded updates retain their new state without
painting; later exposure reconstructs that state. Pointer overlays share the
existing drawing owner and command arena.
