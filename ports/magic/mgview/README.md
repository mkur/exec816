# Original MagiC MGVIEW

The immutable `upstream/` selection comes from the MagiC revision and paths in
`inputs.json`. Each byte was fetched from that revision and SHA-256 checked.
It retains Andreas Kromke's viewer, project file, README and upstream GPLv3
licence. `MEMCHAR2.S` is a reference only; no 68000 code is linked into Exec.

`tools/prepare_mgview.py` verifies the selection, converts host source newlines
and ISO-8859-1 byte code points to UTF-8, adds a final source newline where
needed, lowercases filenames and applies `native.patch` without fuzz. High
source bytes occur in comments; document bytes are never converted here.
`tools/build_mgview.py --output build/mgview` builds an ordinary current-ABI APP
with the common argument runtime, GEMDOS subset and shared rectangle helpers.

The original three modules retain document indexing/expansion, window callbacks
and event dispatch. The patch adapts Pure C 16-bit integers to `WORD`, rectangle
overloads to explicit helpers, and event arguments to the shared GEM binding.
Native glue replaces the `gemut_mt.o` workstation/error helpers and the CR/LF
scanner. It omits grow/shrink animation, VA_START/AV_STARTED and drag/drop pipes.
There is no RSC or file selector in this command-line helper.

The native C profile keeps optimization and disables inlining uniformly, as QED
already does for Calypsi 5.18. The clean loaded pixel probe covers this profile;
temporary diagnostic stores are not part of the shipped viewer.

The initial loader bounds file payloads to 65,519 bytes and the four-byte line
index to 16,380 entries, including clean empty-file and acquisition rollback.
The 273-byte draw scratch is private to each loaded image in upper BSS.
Existing Task stacks and all fixed/per-Task bank-zero reservations are unchanged.

See the [implementation plan](../../../docs/plans/gem4xe/mgview-port-plan.md)
and [execution record](../../../docs/history/mgview-port.md).
