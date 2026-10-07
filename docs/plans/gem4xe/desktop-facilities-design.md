# Small GEM desktop facilities

[Plans](../README.md) · [Control Panel](gem-control-panel-design.md)

Add one small file browser beside the panel, counter and shell. Stay inside the
existing four-layer/four-application limits: the resident controller plus three
GEM applications use four registrations. Closing any window releases its own
resources. Use application-owned trees and the established event/drawing path.

## Menus and resources

Start menu support with window-scoped `menu_popup`, `menu_ienable`,
`menu_tnormal` and `menu_text`. A popup uses the caller's tree and work area;
click-release, Up/Down, Return and Escape select/cancel. It holds UPDATE only
while drawing. WM_REDRAW reconstructs the popup; other window messages are
saved in one caller-local deferred-message slot before the popup cancels.
The next message wait consumes that slot before the port queue. The caller
repaints its content on return. A screen-wide active-application menu bar,
accessories and cascading menus are later work, not emulated with global state.

`rsrc_load/free/gaddr/obfix` support classic big-endian, version-zero RSC files
containing the admitted object types and strings. Convert objects, tree offsets
and character-cell geometry once on load. One resource belongs to each AES
context; explicit free and appl_exit release it. Loading is transactional:
failed replacement leaves the old resource intact. Check file length, table
ranges, supported types and referenced string/tree extents at load time. Trust
valid tree structure at draw time. No icons, TEDINFO, user callbacks, resource
extensions or binary GEM application compatibility are advertised.

## Browser and launching

The browser loads its UI from `SYS:DESKTOP.RSC`, lists eight directory entries
per page, and offers Up, Next, Open, Refresh and a File popup. Directory entry
names and types come from DOS Examine/ExNext, not a packaged catalog. Keep an
absolute bounded path per application; no global current-directory changes.
Open enters a directory or launches a native Exec disk command with an empty
argument tail. A Stop action requests cancellation of that child. The browser
continues processing events and polls collection on its normal timer until
retirement; closing cancels and collects before freeing its Task. A small disk-loaded
TICK companion prints periodically and waits through COMMAND.Delay, providing a
Stop example that works with all four desktop layers occupied. PRIMES uses the
separate tiled-console mode and cannot open its pane in desktop mode.

Use the existing Program/Process loader and lifecycle. Add thin ordinary C DOS
and program bindings over the existing Action!/C bridge, preserving per-Task
DOS ownership. A launched command gets NIL input and RAW output to the shell,
without borrowing keyboard focus. Expose result/error in the browser. Loading
G4A or dynamically linked GEM binaries is a separate executable-ABI milestone;
this launcher handles current Exec commands. No new service Task or RPC queue.

Current VDI rectangles and fixed-font text, plus object rendering, are sufficient
for these applications. Add no unused VDI operations. File browsing is read-only;
launched programs retain their normal behavior. No new bank-zero reservations,
Task slots, DP pages or kernel services. Measure checked stack headroom and keep
all new buffers/resource data in upper RAM.
