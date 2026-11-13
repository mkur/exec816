# Shared Widget and Counter on Exec and MagiC

[Guides index](README.md) · [Source compatibility plan](../plans/gem4xe/gem-source-compatibility-plan.md)

This small pair runs the same application sources on both systems. Widget has
a label and a Toggle button. Click the button or press Space to increment the
label and toggle the selected state. `Q` or its closer exits Widget. Counter
runs in an independent process and keeps running until its own closer is used.
Drag the windows to overlap and expose either application.

Choose one case at a time:

| Case | Foreground | Background |
| --- | --- | --- |
| `solo` | Widget, without a timer | None |
| `silent` | Same Widget | Counter with a 100 ms timer; ticks change only its model |
| `paint` | Same Widget | Counter with the same timer; ticks also repaint the digits |

Silent Counter still draws its initial window and repairs `WM_REDRAW` exposure.
Its digits stay unchanged between exposures. It therefore separates timer/event
activity from repeated drawing, rather than using an invisible or covered window
as a substitute for silent operation. Counter counts delivered timer events;
it does not catch up missed wall-clock deadlines.

## Exec

Build the optional sample into the normal OF816 desktop package:

```sh
python3 tools/build_demo.py --output build/gem-widget/demo \
  --gem-desktop --gem-widget --release-compiler
build/gem-widget/demo/launch-altirra.command
```

Keep the standard five-second OF816 autoboot. In the Shell terminal, enter one
of these commands:

```text
RUN SYS:C/PAIR.APP solo
RUN SYS:C/PAIR.APP silent
RUN SYS:C/PAIR.APP paint
```

Close both sample windows before launching another case. `JOBS` collects the
finished shell job. `PAIR.APP` without arguments selects `paint`, so it can
also be opened from Files. Its Exec wrapper launches `PULSE.APP` and
`WIDGET.APP`, sleeps while they run, and collects their Process identities.
The wrapper opens no window and uses no periodic timer. The current C APP
runtime registers it with AES before `main`; the wrapper immediately releases
that application identity with `appl_exit`. This leaves the existing four
client slots to Desktop, Terminal, Widget and Counter. Its C binding remains
runtime-owned until return. The applications can
also be launched independently. The generated `exec816-demo.zip` contains the
matching writable SYS disk, boot files, short guide, licenses and checksums.

## MagiC

Use the [pinned ST prerequisites](atari-st-reference.md#prepare-and-launch-the-object-tree-sample):

```sh
python3 tools/prepare_magic_widget.py --offline --run
build/magic-widget/launch-solo.command
build/magic-widget/launch-silent.command
build/magic-widget/launch-paint.command
```

Omit `--offline` if the reference inputs are not cached. Run one launcher at a
time. Boot fast-forwards and returns to normal speed when the applications are
ready. Cmd+Q quits Hatari on macOS; AltGr+Q elsewhere. F12 opens its settings.

The resource-free desktop uses MagiC's parallel `shel_write` mode and then waits
for messages without a timer. Startup logs publish addresses for external
observation; they perform no further writes until the application exits. Build
identities, functional results and screenshots stay outside the guest application
sources, under `build/magic-widget/`.

## What is shared and what can be compared

Both compilers build these files directly:

- `examples/gem-widget/main.c` and `widget.c`: the complete Widget application.
- `examples/gem-widget/counter-main.c` and `examples/gem-counter/counter.c`:
  the Counter configuration and complete event/drawing loop.

Startup, executable format, GEM bindings and host observation differ. The
ordinary Counter keeps its default one-second timer and drawing behavior.
Widget uses `evnt_multi`, `wind_update`, visible rectangles, clipping and
`objc_draw`; it has no native presentation extension. Each activation redraws
the same small canvas in one UPDATE transaction.

Widget requests the same **304×128 work area at (32,56)** through `wind_calc`.
AES chooses its own frame and object font. MagiC's objects use its native 8×16
system font; Exec uses its 8×8 object font. Counter uses an 8×8 VDI font on both.
Its outer geometry is shared, so different frame metrics produce different
Counter work areas.

This is a functional reference harness. The pinned ST has an 8 MHz 68000 and
640×400 monochrome display; Exec uses the dedicated AltirraOS 65816 and VBXE
640×240 display. Absolute elapsed times would include CPU, compiler and display
differences. Within-target `silent/solo` and `paint/solo` slowdown ratios are a
useful next measurement. No latency, throughput or relative-speed result is
claimed here. Frozen digits alone do not establish scheduling starvation.

The sample enlarges no fixed/root/kernel/idle or public-Task bank-zero
reservation: every delta is **0 bytes**, including guards, alignment and unused
capacity. Exec uses its existing twelve-Task pools. Applications and the sleeping
launcher consume those existing slots and upper-memory image/heap storage while
running.

All three sample APPs request the existing **1,312-byte stack pools**, including
interrupt headroom. Using the generic 2,560-byte APP request for both launcher
and Widget exhausted the available large pools in the standard desktop. The
smaller requests change APP admission metadata; they do not enlarge any pool.

## Development checks

The [first execution record](../development/gem-widget-comparison.json) passes
all three cases on both pinned machines. Run the Exec check against the package:

```sh
python3 tools/test_gem_widget.py --bundle build/gem-widget/demo \
  --output build/gem-widget/exec
```

Exec checks mouse press/hold/release, Space and Q, label/button pixels, silent
versus painting Counter pixels, independent progress after Widget closes, normal
Counter retirement, guards/ownership and EXIT. It boots the extracted packaged
OF816 XEX, retains the 250-frame countdown, and reads the matching writable SYS.
The ZIP audit matches 72 system files and 12 disk APPs, plus the RAM desktop.
The resident C segments and complete bank-zero reservations match the previous
Terminal idle-polling demo. The sample's reused small stack pools peak at
817–848 bytes, leaving at least 208 bytes above the separate 256-byte interrupt
reserve in those pools. These are observed development high-water marks.

MagiC checks real Space/Q delivery, label/button and Counter pixels, idle behavior
and Counter continuation after Widget exits. Its diagnostic reports stay
unchanged during interaction. Automated mouse interaction, dragging, overlap/
exposure and normal Counter retirement on MagiC remain outside this record.
The interrupted exploratory ATR load is not counted as a passing transport test.
Host checks pass 711 tests with four existing historical skips; full platform,
release and latency qualification remain separate.
