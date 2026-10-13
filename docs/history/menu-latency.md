# Dropdown menu latency

[Design](../plans/gem4xe/menu-latency-design.md) ·
[Implementation plan](../plans/gem4xe/menu-latency-plan.md) ·
[Current desktop contract](../reference/desktop.md) ·
[Development evidence](../development/menu-latency.json)

Menu painting now submits complete labels, batches up to four intersecting
objects within an 80-cell text budget, and scans at most the admitted 32 objects
per callback. Native rows paint up to 24 characters at once and start at the
row intersecting the current strip. The existing 16-row offscreen buffer still
publishes only completed strips.

Native highlighting damages the old and new rows instead of the whole popup
and bar. Opening/closing changes only the affected bar segments or GEM titles;
menu replacement retains full invalidation. Popup/bar painting has precedence
at new scene transactions, with an ordinary round-robin opportunity after two
preferred menu transactions. Live transactions and application update locks
retain their ownership.

## Measurement

`tools/measure_menu_feedback.py` drives keyboard input through the exact OF816
ZIP, on an idle SYS folder desktop. It measures submission to matching pixels
over x=128..639, y=0..207, using settled reference images of the same static
scene. These are complete menu and exposure regions, not acceptance timestamps
or one early-changing pixel. Independent pixels are checked separately by the
AES menu suite. Each cohort contains 20 samples, sampled once per PAL frame
(about 20 ms). Reported p95 is empirical and does not establish a loaded or
real-hardware latency bound.

Application input opens File, highlights its first enabled entry, switches to
View and dismisses with Escape. Native input opens Windows, moves through two
rows and dismisses. Baseline is the unchanged `bf7af75` task-names demo; the
compiler binary, ROM and emulator pins match the new demo. Both use the mild
mouse profile, VBXE and 63 high RAM banks. The timed input is keyboard-driven;
the regression suite additionally checks pointer interaction.

Times in milliseconds:

| Interaction | Median before | Median after | p95 before | p95 after |
| --- | ---: | ---: | ---: | ---: |
| File menu opens | 722.0 | 401.2 | 722.2 | 401.2 |
| Application highlight | 100.3 | 80.3 | 100.3 | 80.3 |
| File to View | 942.5 | 782.1 | 942.5 | 782.3 |
| View closes | 441.1 | 401.2 | 441.3 | 401.2 |
| Windows opens | 280.7 | 180.6 | 280.9 | 180.6 |
| Native highlight | 100.3 | 80.3 | 100.3 | 100.3 |
| Native next row | 140.5 | 100.3 | 140.5 | 100.3 |
| Windows closes | 561.6 | 501.4 | 561.6 | 501.4 |

File opening median improves by 44%; Windows opening improves by 36%.
Native highlight p95 is unchanged at this measurement resolution. The repeated
frame-aligned workload has little variance; it is not a random-arrival tail
study. Raw samples, exact ZIP hashes and machine pins are in the evidence.

The larger gains are in opening. Closing and switching headings still require
the covered application to repaint. The implementation deliberately preserves
that path: unconditional restoration of a saved framebuffer could overwrite
changes made by another Task while the menu was open. A safe save-under design
is the next separate restoration optimization. Faster opening also remains
possible; these changes do not make menus instantaneous.

## Development checks and memory

The optimized emitted menu regression checks exact application/native pixels,
63-character labels at odd X, a partial final glyph, a vertically clipped glyph,
checked and disabled states, and two long labels intersecting one strip to
exercise the budget continuation. It also covers hidden entries, pointer and
keyboard selection, heading switches, held-button cancellation, replacement,
different owners, removal, durable message delivery and cleanup. All 290 AES
checks pass with intact guards. The smallest observed public-Task margin above
its stack floor is 575 bytes in this fixture.

The exact packaged desktop also passes 30 consecutive highlight changes in
each menu type while a visible Counter updates. Counter completes two timer
updates and two repaints in each burst, with changed digit pixels. This checks
progress under menu input, not loaded latency. The final OF816 walkthrough
observes 249 PAL autoboot frames (within the five-second check), exits with
intact guards and leaves no live Tasks. Earlier harness attempts used too short
a cold-launch wait or hid the changing Counter digit behind Files; the final
check waits for the child and verifies a fully visible digit rectangle.

The host suite runs 459 tests: 455 pass and four existing cases skip. No compiler
test suite, full qualification matrix or hardware qualification was run.
The release host compiler uses the unchanged clean pin and has the same binary
hash as the baseline. A development stall in the new budget calculation was
isolated to incorrect signed-shift emission by Calypsi 5.18; positive pixel
sizes now use unsigned arithmetic. The emitted long-label case verifies
forward progress and final pixels.

ML1–ML4 add **0 fixed / 0 per public Task / 0 idle reserved bank-zero bytes**,
including guards, alignment and unused capacity. Baseline and new demo have
identical `bank_zero_budget`, `runtime_reservations` and `task_pools` records.
No VRAM reservation, public ABI, Task, message, signal or timer is added.

## Demo

The distribution is `build/menu-latency/demo/exec816-demo.zip`, built through
`tools/build_demo.py`. It includes OF816, the pinned ROM, system/WORK disks,
notices, checksums and five-second autoboot. Development outputs stay outside
the ZIP. Launch from the repository with:

```sh
./build/menu-latency/demo/launch-altirra.command
```

ZIP SHA-256:
`81c339570194b9041be0407fa85c096d79d596236bc133795c23ccfc3d95b2a2`.
The source remains uncommitted at the time of this record; evidence includes
the base revision and exact changed-source hashes.
