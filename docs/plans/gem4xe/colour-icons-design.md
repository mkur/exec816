# CG1: colour GEM icons

[Roadmap](../../roadmap.md#colour-gem-desktop-roadmap) · [Plan](colour-icons-plan.md)

Add ordinary `G_ICON` objects to application-owned trees and classic resources.
Use the standard 34-byte ICONBLK, with full 32-bit mask, data and label addresses.
Its monochrome planes select foreground/background pens from the existing
sixteen-colour palette. Selected icons exchange those pens. Draw the optional
character and centered label with the existing 8×8 font. Transparent pixels and
neighbouring packed nibbles survive clipping and odd-X placement.

The bounded subset admits word-aligned bitmap widths of 16, 32, 48 or 64 pixels,
heights 1–64 and labels of at most 63 characters. Compiled trees supply native
16-bit bitmap words, most significant bit first. RSC loading checks extents and
converts big-endian bitmap words once, including shared planes. Hot drawing
trusts the tree, ICONBLK and lifetime, as it does ordinary buttons.

The linked application callback expands only the visible bitmap strip into
packed AND/OR planes. Reuse the adapter's 4 KiB CPU staging page after draining
previous work; upload only the used bytes. Reuse the existing 4 KiB glyph scratch page
at $36000–$36FFF. Display ownership and draining queued blits before a glyph
write serialize both uses. Two bounded blits compose each strip. No framebuffer readback or new
Task is required. Existing UPDATE, display grants, pointer removal and fences
cover the operation. Cache policy is deferred until measurements justify it.

The application object binding handles icons beside the extracted GEM4XE
object routines. Preserve the donor's mask/data, colour-exchange and label
semantics without enabling unsupported object types in the native retained
widget service. Public raster-copy APIs and CICON remain separate extensions.

Reserved bank-zero change: fixed 0, per Task 0, idle 0 bytes. VRAM and CPU staging
reservations unchanged. This milestone changes no
kernel API, signals or scheduling policy.
