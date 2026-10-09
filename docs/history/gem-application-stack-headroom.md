# GEM application stack headroom

[Plan](../plans/gem4xe/application-stack-headroom-implementation-plan.md) ·
[Platform contract](../reference/platform.md#bank-zero-memory-budget) ·
[Evidence](../development/gem-application-stack-headroom.json)

## SH1 — attribution and sizing decision

ED3 recorded a minimum of 17 bytes above the checked application floor in the
Files walkthrough and 49 bytes in the calculator walkthrough. These are
cumulative watermarks of physical pools, including earlier Task occupants.
They do not identify the operation responsible for the minimum.

The passive observer in `tools/measure_gem_stacks.py` joins live Task descriptors
and incarnations to loaded Process identities. It samples selected resident
C/native instructions, post-frame-reservation instructions, interrupt entries
and context restoration separately. It never changes guest instructions or
refills live stacks. Host tests cover listing offsets/CRLF and physical-stack
attribution, including kernel and interrupt samples. Selected entry candidates
are hints requiring source/listing inspection, not an unwinder or a maximum
stack-depth proof. Fill scans can miss unwritten reserved frames.

An exploratory ED3 Files replay reached Path editing, exposure and both resize
sizes before being deliberately interrupted. Files occupied slot 5, Process 3,
image `$090000`; its cumulative margin fell from 131 bytes at desktop readiness
to 52 bytes after opening the Path dialog. Panel and counter occupied slots 3
and 4. The selected rendering chain is:

```
objc_edit → objc_draw → GemDrawingBorrow → draw → ExecAESDrawEdit
→ App_just_draw → App_gr_rect → App_bb_fill → App_WidgetFill
→ GemWidgetFill → vbxe_fill_rect → blit_fill → blit_mask
```

This identifies a deep editable-field drawing path; it does not attribute the
historical 17-byte result to that path. The interrupted replay is diagnostic
evidence only, not a passing complete walkthrough.

A discarded local-storage experiment reduced nested emitted frame reservations
as follows (Calypsi 5.18, optimized large-code/huge-data):

| Routine | Original frame | Experimental frame | Saving |
| --- | ---: | ---: | ---: |
| `App_just_draw` | 54 | 6 | 48 bytes |
| `ExecAESDrawEdit` | 52 | 12 | 40 bytes |
| `App_bb_fill` | 18 | 10 | 8 bytes |

These counts include saved registers and explicit local reservations, excluding
the caller's return address/arguments and deeper calls. The combined 96-byte
saving would leave only 113 bytes if applied to the 17-byte historical margin,
below the 128-byte target. The user explicitly accepts larger stacks and prefers
them to a major refactor. The selected change adds 256 bytes to each ordinary
pool, preserving the renderer and its existing ownership. No experiment code
is retained. SH1 adds **0 fixed, 0 per-public-Task and 0 idle bank-zero bytes**.

## SH2 — ordinary pools and boot arena

Ordinary slots 1–5 use 1,280
bytes; root, kernel, large worker and idle sizes remain unchanged. Guards and
the 256-byte interrupt reserve are retained. The boot arena moves above the
enlarged stacks and the loader reservation shrinks from 5 KiB to 3 KiB. Its
1,874-byte emitted payload leaves 1,198 bytes spare, enforced by packaging.

Compared with ED3, reserved bank-zero deltas are **0 fixed runtime, +256 bytes
for each of public slots 1–5, 0 for slots 0/6/7, and 0 private idle**. This
includes DP, guards, alignment and unused capacity. Eight-Task runtime grows
1,280 bytes to 57,408 including OS ranges; initialization grows to 59,456.
Loading falls by 1,792 bytes to 50,800: the bootstrap slot gains 256 while the
loader loses 2,048. Four-Task runtime remains 51,392; its loading reservation
falls 2,048 to 52,080. Post-startup eight-Task free space is `$6040–$7FFF`
(8,128 bytes), with the existing 176-byte gap before boot staging.

No application context, production upper-RAM/heap or VRAM allocation grows.
The resident C payload is byte-for-byte unchanged at 164,951 bytes. No compiler
pin, C ABI, interrupt protocol or driver policy changes. Rebuild the platform
image and loader together; do not mix the old and new memory maps.

Diagnostic capture now borrows space from the generated retired-manifest
address, with checks against live stacks and the helper itself. The OF816
caller-return probe also derives its address from the loader reservation.
The G5 rendezvous word moves out of `$6000` into fixture-owned upper RAM;
its obsolete hook replacements now fail explicitly if their source boundaries
move. Current fixture map checks use the platform profile; historical evidence
is preserved. Composed DOS/console fixtures require 4 KiB of upper global
storage (2 KiB more than their old default), independent of production stacks.

Development checks pass: 421 host tests with four historical skips; all 12
OF816 loading/return/payload/feedback cases; optimized larger-stack physical
I/O coexistence (6,798 checks), checked-floor rejection before guard damage,
and G5 rendering/peer/physical-SDFS overlap (260 checks). The latter checks
pixels, context/DP restoration, ownership, aperture and OS return. A focused
4,098-byte capture-buffer probe checks two chunks, CPU/borrowed-RAM restoration,
guards and OS return. The legacy full G4 runner expects the removed `commonKind`
symbol and is not counted as passing; its unrelated fixture drift is recorded
in the evidence. This is focused development coverage, not a full raw/optimized
qualification matrix.

The bounded Path edit/exposure/cancel replay passes on the enlarged build,
including exact pixels, shell EXIT, guards, ownership and OS return. Its smallest
ordinary-pool watermark is **309 bytes**, versus 52 in the corresponding baseline
interaction. Files selected-code and IRQ-entry margins are 339 and 333 bytes.
All ordinary pools exceed 128 bytes in both the fill and selected-S observations.
This is a scenario gate; full Files/calculator validation follows in SH3.

## SH3 — integrated desktop

The same final OF816 ZIP passes uninstrumented Files and calculator walkthroughs,
plus a 127-character Files edit field. The latter checks rejection of an extra
character, NUL preservation, exact pixels, Backspace, exposure, cancellation and
EXIT. Minimum ordinary-pool margins are **280 bytes for Files** (ED3: 17),
**329 for calculator** (ED3: 49), and **254 for the maximum-length edit**. All
exceed the 128-byte development target. Interrupt timing and Task reuse affect
watermarks, so the observed gains are not assumed to equal exactly 256 bytes.

| Physical pool | Files margin | Calculator margin | Maximum edit margin |
| --- | ---: | ---: | ---: |
| Root 0 | 700 | 685 | 710 |
| Ordinary 1 | 418 | 705 | 711 |
| Ordinary 2 | 825 | 825 | 825 |
| Ordinary 3 | 308 | 337 | 384 |
| Ordinary 4 | 382 | 339 | 382 |
| Ordinary 5 | 280 | 329 | 254 |
| Large 6 | 1533 | 1542 | 1548 |
| Large 7 | 1951 | 1747 | 2286 |
| Private idle | 121 | 121 | 127 |
| Kernel | 979 | 981 | 991 |

These are cumulative physical-pool fill watermarks, including previous occupants.
The reports also retain the completion snapshots taken before debugger helpers
reuse retired stacks. The 128-byte target applies to ordinary application pools;
the unchanged private idle stack remains outside it. Selected direct-S samples
and emitted-frame inspection supplement, rather than replace, these watermarks.

Files passes all three dialogs and their operational failures, resize/scroll
repair, native/GEM launch and Stop, close while editing with a child, relaunch,
idle collection, heap restoration and exit with a GUI child and popup. The disk
audit confirms the renamed `BBB` directory and consistent allocation. Calculator
passes window-capacity rejection cleanup, Files launch/Stop/reload, two independent
instances, resource isolation, shell/counter coexistence, heap return and exit.
All three runs retain intact guards, release ownership and return to the OS.
The initial panel/settings matrix is not repeated.

Long-field exposure revealed a host pixel-oracle error: Backspace keeps the
existing viewport while the caret remains visible; the old oracle recomputed
its start from the caret index. The oracle now reads the owning AES context's
retained scroll position and checks caret bounds. A host regression covers the
127 → 126 transition. Target rendering code remains unchanged. The maximum-edit
runner waits for application insertion after each key; it makes no burst-input
throughput claim. Failed/interrupted diagnostic attempts are explicitly excluded
in the evidence rather than relabelled as passing walkthroughs.

`build/gem-stack-headroom/final/exec816-demo.zip` was built through
`tools/build_demo.py --gem-desktop` from clean implementation commit `6cfe747`.
Its SHA-256 is
`0f4383116a12004e613e43c2ec2514be83e2fff93db4da8529b13c9b936507a9`.
It contains 19 distribution files with 18 verified payload checksums; all 127
recorded source inputs match. OF816, five-second autoboot, matching system/WORK
disks, pinned ROM, guide and licence notices are included; observers and build
intermediates stay outside the ZIP. The final resident C payload is still
byte-for-byte identical to ED3. The actionc pin and Calypsi inputs are unchanged.

Final host checks pass: **422 tests, four historical skips**. Runtime checks use
optimized emitted code; no compiler ABI or code-generation behavior changed,
so no new raw-mode matrix is required. SH3 adds **0 fixed, 0 per-public-Task and
0 private-idle reserved bank-zero bytes**, including guards, alignment and unused
capacity. These are development checks on the pinned emulator/ROM, not hardware
qualification or a new HY4/PI4 latency claim.
