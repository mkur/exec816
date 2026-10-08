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

WG2 adds captured size/thumb outlines and release-triggered arrow/page requests
inside the existing gesture continuation. Inactive gadgets top first; Escape,
loss and geometry/retirement retain the existing cancellation protocol. There is
no held-button repeat or live client redraw during a drag. The application owns
acceptance and logical scrolling.

[WG2 evidence](../development/window-gadgets-wg2.json) records 241 passing emitted
checks, size acceptance, four arrow/page codes, slider endpoints and unchanged
client state before acknowledgment. An independent raster matches all 2,688
pixels in the resized gadget strip; cancelled size outlines restore exact pixels.
The smallest active public-Task margin in this fixture is 589 bytes; the presenter
retains 1,604 bytes above its floor. Guards and ownership retirement pass.
Seven upper global bytes store additional gesture state; fixed, per-public-Task
and private-idle bank-zero deltas are all zero. No VRAM allocation changes.
