# Native drag and queued UPDATE

[Implementation plan](../plans/gem4xe/native-drag-update-plan.md) ·
[AES contract](../reference/aes.md) · [Desktop contract](../reference/desktop.md)

## Cause and change

Counter requests UPDATE before its periodic repaint. While a native title
gesture holds the physical button, acquisition correctly waits for release.
The queued request also made `MouseBlocked()` defer native input and made
`Suspend()` erase the outline. This froze tracking before any client repaint.
Files alone worked, but Files could be affected when Counter ran behind it.

`DESKDRAG.Continuing()` distinguishes an existing native capture from new
interactions. Held move, close, size, slider and arrow phases may continue
input and outline presentation while an ungranted request waits. Escape can
cancel immediately. Active mouse ownership, including UPDATE's implicit
ownership, still excludes this path. Application file-drag visuals retain
their existing policy.

`DESKINPUT` applies this exception to input/replay and presentation. Focus,
widgets, menus, new gestures and released-button geometry/action completion
retain the normal queue gates. UPDATE eligibility, eligible-waiter ordering,
display/DMA arbitration and the public ABI are unchanged. Clean stationary
captures do not become runnable merely because a request is pending.

## Development checks, 2026-10-16

The new `tools/test_native_drag_update.py` drives physical mouse and keyboard
events against the extracted OF816 package. It neither patches guest state nor
injects a timer. The original optimized `cbc0a16b` package fails the regression:
Counter has phase 1, a held button, pending BEGIN code 513 and zero acquired
window updates, but both outline flags are zero. Its relevant input, drag,
lock, console and Counter sources matched the starting tree.

The fixed optimized package passes:

- Files alone holds a visible outline for 130 PAL frames and follows motion.
- Counter's natural timer queues BEGIN without painting; the held outline
  stays visible and moves from `[64,32,208,80]` to `[80,32,224,80]`.
- A stationary held capture reaches the presenter's WAIT state.
- Release commits the final geometry, clears both outline flags and resumes
  repainting: Counter paints advance from 3 to 6 in the observed interval.
- Escape cancels a second captured drag while BEGIN is pending and the button
  remains held. Geometry is unchanged, the border is restored, and repainting
  resumes after release.
- Files keeps tracking when Counter's request queues from another application.
  Release commits Files geometry and resumes Counter painting.
- Counter closes through its gadget; Shell EXIT returns normally with intact
  guards, zero live Tasks and no required reset.

Eight independent scanout checks compare all four outline edges with the
pre-press scene using the XOR-15 contract, excluding old/current pointer
footprints. They cover **380 pixels per Counter border** and **1,312 per Files
border**, including erased borders after cancellation.

The optimized AES lock fixture passes **181 C checks and 4 native checks**,
covering UPDATE/MCTRL ownership, recursion, queued handoff and local/RPC paths;
normal return, guards and zero-live-Task cleanup also pass. The host suite runs
498 tests: **496 pass, 2 fail**. Both failures reproduce in an untouched HEAD
export with the same pinned compiler: the C-package fixture expects ABI 19
instead of 20, and the provider-manifest fixture expects 1,807 bytes instead
of 1,844. They are unrelated to this change. Desktop/AES generated-definition,
Python syntax, documentation-link and whitespace checks pass.

These are development checks on pinned AltirraOS 3.44 for 65C816
(`85a6e927…`), the pinned mouse-capable Altirra bridge, PAL, 65816 ×8,
63 linear banks and VBXE FX 1.26 at `$D600`. Compiler revision is
`05c01f39ff3beef97af0e65b0a16666f5a1bd805`. No raw ABI matrix, full release
matrix or real-hardware qualification ran.

## Memory and package

Reserved bank-zero growth is **0 fixed, 0 per public Task, 0 idle bytes**,
including guards, alignment and unused capacity. Both packages reserve 10,528
fixed runtime bytes, public Task slots of
`[1824,1600,1600,1600,1600,1600,2848,2848]`, and 800 idle bytes: 26,848 bytes
excluding the OS. Runtime reservations, Task pools and the 7,424-byte image-data
arena are identical. No persistent state, Task, signal, timer, kernel service
or VRAM surface is added.

Emitted `DESKDRAG` code grows **14,555 → 15,049 bytes** (+494) and `DESKINPUT`
grows **9,045 → 9,271 bytes** (+226): **720 code bytes** in total. The unchanged
module sources and compiler make this a comparison of the affected modules;
the older full package predates unrelated DOS changes.

The refreshed demo is `build/native-drag-update/demo/exec816-demo.zip`, built
with `tools/build_demo.py --gem-desktop --release-compiler`. OF816 autoboot
remains **249 PAL frames**, all 22 archive checksum entries verify, and the
OF816 XEX fits the cartridge payload with 467,057 bytes of headroom.

Physical observations, pixel checks, screenshots and the complete result are
in that directory (`native-drag-update-results.json`). The lock fixture and
memory comparison are under `build/native-drag-update/locks` and
`build/native-drag-update/memory-comparison.json`. Baseline investigation
evidence remains under `build/counter-drag-investigation`; its existing
`observations.json` records the frozen target after timer expiry.

To rerun the focused checks:

```sh
python3 tools/test_native_drag_update.py --bundle build/native-drag-update/demo
python3 tools/test_aes_server.py --suite locks --mode opt --output build/native-drag-update/locks
```
