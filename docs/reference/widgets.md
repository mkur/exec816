# Hosted AES widgets

[Desktop](desktop.md) · [Source port](../../ports/gem4xe/aes/README.md) ·
[Implementation plan](../plans/gem4xe/aes-widgets-implementation-plan.md)

The native widget interface is an ordinary desktop content lane. It ports
selected GEM4XE object and form code, without full AES compatibility. The
presenter retains copied trees; applications own stable request and payload
storage until exact reply collection. No application pointer or callback is
kept in a retained tree. Retained transactions, desktop painting and event-driven
form interaction run in the existing presenter.

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
eligible object. Damage keeps changed visual bounds and old/new focus as
separate rectangles. Focus changes damage only the one-pixel underline;
selection, label and gesture feedback retain complete object bounds, including
outward borders. A press queues its control before the previous focus mark.

The private presenter/C packet copies up to eight damage rectangles. Contained
duplicates are removed; capacity overflow falls back to the complete client,
so earlier damage cannot be lost. The presenter invalidates its snapshot once
per visual transaction and passes each rectangle independently to Layers.
SET_TREE damages the complete client. Rejected/no-op updates return no damage.
The drawing clip fields keep their paint-only role. The packet is 124 bytes,
66 more than before, inside the existing upper C data reservation; public tree,
update and snapshot payload sizes are unchanged. Rebuild both internal callers
with the generated definition when this packet changes.

STALE rejects an outdated epoch or revision; read current state before retrying.
Epoch and revision never wrap to reusable identities. EXHAUSTED preserves the
old model and permits close/retirement. Old-epoch queued widget events are
discarded; applications must also reject old notifications already collected.
WIDGET_ACTION and WIDGET_CANCEL events carry epoch, revision, object and
resulting state. Route, capture tick and the tick-valid flag retain their input
meaning; BREAK cancellation can arrive without a valid capture tick.

Each admitted widget window reserves 4,096 upper-RAM bytes, including unused
capacity. The current C context occupies 2,200 bytes. One shared 2,200-byte
staging context prepares replacement and updates; replacement does not allocate
a second per-window block. CLOSE releases the block after the Layers token
retires. There are still four window slots, eight public Task pools, one display
owner and the existing 2,560-byte presenter stack. Reserved bank-zero growth is
zero for fixed/root/kernel, every public Task and private idle, including guards,
alignment and spare capacity. Widgets add no VRAM reservation.

Painting reconstructs the damaged client background and intersecting objects
in tree order. Each C step draws at most one visible, intersecting object part and
examines at most eight objects, including hidden and out-of-clip objects.
The next tree-order index survives each return, including a scan-only step.
Strips remain at most sixteen scanlines high. Wide text objects whose glyph row
is clipped vertically resume in disjoint horizontal spans of at most 96 pixels;
whole glyph rows retain the run encoder. Only a scalar horizontal offset survives
the call, reset at the next strip. Background initialization shares the first object batch,
and a visible solid root box supplies its own background. A 5,120-byte VRAM strip
holds partial drawing; the final chunk copies only completed pixels to the screen,
preserving adjacent nibbles at odd clip edges. This uses the former screen padding,
so total VRAM reservation is unchanged. Frame work returns before widget
drawing; strips wholly inside the client skip frame work. The worker drains at most four ready steps of the same strip per turn,
servicing captured input and the pointer between C calls. This does not renew
control admission or console-output budgets or add a voluntary Yield.
Scratch-only writes do not set the screen-change hint; captured motion can still
move the pointer between them. One Layers token freezes the
model across these turns. Occluded updates retain their new state without
painting; later exposure reconstructs that state. Pointer overlays share the
existing drawing owner and command arena.

Mouse input arms an enabled visible button on a fresh press. Moving outside
removes its pressed appearance; moving back restores it. Release inside commits
one action. Release outside, focus loss, hiding, replacement and close cancel the
gesture. Press appearance is separate from committed selection. Momentary EXIT
buttons report an action without retaining selection. A selected radio can
report an action without incrementing the model revision.

Tab and Shift-Tab traverse eligible controls in tree order. Space activates the
focused button; Return activates the enabled visible default. Escape and BREAK
emit WIDGET_CANCEL without closing the window. Control-modified keys outside
these cancellation semantics remain raw input. Consumed widget input is not
also delivered as an actionable raw key or click. Title/close gestures keep
priority; an existing widget capture retains movement and release outside its
window until retirement.

Sixteen presenter-owned records defer input while a Layers paint or scroll
owns the scene. Adjacent motion coalesces only for the same window, epoch, route
and button state. A safe turn processes at most four records. Queue overflow,
stale destinations and client event loss disarm routing immediately, then repair
pressed pixels after the immutable paint snapshot retires. A fresh released
button observation is required after ambiguous input. Applications read current
state after LOSS; they must never synthesize commands from selected bits.

The desktop service occupies 14,186 bytes (14,192 rounded), including its
sixteen deferred records, enlarged client event queues and DR7 rendering state.
The AW4 widget work accounted for 1,456 bytes of its growth over the pre-widget
service; AW5 adds no service storage. No new Task, kernel primitive, bank-zero
reservation or VRAM extent is introduced.

The optional `DESKAPP` Control Panel demonstrates this interface from an ordinary
Task. Its eight-object tree, update packet and snapshot share one 3,072-byte
upper-memory allocation; the presenter separately owns its 4,096-byte context.
The panel uses selected-state GEM buttons for toggles/radios. Apply is the
default momentary action; Cancel and Escape/BREAK report cancellation without
closing the window. The close gadget and shell EXIT retain cooperative Task
retirement. These controls demonstrate application state, not system settings.

The panel uses the action's copied epoch, revision and state for its first
status-label patch. A stale revision triggers a fresh state read and retry;
LOSS also reads the current state, and an action from a replaced tree is
discarded. Focusing a widget window damages its title bar and focus underline;
it does not require repainting unchanged client contents.

Input capture, widget state commit, application consumption and visible status
are distinct stages. A scene token can delay widget dispatch or state requests,
and a successful patch reply precedes its pixels. Functional completion does
not imply the desktop meets its latency targets; see the
[execution record](../history/aes-widgets.md).
