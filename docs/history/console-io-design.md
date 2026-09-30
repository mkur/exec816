# Console input/output

> Historical record: applies to the revisions and profiles described below.
> See the [current documentation](../reference/console.md) and [history index](README.md).

Status: initial full-screen console complete, 2026-09-21. All eight slices of
the [implementation plan](../plans/console-io-implementation-plan.md) pass on the pinned
emulator; the [implementation record](console-io-implementation.md) links each
commit and its evidence. Configure startup with `--console` and use the
[resident DOS example](../guides/console-example.md). The
[eight-task qualification](../qualification/console-concurrency.json) includes
raw/optimized execution, 125 kbaud SIO, real MyDOS media, physical key input,
scrolling output and unchanged-image replays. Under the scrolling stress test,
observed visible echo can take about one second; no hard keyboard-latency
guarantee is claimed for that historical workload. [Independent windows and
focus](../reference/console-windows.md) are now implemented through W3 with focused
development checks; their full release qualification remains pending.
The subsequent [scrolling optimization](console-scrolling.md) preserves these
interfaces and bounded quanta while improving idle throughput.

The [DOS console streams](../reference/streams.md) layer file handles and
standard input/output over this device. RAW: and NIL: add no worker;
[cooked CON:](../reference/cooked-console.md) provides editing and foreground scopes.

Provide a native keyboard and text screen for a resident shell while other
tasks, MyDOS and native SIO continue running. Use the existing Exec device API
and one console worker. Keep command parsing, line editing and filesystem text
conversion above the device. A shell and its built-in commands can be linked
into the current image; neither this console nor that shell requires an
application binary format, executable loader or full Amiga Process structure.

**Multiple independent text windows are a required future capability.** Each
virtual console owns its text and I/O state; windows present those consoles on
one physical display. Several windows must be able to remain visible and print
independently. Switching between full-screen consoles alone does not meet this
requirement. The first milestone creates one instance of this model.

## Current boundary and first milestone

[`EXECOS.Write`](../../lib/exec/execos.act) is a serialized ROM CIO adapter. It accepts
at most 255 ATASCII bytes in the launcher's bank-zero image arena, has no input
counterpart, and rejects ROM entry while native SIO or the native console owns
hardware. Waiting for an
idle sector boundary does not make that adapter available: SIO ownership lasts
for the resident driver's lifetime. See the
[native adapter](../../platform/altirraos/hosted.s) and
[SIO ownership contract](device-io-sio-design.md#irq-rom-and-scheduling-coexistence).

The first milestone is one full-screen, 40-column by 24-row console with
translated keyboard input, text output, wrapping, scrolling and a visible
cursor. A pending keyboard read must coexist with output and disk transfers.
It must not retain an OS activation, busy-poll the keyboard, stop other tasks,
or need a successful-transfer sleep to give ROM input services time to run.

Implement multiple windows and focus management after the first milestone, but
keep console state separate from the physical screen now, as specified below.
Defer serial terminals, graphics, mouse input, raw input events, configurable
keymaps, automatic key repeat, scrollback, escape-sequence emulation, pipes and
redirection. These are not prerequisites for the first prompt, simple line
editor, `dir` or `type`.

## Console instances and future windows

Keep three responsibilities separate, initially within the same worker:

| Layer | State and responsibility |
| --- | --- |
| Console instance | Logical dimensions, retained character cells, cursor, input FIFO/loss state, pending read, write queue and rendering progress. Future text attributes and escape-parser state also belong here. |
| Window presentation | Position, visible bounds, clipping and dirty regions; later stacking/occlusion and focus selection. Maps a console's cells onto its visible screen region. |
| Platform display/input | One physical screen, display shadows and keyboard IRQ ring. Owns POKEY coexistence and hardware restoration for the whole service. |

The first instance has a 40-by-24 cell buffer in upper RAM and a presentation
covering the entire screen. All text operations take an instance; row/column
limits come from that instance. They update its cells and cursor, then mark
regions for display. Only the presentation layer writes physical screen RAM.
Do not make the hardware screen the only copy of the text or keep a global
cursor/write queue that would mix future windows' output.
This requires one instance record and a simple full-screen presentation now;
dynamic window management and a general compositor remain later work.

The future multiwindow contract is:

- Each open binds its requests to one console instance through opaque
  `io_Unit`. Several independent opens can target different instances. The
  initial exclusive open applies to the default instance, not permanently to
  the entire device. Define window creation/selection arguments when adding
  that service; no speculative Window ABI or extra gateway is needed now.
- Writes, clear-screen operations, wrapping and scrolling affect only the
  addressed console. A busy producer cannot move another console's cursor,
  erase its text or block its input. Preserve FIFO write order within each
  instance; service runnable instances fairly between bounded quanta.
- Unfocused, covered and hidden consoles continue accepting output into their
  retained cells. Completion does not wait for focus or exposure. Exposing a
  window redraws its current contents; it does not ask the application to print
  again. Retained cells cover the current console contents, not scrollback.
- Several windows can be presented simultaneously with clipping. Tiling is a
  suitable first window layout; overlap, movement, resize/reflow and decorations
  need their own later specification. A console's visible cursor appears only
  when it has keyboard focus; its logical cursor always advances on output.
- One focus target receives keyboard input, including Ctrl-C/BREAK. Background
  reads can remain pending while background writes progress. Order focus changes
  with captured input so already captured or buffered keys keep their original
  destination. Closing a destination discards its undelivered input; never send
  stale keys to the next focused console. Define that handoff before enabling
  multiple windows; IRQ delivery still posts only to the known console worker.
- Closing a console settles its requests and detaches its presentation before
  releasing its state. It does not stop other consoles or restore the OS screen.
  Physical hardware is released only at service shutdown.

Use one shared console worker for these instances and their presentation.
Adding a window costs upper-RAM cells and metadata, not another task, stack,
direct page, bank-zero screen or IRQ binding. Application tasks may own windows,
but a window is not a Task and one application may own several windows. The
number of windows is limited by admitted memory and display/service capacity,
not by the eight execution slots. Set explicit limits and measure fairness when
implementing the window service; no unlimited-window claim is made here.

## Public interface

Register the resident name `console.device`. Open flags must be zero. Unit zero
selects the default full-screen console; W1 adds opaque units created through
the [instance lifetime API](../reference/console-windows.md). Each unit selects one
instance, with one successful open at a time; another open of that instance
returns `IOERR_UNITBUSY`. The selector does not equate console identity
with physical display ownership. Unsupported units or flags fail with
`IOERR_OPENFAIL`. Validate the full-width arguments.
Device availability is established during configured service startup, before
publication; `OpenDevice` itself does not allocate a worker or enter ROM.

Use the existing 42-byte `IOStdReq` and `OpenDevice`, `CloseDevice`, `SendIO`,
`DoIO`, `CheckIO`, `WaitIO` and `AbortIO` from the
[device API](device-io-sio-design.md#public-exec-contract). Do not add a console COP
gateway, another message type or a synchronous ROM input wrapper. Names are
NUL-terminated byte strings. Additional requests can borrow a successful open's
binding under the existing lifetime rules; initialize their Message fields
individually, including reply ports, instead of copying active links.
Initially opening needs no Window pointer or other `io_Data` setup. Add console
constants and private layouts to machine-readable ABI/map inputs during
implementation and generate their shared Action!/assembly definitions.

| Field or command | Initial contract |
| --- | --- |
| `io_Data` | Caller-owned buffer, including upper RAM. Validate the entire readable/writable extent before transfer. |
| `io_Length` | Unsigned 32-bit byte count for READ/WRITE; zero succeeds with zero actual bytes. Reject the Amiga NUL-terminated-write sentinel `$FFFFFFFF` with `IOERR_BADLENGTH`. |
| `io_Offset` | Must be zero; otherwise `IOERR_BADADDRESS`. A terminal is not seekable. |
| `CMD_READ` | Return available translated bytes, up to the capacity. If none are available, remain pending until input, input loss or cancellation. A successful nonempty read may be short; it does not wait for Return or fill the buffer. |
| `CMD_WRITE` | Consume the supplied byte stream into the bound console's retained cells and cursor state. Completion means those effects are committed and the caller's buffer is no longer needed, independent of focus/visibility. `io_Actual` counts source bytes consumed, not screen cells changed. |
| `CMD_CLEAR` | Discard buffered input and the input-loss latch; ignore Data/Length and return zero actual bytes. Does not clear the screen or cancel a pending read. |
| Other commands | Complete with `IOERR_NOCMD`; no silent success for RESET, STOP, START or FLUSH. |

Admit only one outstanding nonempty read on the unit; reject another with
`IOERR_UNITBUSY`. Permit queued writes alongside it. This makes input ownership
explicit for the first shell, while separate requests allow asynchronous input
and output. A later DOS console handler can own this open and arbitrate clients.

Keep `io_Data` and `io_Length` unchanged; report progress through `io_Actual`.
Lengths do not impose a 64 KiB payload limit. A buffer may cross banks only
through a validated linear RAM extent; widen arithmetic before checking its
end and never wrap the 24-bit address space. Request records retain the ordinary
device ABI's placement and size restrictions.

Public calls are task-only. Blocking calls require scheduling and IRQs enabled.
Buffers, requests, ports and the owning open stay live until completion has
been collected. Close requires all borrowed requests to be settled too.
A Task-owned console open retains its opening Task through a public Task lease
until Close. Borrowed request bindings do not transfer that hold. An owning
request with an independent `PA_IGNORE` reply port, such as the shared DOS
endpoint, does not retain the first opener. Its owner must keep the endpoint
alive until its last reference closes; the worker still rejects shutdown while
the instance is open. Window creators and presentation transactions likewise
retain their owning Task; removing a retained Task is rejected by the common
Task lifetime rules.

## Worker, queues and completion

One worker owns keyboard translation, console instances, presentation and
replies. Open count and queued request count do not create more tasks. A shared
private arrival port and keyboard signal serve the worker; each instance owns
its pending-read pointer and write FIFO. Request storage supplies queue nodes;
do not allocate per character or introduce a registry search on each interrupt.

Protected device entry points validate and queue requests, publish cancellation
and perform short bookkeeping. They do not render, copy payloads, wait, call
ROM or allocate. The worker checks durable queues, the input ring and dirty
visible cells, then waits on request arrival OR keyboard notification only when
no runnable work remains. Signal coalescing is harmless because
the bytes and requests remain in their queues. Publication and Wait use the
existing lost-wake protocol.

An empty read must never occupy the worker in `WaitIO` or block the write FIFO.
The worker services input between bounded output quanta, initially at most 64
source bytes or 40 cells of a scroll/redraw before checking input/cancellation.
A scroll is a resumable rendering operation: do not begin the next source byte
until it finishes. Yield between quanta when more work remains. Keep an active
write ahead of subsequent writes to the same instance so their byte streams do
not interleave. Future windows rotate at these boundaries; an unfinished write
in one instance does not hold a global write queue. Copies run with IRQs and
preemption enabled, outside kernel policy exclusion.

Refresh dirty visible cells in bounded quanta alongside request work, including
when no new requests arrive. A reply need not wait for the display to catch up;
it must leave no deferred renderer referencing caller storage. Later occlusion
must not stall writes, and sustained output must not starve display refresh.

Initially, nonempty reads/writes clear `IOF_QUICK` and complete by one reply.
Immediate validation failures and zero-length operations may complete quick
only when requested; `SendIO` always gets a reply. `CMD_CLEAR` executes at a
worker boundary in submission order relative to input delivery. It is not
serialized behind an empty read. Preserve the existing request state machine.

Queued cancellation unlinks the known request; active cancellation asks the
worker to stop at a quantum boundary. Normal completion may win. An aborted
write reports the consumed prefix and does not undo committed text. Finish an
in-progress logical scroll and leave the instance's cells/cursor coherent before
publishing its terminal reply; its dirty regions can still await display.
Never access a request or buffer after replying; the recipient may immediately
free it. Every accepted deferred request receives exactly one
terminal reply, including cancellation and shutdown.

## Keyboard capture and signals

Own the POKEY keyboard and BREAK IRQ sources while the console service is
resident. Both native entry and IRQs reached from an emulation-mode OS/VBI
activation need supported callbacks. Use the existing context-preserving
adapter and defer scheduling until the activation can safely retire.

The IRQ captures a key code with its modifiers, event kind and native tick
timestamp into a fixed upper-RAM ring, acknowledges only its source, and posts
directly to the known console worker. It performs no translation, echo, screen
work, allocation, port operation or Task scan. Start with 64 event slots and
byte-sized producer/consumer indices. Publish each complete slot before its
head index; the worker copies a slot before releasing it through the tail.
Only IRQ code produces events and only the worker consumes them; NMI does not
write this ring. Use a coherent tick snapshot across asynchronous NMI entry.

The current [direct-post implementation](../../platform/altirraos/signal-irq.s)
uses a serial-specific binding. Add an independent upper-RAM console binding,
sharing the bounded posting logic through an explicit binding argument or
entry point. Do not overwrite the SIO binding, reserve a signal in every Task,
or add a public IRQ-safe port API. Bind the worker Task/context/mask before
enabling the producer; disable and retire the producer before freeing it.

The worker uses a fixed Atari keyboard map. Required input is letters, digits,
ordinary punctuation, Shift, Control, Caps Lock, Return (`LF`), Backspace (`BS`),
Tab and Escape. Control-letter combinations produce their control bytes; BREAK
produces byte `$03`, like Ctrl-C. Debounce/duplicate suppression uses captured
native ticks, not ROM `CH`, `KEYDEL` or stage-two VBI. Qualify press/release and
held-key behavior; automatic repeat and arrow/function-key sequences are
deferred. There is no device echo or line buffering.

Use a 128-byte translated-input FIFO per console instance so input can arrive
without a posted read. The raw IRQ ring is shared by the service; FIFO and loss
state belong to the destination console. Do not overwrite unread data when
either ring fills. Drop new events, latch loss and wake the worker. Define
device-specific
`CONERR_INPUTOVERFLOW = 1`: the next read processed after the latch reports this
error with zero actual bytes and discards that console's remaining buffered
input. This starts a fresh stream; the shell must discard its partial command
and report the loss. A prefix already returned cannot be recalled. `CMD_CLEAR` explicitly
performs the same reset without reporting an error. W2 acknowledges only that
instance's captured loss and tombstones its queued events while preserving
other instances. Bitmap updates use short IRQ exclusions; the bounded scans
keep IRQs enabled. See the [window contract](../reference/console-windows.md).
Count hardware keyboard overruns as input loss when detected.

Ctrl-C/BREAK is input, not an out-of-band task signal in this milestone. It can
cancel the shell's current line when read; it does not promise interruption of
a built-in blocked in a DOS call or cancellation of disk I/O. Job control and
AmigaDOS break-signal policy belong in a later shell/Process design.

## POKEY coexistence: first executable gate

Keyboard input uses POKEY even though it needs no audio channel or serial timer.
The current native SIO engine owns IRQ mask `$3B`; keyboard/BREAK use `$C0`.
Disjoint IRQ masks are necessary but insufficient: both depend on `SKCTL`, and
`SKREST` clears error latches shared by keyboard and serial input.

The first [coexistence probe](console-io-implementation.md) demonstrated that
the former per-transaction `SKCTL = 0` reset repeated held keys.
[sio.s](../../platform/altirraos/sio.s) now keeps scanning enabled during setup,
uses `$23`/`$13` for serial phases and restores saved state at shutdown. The
probe also required one bounded serial RX recheck after keyboard delivery to
meet the byte deadline under display DMA. Preserve those measured properties
when promoting the probe into the resident adapter.

The platform adapter owns the shared register contract:

- Console code does not write AUDF/AUDC, AUDCTL, STIMER, serial configuration,
  PIA COMMAND or CRITIC. Key clicks and audible bells are disabled.
- Merge keyboard and SIO enable/acknowledgement changes through the current
  IRQ shadow, preserving the other owner's bits. Never restore a stale whole
  IRQEN snapshot when either service starts or stops.
- Keep keyboard scanning enabled outside any measured, necessary SIO reset
  interval. Any required change to SIO setup belongs in its native adapter and
  must requalify serial timing and errors; it is not a console-side reset.
- Capture relevant keyboard/serial error state before a shared latch reset;
  console handling must not erase evidence of a serial overrun. Define the
  common `SKCTL` baseline and restore it according to remaining ownership,
  including when SIO stops while the console remains active.
- Service serial work first, then bounded keyboard work, then chain remaining
  unowned sources. Bound the combined path when events coincide. Preserve
  unrelated timer/vector state in both native and emulation entry paths.

An early probe must type a known sequence, hold/release keys and exercise BREAK
while repeatedly reading sectors at FASTEST125, including transaction setup,
turnaround and error recovery. If reset loses keys or creates duplicates,
resolve the reset/scan ownership before building the shell on this interface.
Do not add OS-service sleeps or move keyboard polling into ROM CIO as a fix.

## Display and text representation

Borrow the launcher's already reserved bank-zero GRAPHICS 0 screen and display
list. At service startup, validate the pinned 40-by-24 geometry, screen extent,
display-list addresses and character set against the platform memory map.
Reject unsupported graphics modes or overlapping/unsafe addresses. Do not
assume every launch has a valid screen at one hardcoded address.

ANTIC needs display-visible memory; ordinary upper CPU RAM is not a substitute
for its screen storage. Use the existing 960-byte screen inside the OS/display
reservation, with an upper-RAM snapshot for restoration. Preserve the display
list, font selection, display shadows and OS editor/cursor state. Remove the
old editor cursor at takeover; native presentation draws the focused console's
nonblinking cursor. Restore the previous screen and editor state on normal
service shutdown. No second bank-zero screen or writable font is planned.

Retain the console's own cell buffer separately from the OS screen snapshot:
the former is live application output; the latter exists only for shutdown.
Initially use one byte of logical character data per cell, requiring 960 bytes
in upper RAM for the full-screen console, with cursor state outside those cells.
The presentation layer maps dirty cells to screen RAM using an explicit
byte-to-screen-code table and draws the visible cursor as an overlay. Copying
or removing that overlay must not change the retained text. Future attributes
can enlarge the cell format without adding a bank-zero buffer per window.

Printable ASCII `$20`–`$7E` uses available ROM glyphs; a character without a
matching glyph renders `?`, rather than silently becoming an Atari control or
graphics character. Document and test that mapping, including punctuation.

| Output byte | Effect |
| --- | --- |
| BS (`$08`) | Move left one column, clamped at column zero; do not erase. |
| HT (`$09`) | Advance to the next eight-column tab stop; at the right edge, move to the next line. |
| LF (`$0A`) | Move to column zero of the next row, scrolling at the bottom. |
| FF (`$0C`) | Clear the bound console's cells and move its cursor to the top left. |
| CR (`$0D`) | Move to column zero of the current row. |
| Other C0 controls and DEL | Consume without effect; BEL does not touch POKEY. |
| High-bit bytes | Render `?`; no implicit inverse-video, UTF-8 or ATASCII interpretation. |

Printable output wraps and scrolls at the instance's bounds: initially after
column 39 and at row 23. FF clears only that instance's cells. CSI/escape
sequences are unsupported initially: ESC is ignored and following printable
bytes have their ordinary effects. In particular, `$9B` is **not** a newline.
An ATASCII file viewer must translate its line endings explicitly; DOS `Read`
continues returning exact file bytes. A simple shell can erase its last typed
character within a row with BS, space, BS. Its first editor must limit input to
the remaining row width or provide explicit redraw behavior; backspace does
not reverse a wrap or scroll.

No console rendering or keyboard translation runs in VBI. Keep display hardware
and shadows consistent so an occasional ROM stage-two VBI cannot undo the
native display. Audit retained attract/color handling and restore any shadow
state changed for the console. Progress must not depend on stage two, which
continuous native SIO can defer. Do not hold `Forbid`, SWITCHING or an IRQ mask
across a screen clear or scroll. No tearing-free display guarantee is required.

## Admission, lifetime and resource budget

Enable the resident console explicitly in the build/startup configuration;
existing headless test images need not acquire it. Admit its worker, upper-RAM
state, port, signals, console cell buffer and OS screen snapshot before
publishing the device. Failure rolls back without leaving enabled IRQ sources
or a partially openable device.
Both console-before-SIO and SIO-before-console startup need defined ownership.

Closing the owning open requires all its reads/writes collected, discards its
buffered input and permits another open of the default instance. It does not
expunge the resident worker or return the display to ROM. In the initial
single-instance profile, service IRQs acknowledge/discard input while the
default instance is closed; reopening starts with a clean stream. Open/close
transitions serialize this state with the producer. Hardware ownership lasts
until ordered service stop.

At system stop, reject new work, cancel/collect requests, disable input sources,
retire callbacks and pending wakes, restore display/shared hardware ownership,
then remove the worker and free its resources. A user must not `RemTask` a
service worker or a client with outstanding requests. Integrate this sequence
with existing service shutdown, including when the shell/root exits first.
An unsafe SIO bus still follows its existing offline/fail-stop policy: console
cleanup must not turn `$FF93` into a normal return to ROM.

The ROM adapter remains available for bootstrap and configurations without
native owners. While the native console owns screen/keyboard, reject conflicting
ROM console calls even if SIO is inactive. Normal shell output uses the native
device. Preserve COP `$00` routing and the established OS-activation protocol;
this is explicit service exclusion, not replacement of every OS entry point.

| Resource | Proposed placement and cost |
| --- | --- |
| Worker context | One existing public Task slot; no new private IRQ stack/domain. |
| Typical live system | Shell/root + console + filesystem + SIO = four of eight public slots; four remain, plus the separate idle context. |
| Worker bank-zero occupancy | 1,568 bytes in the current eight-task pool, including stack/DP, guards and padding. This is already reserved, even while the slot is free. |
| Input storage | One shared 64-slot event ring plus a 128-byte FIFO per console in upper RAM; freeze the event layout and exact reservation during implementation. |
| Console cells | Initially 960 bytes in upper RAM, separate from the OS snapshot; future windows allocate cells according to their logical dimensions. |
| Display backup | One 960-byte OS screen snapshot plus saved state in upper RAM, regardless of console count; existing bank-zero display storage is borrowed. |
| Other state/code | Queues, Task record, binding, key/glyph tables, cursor state and code in upper RAM relative to the configured kernel bank. |

The dedicated worker costs a slot, but keeps input translation, screen copying
and task-only reply delivery out of IRQ and protected device entry. Combining it
with the filesystem worker would strand console progress behind long DOS calls.
Do not add a second input worker, a full input.device task or a task per open.
For scale, sixteen 40-by-24 consoles would use 15,360 bytes of one-byte cells
and 2,048 bytes of input FIFOs in upper RAM, plus per-instance metadata, caller
requests and shared service state. That is a sizing example, not a qualified
capacity or a request to preallocate sixteen instances in the first build.

This documentation change reserves **zero additional bank-zero bytes**, fixed
or per Task. The implementation target is also zero reservation growth, using
the existing pool and screen. It is not a claim that new callbacks already fit.
Measure adapter growth and maximum worker/IRQ/NMI stack usage; update the map
and report complete reservations, including slack, if placement changes. The
current eight-task totals are 61,536 runtime bytes and 57,232 loading bytes,
including OS reservations; see the
[bank-zero budget](../reference/platform.md#bank-zero-memory-budget) and
[capacity accounting](../architecture/task-capacity.md#complete-bank-zero-budget).

## Relationship to Amiga Exec and DOS

The reference is the classic console.device contract: standard device calls,
IOStdReq and byte-stream reads that can finish short. See the original AutoDocs
for [CMD_READ](https://d0.se/autodocs/console.device/CMD_READ),
[CMD_WRITE](https://d0.se/autodocs/console.device/CMD_WRITE) and
[CMD_CLEAR](https://d0.se/autodocs/console.device/CMD_CLEAR), plus
[OpenDevice](https://d0.se/autodocs/console.device/OpenDevice).

| Deliberate difference or deferred feature | Reason |
| --- | --- |
| One default console instance initially; no Intuition Window argument or special unit modes yet | Keep the first milestone small while retaining per-instance state and presentation separation for the required multiple text windows. |
| One pending read per console; writes may queue | Avoid competing consumers of one keyboard stream. Future independent consoles have separate queues and focus-directed input. |
| Native 24-bit pointers and existing 42-byte IOStdReq | Reuse the current 65816 ABI, without 68000 binary compatibility. |
| Explicit lengths only; input pointer/length remain unchanged on writes | Bound memory access and preserve the existing Exec816 request convention; classic console writes also support `-1` and update those fields. |
| Fixed keyboard map, ASCII/control subset, ROM-glyph fallback | Deliver a usable shell before implementing raw events, keymap.library and full ANSI/Latin-1 rendering. |
| BREAK/Ctrl-C as input bytes, no DOS break-signal policy | Process/job lifetime and DOS cancellation are not specified yet. |
| Deferred nonempty writes and explicit input-overflow errors | Keep long work preemptible and make lost keyboard input visible with finite storage. |
| Native keyboard/display adapter, task-only calls | ROM CIO cannot provide this concurrency; preserve current IRQ and port restrictions. |

Amiga's console byte stream and its higher-level DOS console handling are
separate concerns; see the [console device overview](https://wiki.amigaos.net/wiki/Console_Device).
Initially the shell owns the device requests and line editor directly. Do not
claim `DOS.Open("CON:")`, `Input`, `Output`, `DOS.Write`, inherited handles or
redirection: the [current DOS design](../reference/dos.md) covers file reads
and directory access. A later console handler can add those interfaces over
this same device without changing the application image format.

## Acceptance and implementation order

First prove keyboard/SIO coexistence with a small native probe. Then implement
instance state and input delivery, queued device requests and native screen
presentation. Complete service lifetime before enabling ordinary use, then
add a resident MyDOS example and eight-task qualification. Keep these as
executable slices with separate commits, following the
[implementation plan](../plans/console-io-implementation-plan.md).

Acceptance requires:

- Emitted raw and optimized code: short/zero reads, empty-read waiting,
  simultaneous output, FIFO writes, exact replies, both abort races, overflow,
  clear, close/reopen and failed admission rollback. Exercise bank-crossing
  linear buffers and rejected extents without guard corruption.
- Keyboard press/release, Shift/Control/Caps Lock, held keys, BREAK and burst
  overflow while idle and under sustained SIO. Include shared-register reset
  intervals and both service start/stop orders; no phantom or missing keys in
  the defined test sequence below the declared buffer capacity.
- Full-screen wrapping, scrolling, cursor preservation, control bytes, glyph
  mapping and screen/editor restoration. Verify retained cells separately from
  screen RAM and the cursor overlay, including redraw from cells with the caller
  buffer already released. A successful CIO status is not a native-display test.
- Native and emulation IRQ entry, simultaneous serial/keyboard sources,
  asynchronous NMI, unowned IRQ chaining, full register/DP restoration and
  stack/domain guards. Exercise blocked clients while other tasks progress.
- Eight live tasks with console typing/output and MyDOS reads on 128/256-byte
  media, including one large read. Repeat the existing 125-kbaud wire gates
  with unchanged thresholds and an identical unobserved replay. Report keyboard
  IRQ-to-read-reply latency and maximum masked intervals separately; keyboard
  worker latency is not the SIO byte-service deadline. Cover kernel banks 1 and
  3 functionally; report the exact configuration used for timing.
- Shutdown after ordinary use, cancelled reads, DOS errors and unsafe SIO
  recovery. Prove that callbacks cannot reach freed state and that only a safe
  system returns to the OS.

The later multiwindow milestone must additionally qualify simultaneous visible
output, clipping isolation, hidden-window output and exposure redraw, per-console
FIFO/fairness, input across focus-change races, and closing one console while
others have active I/O. Report the upper-RAM cost per console and demonstrate
that adding consoles does not allocate task contexts or extra bank-zero display
buffers. These future tests are not prerequisites for the initial single-instance
milestone, but its instance/presentation boundary and retained cells are required
from the start.

Pin compiler, ROM, emulator, machine and disk profile in the resulting record,
starting from [the current SIO pin](../../toolchain/altirra-sio-queued.json). The
ROM source observations above come from that pin's source archive,
`src/Kernel/source/Shared/irq816.s`, `keyboard816.s`, `vbi816.s` and
`screenext816.s`: keyboard translation and repeat are separate ROM services,
and stage two writes display shadows. The archive's
`src/ATAudio/source/pokey.cpp` also exposes shared error-latch reset and keyboard
scan behavior on `SKCTL` writes. Source inspection identifies integration work;
existing SIO tests and this note do not qualify the proposed console or physical
hardware.
