# GemARC

[Guide index](README.md)

GemARC opens ARC archives in a GEM window. Launch `RUN C:GEMARC.APP` or pass one
quoted native filename, for example `RUN C:GEMARC.APP "WORK:SAMPLE.ARC"`.
Opening an ARC document in Files uses GemARC unless a saved user association
overrides ARC. Keep `SYS:GEMARC.RSC` on the matching system disk.

Click a member to toggle its selection. Up/Down scroll; the window arrows and
slider also scroll. Ctrl-A selects all. Ctrl-E extracts the selection, Ctrl-I
adds files, Ctrl-N creates an archive, Ctrl-O opens one, Ctrl-U closes the
archive and Ctrl-Q quits. The window's close gadget quits. The file selector
chooses the extraction directory; its filename is ignored for extraction.
For Add, enter a filename or wildcard. Matching members are replaced.

The limit is 512 archive members and 64 source files per Add. Larger wildcard
matches fail before changing the archive. Input enumeration streams directory
batches; it has no hidden 256-entry truncation. Member output names are
converted to uppercase native 8.3 names. Different archive names can map to
the same output name; existing destinations require an explicit overwrite
decision, with Cancel selected by default. Paths use native volumes and `/`
separators. The standard file selector supports 127-byte paths; command-line
archive paths support 255 bytes.

Stored, packed/RLE, squeezed and dynamic LZW methods 1–4, 8 and 9 are supported.
Methods 5–7 can be listed but cannot be extracted. Encrypted archives, nested
directory restoration and arbitrary long filenames are unsupported. Extraction
checks output size and CRC before publishing a replacement. Escape cancels
work; a close/Stop request also cancels and retires the application. Work polls
between bounded I/O chunks so redraws and close requests remain serviceable.

Writes use exclusive same-directory `Gxxxxxxx.TMP` files. Replacing an existing
file first renames it to a `Gxxxxxxx.OLD` backup, then publishes the replacement.
If publication fails, the alert names the retained recovery copy. Preserve
both files: `.OLD` contains the original and `.TMP` contains the replacement.
A failed Close can leave a `.TMP` whose contents need checking. A failed backup
deletion can leave `.OLD` beside the successfully published destination. These
files are excluded from wildcard Add. Inspect them before renaming or deleting
them. This sequence provides recovery copies; it does not promise atomic
replacement or power-loss durability.

ARC dates have two-second resolution. The port reads and restores representable
1980–2049 dates on RAM/SDFS. Missing or invalid dates are omitted. MyDOS has no
timestamp operation, so extraction there keeps the backend's normal metadata.
Other metadata errors stop publication and leave the temporary copy available.
Read-only media and insufficient disk space are ordinary operation failures.

The port uses the [common C runtime](../reference/c-runtime.md), with no private
allocator, descriptor table or startup implementation. The nine persistent
codec/list/name buffers request 84,610 upper-memory bytes, plus allocation
prefixes and rounding. No additional bank-zero reservation is introduced.
Source pins and ordered patches are in
[the port directory](../../ports/gem4xe/apps/gemarc/README.md).
