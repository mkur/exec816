# Application-owned GEM objects

[Plans](../README.md) · [AES contract](../../reference/aes.md)

Expose the existing extracted GEM4XE object algorithms to ordinary GEM C
applications. Trees and strings belong to the caller; there is no registration,
copy, presenter model or new protocol for a tree. The supported objects are
G_BOX, G_IBOX, G_STRING, G_TITLE and G_BUTTON, with SELECTED/DISABLED states and
SELECTABLE, DEFAULT, EXIT, RBUTTON, LASTOB and HIDETREE flags. Trees have at most
32 objects, eight levels and 63 characters per label. Coordinates are pixels;
strings use huge pointers in the standard 24-byte OBJECT layout.

Provide objc_draw/find/offset/change, form_center/button/keybd as named calls
and AES parameter-block operations. Draw and change-with-redraw require the
caller's open workstation, window and BEG_UPDATE. Drawing intersects the caller
clip with the published visible work rectangles. Geometry and state operations
are local. Trust valid pointers, object links, indices and declared bounds; do
not repeat the native retained-widget admission validator.

Reuse the pinned extracted object, geometry and button code. Link a separately
named application instance of its small GSX scratch state. The presenter can
run during a caller's blocked display acquisition, so sharing its WidgetCurrent
or gl_clip would be unsafe. This is a second binding of the same source, not a
second widget implementation. Application scratch is touched only inside a
DISPLAY grant; one intersecting object/at most 16 scanlines is drawn per borrow.
No borrowed application pointer survives the synchronous call.

The first form subset is for windowed event loops. form_button commits an
already accepted release or keyboard action; unlike classic modal GEM it does
not wait for release, draw, or consume input. It reuses the extracted radio and
selection helper. EXIT buttons are momentary. form_keybd handles Tab/Shift-Tab,
Space and Return, reporting the target and unconsumed key; it does not wait or
paint. Applications keep press/cancel state and handle WM_REDRAW/MOVED/CLOSED
through evnt_multi. form_do, editable text, icons, user callbacks, indirect
specs and modal screen ownership remain unsupported. This explicit subset keeps
the full application event pipeline visible and avoids a new event framework.

No kernel, Task, signal, DP or stack reservation changes. All new code/state is
in the existing upper-bank C image. The panel follow-on will measure actual
stack use and exercise physical input and clipped redraw beside the shell.
