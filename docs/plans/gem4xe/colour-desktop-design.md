# CG3: one desktop application, several windows

[Roadmap](../../roadmap.md#colour-gem-desktop-roadmap) · [Plan](colour-desktop-plan.md)

Keep one AES registration, receive port, workstation, menu and event loop per
application. Separate window state from the client registration: each window
owns its geometry, open epoch, pending GUI facts and published visible region.
The application allocates its window views in upper RAM. The presenter owns
the corresponding bounded window records. Closing one window retires that
window's queued notifications without withdrawing sibling windows or the port.
UPDATE ownership remains per application and publishes all its window snapshots.

This follows Intuition's useful separation of application event ports from
window lifetime: several windows can share a port, and closing one must dispose
of its outstanding events without deleting the shared port. We retain GEM WM_*
messages and evnt_multi at the application boundary. See the AmigaOS
[input/output documentation](https://wiki.amigaos.net/wiki/Intuition_Input_and_Output_Methods)
and [window communication](https://wiki.amigaos.net/wiki/Window_Communication).

The caller keeps a bounded array of window-view pointers and one current drawing
view. A query or mutation naming a handle selects that view; the normal
WF_WORKXYWH / WF_FIRSTXYWH redraw sequence therefore selects the right target.
VDI and objc_draw retain their existing single-view hot loop. UPDATE acquisition
refreshes every owned view, not just the last queried window. Form interaction
uses the selected view; applications keep their existing explicit redraw loops.

GUI records carry the corresponding window's open epoch; application-menu
notifications use the application input-session/menu epochs. Retiring one window does not
change the application's delivery port or invalidate sibling GUI records.
Captured input likewise identifies its originating window and open epoch.
Retirement discards only records for closed/reopened windows, preserving siblings.
The desktop can read the input's owning handle through a small caller-local Exec
binding extension, `ExecAESInputWindow(MU_KEYBD or MU_BUTTON)`; it need not infer a captured event's target from later focus.

Use fixed bounded arrays and direct handle lookup. Do not introduce a second
dispatcher, window Task, private kernel operation or generic object framework.
Rebuild the one current ABI and its callers. Keep application message capacity
independent of GUI delivery. Window epochs continue to distinguish stale GUI
messages from ordinary application messages with similar payloads. Input remains
on the existing application inbox and signal, with capture-time ownership.

Evolve Files' directory model into a persistent desktop application. Its directory
windows share resources, icons, menu policy and the event loop; each keeps its
own path, snapshot, selection and scroll position. A borderless bottom window
provides the desktop's ordinary clipped drawing/input surface. A small Exec AES
extension identifies that desktop window, pins it below ordinary windows and
excludes it from window cycling. The desktop menu remains available when its
background is active. Other GEM applications continue using ordinary window APIs.

Support six client windows plus the two existing menu layers. The desktop uses
one background and initially up to three directory windows. Additional windows
cost upper-memory records and region storage, not Tasks. Actual capacity failures
remain normal operation errors. The public eight-Task pool stays unchanged.
Launch supervision and persistent settings follow in CG4.

Development evidence must cover two windows in one Task beside another client:
draw and clip independently, close/reopen with delayed events, shared-port
survival, update snapshots, focus, background exposure and final retirement.
Count all reserved bank-zero changes, including zero, and measure stack margins.
