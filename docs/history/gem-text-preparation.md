# Text preparation audit and sequential string conversion

[GEM plans](../plans/gem4xe/README.md) ·
[Inputs and measurements](../development/gem-text-preparation.json) ·
[Previous copy slice](gem-copy-grant.md) ·
[Current VDI contract](../reference/gem-vdi.md)

The requested text audit separates input conversion, clipping, damage reporting,
glyph preparation and command encoding/upload. The largest preparation cost is
byte-string conversion: **2.72 ms CPU** for the observed 80-word chunk. A
MagiC-style sequential pointer walk reduces it to **1.28–1.29 ms**. The complete
`v_gtext` call improves by **0.43/0.82 ms** down/up in the matched samples;
observed key-to-complete latency remains around **120/140 ms**.

## Passive audit

`tools/measure_mgview.py --text-detail` runs the unchanged cached APP/provider
with extra PC observations and no target instrumentation or build. The initial
capture reproduces the previous copy slice's timing and viewport hashes exactly.
The exposed file rows are 108 expanded characters; the library converts one
80-word chunk before screen-right exclusion. Its visible region is 77 cells.
MGVIEW's own tab expansion remains application work outside `v_gtext`.

The observer resolves local `text`, `paint` and driver `text_run` functions by
matching their emitted listing bytes against executable image segments, with
relocations as wildcards. A same-named global data symbol is not a reliable
function address. Unique-match checks and host fixtures cover this distinction.
Source PCs bracket chunk conversion and damage preparation. The innermost
routine/interval owns each CPU interval; off-Task and interrupt time are separate.
The exclusive charges reconcile to each complete `v_gtext` span.

| Baseline text work, disjoint Task CPU | Down | Up |
| --- | ---: | ---: |
| Entry/context lookup | 0.763 ms | 0.763 ms |
| Text setup/loop | 0.109 ms | 0.114 ms |
| Input conversion, including chunk setup | **2.721 ms** | **2.720 ms** |
| Visibility/user clipping | 0.263 ms | 0.263 ms |
| Drawing admission/wrappers | 0.430 ms | 0.429 ms |
| Visible glyph preparation | 1.220 ms | 1.221 ms |
| Glyph adapter/driver setup/queue | 0.297 ms | 0.304 ms |
| Text command encoding/upload | 2.288 ms | 2.280 ms |
| Fences | 0.922 ms | 0.884 ms |
| Damage preparation/reporting | 0.172 ms | 0.172 ms |
| **Whole `v_gtext`** | **9.184 ms** | **9.150 ms** |

Clipping and damage reporting do not account for the dominant preparation cost.
The word-to-byte visible-glyph packing and text command encoder are separate
measured costs; this slice changes only the first byte-to-word conversion.

## MagiC/GEM4XE comparison and implementation

MagiC pin `28cfdd29aa16fef692cc287bad3046b44ddcce3d` supplies two relevant paths:

- `AESOBJ.S:874–904`, `str_to_ints`: load a byte through the source pointer,
  stop on NUL and store a word through the advancing output pointer. Its other
  bookkeeping supports MagiC's text state and is not introduced here.
- `TEXT_BMP.S:292–310`, `text`: consume the already word-form `intin` with
  workstation state, then handle font metrics/clipping and rendering. Input
  representation is established before its glyph traversal.

GEM4XE pin `e413c39d2f8e1bec8fe16596f610b923de4a0ae9`,
`src/vdi/vdi.c:405` `vdi_v_gtext`, consumes a known word buffer, computes alignment
and selects the visible complete-cell run. The current Exec renderer already
uses that run structure. No new ownership or rendering boundary is needed.

Exec's previous chunk loop tested byte/word representation per character,
read each nonzero source byte twice and rebuilt `w->intin[count]` addresses.
Emitted code includes repeated workstation-field/index address helpers. The
changed loop selects representation once per chunk, establishes `WORD *out`
once, reads each source byte into a native-width value and advances both pointers.
It leaves NUL at the source cursor so the next empty iteration cannot resume
after the terminator. The emitted byte-copy loop uses direct pointer increments.

The 80-word workstation buffer, word-input GEM/ATASCII grouping, string alignment,
clipping, damage reporting, physical grants and normal Task preemption retain
their existing semantics. MGVIEW source and APP bytes are unchanged. No new
platform service, ABI, buffer, Task or synchronization mechanism is added.

## Result and focused development checks

| Matched scroll work | Down before → after | Up before → after |
| --- | ---: | ---: |
| Input-conversion interval CPU | 2.721 → **1.288 ms** | 2.720 → **1.280 ms** |
| Whole `v_gtext` CPU | 9.184 → **8.758 ms** | 9.150 → **8.331 ms** |
| Exposed-row drawing CPU | 18.905 → **18.483 ms** | 18.994 → **18.213 ms** |
| Whole `set_shift` CPU | 83.500 → **82.761 ms** | 82.503 → **81.326 ms** |
| Whole `set_shift` elapsed | 116.953 → **115.862 ms** | 113.155 → **111.711 ms** |
| Complete viewport observed | 120.031 → **120.535 ms** | 140.308 → **140.270 ms** |

Inclusive rows overlap. The conversion interval saves about 1.44 ms CPU, but
other intervals vary: drawing admission/wrappers rise from 0.430 to 1.433 ms
on down, and entry/context work rises from 0.763 to 1.377 ms on up. These are
observed interval changes, not proof of a particular waiting mechanism. The
net text-call saving is smaller than the conversion saving. No end-to-end
latency improvement is established by these two PAL/COP observations.

The optimized emitted text probe passes **274 assertions**, checking all six
vertical alignments, whole-string horizontal alignment, high byte values,
79/80/81-character boundaries, a nonzero byte after NUL, second-chunk source
position and mixed GEM/ATASCII word runs. It captures glyph contents while each
physical callback runs, rather than retaining a pointer to a later overwritten
chunk. Existing clipping, error publication and workstation isolation checks
remain covered. Fixture initialization now supplies the real glyph-array binding;
an unused retained lifecycle helper has a tripwire binding.

The host suite passes **726 tests, four skipped**, including two local-function
PC resolution/source-boundary checks. Production DMA executes in the loaded
MGVIEW pair. Both viewport hashes and all **140,526 final full-window pixels**
match the baseline. Each scroll retains one viewport copy, one row draw, one
text grant and the same total six physical admissions and eight raw submissions.
Three Process lifetimes, heap/ownership restoration and stack/domain guards pass.

Only the VDI object was recompiled; 56 unchanged provider objects, generated
tables and the MGVIEW APP were reused. The provider was relinked and native
loader rebuilt. No Counter, QED, catalog, demo or release matrix ran.
MGVIEW's measured stack peak is 1,306 bytes in its existing 2,560-byte pool,
leaving 998 above the ordinary floor. Generated bank-zero budget, runtime
reservations and every Task pool match the prior build: **0 added fixed, root,
kernel, idle and per-public-Task reserved bytes**, including guards, alignment
and unused capacity. These are development results.
