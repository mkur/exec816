# Mapped VRAM raster copies

[History](README.md) · [Plan](../plans/gem4xe/mapped-raster-plan.md) ·
[Display contract](../reference/display.md) ·
[Foundation evidence](../development/gem-raster-mapped-foundation.json)

## Workspace and driver foundation

The foundation reserves `$4C000–$4FFFF` (16,384 bytes) from the previously
unassigned 20 KiB interval. The generated C and Action! constants agree with
the map. Total reserved VRAM is 489,984 bytes, with 34,304 unassigned (34,272
after diagnostic borrowing). The retained Shell backing is unchanged.

Private `VbxeOwnerMapPage` fences, maps one prepared page, invokes a synchronous
CPU callback and disables the aperture before return. Only the admitted
physical owner runs it. The callback cannot start graphics, remap, wait or
retain its window pointer. Normal Task preemption and interrupt delivery stay
enabled. The existing mapping assembly and asynchronous recovery protocol are
unchanged; there is no new kernel or public ABI operation.

The optimized G3 pattern, mapping-NMI and mapped-page cases pass. Each checks
32,914 mapped-page assertions, all 16 KiB including untouched bytes, four
callbacks across active VBI and a computing peer, underlying CPU aperture RAM,
exact OS screen/cursor preservation during display ownership, physical SIO,
retained native/C context, guards and normal cleanup. Four injected NMI entries
between mapping stores retain the expected hardware publication order and
saved Task frame.

The old G3 runner needed a focused refresh to execute against the current
kernel: compare its eight-Task fixture with an eight-Task reference, allow
8 KiB of upper image data, and recognize the current guarded-stack NMI
prologue. Volatile fixture rendezvous points now check OS screen preservation
after close and before the deliberate CON write. Native target assertions
still require successful console reopening, the complete write and teardown.
These changes do not alter production interrupt code or Task reservations.

The legacy GEM source manifest fingerprints an older compiler configuration.
The execution record explicitly preserves the local test override to the
current `toolchain/actionc.json` pin, revision
`05c01f39ff3beef97af0e65b0a16666f5a1bd805`. Only the host compiler build profile
changes to release; the compiler revision and optimized guest policy remain
pinned. The fixture's upper image-data allowance grows by 4,096 bytes; production
upper reservations do not change in this foundation.

Reserved bank-zero growth is **0 fixed, 0 root/kernel, 0 idle and 0 bytes per
public Task**, including guards, alignment and unused capacity. The CPU
aperture remains `$8000–$8FFF` (4 KiB). The entire 16 KiB VRAM reservation is
counted, including unused row-slot capacity. These are development checks,
not full hosted qualification or a copy-performance result.
