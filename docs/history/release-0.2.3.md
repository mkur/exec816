# Exec816 0.2.3 patch preparation

[History](README.md) · [Release notes](../releases/0.2.3.md) ·
[Machine record](../development/release-0.2.3.json)

The 0.2.3 draft prerelease includes initial boot SIO synchronization, early
kernel/ROM diagnostics, assumed-XLOS continuation and corrected local ATR
launchers. Its distribution is built from clean `v0.2.3`, source
`bcf3b381be037e16446eb978fa054f6c1ef998ad`, with the pinned Action! compiler
and no local override. Startup and physical Shell `VER` show
`Exec816 0.2.3 (v0.2.3)`. Existing 0.2.2 tags and assets are preserved.

## Frozen candidate checks

| Check | Result |
| --- | --- |
| Host suite | All 659 tests pass. |
| Hosted console/context matrix | All 28 raw/optimized cases pass. |
| Cooperative matrix | All 46 raw/optimized cases pass. |
| Preemptive matrix | All 60 raw/optimized cases pass, including eighteen NMI checkpoints, forwarding signatures, timer and keyboard IRQ work. |
| Firmware matrix | All 54 component placement/transition cases and eighteen XLOS native ROM/COP boundary cases pass on the three pinned ROMs. |
| Resident stack matrix | All sixty raw/optimized cases pass, with 3,018 assertions covering minimum headroom, scrolling, borrowing and lease transitions. |
| ROM diagnostics | Eleven optimized cases pass, including quiet startup, unknown CRC/vector fallback, scrolling, mapping/state failures and first-cause preservation. |
| Native bindings | Four raw/optimized cases pass, including the full-width `$C219` argument and direct worker output. |
| SIO handover | Seven real-FujiNet-PC cases pass on AltirraOS and both stock XLOS ROMs, including natural fast handoff, controlled initial rates and standard policy. |
| Split-reader recovery | All nineteen recovery/failure cases pass, plus a real-NMI publication checkpoint with two local callbacks. |
| Extracted boot packages | Ten boot walks pass: ATR on all three ROMs, new Atarimax on all three, old Atarimax on AltirraOS/XLOS 2.49F, XEX on AltirraOS and test-only assumed-XLOS continuation. |
| Full FujiNet-PC boot | An eleventh extracted-package walk passes on stock XLOS 2.49F; all 2,596 reader-owned bulk reads remain at 57,600 baud. |

Each final-package walk checks the exact tagged version, MD5, argument-free ARC
help, archive listing, WORK write/read, `FBI WORK:HELLO.BAS`, `FB WORK:CALC.BAS`,
guards, released ownership and clean EXIT. The ten regular walks also check
early identity, ROM checksum and classification. ATR loading verifies expanded
native bytes and zero-fill, loader guards, five-second OF816 countdown and
firmware context. The assumed-XLOS walk changes only its private comparison
catalog; the stock ROM and distributed binaries remain unchanged.

The synthetic SIO probes emit their readers from the frozen 0.2.3 source. They
reuse only the unchanged pinned OF816 machine configuration from the previous
bundle; final package walks execute the extracted 0.2.3 images. Exact hashes,
machine settings and observer sources are in the machine record. Completed
resident cases were retained only after source, image and XEX hashes matched;
the remaining independent cases ran concurrently. Build setup attempts and
orchestration logs remain in `build/release-0.2.3`, outside the downloads.

## Distribution and memory

`exec816-demo.zip` contains 29 entries: the combined writable ATR, matching
OF816 XEX and Atarimax images, licensed AltirraOS ROM, short guide, notices
under `licenses/` and checksums. All 28 payload checksums pass. XLOS ROMs, QED,
manifests and test output are absent. The system disk retains MD5, ARC, EDX,
overlays and FastBasic. The matching `exec816-fastbasic-source.zip` contains the
tagged Exec source and pinned patched FastBasic donor tree; all 4,539 source
checksums pass. Both ZIPs have separate SHA-256 files.

All eight application binaries match the checksum-verified 0.2.2 distribution
byte for byte. Reserved bank-zero growth is **0 fixed/root/kernel bytes,
0 bytes for each of twelve public Tasks and 0 idle bytes**, including guards,
alignment and unused capacity. The complete bank-zero budget and Task pool
reservations match 0.2.2. The diagnostics buffer and initial SIO call use
existing stack reservations; no pool or loading arena grows.

## Remaining gates

This is the **release-preparation tier** for a draft preview. These selected
matrices and final-package checks pass; full hosted-system/release qualification
remains open. The full o65 release matrix and accurate 256-byte MyDOS COPY
matrix were not rerun. Physical accelerator/cartridge hardware, physical
FujiNet UART timing and XLOS CONFIG/OPTION boot remain unqualified. Assumed-XLOS
injection does not qualify arbitrary ROM compatibility. Arbitrary OS high-memory
allocations and third-party PBI/native interrupt handlers remain unsupported.
No editor-latency or boot-speed qualification is claimed.
