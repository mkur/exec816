# CG1 implementation plan

[Design](colour-icons-design.md) · [Roadmap](../../roadmap.md#colour-gem-desktop-roadmap)

Status: implemented; focused development checks pass. Development checks do not establish release qualification.

1. Add ICONBLK and G_ICON to the public object header. Implement clipped masked
   bitmap composition in the existing renderer and icon/label drawing in the
   caller's object callback. Keep scratch shared under the display grant.
2. Extend classic RSC admission/relocation for ICONBLKs and shared bitmap words.
   Add icon resources to the reviewable resource generator. Preserve a previous
   resource after a failed load.
3. Exercise compiled and loaded icons through emitted code: both X parities,
   selection, transparent mask holes, clipped edges, labels, exposure and
   resource retirement. Include small raw/optimized ICONBLK layout probes and
   operational resource errors. Keep pixel expectations independent of the
   renderer implementation.
4. Update the supported AES contract and record actual memory/test results.
   CG2 integrates the three stock icon designs into Files and the OF816 demo.

[Development evidence](../../development/colour-gem-cg1.json): eight independently
checked pixel scenes and exact heap return after warming the filesystem extent
cache. ICONBLK offsets agree in raw and optimized emitted layouts. Fixed,
per-Task, idle bank-zero and VRAM reservation deltas are all zero.
