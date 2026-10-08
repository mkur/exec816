# Window gadgets implementation

[Current AES contract](../reference/aes.md) ·
[Design](../plans/gem4xe/window-gadgets-design.md) ·
[Plan](../plans/gem4xe/window-gadgets-implementation-plan.md)

WG1 adds kind-aware work rectangles, application-accepted bounds changes,
vertical slider fields and frame composition. Fixed windows retain their old
geometry. Layers damages both old and new bounds and rebuilds visibility.
Slider geometry is cached at geometry/slider mutation, not during frame painting.

Development evidence: [WG1](../development/window-gadgets-wg1.json). The optimized
window fixture passes 215 checks, including existing physical top/move/close,
size/work conversion, grow/shrink, slider values and visible iterator invalidation.
Raw/optimized context probes each pass 1,049 checks in both independent C
contexts, cross-bank records and native bridge register/DP restoration. Host
checks: 417 tests, four existing historical skips. These checks do not establish
whole-system or physical-hardware qualification. New gadget gestures follow WG2.

Reserved bank-zero delta: **0 fixed, 0 per public Task, 0 private idle**, including
alignment, guards and unused capacity. Desktop window storage grows 6 bytes per
slot (24 total), to a 14,210-byte service. Each allocated WindowView adds 4 bytes;
pending GUI facts add 28 bytes per registered client including alignment.
No new VRAM allocation or Task is introduced. Stack/ownership results and exact
machine pins are retained in the evidence. The integrated package follows Files
and dialogs, using the existing OF816 distribution workflow.
