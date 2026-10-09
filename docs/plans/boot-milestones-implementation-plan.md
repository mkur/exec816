# Kernel boot milestones and fatal startup reporting

Status: BD1–BD3 implemented at the development tier. The standard packaged
console passes the focused startup cases below. Physical Antonia II / OSXL /
IDE Plus 2.0 behavior and VBXE terminal scanout remain unqualified.
The subsequent alignment and relaxed display-admission changes were rebuilt
without rerunning tests, as requested; the recorded checks cover the earlier build.
Release preparation also enables the startup phase for deferred bitmap-console
boot; that follow-up is build-only and does not extend the recorded test scope.

Follow the [platform contract](../reference/platform.md),
[console contract](../reference/console.md) and
[testing policy](../contributing/testing.md). This extends the existing boot
reporter rather than introducing a logging service or a separate design note.

## Behavior

In verbose boot mode, report successful boundaries in this order:

```text
VBI/IRQ       =OK
CONSOLE WORKER=OK
CONSOLE       =OK
SHELL         =LAUNCHED
```

- VBI/IRQ: vectors and scheduler state are installed, and interrupts are enabled.
  This reports initialization, not qualification of every interrupt path.
- Console worker: the Task is running and its request/input/stop signals and
  resident endpoint are established, before it claims the display.
- Console: Start has published readiness after display, retained cells and input
  capture are established. Print through the console once its stream is open.
- Shell: the session, standard streams and initial aliases are established.
  Mounting and startup scripts follow; the prompt still means interactive ready.

The first two messages use the existing OS-screen reporter. Worker readiness
appends directly before display claim: admission has already blocked ROM entry.
This bounded append updates the cursor under IRQ/NMI exclusion and lets Adopt
retain the message, including when the OS screen needs scrolling. The final two
use the console stream so physical screen and retained cells remain consistent.
Suppress routine milestones in quiet mode. Existing hardware error reports
remain visible. Do not let appended success event numbers inherit the existing
"all events after the first failure are forced" rule.

Any terminal kernel failure before shell launch prints, even in quiet mode:

```text
System halted: $FF95
```

Preserve the original fatal code separately from a later reset-required status.
Use a known kernel stack and DP; never unwind a damaged Task stack. Terminal
reporting must not allocate, wait for the console worker or call ROM services.
Place the final line after normal console restoration, or on the reset-required
path where resources remain reserved. For an owned VBXE display, expose the
saved OS text display without treating this as DMA recovery or freeing storage.
Stop IRQ/NMI before this operation. No cleanup may subsequently erase the line.

A small startup phase distinguishes these failures from normal shell/command
errors. End the phase at shell launch. The early unclaimed-state rejection and
loader failures retain their separate paths; they cannot use kernel state.

## BD1 — admission and early milestones

1. Remove DRKMSK from GRAPHICS 0 admission: its value does not define display
   memory or rendering. Keep display bounds/layout checks. The subsequent
   admission update also accepts arbitrary CHBAS and attract/color state;
   display claim establishes CHACT=2/GPRIOR=0 and release restores them.
2. Extend machine-readable diagnostic events and generated definitions with a
   bounded forced-failure range and successful milestone events.
3. Use spare bytes in the existing adapter state page for startup phase, original
   fatal code and the initial OS screen/list/DMA snapshot. No new reservation.
4. Print VBI/IRQ after interrupt enable and worker readiness before display claim.
   Gate worker reporting on the active startup phase, avoiding restart chatter.
5. Update the display fixture to accept arbitrary DRKMSK while still rejecting
   invalid display state. Assemble the native adapter and check generated files.

## BD2 — console handover and terminal failures

1. After ShellOpen succeeds, print console and shell milestones through its
   ordinary output stream, honoring the boot verbosity bit.
2. End startup only after shell readiness output succeeds. A session-open/output
   failure enters the terminal path with its causal DOS error; disk mounting
   failures retain their existing recoverable behavior.
3. Route startup failures through the common native finish path. Capture the
   original code once, reset the stack/DP before diagnostic work, and render the
   final fatal line after restoration. Retain existing safe-bus and reset-required
   policy; a diagnostic is not permission to reclaim live DMA storage.
4. Remove duplicate pre-cleanup halt messages. Ensure direct reset-required
   entries also retain/report their cause during startup.

## BD3 — focused emitted-code checks and documentation

1. Build the standard OF816 demo with the pinned compiler and five-second
   autoboot. Check cart capacity when augmenting the local demo.
2. Pin ROM/emulator inputs and verify ordered verbose milestones and a prompt;
   repeat in quiet mode, checking that routine milestones are absent.
3. Inject a console-admission failure and a kernel fault after display ownership,
   including an invalid Task stack/DP. Check bounded completion, original fatal
   code, persistent visible text and unchanged guard/reservation accounting.
4. Exercise reset-required reporting without granting recovery/reclamation.
   Run a bounded XLOS standard boot as compatibility evidence only.
5. Update platform and console references and the standard distribution guide;
   record exact development execution scope and memory costs in this plan.

## Budget and scope

Target **0 fixed, 0 per-public-Task and 0 idle reserved bank-zero byte growth**,
including guards, alignment and unused reserved capacity. Reuse the existing
256-byte adapter state and upper native code arenas; measure their emitted size.
The OS-screen success reporter retains its private 24-byte temporary stack
buffer. Emergency output uses the existing kernel DP/stack and saved OS screen.
No public Exec gateway operation or external command ABI change is required.

Exclude full release matrices, new debug commands, a general logger, remote
logging, filesystem checking and hardware recovery. Do not publish new packages
as part of this work.

## Execution record

- Removed DRKMSK admission and implemented the four successful milestones.
  Worker reporting uses a bounded direct append because console admission has
  already blocked ROM calls. The other early trace events still use CIO.
- Common finish captures the first startup error and establishes the kernel
  stack/DP before shutdown. The final line survives screen restoration and
  reset-required parking. Successful root return and post-launch faults do not
  produce a fatal-startup message.
- The pinned standard OF816 demo boots from the new Atarimax CAR in ten bounded
  cases: verbose, quiet, arbitrary brightness mask, rejected display, fault
  before console, fault after display claim, unsafe-bus reset-required, normal
  return, post-startup fault and XLOS 2.48A. The last case is compatibility
  evidence with an explicit ROM override, not platform qualification.
- Small raw/optimized emitted probes check Active/Complete/Halt, the CARD error
  argument, quiet suppression and bottom-row worker append/scroll. They retain
  stack/domain guards and OS restoration checks. The host suite passes 421
  tests; generated ABI checks and changed documentation links pass.
- Fixed, per-public-Task and idle reserved bank-zero changes are **0 / 0 / 0
  bytes**, including guards, alignment and unused capacity. State uses eight
  previously spare bytes. The upper blitter arena emits 1,650 / 2,048 bytes;
  the native signal arena emits 10,874 / 12,288 bytes. Reservations stay fixed.
- The local standard ZIP contains XEX, old/new CAR and raw BIN images. Its boot
  XEX is 327,045 bytes, leaving 705,146 bytes of cartridge payload capacity.
  OF816, five-second autoboot and matching disks remain included.

See the [development record](../development/boot-milestones.json) for pins,
checksums and case results. Logs/screens/build intermediates stay under
`build/development/boot-milestones/`; the distributable local demo is
`build/boot-milestones-cartridge/exec816-demo.zip`. No release was published.
