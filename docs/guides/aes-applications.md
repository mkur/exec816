# Resident GEM applications

[Guides](README.md) · [AES contract](../reference/aes.md)

Exec816 supplies a small GEM source interface in `<gem.h>`. Application code
uses ordinary GEM calls and private parameter blocks. The Exec816 startup
wrapper supplies the retained service endpoint and owns Task termination.
This profile supports registration, copied messages, timers, GUI locks and
fixed-size GEM windows, keyboard/left-button input and private VDI drawing. Open with `graf_handle` and
`v_opnvwk`; use `BEG_UPDATE` around visible-rectangle enumeration, user clipping
and bar/text painting, then release with `END_UPDATE` before the event wait.
See the [workstation profile](../reference/gem-vdi.md#resident-application-workstations)
for supported attributes and output buffers.
See the [window contract](../reference/aes.md) for supported kinds and fields.

## Counter example

The [counter body](../../examples/gem-counter/counter.c) uses only `<gem.h>`
through its [model header](../../examples/gem-counter/counter.h). It opens a
fixed 208×104 window, updates six decimal digits on a one-second timer, accepts
top/move/close requests and reconstructs exposed pixels from its current model.
It handles both bits when `evnt_multi` returns a message and timer together.

The separate [resident wrapper](../../examples/gem-counter/resident.c) supplies
two upper-memory models, attaches each Task, and detaches before removal. A
registered controller sends ordinary GEM close messages during shutdown. It
uses no application window and consumes one of the four registrations: the two
counter instances plus controller occupy three. Each counter requests a 1,024-byte
stack. Failure to detach prevents Task/image retirement.

Build and exercise the focused counter proof:

```sh
CARGO_PROFILE_DEV_OPT_LEVEL=2 python3 tools/build_aes_desktop.py \
  --counters --output build/aes-windows/counters
python3 tools/test_gem_counter.py --program build/aes-windows/counters/program \
  --output build/aes-windows/counters-test
```

The proof adds development-only pause and timing hooks outside rendering
ownership. It compares full framebuffers after timers, physical top/drag/close,
full cover/exposure, simultaneous readiness and repeated restart. Closing the
focused window clears keyboard focus under the current desktop policy; click
another window to focus it.

## Optional OF816 counter desktop

```sh
CARGO_PROFILE_DEV_OPT_LEVEL=2 python3 tools/build_demo.py --aes-counters \
  --output build/aes-counter-demo
```

Distribute only `build/aes-counter-demo/exec816-demo.zip`. Extract it and follow
its short guide: boot `Exec-of816.xex`, mount the matching `system.atr` in D1
and a disposable `work.atr` in D8, and use the bundled pinned ROM with VBXE.
The five-second countdown enters a native shell and two counters. This explicit
selection replaces the native panel; the default build still starts shell/prime.
The selected pointer acceleration profile applies to both native and GEM windows.

Click a title to focus/top, drag a counter to any on-screen pixel position, or
click X to close it. Click the shell before typing `CAT STORY.TXT | WC` or
`CAT LONG.TXT`; BREAK cancels the command. `EXIT` first closes/detaches counters,
then stops desktop admission and releases the shell/services. Cold-boot to
restart the resident applications. There is no application launcher yet.

The counter desktop uses six of eight Task slots at its prompt; a two-command
pipeline uses all eight. Three of four desktop layers and three of four AES
registrations are occupied (the controller has no window). A separate native
panel/coexistence proof uses the fourth layer and seven Tasks while reading
disk, without pipeline children. See the [resource and timing record](../history/aes-windows.md#wa6--coexistence-and-the-of816-demo).

## Application body

This event loop accepts a private eight-word quit message and a one-second
heartbeat without needing a window. To request `MU_KEYBD` or `MU_BUTTON`, first
open an application window. Wait for down with `(clicks,mask,state)=(1,1,1)`,
then release with `(1,1,0)`; use returned screen coordinates to distinguish an
inside activation from an outside cancellation. `evnt_keybd` returns a GEM
scan/ASCII word. Rectangle and multiple-click events remain unsupported.

```c
#include <gem.h>

WORD gem_main(void)
{
    WORD id = appl_init();
    WORD words[8], mx, my, buttons, keys, key, clicks;
    if (id < 0) return 1;
    for (;;) {
        WORD events = evnt_multi(MU_MESAG | MU_TIMER, 0, 0, 0,
            0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
            words, 1000, 0, &mx, &my, &buttons, &keys, &key, &clicks);
        if (!events) { appl_exit(); return 2; }
        if ((events & MU_MESAG) && words[0] == 0x7fff) break;
        if (events & MU_TIMER) {
            /* Perform a bounded piece of application work. */
        }
    }
    return appl_exit() ? 0 : 3;
}
```

A sender uses `appl_write(destination, 16, words)`. It may reuse the words after
return. The destination queue holds sixteen copied messages; zero means the
send was not accepted. Startup currently supplies peer IDs: `appl_find` and
application discovery are outside this profile. A pointer in a GEM message
has no special ownership or lifetime support. Messaging and event/timer waits
run in the application Task using its receive port and lazy timer binding; they
do not wait for the presenter to dispatch a request. Registration, exit and
`wind_update` retain presenter arbitration. Existing GEM call sites need no change.

For a native failure, inspect `ExecAESDiagnostic()` from `<exec816/aes.h>`.
A failed timer consumes no selected payload. `AES_INPUT_LOST` retires only the
lost selected input source; clear any armed application control and wait for
release before accepting a new press. Unsupported event bits fail
as a whole; they do not silently disappear from the requested mask.

## Startup and retirement

The controller enables the optional endpoint before starting the existing
desktop presenter and retains its allocation until every application detaches.
After readiness, `AESBOOT.Port()` supplies its native endpoint. Each C Task's
wrapper calls `ExecAESAttach(endpoint)` before `gem_main()` and
`ExecAESDetach()` afterward. Attach allocates a private context and reply port;
`appl_init()` allocates a receiving port and message pool, then registers the
application with the service. A failed registration releases those resources;
retry is permitted. The shared directory is internal to the binding.

Detach calls `appl_exit()` when the application has not already done so, waits
for endpoint retirement and the final reply, then deletes its ports, message
pool and private context. A failed detach
must prevent Task/image retirement. Do not remove a registered Task or free its
image while the service retains its lease. Do not share one registration across
Tasks or invoke a second AES call from a callback while the first is pending.

`wind_update(BEG_UPDATE)` excludes native painting and implicitly owns mouse
control; match it with `END_UPDATE`. An explicit `BEG_MCTRL`/`END_MCTRL` pair
excludes native gestures while allowing console painting. Locks recurse, so
match every BEGIN with its corresponding END. Keep holds short: native damage and gestures
wait until unlock, while application content input continues. A content press
retains its recipient through physical release. Release update ownership before
the ordinary event loop; use mouse control only for a bounded interaction. The application may still exchange messages and
wait on a timer while holding a lock. Cooperative exit releases nested holds.

## Build and exercise the optional proof

The checked fixture composes two C entries with the production drawing image,
the native Control Panel, and a root DOS Process for disk work:

```sh
CARGO_PROFILE_DEV_DEBUG=0 CARGO_INCREMENTAL=0 \
  python3 tools/build_aes_desktop.py --load --output build/aes-server/proof
python3 tools/test_aes_desktop.py --integrated \
  --program build/aes-server/proof/program --output build/aes-server/proof-run
python3 tools/test_aes_desktop.py --integrated --unobserved \
  --program build/aes-server/proof/program --output build/aes-server/proof-replay
```

The runner creates its own SDFS test disk and uses the pinned emulator/ROM.
The two C Tasks fit existing 1,024-byte stack pools. They are ordinary Exec
Tasks; the root performs DOS work because it owns the Process context.
See [aes_desktop.c](../../tests/programs/aes_desktop.c) for application loops and
separate startup/termination control, and the
[builder](../../tools/build_aes_desktop.py) for named-entry/image composition.

The proof is separate from the five-second shell/prime autoboot. Its checks do
not establish a complete GEM desktop, hardware qualification or support for the
open 125 kbit/s SIO configuration. Existing widget feedback targets also remain
open; see the [execution record](../history/aes-server.md).
The hybrid implementation passes the integrated functional checks, including
independent messages/timers during native GUI exclusion and repeated retirement.
Active GEM traffic still exceeds the native GUI response limits in the HY4
comparison. The profile remains available for development with that performance
gate open; see the [hybrid record](../history/aes-hybrid.md).


## Interactive application example

[The input application](../../examples/gem-input/input.c) is a small ordinary GEM
body using `<gem.h>`, `evnt_multi` and local hit testing. Its
[resident wrapper](../../examples/gem-input/resident.c) supplies Exec attachment,
two Task instances and the native input-loss recovery hook. The model and GEM
arrays live in caller-owned upper memory, outside each 1,024-byte Task stack.

Activate highlights until release. Release inside increments Clicks; release
outside or Escape/BREAK cancels. Keys shows a hexadecimal GEM scan/ASCII word.
Tick changes when the one-second combined wait expires; other events restart
that timeout. The current VDI profile uses opaque white text cells, including
inside the highlighted button. There is no continuous hover tracking.

Build and run the development fixture:

```sh
CARGO_PROFILE_DEV_OPT_LEVEL=2 python3 tools/build_gem_input.py --output build/gem-input
python3 tools/test_gem_input.py --program build/gem-input/program --output build/gem-input-check
```

The fixture adds test-only pause points and capacity/heap failure cases around
the same application body. These hooks are omitted when a demo source is given
to the builder. See the [input execution record](../history/aes-application-input.md#ai6--ordinary-interactive-gem-application)
for exact scope and the external Calypsi array-indexing limitation encountered.


Build the optional two-input-app desktop, with OF816 and matching disks:

```sh
CARGO_PROFILE_DEV_OPT_LEVEL=2 python3 tools/build_demo.py --aes-input --output build/gem-input-demo
unzip build/gem-input-demo/exec816-demo.zip -d build/gem-input-demo/extracted
python3 tools/test_demo.py --bundle build/gem-input-demo --boot-smoke \
  --distribution-root build/gem-input-demo/extracted/exec816-demo
```

Distribute `build/gem-input-demo/exec816-demo.zip`. Follow its short guide for
machine setup, D1/D8 disks and ST mouse capture. At the prompt there are six
Tasks; a two-command pipeline uses all eight public slots. The two application
registrations plus the controller use three of four AES slots. The shell and
two windows use three of four layers. The existing `--aes-counters` profile and
no-option five-second shell/PRIMES autoboot remain available.

For focused cost measurements, the separate development root supplies continuous
console writes or verified disk reads around the same unmodified C body:

```sh
CARGO_PROFILE_DEV_OPT_LEVEL=2 python3 tools/build_gem_input.py --load --output build/gem-input-load
python3 tools/measure_gem_input.py --program build/gem-input-load/program --output build/gem-input-observed
python3 tools/measure_gem_input.py --program build/gem-input-load/program --output build/gem-input-replay --unobserved
```

`--panel` on the builder selects a separate four-layer, seven-Task cohort with
the native Control Panel; run its measurement with `--count 4 --unobserved` for
coexistence, rapid keys while drawing, and panel/disk progress. It has one free
public Task slot, so it is not the two-child pipeline configuration. Timings
report individual physical edges, caller/presenter CPU and completed scanout.
They are development observations; broader latency gates remain open.
