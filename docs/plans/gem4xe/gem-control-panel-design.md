# GEM Control Panel

[Plans](../README.md) · [Application objects](application-widgets-design.md)

Replace the demo's native panel path with an ordinary resident GEM application
using its own compiled-in OBJECT tree. Run it beside the existing GEM counter
and shell. Its body uses gem.h: registration, workstation/window lifetime,
evnt_multi, object/form calls, UPDATE and WM_* handling. The small resident
wrapper supplies Exec Tasks and cooperative shutdown, as for the counter.

The panel contains a toggle, disabled control, two exclusive radio buttons,
Apply and Cancel. Tab/Shift-Tab move focus; Space activates focus; Return
activates Apply; Escape cancels an armed press. A press temporarily changes
SELECTED; a release inside commits through form_button, an outside release
restores the old state. Lost input restores state and waits for a released
baseline. Redraw and move messages remain serviceable throughout a gesture.

Paint only changed objects, both radio peers when necessary, the old/new focus
marks and the status string. WM_REDRAW reconstructs the damaged tree area.
The status reports committed actions; the adjacent counter proves independent
progress. Apply changes the status and Cancel resets the sample settings;
neither exits the application. The window closer ends it.

Do not introduce a general widget controller, damage manager, or copied server
state. Keep the panel's small event loop explicit so input-to-paint behavior is
easy to inspect. This is a functional desktop milestone, not a latency-gate
closure. Existing direct-screen rendering may still flicker; record it honestly.

Use existing Task reservations: bank-zero fixed/per-public-Task/private-idle
reservation delta is zero. Package through build_demo.py with OF816 and retain
the default five-second shell/prime demo when no GUI profile is selected.
