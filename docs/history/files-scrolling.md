# Files scrolling implementation

[Design](../plans/gem4xe/files-scrolling-design.md) ·
[Plan](../plans/gem4xe/files-scrolling-implementation-plan.md)

FS1 replaces page-by-page enumeration with a 256-entry upper-heap snapshot.
Sixteen reusable objects adapt to the work area; arrows, page requests and the
thumb change the first visible entry. Keyboard selection follows into view.
Refresh retains the selected filename. Navigation, launching and child ownership
continue through the existing Files event loop. The obsolete Next button is now
Refresh. Listings above capacity explicitly report truncation.

Development checks: the standalone Files C image, integrated C layout probes,
optimized native desktop and OF816 package build. The complete Files-focused
walkthrough passes; [FS2 evidence](../development/files-scrolling-fs2.json)
records the exact ZIP and machine. Physical resizing produces 8 → 4 → 8 rows,
retains selection, and matches the independent scene raster. Arrow scrolling,
refresh, native HELLO/TICK, GEM child input/Stop, popup cancellation, close with
a child, idle collection, heap restoration, OS restoration and guards pass.
The observer now waits for a complete directory snapshot instead of assuming
the old eight-entry page's enumeration time. Host checks pass (419, four
historical skips, including the subsequent manifest-capacity regression).

The Browser model grows from 2,272 to 2,672 bytes. Its snapshot allocates 28,672
bytes (256 × 112) in upper heap and is freed on all ordinary finish paths.
Reserved bank-zero delta is **0 fixed, 0 per public Task, 0 private idle**,
including guards, alignment and unused capacity. No additional Task or VRAM
allocation is introduced. These development checks are not system qualification.

FS2 reserves **0 additional fixed, per-public-Task or private-idle bank-zero
bytes**. The minimum observed public-Task margin is 58 bytes above its checked
floor; presenter margin is 1,543 bytes. This is a functional development check,
not a new latency or release-qualification claim.
