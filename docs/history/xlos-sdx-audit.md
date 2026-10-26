# XLOS816F and the SDX bridge audit

[Historical records](README.md) · [Current platform contract](../reference/platform.md)

This is the pre-refactor audit. The subsequent
[implementation record](xlos-sdx-support.md) documents the current adapter and
working application/boot checks. Statements about release rejection below refer
to unchanged v0.2.1.

XLOS816F is a credible second firmware target. The reported `$0002` halt comes
from Exec's AltirraOS-specific ROM admission, before an SDX program runs. It is
not evidence that XLOS is incompatible with SpartaDOS X. The ROM author
[lists SpartaDOS X 4.2x and its addons as compatible](https://drac030.krap.pl/en-kompatybilnosc.php),
and developed the OS with an internal SDX installation. That historical list
does not qualify Exec's private-bank guest implementation.

This audit examined stock **2.48 F** and **2.49 F**, from the author's
[December 2025 and October 2026 downloads](https://drac030.krap.pl/en-pliki.php).
Exact hashes, configuration, results and exclusions are in the
[development record](../development/xlos-sdx-audit.json). The reporter's exact
file was not supplied; these results apply to those two images, rather than
every file named `XLOS816F.ROM`.

## The startup failure

The unchanged v0.2.1 cartridge reproduces the photographed sequence on both
images: OF816, kernel loading, RAM adoption, Task/heap initialization and VBXE
detection succeed, followed by `KERNEL READY=$0000` and
`System halted: $0002`. The failing call is `sdx_rom_install`.

That routine compares all 14,336 CPU-visible ROM bytes with the embedded
AltirraOS image before modifying PORTB or taking ownership. XLOS differs at the
first compared byte, `$C000`. Status 2 means ROM mismatch here. It does not mean
that the reporter's VBXE revision failed detection.

Admitting different bytes alone would be incorrect: three bank-zero bridge
jumps still enter AltirraOS internals. Those addresses point into unrelated
XLOS code, sometimes even into the middle of an instruction.

| Entry used by the bridge | AltirraOS 3.44/816 | XLOS 2.48 F | XLOS 2.49 F |
| --- | --- | --- | --- |
| Emulation NMI dispatcher, two jump sites | `$C17B` | `$C018` | `$C018` |
| Emulation IRQ dispatcher, one jump site | `$C1E1` | `$CA86` | `$CA7B` |
| Native NMI handler, obtained through `$0259` | Saved at startup | `$CAA3` | `$CA98` |
| Native IRQ handler, obtained through `$025C` | Saved at startup | `$CA73` | `$CA68` |
| Native COP handler, obtained through `$0256` | Saved at startup | `$CAE2` | `$CAD7` |

The emulation entries above are the original ROM vector destinations, captured
before the shadow vectors are replaced. Chaining through the *patched* `$FFFA`
or `$FFFE` would recurse into Exec's hook.

## Compatible interfaces and significant differences

The public CIO entry, COP `$00` calling mechanism and native RAM-vector layout
match the interfaces Exec uses. Exec can retain its COP `$50` gateway while
forwarding OS calls through the saved native COP vector. The
[author's programming reference](https://drac030.krap.pl/en-specyfikacja.php)
describes these interfaces and the native interrupt rules.

Disassembly confirms that XLOS's native IRQ/NMI wrappers keep native mode,
normalize D/DBR, save index registers and construct a compatible legacy-handler
frame on the current stack. AltirraOS's native interrupt path instead enters
emulation mode. XLOS's COP `$00` still enters emulation for the called legacy
routine and restores the native caller afterward. These distinctions require
separate stack accounting, even when the visible APIs agree.

XLOS does not remove the reason for our early guest hooks: an emulation guest
can have a private D and upper-bank DBR. The original emulation dispatchers do
not establish the complete native/guest ownership protocol before touching OS
state. Keep the shared page-one lease, interrupt exclusion, complete context
save and native return handling.

The ROM's F suffix selects Marslett floating point. Exec FastBasic uses its
own generated private math pack, described in the
[port notes](../../ports/fastbasic/README.md), so this difference does not itself
require changing the guest's floating-point implementation.

## Executed evidence

All checks are **development tier**, on the pinned macOS arm64 AltirraSDL
bridge, 65C816 at 8x, PAL, 64 KiB base plus 63 high banks, and private VBXE
FX 1.26 at `$D600`. SIO patching and burst transfers are disabled. XEX fixtures
use Disk Boot because the default emulator XEX loader fails before entry under
XLOS. Production-startup experiments use the released Atarimax image and a
private writable copy of the combined system disk.

For each ROM:

- Eight native interrupt cases cover all four M/X combinations with I clear
  and set, including decimal status, hidden accumulator B, private D/DBR and a
  stack at `$47EF`. Registers, status, stack and guards survive; the OS clock
  advances.
- A real COP `$00` call reaches a bank-zero RTS target and returns its index
  registers while restoring the native caller's D/DBR/S/E and guards.
- Five standalone P2 guest-transition cases each retire 32 real VBIs and
  thousands of POKEY timer IRQs. Complete contexts, DP/stack guards, ROM mapping
  and RAM beneath the ROM are checked. Only the fixture's expected ROM source
  and NMI chain destination change. P2's historical page-copy mechanism is a
  component test, not evidence for the current resident lease by itself.
- The separately pinned optimized resident-stack fine-scroll fixture passes
  all 113 assertions at anchor `$0190`. It exercises real nested ROM VBI work,
  preservation of the retained page-one frame, guard checks, native cleanup
  and vector/MEMLO restoration. Its earlier Exec build is identified explicitly
  in the record; it is not substituted for the release binary.
- An unchanged release boot rejects the ROM with status 2. A disposable
  emulator-only adaptation replaces the 16 KiB expected image and the three
  jump operands listed above. Installation then returns 0 and native Task/VBI
  activity continues for 120 PAL intervals. This bounded observation stops
  during startup; it does not establish a ready desktop or working disk tools.

No ROM file, release asset, platform pin or production bridge was changed.
The audit adds **0 reserved bank-zero bytes**, fixed, root/kernel, each of
twelve public Tasks and idle, including guards, alignment and spare capacity.

## Work needed for support

Use an explicit firmware adapter/profile with exact admitted ROM identity,
matching shadow source and original emulation entry destinations. Preserve the
existing reversible install/remove protocol and capture vectors before patching.
Do not simply remove the ROM comparison or claim compatibility from a filename.

Re-establish the worst-case ROM/interrupt stack bound for XLOS. The passing
`$0190` scrolling case supports keeping the existing 128-byte reserve, but does
not prove every permitted IRQ/NMI interleaving fits it. The current 122-byte
source bound is specifically for AltirraOS.

Then exercise current MD5, argument-free ARC and archive operations, EDX
typing/cursor/save, parked FastBasic and restart, console batching, concurrent
native SIO, and clean shutdown. Complete combined-ATR/FujiNet boot and supported
accelerator hardware checks separately. XLOS high-memory allocations and any
PBI/native extensions must respect Exec's upper-memory ownership; the existing
bank `$01` reservation alone does not authorize arbitrary firmware allocations.

The old [XLOS boot record](../development/xlos-boot.json) predates current SDX
admission and cannot replace these checks. Clear firmware-specific startup
diagnostics would also make this failure much easier to understand.

## Reproduction

The JSON record freezes the original runner and fixture hashes. The runner has
since become the acceptance check for the refactored adapter; it no longer
injects ROM bytes or jump operands. To check the current implementation, keep
the original ROM files outside the distribution and use current emitted fixtures:

```sh
python3 tools/audit_xlos_sdx.py \
  --rom /path/to/2.48/XLOS816F.ROM \
  --rom /path/to/2.49/XLOS816F.ROM \
  --resident-build build/xlos-refactor/stack-opt \
  --output build/xlos-refactor/firmware-matrix
```

The optional resident argument replays a hash-verified emitted fixture and
records its compiler/build identity. Without it, no resident-stack execution
is claimed. Use `test_sdx_firmware_demo.py` for the full current boot/tool smoke
checks recorded in the implementation history.
