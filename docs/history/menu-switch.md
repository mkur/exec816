# Reusing unchanged menu backgrounds

[Plan](../plans/gem4xe/menu-switch-plan.md) ·
[Cache design](../plans/gem4xe/aes-layers-vram-design.md) ·
[Machine-readable evidence](../development/menu-switch.json)

This fixes the idle Files case: switching menu headings no longer wakes Files
to reconstruct an unchanged background. It does not change directory enumeration,
sorting, Files refresh, kernel scheduling or display-driver policy.

## Implementation

`ExecAESBeginUpdate(window)` scopes the shipped desktop's existing UPDATE lock
to the window actually being painted. Untouched sibling windows keep their
cache eligibility. Ordinary GEM UPDATE stays conservative, including empty
updates; nested calls retain the outer scope. AES wire version 16 and C-program
import ABI 17 require rebuilding the host and applications together.

A menu interaction captures the union of its admitted popup bounds once in the
existing menu-under buffer. The popup layer keeps its identity across size
changes. Switching restores the old popup's rectangle from the saved union,
then draws or restores the next popup. A successful intermediate restore does
not create an application repaint obligation. The presenter accumulates that
exposure and delivers it after final dismissal and menu-bar repair.

Layers API version 11 adds the `keep` argument to `FinishSave`. The existing
`Scene.copyTarget` records the actual restore rectangle. A stale or failed
transfer cannot publish valid pixels or clear manager damage; transfer pins
remain held until completion or established quiescence. Ordinary fallback is
still used when the source is incomplete or has changed.

## Memory

The AES service grows from 1,812 to 1,814 bytes; both requests round to 1,816
heap bytes. Menu metadata adds exactly 10 fixed upper-RAM bytes: two one-byte
flags and an eight-byte rectangle, naturally aligned. The extra C import adds
three static table bytes; including alignment, the complete fixed upper-data
span grows by 14 bytes. No caller or Scene record
grows. VRAM remains 375,296 bytes, including the existing 76,800-byte menu-under
slot. There are no new queues, Tasks, signals, stacks or direct pages.

Every slice has reserved bank-zero delta **0 fixed / 0 per public Task / 0 idle
bytes**, including guards, alignment and unused reserved capacity.

## Development checks

- Host suite: 459 tests, four existing skips.
- Scoped AES cache fixture: 96 checks, including delayed grant behind MCTRL,
  nesting, empty hidden sibling updates and empty target invalidation.
- Raw/optimized C/native context and layout checks.
- Optimized Layers: 60,174 checks, including retained subrectangle restores,
  different popup sizes, out-of-bounds fallback, failed restore, in-flight
  invalidation and deferred external repaint.
- Raw/optimized far-record and call-boundary probes: 124 checks each.
- AES menu pixel/input/mutation/owner-exit regression.
- Native cache oracle: twelve scenes, 53 checks, including composite menu save
  and restore across multiple underlying layers.
- Snapshot transfer oracle: 109 checks, including failure, stale revisions and
  simulated unquiesced pin retention through the production transfer path.
- Exact OF816 ZIP walkthrough: Files, Counter progress, Panel pointer/keyboard,
  Text scrolling and document hash, Open selector cancellation, window closing,
  HELLO and clean EXIT with guards/ownership checked.

One existing lock fixture remains unresolved: it times out at 118 checks with
zero assertion failures, three ready peers and no completed peers in its second
round. A control restoring the pre-change C UPDATE implementation and native
lock/window-state/service sources reproduces the same result with the same pin.
It is not counted as a pass. The new queued scoped-update fixture passes.

These are development checks, not release or real-hardware qualification.

## Timing and remaining limits

All primary cohorts contain 20 samples. Times are median / p95 in milliseconds.

| Warm interaction | AV6 | This change |
| --- | ---: | ---: |
| File open | 160.4 / 160.7 | 200.6 / 200.6 |
| File highlight | 80.3 / 80.3 | 100.3 / 100.3 |
| File → View | 702.0 / 702.0 | 220.5 / 220.8 |
| View dismissal: restored pixels | 421.1 / 421.4 | 160.4 / 160.7 |
| View dismissal: final app repaint | 421.1 / 421.4 | 601.7 / 601.7 |
| Windows open | 140.5 / 140.5 | 180.6 / 180.6 |
| Windows dismissal: restored pixels | 521.4 / 521.6 | 140.5 / 140.5 |
| Windows dismissal: final app repaint | 541.4 / 541.6 | 380.9 / 381.2 |

The 300 ms warm keyboard switch gate passes: p95 improves by about 69%. Each
switch restores 12,960 background bytes and then the 5,904-byte View popup.
One 22,680-byte background capture serves the interaction. Files records zero
repaints during opening, highlight and heading replacement, and one on dismissal.

Cold popup control: File open is 441.3 / 441.3 ms (previously 401.1 / 401.1);
File→View is 341.0 / 341.0 ms (previously 822.3 / 822.3). Native cold open is
220.8 / 240.7 ms (previously 180.6 / 200.6). Background reuse remains enabled.

The cost has not vanished: capturing the union adds roughly 40 ms to opening;
application highlighting is one PAL frame slower. Deferring accumulated exposure
makes the final application repaint roughly 180 ms later, although the visible
background returns much sooner. Native final repaint improves. The 100 ms valid
dismissal gate remains open for both application and native menus.

Both repeated-input cases pass 20 background restores with no recapture or Files
repaint. Keyboard cycling through three headings gives 341.0 / 401.2 ms because
the two rendered-popup slots miss on all 20 transitions. Physical File/View
alternation gives 421.1 / 561.6 ms, including mouse travel and processing;
19 of 20 rendered popups hit. This is not a matched physical-baseline comparison
and must not be presented as the 221 ms keyboard result. Final dismissal still
delivers application repaint. Counter ticks and visible digits continue changing
during 30 highlights in each application/native menu.

Baseline is the frozen AV6 package and PAL emulator/ROM configuration; the
compiler pin is unchanged.
Whole-region scanout comparisons are sampled once per PAL frame, so values have
approximately 20 ms resolution. Existing transfer and Files paint counters are
read outside timed intervals; there is no new executable observer.

The repeated keyboard test cycles File/View/Desk because the pinned bridge does
not expose the left-arrow key. The pointer test alternates File/View. Their
comparison region starts below the cursor tail; the existing emitted menu oracle
checks the title bar and complete popup pixels separately. The primary warm/cold
cohorts compare the complete original menu region with the pointer parked away.

## Artifact

Production source matches `9e02ece`; the ZIP was built while those changes were
still uncommitted, so its startup stamp is `765fa8f-dirty`. Subsequent changes are
test and documentation only. Compiler pin:
`05c01f39ff3beef97af0e65b0a16666f5a1bd805`; the local pinned checkout is clean and
uses its release executable. The pin includes the previously documented actionc
address-promotion fix, still unpublished. No compiler override was introduced.

The demo contains OF816, pinned AltirraOS ROM, matching system/work media,
licenses and checksums, with the five-second autoboot retained. The launch
command is:

```sh
/Users/michalkurcewicz/action/exec816-public/build/menu-switch/demo/launch-altirra.command
```

ZIP: `build/menu-switch/demo/exec816-demo.zip`; SHA-256
`021b08a268bba760a3d82c6013d52840f6a227190c5beced08affbdf87d2219b`. Exact source, artifact hashes,
configuration, raw samples and check outputs are recorded in the evidence JSON.
