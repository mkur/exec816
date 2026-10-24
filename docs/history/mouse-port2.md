# Mouse on joystick port 2

[Current input contract](../reference/input.md) ·
[Platform contract](../reference/platform.md) ·
[Development evidence](../development/mouse-port2.json)

The Exec ST mouse backend now uses **joystick port 2**. It normalizes PORTA
bits 4–7 to the existing four-bit decoder and reads the active-low left button
from TRIG1 (`$D011`). The shared timer, quadrature decoder, queues, routes,
acceleration, ownership and cancellation semantics stay unchanged. Capture
continues to avoid PIA direction, paddle, trigger-latch and SKCTL writes.

`INPUT.POINTER_PORT` and C `INPUT_POINTER_PORT` are generated from
`abi/input.json` and equal 2. Every current native/test caller uses that
selection. A pointer configuration selecting port 1 reports `UNSUPPORTED`;
rebuild callers with the current definitions. Config/event layouts remain
version 4 with unchanged offsets and sizes.

Graphical Exec launchers select the unmodified Altirra **Mouse → ST Mouse
(port 2)** preset in their private input profile. They preserve the user's
original settings. The headless observer selects the same preset; current
binary/source/patch pins were refreshed. The separately packaged, unmodified
GEM4XE reference still uses its donor's port-1 setup.

## Development scope

All 644 host checks pass, including inherited launcher input settings and
preservation of the user's source configuration. The electrical probe observes
all four directions and left-button edges on the real emulated controller.
The optimized capture probe passes 117 checks and confirms that a joystick's
motion/fire on port 1 produces no port-2 pointer events. Raw and optimized C/native
ABI probes each pass 105 checks, including rejected port-1 configuration,
context restoration, timer IRQ coexistence, ownership and guards.

The ABI fixture's reservation comparison now selects its actual eight-Task
capacity before comparing with the platform map; the default map has twelve.
No reservation assertion was removed. The final twelve-Task build's bank-zero
budget, pools, runtime and phase reservations exactly match the preceding demo.
Added reserved bank-zero bytes are **0 fixed, 0 root/kernel, 0 per each of twelve
public Tasks and 0 idle**, including guards, alignment and unused capacity.
The two nibble-normalization sites add four code bytes in upper `NATIVE_WORK`,
with no new state. A sampled hardware read costs six more CPU cycles than the
previous mask; timer rates are unchanged.

The full demo was rebuilt with OF816 and its five-second autoboot, the combined
D1 system/work ATR, MD5/ARC/EDX, FastBasic and sample sources, separate QED ATR,
cartridge transports, ROM, notices and checksums. Current corresponding source
is supplied separately; QED source packaging can explicitly snapshot the working
tree while still verifying every recorded native runtime source hash.

The extracted final ZIP cold-boots through OF816's five-second countdown into
Exec. Physical mouse motion and clicks select windows, and the shell launches the
FastBasic editor. Four typed characters and four vertical caret moves match independently
reconstructed scanout. Quit/Discard, resource collection and normal EXIT pass
with intact guards. These eight samples are an interaction smoke test, not a
new timing comparison. The package audit verifies every ZIP checksum/CRC, all
25 notices and all 78 independently extracted system files, including the tools
and sample source.

The refreshed ZIP is at the repository root and
`build/mouse-port2/demo/exec816-demo.zip`; its launch script is
`build/mouse-port2/demo/launch-altirra.command`. FujiNet's `SD/EXEC816` contains
the same files after both writable media matched the previous templates.
Corresponding FastBasic and QED source/relink packages are under
`build/mouse-port2/` with checksums, outside the small boot ZIP.
These are development checks on the pinned AltirraOS 3.44 65816 / 800XL / PAL /
8× / 63-high-bank / VBXE configuration, not a release or physical-hardware
qualification. Existing historical timing and qualification records retain their
original port, inputs and hashes.
