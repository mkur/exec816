# SDX utilities

[Guide index](README.md) · [SDX contract](../reference/sdx-services.md) · [EDX port](../development/sdx-edx.md)

The optional development personality runs pinned MD5, ARC and EDX binaries on
Exec816. Build verified inputs and a writable test disk:

```sh
python3 tools/prepare_sdx_inputs.py --nomarch /path/to/nomarch
python3 tools/make_sdx_utils.py --output build/sdx-utils
python3 tools/build_demo.py --output build/sdx-demo --gem-desktop --sdx \
  --sdx-drive-a D2: --sdx-car-root D2: --release-compiler
build/sdx-demo/launch-altirra.command --disk 2 build/sdx-utils/sdx-utils.atr
```

The demo includes OF816 and its five-second autoboot. Select the Shell window,
then mount the test disk:

```text
MOUNT D2: FORMAT SPARTA READWRITE
D2:MD5 ABC.TXT
D2:ARC
D2:ARC L SAMPLE.ARC
D2:EDX EDIT.TXT
```

Run EDX as a foreground command. It uses its console's geometry in the text or graphical shell. Ctrl-Z moves to
end of line. Ctrl-S saves; Return confirms the filename. Escape exits. Read
`D2:EDX EDX.MAN` on the utility disk for the other editor commands. Keep documents in
ATASCII text format. Do not resize the console while editing.

Both `EDX` and `EDX.COM` work when the file is in the current directory or PATH;
`D2:EDX` works with an explicit path. The Exec shell tries the literal name first,
then `.COM` if the literal is absent and its last component has no extension.
SpartaDOS X also assumes `.COM` for external commands.

Guest A: and CAR: map to the immutable roots selected at build time. In the
example both select D2:, independently of the native shell's current directory.
Other SDX programs are not admitted. ARC's original no-argument help lists all
original operations; the [supported subset](../reference/sdx-services.md) remains
limited. The utility disk stays outside the boot-only `exec816-demo.zip`.
