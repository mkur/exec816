# Hosted AES objects

[Implementation plan](../../../docs/plans/gem4xe/aes-widgets-implementation-plan.md)

AW0 extracts actual GEM4XE object, graphics and form routines at the revision
and hashes in [inputs.json](inputs.json). [selection.json](selection.json)
lists the functions; the ordered [patch](patches/0001-hosted-object-subset.patch)
makes the supported branches independent of donor device and event ownership.
Extraction normalizes source newlines and copies the donor GPL/LGPL notices.
The upstream copyright and licence notices remain applicable; the Exec public
interface grant does not relicense these routines.

Object traversal, coordinates, hit testing, box geometry, text placement and
radio selection run selected donor code. The host validates the complete tree
before donor walks, resolves string offsets into its own retained text, and
replaces blocking form waits with release-time selection. Unsupported drawing
branches and direct screen mutation in ob_change are removed. No form_do,
GEMDOS, resource loader, application callback or donor input/startup is linked.

The generated native packet uses the donor's 24-byte object layout, with
offset specifications for strings. A tree is 1,800 bytes, below the 2,048-byte
packet ceiling. It admits at most 32 objects and eight levels, G_BOX/G_IBOX,
G_STRING/G_BUTTON, SELECTED/DISABLED, and selection/default/exit/radio/hidden/
last flags. Box interiors are hollow or solid, with inward borders 0–3;
buttons have the donor's outward 1–3 pixel border. Children, labels and outward
borders must fit their parent and client. Indirect specs and other types, flags
and decorations are rejected. The fixture covers malformed cycles, terminators,
depth, capacity, pointers, extents and radio groups.

Run the focused source/model and native development checks:

```sh
python3 -m unittest discover -s tests -p 'test_widgets_contract.py'
python3 tools/test_widgets.py --mode raw --output build/widgets/aw0-raw
python3 tools/test_widgets.py --mode opt --output build/widgets/aw0-opt
```

The native checks exercise the C bridge on an ordinary Task through VBI,
emitted C/Action layouts, donor operations, stack floors and ownership teardown.
They use the pinned AltirraOS ROM and mouse-capable emulator. They do not
qualify desktop graphics or physical hardware. Reserved bank-zero growth is
zero: fixed/root/kernel, each of eight public Task pools and private idle,
including guards, alignment and unused pool capacity. The existing 20-byte
C DP workspace and 2,560-byte large Task stack are reused. The existing complete
C code/data banks remain reserved (131,072 bytes). AW0 reserves no VRAM.

AW1 connects the selected draws to the existing VBXE font atlas and bounded
command lists. A synchronous trusted renderer closure checks ownership once
per four-object, sixteen-scanline quantum. Transparent text preserves partial
glyphs and packed neighboring pixels; selected controls invert their rebuilt
base, disabled stipple stays anchored to screen coordinates. Keyboard focus
is a one-pixel inset underline. No new public VDI opcode or VRAM extent is added.
See the [native pixel record](../../../docs/development/aes-widgets-aw1.json).

AW2 adds copied desktop widget contexts and atomic state/label updates.
[Native service and model evidence](../../../docs/development/aes-widgets-aw2.json)
covers raw/optimized admission, stale identities, no-op updates, identity
exhaustion, heap exhaustion/recovery, returned-buffer independence and teardown.
Reserved bank-zero and VRAM growth remain zero. The service fixture alone uses
an 8 KiB image-data arena to hold its deliberately separate test packets.
