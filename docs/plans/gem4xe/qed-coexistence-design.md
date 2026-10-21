# QED practical coexistence design

[GEM plans](README.md) · [Strategy](qed-port-strategy.md) ·
[Implementation plan](qed-coexistence-implementation-plan.md) ·
[Saving handoff](../../history/qed-saving.md#qw8-saving-gate-and-coexistence-handoff)

Strategy step 6 establishes a usable single-document QED session under ordinary
desktop load. Measure the current production APP, including the
[idle caret correction](../../history/qed-saving.md#idle-cursor-repaint-correction),
before choosing performance changes. Open, edit, navigate, Find, Save and Quit
must preserve text and ownership while another admitted client makes progress.
Supported delivery remains step 7.

## Workloads and admission

Keep the pinned compiler, C APP ABI, provider, AltirraOS ROM and emulator from
the current interactive preview. Use PAL, 65C816 at 8x, 63 high banks, VBXE,
ST mouse and the existing eight public Task pools. Preserve the five-second
OF816 startup and exact production APP. Use disposable WORK copies; never test
against the user's writable disk. Earlier artifacts and records stay frozen.

The [shared Task budget](../../architecture/task-capacity.md#shell-controller-admission-budget)
requires separate cohorts:

| Cohort | Live Tasks | Purpose |
| --- | ---: | --- |
| QED baseline | 7 | Controller, console, filesystem, SIO, shell, desktop APP and QED |
| QED and Counter | 8 | Add an ordinary loaded GUI client; shell remains at its prompt |
| QED and checksum | 8 | Shell starts foreground CKSUM on an unrelated large WORK file while QED remains its background job; Counter is closed |

The checksum cohort supplies real shell command execution, CPU work and disk
reads without introducing the SDX guest profile solely for MD5/ARC. These are
the strategy's shell-activity alternative. A shell owns one background job, so
QED uses RUN and CKSUM uses its ordinary foreground command path; input focus
can return to QED while that command runs. Never run the checksum and Counter
simultaneously with QED. Attempt one additional launch at the full peer cohort
to check ordinary capacity failure and cleanup, without increasing any pools.

## Production workflow and measurements

Run the same small tabbed, multi-line document through physical keys and normal
shell RUN in each cohort. Exercise insertion, grouped Undo, navigation that
reveals another row, Find and cancellation, checked Save/backup, reopen and
Quit. Verify saved and backup bytes independently after closing the ATR.
Use a larger document and retained clipboard/Undo in the lifetime cohort to
measure variable backing and fragmentation. Include covering and exposing QED
with another window; check both application pixels and peer progress.

Observe private state only to establish identity and completion. Resolve loaded
symbols through the retained Process image. Obtain C record offsets from the
target-emitted layout table compiled from matching QED headers, never host
`sizeof` or guessed offsets. Production timing uses an unmodified APP and native
desktop. Failure interposition belongs to a separately identified fixture that
forwards successful operations to the real implementation.

Measure physical key-down to the first independently correct completed video
frame for warm insertion and navigation. Before the timed navigation block,
wait for the untimed positioning sequence to reach completed scanout; cursor
state alone can precede its viewport paint. Poll scanout once per PAL frame and
report the resulting upper bound, including keyboard scan and up to one frame
of observation quantization. Release keys after three frames so a slow painter
cannot create auto-repeat. Compare text pixels outside the caret band; logical
completion alone does not establish visible response. Record Find, load, Save
and retirement completion separately from input feedback and human consent.
Do not include the host's sleeps or bridge round trips in emulated time.

Pin the following development limits before measuring:

| Endpoint | Limit on this pinned configuration |
| --- | ---: |
| Warm character insertion | 500 ms per sample |
| Navigation with viewport repaint | 1,000 ms per sample |
| Opening or dismissing the small Find form | 1,500 ms to completed form/text pixels |
| Counter progress while QED owns input or a form | At least one tick in a two-second observation |
| Clean Quit after pending I/O finishes | 2,000 ms to Process retirement |
| Individual disk operation | Bounded completion within the existing 12,000-frame desktop observer limit |

Record all samples and maximum/median per cohort. Relative changes are useful
diagnostics; they do not replace the absolute limits. The small sample counts
are development observations, not percentile or worst-case latency proofs.
If a gate fails, retain the failure and diagnose its responsible owner before
changing a limit or adding capacity. A justified design amendment must precede
any changed acceptance criterion.

## Memory and lifetime

Capture upper heap free bytes, largest free extent and free-extent count at
warmed idle, document/clipboard/Undo peaks, forms, active load and collection.
Keep QED's private allocator totals separate from its aligned image backing and
native/filesystem allocations. Sampled peaks are lower bounds on transient
peaks. Repeated comparable retired checkpoints must restore free bytes and the
largest extent, with no accumulating fragmentation. Record ownership ledgers,
live Task peaks and application/window/workstation return as well as memory.

Exercise repeated loaded lifetimes, a real line-allocation refusal, form
allocation refusal, Cancel and cooperative Stop with the peer alive. Failure
must retain the document, permit subsequent editing and leave the desktop
usable after normal collection. Reuse earlier saving failure records only for
their original matching scope; this step adds coexistence and repeated-use
coverage, not another transport-fault matrix.

Keep the existing 2,560-byte QED admission, conditional source bound and native
continuation allowance unless measurements justify a change. Preserve guards,
DP ownership and complete native context. Observe ordinary and asynchronous
stack headroom in the targeted lifetime fixture and inspect production runtime
guard results. No kernel, driver or scheduler policy change is planned. Exec's
current scheduling and public coordination semantics remain authoritative.

## Changes and completion

The first baseline exposed whole-viewport damage after every character. QC1a
narrows same-row replacement damage and retains full redraw when clamping moves
the viewport. This is a QED rendering-policy correction; the response limits,
public interfaces and capacities remain unchanged. See the
[implementation record](../../history/qed-coexistence.md#qc1a-incremental-edit-damage).

Loaded measurements also exposed repeated full selection redraws and separate
caret/text transactions. Patches 0019–0022 consume paired selection endpoints,
paint the caret inside edit/navigation row updates, use opaque default-colour
rows through existing VDI replace text, and avoid repeating a scroll owner's
complete paint. Selection colours keep their existing explicit fill path; idle
blinking keeps its narrow caret-band path. These changes remain QED painting
policy, with the same response limits, ABI and capacities.

Optimize only a measured failure or material bottleneck in this workflow. Keep
application drawing policy in QED, reusable GUI behavior in AES/VDI, filesystem
and transport coordination with their owners, and compiler defects in actionc.
Do not add QED-specific kernel services, duplicate validation or private driver
protocols. No stack, image or Task capacity increase is automatic.

The reservation target is **0 fixed / 0 per-public-Task / 0 private idle
bank-zero bytes**, including guards, alignment and unused capacity. Report the
actual delta in every slice, separately from upper-memory and disk-fixture
costs. Unchanged native packages may be reused after input and hash checks.
Any demo refresh uses `tools/build_demo.py`, including OF816, matching media,
pinned ROM and notices; publication and cartridge delivery remain step 7.

Complete step 6 when all admitted cohorts pass the specified workflow and
response limits, both clients progress, saved bytes are exact, warm lifetime
checkpoints restore resources, selected stack checks pass and current evidence
is reconciled. Record the tested document/load sizes and limits. Development
completion does not qualify the hosted system or a release, nor extend the
single-document feature scope fixed in step 1.
