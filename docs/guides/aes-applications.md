# GEM applications

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
focused window restores the frontmost remaining window. The Windows menu or
Ctrl+Tab reaches covered windows; the active-window menu provides Close.

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
click the boxed closer at the left of its title to close it. Click the shell before typing `CAT STORY.TXT | WC` or
`CAT LONG.TXT`; BREAK cancels the command. `EXIT` first closes/detaches counters,
then stops desktop admission and releases the shell/services. Cold-boot to
restart this focused resident profile. The loadable desktop below includes Files.

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
two windows use three of four application-window slots. The existing `--aes-counters` profile and
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


## GEM Control Panel and Files desktop

The [panel](../../examples/gem-panel/panel.c) uses a compiled-in OBJECT tree,
local form state changes and changed-object drawing. The
[browser](../../examples/gem-browser/browser.c) loads its trees from a classic
RSC generated from [resource.json](../../examples/gem-browser/resource.json).
The panel, counter and Files each supply a small `main` wrapper and a private
model in a disk-loaded APP. Program/Process owns startup and Exec attachment.
The shared GUI loads once from `GEMSYS.BIN`; ordinary drawing calls stay local
to the application Task. See the [C loading contract](../reference/c-program-loading.md).

```sh
CARGO_PROFILE_DEV_OPT_LEVEL=2 python3 tools/build_demo.py --gem-desktop --output build/gem-desktop-demo
python3 tools/test_gem_desktop_boot.py --bundle build/gem-desktop-demo
```

Distribute `build/gem-desktop-demo/exec816-demo.zip`, including OF816, its pinned
ROM, matching D1/D8 disks, notices and guide. Boot retains the five-second delay.
The no-option build still starts the standard shell/prime demo.

Use Off/Mild, Defaults, Apply and Cancel in the panel (see
[mouse settings](#mouse-settings-in-control-panel)). Tab/Shift-Tab changes
keyboard focus, Space activates it and Return activates Apply. Release outside
or Escape cancels a press. In Files, select a directory/file and press Return;
Up navigates to the parent; Refresh reloads the directory. Drag the lower-right
size gadget to change the view, and use arrows, track clicks or the thumb to
scroll. Files caches at most 256 entries and adapts up to sixteen visible rows;
Refresh preserves the selected name. The top Files menu provides
Open/Refresh/Stop/Quit/Path/New Folder/Rename;
File inside the window or F opens the existing popup. Tab/Up/Down and Return select;
Escape cancels. HELLO in SYS:C is a simple launch example. Commands have empty
arguments, NIL input and shell output; Stop requests native BREAK or a GEM close. TICK prints periodically until Stop, without a private pane. PRIMES requires
tiled-console mode and returns an error in this desktop. Close one GEM window
before a two-child shell pipeline.
Path (P), New Folder (N) and Rename (R) open a text dialog in Files' work area.
Type into the field; Tab/Shift-Tab changes focus, Return accepts, and Escape or
Cancel dismisses it. The mouse can also select the field and OK/Cancel. Use
`WORK:` for writable operations; `SYS:` is read-only. Errors preserve the text
for correction. Other windows remain usable during the dialog.

Files can also launch `PANEL.APP`, `COUNTER.APP`, `FILES.APP` or `CALC.APP`. Close an existing
GEM window first when all four application-window slots are occupied. Closing Files stops and
collects its child before retirement. The shell collects closed initial apps
even at an idle prompt. Use `RUN C:FILES.APP` to reopen Files; this uses the
shell's one background job. EXIT closes the desktop and any owned GUI child.

This profile uses four application-window slots, two private menu layers, three
AES registrations and seven idle Tasks. The desktop bar follows the active
window and supplies Next window, Close and the Windows list. Ctrl+Tab cycles;
Ctrl+Escape opens Windows, then Tab/arrows and Return select, or Escape cancels.
Applications can install bounded GEM menu bars (see below). Atari ST binaries
remain unsupported. See the [current AES contract](../reference/aes.md)
and [desktop plan](../plans/gem4xe/desktop-facilities-implementation-plan.md).

## GEM4XE calculator

Close Panel, open C in Files, select CALC.APP and press Return. Alternatively,
use `RUN C:CALC.APP` from the shell. Calculator loads `SYS:CALC.RSC` regardless
of the launcher's current directory. It is an ordinary private loaded Process;
Quit, X and Files' Stop release its window, resource and workstation.

Click keys or type digits, `+`, `-`, `*`, `/`, `=` and `C`. Tab/Shift-Tab moves
focus, Space activates it, and Return activates equals. Sign change uses the
`+/-` button; Escape or releasing outside cancels a held press. Operations apply
in entry order: `2 + 3 * 4 =` gives 20. Values are whole numbers in the symmetric
range −2147483647 through 2147483647. Division truncates toward zero. Excess
entry, overflow and division by zero leave the displayed operand unchanged.

The [pinned donor inputs and patches](../../ports/gem4xe/apps/calculator/README.md)
retain its arithmetic and keypad/resource IDs. The adaptation replaces the
modal dialog with the existing windowed event loop and repaints changed objects.
The calculator display uses noneditable TEDINFO; the separate `objc_edit` API
is available for application-owned editable fields.

```sh
python3 tools/build_calculator.py --output build/calculator/app
python3 tools/test_calculator_desktop.py --bundle build/gem-desktop-demo
```

The first command builds APP/RSC inputs; the matching desktop build above ships
them together with the shared GUI, OF816 and the calculator's upstream notices.
See the [implementation record](../history/calculator-port.md) for costs and
the exact development checks.

## Mouse settings in Control Panel

`PANEL.APP` now changes the session's mouse acceleration. Choose Off (fixed 2×)
or Mild (the existing acceleration curve), then Apply. Defaults stages Mild;
Cancel reloads the active choice. Closing discards unapplied edits. Reopening
reads the current preference, including a choice applied by another panel.
Settings are session-only. Tab/Shift-Tab, Space and Return operate the controls;
Escape cancels an armed press, and releasing outside a button cancels it too.

The application uses standard GEM object/form/redraw calls and the small
[`ExecAESMouseProfile` extension](../reference/aes.md#session-mouse-preference)
for the desktop preference. An Apply during a held mouse gesture takes effect
after release. The counter and shell continue independently.

## Application menu bars

Keep a compiled or resource-loaded menu tree alive for the application's menu
registration. Install it with `menu_bar(tree,1)` before or after opening the
window. Background installation does not take focus. In the existing message
loop, dispatch `MN_SELECTED` using `message[4]`, then call
`menu_tnormal(tree,message[3],1)`. The two tree-address words identify the
application-owned tree; the presenter does not copy the tree or its strings.

Use `menu_ienable` for command availability and `menu_text` to replace a label
pointer without changing geometry. These calls safely patch an installed menu;
do not edit a live installed tree directly. Withdraw with `menu_bar(tree,0)`
before freeing its storage or resource. `appl_exit` also withdraws it.
See the [bounded menu contract](../reference/aes.md) for supported objects,
counts and keyboard interaction. Rebuild GEMSYS and APPs against the current
C component ABI.

## Standard dialogs

[The dialog example](../../examples/gem-dialog/dialog.c) is a separately loaded
`C:DIALOG.APP`. Close one existing GEM application, then run `RUN C:DIALOG.APP`.
Continue accepts an alert before the example owns a window. Edit (E) opens a
compiled-in editable tree; Apply repeats `form_do` inside START/FINISH and Done
returns to the application. Alert (A) borrows its existing window. Open (O) and
Save (S) invoke the standard file selectors and display the returned selection;
Save does not write a file. `SYS:SELECT/` has multiple pages and a subdirectory
for trying filters and navigation. `RUN C:DIALOG.APP SELECT` also opens the
selector before the application owns a window. The Dialog menu and Quit (Q)
remain ordinary application policy.

Use `form_center`, `form_dial(FMD_START, ...)`, one or more `form_do` calls and
`form_dial(FMD_FINISH, ...)` for an explicit session. An isolated `form_do` or
`form_alert` creates and finishes an implicit session. Keep the tree and text
buffers alive through FINISH; this includes a failed cleanup pending retry.
End an existing `objc_edit` association and release UPDATE/MCTRL before entry.
Drawing ownership is short-lived; all other applications continue running.

`form_do` returns an EXIT index with SELECTED set. Check for a negative result
before indexing the tree, and clear SELECTED before reusing that button:

```c
result = form_do(tree, 0);
if (result < 0) {
    status = ExecAESDiagnostic();
    /* FINISH an explicit session, then handle AES_PENDING in the event loop. */
} else {
    tree[result].ob_state &= ~SELECTED;
    /* Apply the accepted application action. */
}
```

A borrowed window's move/size/scroll/close, a menu selection or an ordinary
application message returns `AES_PENDING`. FINISH, resume the event loop and
process the retained message. The following WM_REDRAW repairs the application's
work area from its own model. Repaint the whole damaged area, including margins;
a saved screen image is neither needed nor maintained. Temporary hosts accept
movement themselves; their closer dismisses with `AES_OK`.

`form_alert` returns a **one-based** button or **zero** on interruption,
dismissal or failure. Zero is never an accepted button. The bounded syntax,
limits, default selection and unsupported operations are in the
[AES contract](../reference/aes.md). Files and calculator retain their existing
event-driven loops. Rebuild the shared GEMSYS component and every application
for the current C component ABI.

## Selecting a file

Keep a writable 128-byte path/filter and 13-byte filename in application storage.
Enter without an active form/editor or an UPDATE/MCTRL lock. The selector borrows
your shown work area, or creates a temporary host before you have a window:

```c
static char path[128] = "SYS:*.TXT";
static char file[13] = "";
WORD button;

if (!fsel_exinput(path, file, &button, "Open text")) {
    if (ExecAESDiagnostic() == AES_PENDING) {
        /* Resume the event loop: retained policy precedes WM_REDRAW repair. */
    } else {
        /* Handle failure; original path/file are unchanged. */
    }
} else if (button == FSEL_OK) {
    /* Replace the final filter with file, then perform the application's I/O. */
} else {
    /* Normal Cancel returns the current fields, but no selection to use. */
}
```

`fsel_input` uses the default caption. Both calls can select a new Save filename;
the application checks existence and decides how to handle overwrites. Use Exec
prefixes and `/`, rather than GEMDOS drive/backslash paths. Do not reopen the
selector automatically after AES_PENDING: first handle the application message.
The [file-selector contract](../reference/aes.md#file-selector) describes the
bounded snapshot, filters, input controls, cancellation and cleanup rules.
Rebuild GEMSYS and all applications with C component ABI 11.

## Text viewer

Close one GEM application to free a window, then run `RUN C:TEXT.APP`, or
`RUN C:TEXT.APP "SYS:STORY.TXT"`. The loadable viewer uses the existing selector,
DOS calls and caller-local VDI drawing. It adds no startup Task. Files also
opens `.TXT` entries in the viewer; close another GEM window first. Files owns
that child, so File > Stop closes it, and closing Files stops and collects it.
Other files retain normal program launching.

Use File > Open or O to choose a file. Up/Down scroll one line; Space and
Shift-Space scroll a page. The arrows, track and thumb provide vertical scrolling.
Drag the size gadget to resize; long lines are clipped rather than wrapped.
Escape or File > Cancel Load cancels a pending replacement. Q, File > Quit and
the closer exit. Cancellation takes effect between synchronous DOS calls.

Files must be regular files of at most 65,536 bytes and 4,096 lines. LF, CR,
CRLF and ATASCII `$9B` end lines. Tabs use eight-column stops; unsupported bytes,
including embedded NUL, display as dots. The viewer is read-only. Cancel and
failed Open preserve the current document and scroll position.

[The application](../../examples/gem-text/text.c) keeps a candidate separate
from its committed document, reads at most 1 KiB per event-loop turn, and paints
at most four text rows per UPDATE section. It polls `evnt_multi` with a zero
timer only while work remains and blocks normally when idle. Repainting and
scrolling use the retained line index without disk reads. The minimum work area
also leaves enough room for the borrowed file selector. After selector policy
interruption, the application resumes event delivery before repairing pixels.
