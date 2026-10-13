# Desktop file drag and drop

[Current AES contract](../reference/aes.md) ·
[Design](../plans/gem4xe/desktop-drag-drop-design.md) ·
[Plan](../plans/gem4xe/desktop-drag-drop-plan.md) ·
[History index](README.md)

The desktop copies regular-file selections between its folder windows in icon
and list view. A four-pixel threshold separates a drag from an ordinary click.
An existing selection stays intact; an unselected source becomes the selection.
A small outline follows the pointer, while the destination status names the
folder or directory entry. Escape cancels. Directory sources, Move, desktop-icon
rearrangement, auto-scroll and drops to independent applications are not provided.

`MU_M1` uses caller-local matching against the coherent pointer snapshot and
existing signal. No motion messages or polling timer are added. `wind_find`
queries the actual layer stack, including foreign/native occlusion. The presenter
owns one application outline under explicit MCTRL, reusing native outline
storage. Owner UPDATE drawing suspends/restores it; foreign UPDATE requests
retain the existing MCTRL wait policy.

Release copies the destination path and publishes one private eight-word AES
message. The one pending record survives cancellation until consumption, so a
late completion cannot admit a later gesture. Queue exhaustion cancels. The
receiver starts the existing sequential copy job after releasing mouse/display
ownership. Single drops preserve the filename; menu Copy retains its full-path
entry semantics. No additional work is added to the Read/Write loop.

## Development checks

The input fixture passes 705 checks plus four native checks, covering M1-only
waits, enter/leave boundaries, interest-before-Wait publication, all 31 combined
masks, retained button precedence, parameter blocks and loss/close during timer
retirement. The expanded sequence exposed a fixture error: a cancelled timer's
leftover signal was treated as a completed new alarm. The fixture now checks the
request completion before injecting simultaneous input. Production timer policy
is unchanged.

The window fixture passes 256 checks plus four native checks. It exercises
foreign window targeting and the parameter-block query, plus native top/move/
close/resize/slider behavior. Cancelled outlines restore exact pixels; 2,688
frame pixels match the independent raster. Small native ABI probes pass 39
checks in each of raw and optimized mode; C shared layouts pass at O0 and O2.

Host tests execute the actual gesture source with controlled API outcomes for
queue-full failure, cancelled queued completion after source retirement,
duplicate consumption, release without an intervening motion event, Escape and
rearming, invalid/file/same-directory targets and directory-containing groups.
These host cases are distinguished from physical emulator input and disk tests.

The extracted demo walkthrough passes physical icon/list drags, a single file
onto another folder's background and a two-file selection into its subdirectory.
Independent disk readback matches all three source files and finds no leftover
copy temporary. Escape/rearming, repeated gestures, default overwrite Cancel,
stable-hover repaint suppression and exact cancellation restoration pass.
Counter can request UPDATE while MCTRL is held: the outline continues moving,
and the waiting peer repaint resumes after release. The final desktop pixel
oracle, shell HELLO and orderly EXIT pass without reset and with guards intact.
The complete host suite passes 455 tests with four historical skips.

The existing menu Copy regression passes with independent binary readback:
empty/short/exact-buffer/tail files, Replace/Skip/default-Cancel, unavailable and
read-only destinations, a preexisting temporary file, cancellation after a
completed file, owner close and desktop shutdown. Partial/all-skipped jobs
return to the same 2,332,104-byte free-heap baseline. Its four-file 49,226-byte
corpus takes 99.8852 emulated seconds, against the recorded 99.8840 seconds for
that same corpus before this refactor. This is one matched batch observation,
not a statistical throughput claim or a new disk optimization. It reuses the
established benchmark instead of adding a separate single-file fixture.

## Feedback measurements

The final demo records these submission-to-scanout measurements, in milliseconds:

| Event | Idle median / p95 | Counter median / p95 |
| --- | ---: | ---: |
| Press through threshold movement to outline | 140.45 / 140.46 | 160.41 / 160.66 |
| Threshold movement packet to outline | 104.84 / 104.84 | 121.00 / 121.25 |
| Subsequent motion packet to outline | 40.17 / 40.17 | 60.12 / 60.37 |

Each column has 12 physical-input trials with one PAL-frame scanout polling.
The electrical packet submission includes its 2,000-cycle delay. Values use the
existing observer's upper-middle median and nearest-rank p95 convention; with
12 samples p95 is the maximum. These are bounded development observations, not
capture-to-visible measurements or a reopened HY4 qualification claim.

An initial implementation repainted the source status when dragging began.
Removing that redundant paint reduces idle threshold-to-outline median from
225.08 to 104.84 ms. The selection already identifies the source. Only entering
or leaving a destination changes its status strip; stable hover does not repaint
the folder. Every timing cancellation restores the exact 112-by-32 source patch.

Release to the visible copying caption takes 1,925.46 and 2,446.61 ms in the two
observed drops. Existing admission opens/examines filesystem paths before drawing
that caption, so these include directory I/O and cannot isolate AES message cost.
They are separate from the complete-transfer benchmark above; no performance
claim about pure release-to-admission latency is made from those two samples.

Integration reports and measurements are recorded in
[development evidence](../development/desktop-drag-drop.json). The tests use
optimized target code, the pinned PAL AltirraOS/VBXE setup, Calypsi 5.18 and the
release host executable at the unchanged actionc pin. Compiler qualification and
release/hardware qualification were not run.

## Memory and packaging

Each registration adds 20 bytes of upper-memory frozen pointer scratch: the
inbox is 754 bytes and registration storage is 1,306 before heap rounding.
The presenter adds nine logical bytes of ownership state. One 148-byte desktop
drag record brings Desktop to 2,352 bytes. Browser remains 3,973 bytes; the job
remains 974 bytes with the existing 16,384-byte copy buffer. No new Task,
signal, timer, directory snapshot or VRAM save surface is allocated.

Fixed, per-public-Task and idle reserved bank-zero deltas are all **0 bytes**,
including guards, alignment and unused capacity. The demo's reservations match
the previous desktop-style build. All loadable C apps are rebuilt for ABI 15;
the AES wire profile is version 14.

The drag walkthrough's minimum observed ordinary-Task headroom above its floor
is 178 bytes; the broader menu Copy fixture reaches 151 bytes. Idle retains
127 bytes in the drag run, and the kernel retains 993 bytes above its floor with
its interrupt reserve untouched. No stack reservation was increased.

The demo is built and packaged through `tools/build_demo.py --gem-desktop` with
OF816, five-second autoboot, matching disks, pinned ROM, notices and checksums.
An initial Text-app compiler timeout was retried with a longer host timeout.
A relative-path build-wrapper packaging error was corrected using the normal
packager with the already emitted resident image and final rebuilt applications.
Neither changes the compiler pin or the target runtime.
