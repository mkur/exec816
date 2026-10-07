# Resident GEM applications

[Guides](README.md) · [AES contract](../reference/aes.md)

Exec816 supplies a small GEM source interface in `<gem.h>`. Application code
uses ordinary GEM calls and private parameter blocks. The Exec816 startup
wrapper supplies the retained service endpoint and owns Task termination.
This profile supports registration, copied messages, timers, GUI locks and
fixed-size GEM windows and private VDI drawing. Open with `graf_handle` and
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
another window to focus it. The packaged shell/counter selection follows in WA6.

## Application body

This event loop accepts a private eight-word quit message and a one-second
heartbeat. Mouse and keyboard event bits are not yet supported.

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
A failed timer does not consume a queued message. Unsupported event bits fail
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
match every BEGIN with its corresponding END. Keep holds short: native damage
and input wait until release. The application may still exchange messages and
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
