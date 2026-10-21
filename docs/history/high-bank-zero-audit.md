# Bank-zero RAM above the VBXE aperture

[Historical records](README.md) · [Current platform contract](../reference/platform.md#bank-zero-memory-budget)

The subsequent [twelve-Task delivery](twelve-task-layout.md) implements this
audit's proposed map; the findings below retain their original audit scope.

## Decision

Use **`$9000–$BBFF` (11,264 bytes, 44 pages)** as ordinary bank-zero RAM in
the next memory-map revision. Cartridge compatibility is excluded by project
direction. This range can hold native direct pages and guarded stacks; it needs
no bank-switching API. The present allocation remains unchanged by this audit.

The pinned machine actually has **11,296 free bytes at `$9000–$BC1F`**.
Leave the final 32 bytes unused and reserve `$BC00–$FFFF` in the proposed map.
Keep the OS display list at `$BC20–$BC3F` and its 960-byte screen at
`$BC40–$BFFF`. Dropping cartridges does not remove those live OS allocations.

## Scope and pins

This is a source audit and focused **development** execution record for the
unchanged optimized WB9 GEM desktop, not release qualification or a twelve-Task
implementation. The machine is an 800XL, PAL, 65C816 at 8×, 64 KiB base RAM,
63 linear high banks, ROM shadowing enabled, BASIC disabled, no cartridge, and
VBXE FX 1.26 with private 512 KiB VRAM at `$D600`.

The executed ROM is AltirraOS 3.44 for 65C816, SHA-256
`85a6e927038f401f05f0056fd41a062986cbf7e104c1ac135c248764c132c9a7`.
Its unmodified source comes from `Altirra-4.40-src.7z`, archive SHA-256
`77ff8057e92c17127cc1f5b70084f11ac13d56d6c896d2439b52574deec961ca`.
The ROM's exact assembly listing and provenance are retained in
`build/firmware/altirraos-816.lst` and `provenance.json`.
The actual bridge binary is SHA-256
`a7defb3b8a471711b4f1fd679f3b8f8364a415494ae68f59be6628334713ca59`;
the full machine, compiler, image and executable pins are in the
[audit evidence](../development/high-bank-zero-audit.json).

## Ownership audit

| Range | Finding |
| --- | --- |
| `$8000–$8FFF` | Live 4 KiB VBXE CPU aperture. Retain its reservation. |
| `$9000–$9FFF` | Base RAM when no cartridge is mapped. No admitted Exec/ROM owner was found. |
| `$A000–$BBFF` | Base RAM with BASIC disabled (`PORTB` bit 1 set), and no cartridge. No admitted Exec/ROM owner was found. |
| `$BC00–$BC1F` | Also free on the pinned mode-0 screen; leave as 32-byte boundary slack. |
| `$BC20–$BC3F` | Live ROM display list. Preserve. |
| `$BC40–$BFFF` | Live ROM text screen. Boot diagnostics write it, and console shutdown restores it. Preserve. |
| `$C000–$FFFF` | ROM, hardware and the SDX reversible ROM-shadow windows. This audit does not reclaim them. |

The exact ROM listing resolves the apparent `$9000` ceiling:

- `ScreenOpenGr0` at `$F441–$F49A` allocates from `RAMTOP`, records `SAVMSC`
  and the display-list address, checks `APPMHI`, then decrements `MEMTOP` at
  `$F49A`. **MEMTOP is inclusive**, despite an earlier misleading routine
  comment. Measured values are `RAMTOP=$C0`, `MEMTOP=$BC1F`,
  `SDLSTL=$BC20` and `SAVMSC=$BC40`.
- The loader and hosted entry use `$9000` as their own minimum-memory/claim
  constant and publish `MEMLO=$9000`. They do not set the OS's MEMTOP to
  `$9000`. See [loader.s](../../platform/altirraos/loader.s),
  [hosted.s](../../platform/altirraos/hosted.s) and
  [layout.inc](../../platform/altirraos/layout.inc).
- ROM VBI/keyboard/serial handling uses OS workspace, vectors and supplied
  buffers; it has no fixed scratch allocation in the candidate interval.
  ROM editor output writes its screen through the saved screen pointers.
  ROM graphics modes can allocate larger screens down into this interval;
  arbitrary OS `GRAPHICS`/`S:` mode changes remain outside the admitted native
  console/display ownership contract.

[VBXE transfers](../../platform/altirraos/vbxe.c) map only the 4 KiB window
at `$8000`, using control `$88`; their CPU-buffer extent check already admits
buffers above `$8FFF`. The mapper, upload and blitter paths do not borrow the
candidate RAM. The SDX [ROM-shadow adapter](../../platform/altirraos/sdx-rom-shadow.s)
changes only `PORTB` bit 0, preserving BASIC's disabled bit, and copies only
`$C000–$CFFF` and `$D800–$FFFF`. Guest FastBasic's virtual MEMTOP is separate
from this physical native bank-zero map.

The existing [cartridge stub](../../platform/altirraos/cartridge.s) copies a
1 KiB live loader to `$9000–$93FF`. It would conflict with early high-RAM pool
initialization. Cartridge launching is excluded; preserving that loader is not
a requirement for the new map. The XEX/OF816 path has no corresponding owner.

## Executed evidence

The [audit runner](../../tools/audit_high_ram.py) performs two independent
checks and keeps all intermediates under its development output directory:

1. A [disposable assembled XEX](../../probes/os-boundary/high-ram.s) fills and
   verifies every word in `$9000–$BC1F` with two address-dependent complementary
   patterns through CPU instructions. It uses native `D=$B000` and
   `S=$BBEF` for direct-page and subroutine/push/pop operations with NMI masked,
   restores the canary, then calls real ROM CIO through `COP $00` on the OS
   stack and waits 120 VBI ticks. The whole canary and OS display list survive.
2. The exact optimized WB9 XEX and matching system disk run unchanged in a
   copied development bundle. A debugger-initialized canary covers the same
   11,296 bytes before OF816. Checks span OF816 startup, its five-second
   autoboot, handoff, payload loading, native startup with verbose diagnostics,
   the live desktop, native scrolling, writable disk I/O, MD5, argument-free
   ARC, integer and floating-point compile/run commands, idle VBIs and EXIT.
   Existing execution checks cover stack/domain guards, bank ownership,
   vectors, MEMLO, input state and OS screen restoration.

All 18 canary checkpoints passed. The hosted run completed with 5,726 native
NMIs, 28,663 IRQs, 4,589 context switches, intact guards and no live Tasks at
EXIT. The host suite passed all 548 tests. These counts describe the observed
run and are not timing or interrupt-boundary qualification claims.

The hosted test observes unused high RAM while existing Tasks use their current
pools. The private high-D/S probe masks interrupts. Together they establish
mapping and coexistence for this profile, **not preemptive execution of Tasks
whose pools have been relocated there**. Test those domains and interrupted
stack transitions when implementing the new map. Alternate ROMs, graphics
modes, cartridges and hardware expansions are not covered by this record.

Reproduce with a prepared WB9 development bundle:

```sh
python3 tools/audit_high_ram.py \
  --bundle build/fastbasic-workbench/wb9-demo-final \
  --output build/high-ram-audit/replay
```

Use a fresh output directory. The runner copies the bundle, pins the actual
ROM/emulator and leaves the original delivery and writable media untouched.

## Consequences for twelve Tasks

The current SDX-enabled eight-Task build leaves 6,912 bank-zero bytes free.
Releasing 11,264 bytes raises that to **18,176 bytes before adding pools**.
Four extra ordinary pools cost **6,400 bytes**: four 256-byte DPs, four
1,312-byte stacks and eight 16-byte outer guards. That leaves **11,776 bytes**.
Making one of the new pools a third 2,560-byte large stack raises the added
cost to **7,648 bytes**, leaving **10,528 bytes**. Each stack's interrupt
reserve is included in the stack size; there is no DP alignment padding.

An illustrative placement keeps every existing pool and the entire boot arena:

| New slot | Direct page | Stack reservation, including guards | Stack base / usable allocation |
| --- | --- | --- | --- |
| 8 | `$9000–$90FF` | `$9400–$993F` | `$9410` / 1,312 bytes |
| 9 | `$9100–$91FF` | `$9940–$9E7F` | `$9950` / 1,312 bytes |
| 10 | `$9200–$92FF` | `$9E80–$A3BF` | `$9E90` / 1,312 bytes |
| 11 | `$9300–$93FF` | `$A3C0–$ADDF` | `$A3D0` / 2,560 bytes |

Private idle becomes slot 12 but keeps its current physical DP/stack. This is
checked arithmetic, not a generated or executed twelve-Task profile.

Implementation must update the profile, its checked fixed reservations and the
Task-pool generator together. Publish an explicit per-slot DP map rather than
assuming every DP follows `$0D00 + slot*$100`; the emitted kernel already uses
`poolDp`, `poolStack` and `poolSize`. Raise entry's minimum-memory requirement
to cover the highest claimed byte and publish a MEMLO claim covering the new
pool range, restoring the original MEMLO on shutdown. Keep MEMTOP and RAMTOP
as OS allocation facts. Current build-time `$9000` bounds and the broad
`os-high` reservation intentionally still reject this proposed placement.

No earlier bootstrap retirement is needed for this placement. Root, kernel,
existing public slots, idle, SDX guest pages, guards, diagnostic scratch and
the OF816 five-second path can keep their current addresses and sizes. Task
capacity still needs consistent metadata/caller updates and emitted-code
coverage; guest, AES, window and console capacities are separate limits.

**Actual reservation change in this audit: 0 fixed, 0 root, 0 kernel,
0 per-public-Task and 0 idle bank-zero bytes**, including guards, alignment
and unused reserved capacity. The figures above are proposed follow-on costs.
