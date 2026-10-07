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
