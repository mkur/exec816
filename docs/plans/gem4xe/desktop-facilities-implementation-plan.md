# Desktop facilities implementation

[Design](desktop-facilities-design.md) · [Plans](../README.md)

1. Extend the existing C DOS bridge with file, directory and cleanup calls;
   add thin native program start/collect/break/wait bindings. Exercise emitted
   argument/result layouts and disk ownership, without adding kernel services.
2. Add transactional resource load/free/tree lookup/fixup and window-scoped
   popup menu interaction. Record exact supported RSC/AES contracts. Exercise
   a real resource, malformed/truncated rejection, failed replacement and exit
   cleanup through emitted code.
3. Add the browser's RSC source generator and application, eight-row paging,
   directory navigation, launcher result/Stop and lifecycle. Compose it with
   the existing panel/counter/shell and include the resource in the system disk.
4. Test physical navigation, popup mouse/keyboard, successful/failed launch,
   cancellation, resource redraw and clean shutdown. Build with build_demo.py,
   include OF816, cold-boot the exact package and run a shell command. Run host,
   generated-definition and documentation checks; record development scope,
   stack and zero bank-zero delta; commit executable slices.

No broad performance claim, new scheduler policy, or full GEM/RSC/VDI coverage.


Implemented; [development evidence](../../development/gem-desktop-facilities.json).
The C resource/DOS probe passed 34 assertions in raw and optimized C, with an
additional optimized MyDOS case. Raw emitted C record probes passed 88 checks;
the existing event-wait regression passed 371 assertions. Host: 408 tests,
four historical skips. Generated definitions and changed documentation links pass.

The exact OF816 package passed independent startup/browser/shell pixels, physical
popup keyboard/mouse, real directory navigation, HELLO launch, TICK cancellation
with eight live Tasks, invalid executable rejection, and closing Files during a
popup with another live TICK child. The close message survives, the child is
cancelled/collected, and the shell then executes HELLO and CAT/WC before clean EXIT.
The normal five-second countdown, guards, ownership and OS restoration pass.
TICK is packaged only in the GEM desktop; PRIMES retains its existing restriction
to tiled-console mode. Default shell/prime packaging is unchanged.

Read integration exposed an existing buffer-domain mismatch: DOS admitted native
stack buffers but MyDOS/SDFS Read checked upper-only serial buffers. Their read
paths now use the existing caller-buffer mapping check; serial scratch stays
upper-only. Both disk formats are exercised by the focused resource test.

No fixed, per-public-Task or private-idle bank-zero reservation changed (0 bytes,
including guards, alignment and unused reserved capacity). New models/resources
live in upper RAM. The resource pointer/deferred message adds 21 bytes per C AES
context. Recorded pool high-water marks stay above checked floors; the minimum
public-Task headroom in this session is 189 bytes. This is development coverage,
not a full qualification or a latency-gate claim.
