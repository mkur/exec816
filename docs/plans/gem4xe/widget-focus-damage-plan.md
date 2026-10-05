# Separate widget focus damage

[Plan index](../README.md) · [Widget contract](../../reference/widgets.md) ·
[Previous measurements](../../history/aes-widgets.md#button-feedback-follow-up)

Status: implemented at the development tier. See the
[execution record](../../history/aes-widgets.md#separate-focus-damage-follow-up)
and [machine-readable evidence](../../development/aes-widgets-focus-damage.json).
Scope: Control Panel input and retained widget damage; retain the completed-strip
renderer and existing Layers policy.

Before this change, the widget bridge reduced every change to one bounding rectangle.
Moving focus between distant buttons therefore paints the space between them.
Layers already retains up to eight separate rectangles and only merges exact
rectangular unions, so the lost precision belongs at the widget boundary.

1. Extend the generated private Action!/C widget packet with eight copied
   rectangles and a count. Drawing keeps its existing clip fields. Discard
   contained duplicates; on overflow conservatively damage the full client.
   Rejected/no-op updates return no rectangles. SET_TREE returns the client.
2. Damage only the one-pixel focus underline for old/new keyboard focus. Press,
   cancellation, state and label changes retain their complete visual bounds,
   including outward button borders. Queue the pressed control before repairing
   the previous focus. Preserve tree order when reconstructing each rectangle.
3. Pass each rectangle independently to Layers and invalidate the snapshot once
   per visual transaction. Retain copied state, revision checks, input capture,
   scene-token ownership and the four-object/sixteen-row paint limits.
4. Validate generated layouts and bidirectional Action!/C rectangle access with
   focused raw and optimized emitted probes. Cover focus movement, containment,
   disjoint radios, overflow, hidden/overlapping objects, failed updates and
   complete scene restoration. Run optimized panel/presentation tests and the
   host suite. Compare the same five idle actions with the frozen previous
   build, measuring capture-to-visible button time, intermediate blank pixels,
   paint turns and CPU cost. Timing targets remain unchanged.
5. Record the result, update the contract, and rebuild/package through
   `tools/build_demo.py` with OF816. Check the extracted desktop's controls,
   dragging, disk commands, BREAK and EXIT. Preserve the standard five-second
   shell/prime boot at the archive root.

Acceptance: full-scene pixels and semantics remain correct, disjoint focus
changes do not invalidate their intervening area, no damage is dropped on
capacity overflow, and the measured distant-button press latency improves
without reintroducing the observed erase/redraw flicker. Report any common
button latency regression explicitly rather than averaging it away.

Budget: the shared upper-RAM packet grows by 66 bytes (a count plus eight
eight-byte rectangles), within the existing C data reservation. No per-window
context, public payload, Task, VRAM or bank-zero reservation grows. Account for
fixed/root/kernel, each public Task and idle, including guards, alignment and
unused reserved capacity. Rebuild the internal callers together; keep one ABI.

Result: the five-press idle median falls from 319.49 to 119.17 ms; maximum falls
from 339.70 to 159.08 ms. Final button pixels match and the ten-edge observer
finds no invalid-colour frames. Release/status updates do not improve uniformly;
the execution record preserves the regressions and observation limits. Raw/opt
bridge checks, optimized panel/presentation checks, host checks and the extracted
OF816 demo walkthrough pass. Reserved bank-zero growth is zero in every category.
