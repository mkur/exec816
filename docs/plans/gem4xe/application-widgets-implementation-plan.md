# Application widget implementation

[Design](application-widgets-design.md) · [Plans](../README.md)

1. Add the public OBJECT/GRECT declarations and object/form calls. Bind the
   pinned extracted donor algorithms in a separate application namespace;
   retain the existing presenter binding. Add parameter-block dispatch.
2. Draw directly from application trees through the existing workstation grant,
   visible-region clipping and bounded per-object strips. Implement local
   geometry, button/radio state and keyboard navigation. No tree registration.
3. Exercise emitted object layouts and call results, hidden/nested hit testing,
   radio/default/disabled behavior, clipped pixels, UPDATE admission and clean
   retirement. Run host checks and affected generated-input checks. Record
   development scope and bank-zero delta, then commit this executable slice.

Next: a real Control Panel and then desktop facilities, each with its own design
and plan before implementation. Full hosted qualification and HY4/PI4 latency
closure are outside this implementation gate.

Implemented. [Development evidence](../../development/application-widgets.json):
27 assertions in each raw/optimized C run, 408 host tests (four historical skips).
Physical app/pixel integration is covered by the Control Panel follow-on.
Bank-zero delta: fixed 0, each public Task 0, private idle 0 bytes.
