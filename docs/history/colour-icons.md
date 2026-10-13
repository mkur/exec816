# Sixteen-colour GEM icons

[Current contract](../reference/aes.md#resources-and-popup-menus) ·
[History index](README.md)

The desktop's SYS: and WORK: artwork uses standard G_CICON objects. Each icon
has a 32×16 colour bitmap, a transparent exterior, a black outline, blue body,
grey shutter and white label. Selection reverses the label; C: remains a folder.
The editable pixel rows are in
[resource.json](../../examples/gem-browser/resource.json).

The implementation follows the
[GEM CICONBLK/CICON format](https://tho-otto.de/hypview/hypview.cgi?charset=UTF-8&index=402&url=%2Fhyp%2Fcompend.hyp)
and the standard extension layout used by
[EmuTOS](https://github.com/emutos/emutos/blob/master/aes/gemrslib.c).
GEM4XE's current resource/object code supplied the reference for converting
four-plane artwork once and keeping the image unchanged when no selected form
exists. Exec uses full upper-memory pointers, its own loader ownership and the
existing display grant. No donor near-memory allocator or new event mechanism
is introduced.

The resource loader fixes the first four-plane form, its optional selected
image and native WORD masks. Unsupported depths retain the mono fallback.
Drawing consumes packed device pixels through the existing staging page and
two masked blits. Odd-X and clipped edges preserve neighbouring nibbles. File
extent checks happen during loading, with no repeated drawing-time validation.

The 32×16 colour image and mask occupy 320 bytes. DESKTOP.RSC grows from 1,440
to 2,004 bytes including the fallback, descriptors and extra stock object.
Desktop's seven icon records grow by 28 bytes in upper RAM. Loading temporarily
allocates 2,048 bytes of upper-RAM conversion scratch, freed before returning.
Fixed, per-public-Task and idle bank-zero reservation changes are each **0 bytes**,
including guards, alignment and unused capacity. CPU staging, VRAM reservations,
Task count, direct pages and stack reservations are unchanged.

## Development checks

The focused resource fixture checks compiled and loaded icons, all sixteen
hardware colours, both X parities, clipping, selected artwork with a different
mask, absent selected artwork, unsupported-depth fallback, full twelve-byte
labels, shared CICONBLK references, 64×64 icons and malformed-resource rollback.
It also retains the existing monochrome pixel and heap-return checks.
ICONBLK/CICON/CICONBLK layout probes cover raw and optimized C emission.

[Development evidence](../development/colour-icons.json) records 253 target
checks, eight monochrome scenes and eighteen colour scenes (176,472 compared
colour-scene pixels). Heap availability returns exactly to 2,586,816 bytes;
the root retains 504 bytes above its stack floor and idle retains 192 bytes.
Native context, guards, ownership and OS restoration pass. The host suite has
454 passes and four historical skips; the three icon structures have matching
raw/optimized emitted layouts.

An initial mixed-byte/word pixel loop stalled under Calypsi 5.18. The final
loop keeps nibble arithmetic in native 16-bit temporaries, narrowing only at
staging stores; the optimized pixel fixture covers that path. The compiler pin
is unchanged. Builds use the release host executable from the same pinned
actionc revision; this changes host build speed, not the target optimization mode.

The exact OF816 desktop ZIP also passes the desktop walkthrough, without a
development-media override: disk selection, two independent folder windows,
resize/full/scroll, a separately launched counter, persistent background after
closing folders, reopening, shell HELLO and orderly EXIT. Five desktop scenes
match the independent pixel model. Stack guards remain intact; the smallest
public-Task margin is 177 bytes and idle retains 121 bytes above its floor.
The compiler revision, ROM, package and report hashes are recorded in the
development evidence. These development checks do not establish release or
real-hardware qualification.
