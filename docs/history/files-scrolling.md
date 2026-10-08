# Files scrolling implementation

[Design](../plans/gem4xe/files-scrolling-design.md) ·
[Plan](../plans/gem4xe/files-scrolling-implementation-plan.md)

FS1 replaces page-by-page enumeration with a 256-entry upper-heap snapshot.
Sixteen reusable objects adapt to the work area; arrows, page requests and the
thumb change the first visible entry. Keyboard selection follows into view.
Refresh retains the selected filename. Navigation, launching and child ownership
continue through the existing Files event loop. The obsolete Next button is now
Refresh. Listings above capacity explicitly report truncation.

Development checks: the standalone Files C image and the integrated desktop C
layout probes compile successfully; the optimized native desktop and OF816
package build. Physical integration is recorded by FS2 after its walkthrough.
The host suite passes apart from the separately in-progress C export-version
expectation for editable dialogs; no Files host regressions were reported.

The Browser model grows from 2,272 to 2,672 bytes. Its snapshot allocates 28,672
bytes (256 × 112) in upper heap and is freed on all ordinary finish paths.
Reserved bank-zero delta is **0 fixed, 0 per public Task, 0 private idle**,
including guards, alignment and unused capacity. No additional Task or VRAM
allocation is introduced. These development checks are not system qualification.
