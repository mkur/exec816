# Exec816 demo implementation plan

Status: D1–D6 implemented and development-tested. See the
[implementation record](../history/demo-implementation.md). Deliver a bootable XEX with a companion read-only MyDOS ATR
showing an interactive shell, an independent computation and disk-loaded commands
connected by a pipe. This is a development play image; full release qualification
is a separate gate under the [testing policy](../contributing/testing.md).

## What the user sees

Use the existing 40×24 text screen: a 40×18 shell at (0,0) and a 40×6 computation
at (0,18). The lower region includes a text separator, PRIME SEARCH label, count
and latest prime. Each region scrolls independently; keyboard focus stays on the
shell. Redraw the lower region at most once per second with existing clear/write
operations. No new cursor controls or scrolling optimization are required.

The walkthrough is: boot; use DIR, TYPE README.TXT and TASKS while primes advance;
run `HELLO | WC`, then `CAT STORY.TXT | WC`; interrupt `CAT LONG.TXT | WC` with
BREAK; run another command; compare MEM before/after repeated commands; EXIT.
The prime search continues during commands and pipeline cancellation, and stops
cleanly on EXIT. The prompt returns only after every pipeline stage retires.

## Scope and delivery

Support one foreground pipeline containing exactly two external commands.
Resident built-ins remain shell commands. Named pipes, longer pipelines, scripts,
background shell syntax, filesystem writes, draggable/resizable windows and
forced process termination are outside this demo.

Use current console windows, Process lifetime, o65 loading and the existing WC
implementation. Keep the prime worker resident so the showcase needs no new
loaded-command imports for windows, timers or Task creation. Keep one shared
shell implementation, parameterized by its console binding.

Each slice must run and pass its focused development checks before its commit.
Keep commits separate and record the actual checks, memory delta and outstanding
qualification. The WC prerequisite is committed separately as `4113002`. This document introduces no
runtime changes.

| Slice | Deliverable | Depends on |
| --- | --- | --- |
| D1 | Two text regions, usable shell and independent prime search | Existing windows and Process support |
| D2 | External CAT and useful sample text | Existing command loading and WC |
| D3 | Anonymous pipe handles with blocking I/O and safe lifetime | Existing DOS streams and inheritance |
| D4 | Two Processes share foreground cancellation and retire together | D3 |
| D5 | Shell executes two-stage external pipelines | D2, D4 |
| D6 | Reproducible demo bundle and end-to-end walkthrough | D1, D5 |

### D1: visible multitasking

Add `examples/demo.act` owning two console instances; hide the full-screen default,
show the two tiles and focus the shell. Pass the selected console to shared
shell initialization; update existing callers together, keeping ordinary shell
boot on unit zero. Start a resident background Process with NIL input and the
lower console as output. Compute primes in bounded batches, poll a private stop
request and pace display updates; keep computation and display storage fixed.
Use an explicitly bounded numeric range with a visible pass counter on restart.

EXIT and failed startup request worker shutdown and collect its retirement before
closing shell resources, destroying owned instances and returning through normal
service shutdown. Never destroy an instance with live handles or worker borrows.

**Check:** raw/optimized native startup, failure rollback and exit; physical input
and upper-region scrolling while prime progress remains visible below. Confirm
BREAK in the shell leaves the computation running, default shell startup still
works, and stack/context guards, ownership and OS restoration remain intact.

### D2: CAT and sample data

Add `examples/commands/cat.act` implementing `CAT [file]`: copy one file, or
selected Input when no file is supplied, to
selected Output without translating bytes. Use bounded chunks, handle partial
writes, preserve causal I/O errors, poll BREAK, and close only owned handles.
Accept one optionally quoted path using the existing argument conventions.

Add small STORY.TXT and a larger LONG.TXT to demo media sources. Record independently
calculated WC totals from the exact packaged bytes. Size LONG.TXT to allow a person
to interrupt a real read on the selected disk profile while fitting the small ATR.

**Check:** focused raw/optimized emitted-code copying of empty, binary and
multi-chunk input, partial writes, argument/read/write errors and BREAK; one
disk-loaded smoke. Retain existing WC evidence when its inputs are unchanged.

### D3: anonymous pipe streams

Add a DOS pipe-pair operation and backend compatible with ordinary Read, Write,
Close, stream selection and Process inheritance. Start with a 1 KiB upper-RAM
ring buffer and separate owned reader/writer wrappers. No pipe worker is needed.
Publish the stream contract separately and generate new ABI definitions from
machine-readable inputs where applicable.

Read waits while empty and writers remain; Write waits while full and readers
remain. Last-writer close gives EOF after buffered bytes drain; last-reader close
wakes writers with a defined error. Seek and operations on the wrong end fail.
Define short-transfer/error behavior consistently with existing DOS cancellation.
Cloning and rollback must account for endpoint references. Protect publication
and wakeup transitions against preemption; never hold scheduling exclusion across
a wait or an unbounded copy. Retain backing storage until waiters and references
retire, including canceled operations.

**Check:** raw/optimized native producer/consumer streams larger than the buffer;
wraparound, empty/full waits, close wakeups, inherited references, allocation and
signal failures, cancellation races, repeated reuse and complete reclamation.

### D4: pipeline Process lifetime and cancellation

Extend foreground ownership to a bounded two-member command group. One console
route identifies the group; BREAK becomes durable for both members and wakes
their pipe, console or filesystem waits. Keep IRQ capture bounded; distribute
cancellation in task context. Preserve single-command behavior and reject stale
route events after the next prompt begins. Publish this contract alongside the
existing [Process](../reference/process.md) and [foreground](../reference/foreground-break.md)
contracts, without exposing a general shell job-control API.

Prepare both images, streams and child resources before publishing runnable
members. Both stages must be able to start before either is waited on. The
existing single-child foreground loan suspends parent DOS use, so explicitly
extend that protocol instead of launching two ordinary foreground children.
Close parent copies of pipe ends after handoff; an extra writer would prevent EOF.
Partial launch failure cancels and collects admitted children before releasing
their images, handles or group state. Early consumer exit wakes blocked producers.
Restore the shell foreground only after both children and outstanding I/O retire.

**Check:** a native harness runs loaded HELLO and WC through the pipe; exercise
admission failure, early exit and BREAK during loading, empty/full waits and real
file I/O. Confirm an unrelated worker survives, the next foreground
command is unaffected and resources return to baseline. Include targeted existing
single-child foreground regression coverage in raw/optimized mode.

### D5: shell pipeline dispatch

Recognize one unquoted `|`, including adjacent to a word; preserve quoted pipes
as literal argument bytes. Keep the existing total line/word limits. Reject empty
stages, a second pipe, built-in stages and conflicting redirections before loading
or starting anything. Allow input redirection on the left and output redirection
on the right, using existing destination restrictions. Ordinary commands keep
their current behavior.

Use D4 to launch the stages. Keep prompts and shell diagnostics on the private
shell console. Retain both results: success requires both stages to succeed;
otherwise report the first failing stage in command order. Preserve the causal
setup/I/O error during cleanup; user cancellation follows the existing BREAK
status convention. Document these choices in the shell guide.

**Check:** focused parser cases plus raw/optimized native pipeline execution.
Physically enter `HELLO | WC` (expected `1 3 17`), `CAT STORY.TXT | WC`, malformed
input and a canceled LONG.TXT pipeline; verify exact output and a usable prompt.

### D6: packaged play image

Add `tools/build_demo.py` producing `build/demo/program.xex`, `build/demo/mydos.atr`
and a manifest of source/toolchain/configuration/media hashes. Put the short boot
and walkthrough guide in `docs/guides/demo.md` and include it in the bundle.
Reuse the existing builders; stage HELLO, CAT and WC as exact binary bytes alongside
text sources. The ATR remains a data disk: mount it and boot the XEX. Check disk
capacity, use a single output directory, and avoid copying compiler/emulator trees.
Update stale shell/README status statements relevant to the shipped demo.

Use the compiler recorded in [actionc.json](../../toolchain/actionc.json), stack
checks enabled, the eight-Task profile and the exact ROM/emulator configuration
from the [paced shell pin](../../toolchain/altirra-shell-paced.json). Use the existing
[57.6 kbaud mount](../../config/shell-mydos.json) and matching drive settings. Record
the actual inputs; do not move the compiler pin or run its deferred general
qualification as part of packaging.

**Check:** run one bounded physical walkthrough on the final optimized bundle,
including prime progress during disk reads, physical BREAK and a subsequent
successful command. Repeat a small fixed number of pipelines and compare Task,
handle, Image and heap ownership against the warmed-up idle demo baseline, then
verify EXIT restores the OS. Capture one actual screen image for the guide.
Reuse unchanged raw/optimized slice results with verified input hashes; any
integration fix gets its affected regressions rerun. Report remaining release
qualification explicitly rather than launching the complete matrices by default.

## Resource and validation gates

Peak target: seven public Tasks (shell, console, filesystem, SIO, prime Process
and two pipeline stages), with one slot spare. No new service worker or expanded
Task capacity. Budget both loaded Images, including their alignment overhead,
staging, handles, group metadata and pipe storage against measured free upper RAM
before finalizing sample sizes.

The two new console instances require 1,408 upper-heap payload bytes under the
existing formula: 944 for 40×18 and 464 for 40×6. Their handles/routes, the retained
default instance, allocator overhead and demo worker storage are additional.
The initial pipe ring is 1,024 payload bytes; measure metadata and signal costs
separately. Freeze exact group/waiter layouts in D3/D4, not in this plan.

Target reserved bank-zero delta for every slice: **0 fixed bytes and 0 bytes per
Task**, counting guards, alignment and unused reserved capacity. Using existing
Task slots consumes their pre-reserved stack/DP capacity. Preserve the
[platform memory budget](../reference/platform.md#bank-zero-memory-budget), interrupt
headroom and documented IRQ/NMI protocol; report actual map deltas per slice.

Run host checks for code changes, affected generator checks and the focused native
cases listed above. Documentation-only work needs content/link checks. Reuse
unchanged builds and avoid routine traces or alternate-placement/transport
matrices. Full release qualification is required before claiming a qualified
release; this plan delivers a development demo with its limitations recorded.
