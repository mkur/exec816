# Control Panel session settings

[Plans](../README.md) · [Existing design](gem-control-panel-design.md)

Turn the existing disk-loaded `PANEL.APP` into a useful mouse-settings panel.
Keep its compiled-in OBJECT tree, public GEM forms, explicit event loop and
selective redraw. The first setting is the existing Off/Mild acceleration
profile; no new curve, settings framework or persistent file is needed.

## CP1 — Session preference

Add `ExecAESMouseProfile(profile)` in the Exec816 extension header: Off or Mild
sets the session preference; Query reads it; failure returns -1. One ordinary
AES request executes in the presenter, which already owns the pointer transform.
The call is infrequent and uses the existing request/reply lifetime. No new
kernel operation, Task, signal, timer or shared pointer is needed.

A profile change preserves coordinates, clears fractional motion and takes
effect at an input-event boundary. If a button is held, retain the old profile
through its release, then apply the latest preference. Query returns the chosen
preference even during this deferral. Closing an application leaves the session
preference intact; a new desktop acquisition uses the build default. Caller
supplies a valid profile; do not repeat enum validation through the layers.
Update machine-readable ABI inputs and rebuild every C application.

Check emitted Off/Mild movement, fractional reset, held-button deferral, release,
loss and repeated choices. Retain the existing rational curve regression. Use
small raw/optimized probes for the new C/Action! request boundary; integration
runs are optimized.

## CP2 — Useful controls

Use radio buttons labelled Off/Mild, Defaults, Apply and Cancel. Defaults stages
Mild. Replace the disabled demonstration control with a Mouse label. Selection
only edits the private tree. Apply publishes the staged value; Cancel reloads
the current session preference. Closing discards pending edits. On reopen,
query the session preference instead of resetting it. Status distinguishes
pending edits from the active preference; no action counter appears in the UI.

Keep Tab/Shift-Tab, Space, Return, Escape, outside-release and lost-input
cancellation. Pushbuttons must return to their unselected state. Repaint only
changed controls, focus marks and status; repair exposed regions from the model.

## CP3 — Desktop evidence and demo

Exercise physical pointer and keyboard edits, Apply/Cancel/Defaults, held-button
cancellation, repeated updates, overlap/move/exposure and reopen persistence.
Compare independent pixels after settled updates, record frame-granular feedback
samples, and demonstrate counter progress and shell output. Verify cleanup,
stack guards and OS restoration. This does not close HY4/PI4 or claim that all
transient flicker is removed.

The first walkthrough exposed a three-byte stack-floor margin in Files during
mouse selection in its popup. Move its two MENU descriptors and six event output
words into the existing private application model (36 upper bytes), preserving
all existing field offsets and stack reservations; repeat the packaged check.

Run host checks and focused emitted tests. Build the OF816 desktop through
`tools/build_demo.py`, test the extracted ZIP and update its guide. Preserve the
five-second countdown and default shell/prime selection. Record current artifact,
memory and test scope in a development record. Reserved bank-zero delta for
each slice: **0 fixed, 0 per public Task, 0 private idle**, including guards,
alignment and spare capacity. No new pool or VRAM reservation is planned.

Status: CP1–CP3 implemented and development-tested. See the
[implementation record](../../history/control-panel-settings.md) and
[recorded checks](../../development/control-panel-settings.json).
