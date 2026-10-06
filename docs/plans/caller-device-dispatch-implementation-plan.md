# Caller device dispatch implementation plan

[Plans index](README.md) · [Device API](../reference/device-io.md)

Move established resident-device dispatch into the caller's I/O library. The
[current measurements](../development/trusted-device-io.json) charge about
0.65 ms to the routing gateway within a 1.045 ms quick DoIO. The request already
identifies its device; selecting a callback needs no kernel activation.

## One executable slice

1. Generate caller-side Close, BeginIO and AbortIO dispatch from the existing
   resident descriptions in `abi/io.json`, selecting by `io_Device`. Keep
   OpenDevice's admission gateway and generated route IDs for initial opens.
2. Make IOCORE prepare flags, error and message type once for every submission.
   BeginIO preserves flags, SendIO clears them, and DoIO sets IOF_QUICK. Only
   DoIO may inspect the request after submission, under its existing ownership
   and Forbid rules; copy its signed quick result before Permit. Pending DoIO
   continues through exact-request collection and ordinary Wait.
3. Remove established-device routing from Task policy and its assembly/import
   bindings. Keep the queued diagnostic device behind explicitly test-only
   submission, cancellation and close entries; it retains its existing kernel
   queue protocol. Remove redundant diagnostic SendIO/DoIO selectors. Production
   callbacks continue to use public kernel primitives for actual coordination.
4. Preserve the native Task/domain entry checks, checked compiler frames,
   Forbid/Permit, timer edit gate, completion publication and cancellation
   rules. CheckIO and WaitIO retain their kernel observations/transactions but
   no longer select a resident before performing them.
5. Update the timing observer for the remaining entry points, run the selected
   checks below, record costs and memory deltas, update current contracts and
   commit the completed slice.

The public Action!/C API and request layouts remain unchanged. Internal gateway
selectors and bindings change together; regenerate and rebuild affected images.
The existing static resident table remains the registration model. Timer polling,
priority policy, C wrappers and driver queue/lifecycle policy stay in scope for
separate measured work. Expected reserved bank-zero delta is zero, fixed and
per Task, including guards, alignment and unused capacity.

## Development checks and acceptance

- Host suite and generated-definition checks. Validate both production and
  diagnostic generation, including relocated upper storage.
- A small raw/optimized public-I/O probe for generated dispatch, flags, signed
  quick results and nested Forbid preservation. Optimized lifetime, immediate
  and queued reply handoff, publication-NMI and collect-before-Wait gap cases.
- Optimized timer binding, concurrent expiry/cancellation and C API checks.
  Targeted native context rejection checks cover the unchanged public stubs.
- Rebuild the loaded AES desktop and repeat the 100-frame idle, disk and scroll
  windows with I/O breakdown. Compare idle with the retained trusted-request
  baseline; require intact guards, restored ownership and loaded I/O progress.
  Confirm ordinary submission no longer enters a routing gateway.

Accept the slice when valid-use semantics pass, production routing is removed,
memory accounting is unchanged and measurements record the resulting cost.
Report mixed tails and sample/completion differences rather than claiming an
equal-work speedup. This slice does not close HY4's pointer/button/scanout gate
or qualify a release. Demo packaging is unchanged.

## Status

Implemented and development-tested. The
[execution record](../history/aes-hybrid.md#hy4-caller-device-dispatch) and
[evidence](../development/caller-device-dispatch.json) record the 420 assertions,
five native context cases and three timing workloads. Median DoIO/SendIO costs
fall to 0.394/1.115 ms; variable tails and the GUI latency gate remain open.
