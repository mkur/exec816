# Control Panel session settings

[History](README.md) · [Plan](../plans/gem4xe/control-panel-settings-plan.md) ·
[Public contract](../reference/aes.md#session-mouse-preference) ·
[Development evidence](../development/control-panel-settings.json)

CP1–CP3 are implemented. `PANEL.APP` stages the existing Off/Mild mouse
acceleration choice in its private OBJECT tree. Defaults stages Mild, Apply
publishes it and Cancel reloads the active choice. Closing discards unapplied
edits; a new panel reads the retained session preference. Keyboard, outside
release and Escape cancellation remain available. Pushbuttons return to their
unselected state. Only changed controls, focus and status need repainting.

`ExecAESMouseProfile` uses the existing AES request lifetime and presenter input
owner. Drawing remains caller-local. A held gesture retains its old curve until
release; input loss ends the gesture too. Coordinates are retained and fractional
motion clears only when the active profile changes. There is no persistent file,
new device, Task, timer or signal. This uses AES wire version 9 and C application
import ABI 4; all packaged apps were rebuilt with the unchanged compiler pin.

## Development checks

- 27 native settings assertions in both raw and optimized builds: unchanged
  profiles, fractional reset, query, held-button deferral, release, loss and
  replacement of a pending choice.
- 43 C/AES boundary assertions with raw and optimized C, using the optimized
  native server: Off's zero result, signed Query, operational failures, repeated
  attach/detach and preference lifetime. No record layout changed.
- 2,870 optimized curve cases against the rational oracle, with no external
  arithmetic helper in the emitted transform.
- 416 host tests pass, with four historical-source skips. Generated definitions,
  changed-document links and whitespace checks pass.
- The exact extracted OF816 ZIP passes physical mouse and keyboard settings,
  six independent settled-pixel checkpoints, repeated Apply, overlap/drag,
  exposure after shell scrolling, counter progress, close with unapplied edits,
  Files reload/Stop, shell commands/pipeline, idle heap collection and EXIT with
  a live child/popup. Guards, ownership and OS restoration pass.

The first walkthrough exposed a three-byte margin above the checked stack floor
in Files during mouse selection in its popup. A targeted high-water trace
identified that application and gesture. Moving its two MENU descriptors and six
event-output words into the private model removes 24 bytes from `file_menu` and
12 from `BrowserRun` in the emitted prologues. The final walkthrough's smallest
public-Task margin is **38 bytes above the 256-byte interrupt reserve**.
These are observed high-water marks, not a proof for arbitrary application depth.

Six frame-granular press-to-matching-button samples in each loaded lifetime give:

| Panel lifetime | Median | Maximum |
| --- | ---: | ---: |
| Initial | 120.25 ms | 120.51 ms |
| Reloaded | 120.24 ms | 140.47 ms |

The measured control is Defaults. These are bounded smoke observations, not a
p95 comparison or a claim that transient/subframe flicker is fixed. HY4/PI4,
physical hardware and full release qualification remain outside this work.

## Memory and demo

Each slice changes reserved bank-zero bytes by **0 fixed, 0 per public Task,
and 0 private idle**, including guards, alignment and unused capacity. Fixed
upper reservations, Task pools and populated image banks are unchanged from
CAL4. The transform adds two live upper bytes; the private Panel model grows
by four bytes. Files gains 36 private upper bytes for its stack reduction.
Its rounded image backing grows by 40 bytes; Panel's shorter constants make its
rounded backing eight bytes smaller, for a net 32-byte initial-app heap increase.

The OF816 XEX is 976,395 bytes and leaves **55,796 bytes** of Atarimax capacity.
The default build still selects the five-second shell/prime demo. This executed
walkthrough selects the GEM desktop and retains the five-second OF816 countdown.

Distribute [`exec816-demo.zip`](../../build/panel-settings/final-distribution/exec816-demo.zip)
(SHA-256 `0dad135e9c8bc95e396b751f548df58112d56db66dbf679e0e95b044400cb93d`). Its 19 members contain only boot files, matching disks,
pinned ROM, the short guide, notices and checksums. Development inputs and test
output stay outside the archive. Settings survive app reload within this desktop
session; restarting the desktop restores the selected build default.
