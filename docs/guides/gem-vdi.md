# Optional interactive GEM/VDI demo

[Guides](README.md) · [Supported interface](../reference/gem-vdi.md) ·
[Input and concurrency measurements](../history/gem-input.md)

Build the optional graphics program alongside the standard OF816 demo:

```sh
python3 tools/build_demo.py --gem-vdi --output build/gem-input/i7-demo
```

This uses the pinned Action! compiler, Calypsi 5.18 and GEM source inputs. See
[build prerequisites](../contributing/building.md) and the
[port instructions](../../ports/gem4xe/README.md) for obtaining and verifying
those inputs. The output is `build/gem-input/i7-demo/exec816-demo.zip`.

The ZIP still boots `Exec-of816.xex` into OF816, with its five-second countdown
and standard shell/prime demo. An additional `gem-vdi/` directory contains the
separately selected graphics XEX, its matching SDFS disk and notices. Maps,
manifests, extracted source and test evidence remain outside the ZIP.

For graphics, cold-boot with the supplied AltirraOS ROM. Select Atari 800XL,
64 KiB base RAM plus fifteen CPU high banks, 65C816 at 8×, shadow ROM and PAL.
Enable full VBXE FX 1.26 at `$D600`, private 512 KiB VRAM, no shared RAM and no
VBXE IRQ. Mount **`gem-vdi/graphics.atr`** as drive 1 and load
**`gem-vdi/Exec-gem-vdi.xex`** directly. Use physical `generic56k` SIO with patch,
burst and random delay disabled and accurate sector timing enabled. The exact
emulator/ROM hashes and settings are in the [platform pin](../../toolchain/altirra-gem-vdi.json).

The application displays a text field, Count and Exit buttons while the Action!
root supervisor reads a cold 2 KiB file. Application and renderer use the two
existing 2,560-byte Task stacks. Root owns file work; the application owns input
and the renderer client. Disk completion leaves the scene open for interaction.

| Key | Action |
| --- | --- |
| Tab | Cycle the text field, Count and Exit. |
| Printable keys / Backspace | Edit the focused 24-character field. |
| Return | Activate the focused button. Count advances its number and color. |
| Escape / BREAK | Exit from any control, settling any active disk request first. |

Exit restores text, displays completion for five seconds and returns to the OS.
A missing, wrong, short or corrupt disk file follows cleanup and displays the
matching disk name in text. The root `system.atr` belongs to the standard demo;
graphics requires **the `gem-vdi/graphics.atr` shipped with its XEX**.
If a missing drive leaves the serial bus offline, the message also requests a
reset; the program preserves that bus ownership instead of returning to the OS.
Start from an inactive VBXE baseline; unknown previous ownership is unsupported. A device that remains
busy after bounded recovery requires reset and retains its resources.

![The interactive keyboard scene](../images/gem-input.png)

The [I6 measurements](../development/gem-input-i6.json) bound the recorded small
keyboard redraw workload at 12 raw / 11 optimized PAL ticks from native capture
to visible update during physical SIO, including wrap controls. The renderer's
fixed cursor and button gestures are tested with injected pointer events.
The distributed image contains no injector, timing gates or substituted hardware
status; it has no physical mouse backend. AES, desktop, GEMDOS, virtual workstations,
external fonts and multiple GUI clients remain unsupported. These are focused
development results on the pinned emulator, not general hardware qualification.

To return to the usual demo, use its no-add-ons configuration, mount the root
`system.atr` and boot the root `Exec-of816.xex`.

Reproduce the focused graphics check for the exact packaged image:

```sh
python3 tools/test_gem_interactive.py --mode opt --production --replay \
  --case keyboard --output build/gem-input/i7-demo/gem-vdi
python3 tools/test_of816.py --output build/gem-input/i7-demo/of816
```

The checker verifies visible pixels and palette against an independent font
model, native keyboard state, physical IRQs and file contents, guards, stack
headroom, allocator ownership and OS/display restoration. The OF816 control checks
automatic and Forth-command shell routes, ordinary input, disk commands and exit.

The G5 computing-peer/font workload remains available as a separate development
regression through `tools/test_gem_concurrent.py`. The G4 corpus covers the
[supported drawing primitives](../reference/gem-vdi.md); I5 adds exact cursor
pixels, and I6 covers concurrency and failures. Their historical records remain
unchanged when the optional artifact is refreshed.
