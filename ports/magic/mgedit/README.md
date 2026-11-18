# Original MagiC MGEDIT and EDITOBJC

`inputs.json` pins the immutable `upstream/` files and the common MagiC GPLv3
licence. The selection includes MGEDIT's Atari sources and three resource
variants, the EDITOBJC engine, loader glue and line scanner, and its `TST_APP/EDIT`
client. Resource bytes are preserved exactly. `tools/prepare_mgedit.py --output
build/mgedit/source` verifies the selection and prepares lowercase UTF-8 source
copies with host newlines. The 68000 assembly is the reference for the C port.

The test client uses its own resource and `wdlg_*` host and calls the older
`edit_evnt` signature. The native fixture will use a compiled `G_EDIT` object
and ordinary window, with the event contract in the pinned `MT_EDIT.H`.

| MagiC AES function | Operations |
| --- | --- |
| 210 | Create an `XEDITINFO`. |
| 211–214 | Open, close, delete and explicitly toggle the caret. |
| 215 | Dispatch a key or pointer event and return an editor error code. |
| 216 | Query buffer, format, colors, font, caret, scroll position, dirty state, selection and scroll metrics. |
| 217 | Attach a buffer, set format/colors/font/caret/position, resize, set dirty or scroll. |

The source selection was prepared with the current C816 ABI 48 and Calypsi
5.18. See the [migration plan](../../../docs/plans/gem4xe/mgedit-migration-plan.md)
for the native operation subsets and the [audit](../../../docs/history/mgedit-port-audit.md)
for the pinned release comparison.
