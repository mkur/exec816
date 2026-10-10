"""Select the existing SIO sections in build-generated Action! modules."""
def select_sio(source,enabled):
    output=[];arm=None;other=False
    for line in source.splitlines(keepends=True):
        marker=line.strip()
        if marker=='; IF SIO':
            assert arm is None,'Nested SIO selection'
            arm=enabled
            other=False
        elif marker=='; ELSE SIO':
            assert arm is not None,'Missing SIO selection'
            arm=not arm
            other=True
        elif marker=='; ENDIF SIO':
            assert arm is not None,'Missing SIO selection'
            arm=None
        elif arm is None or arm:
            if arm is not None and other and line.startswith('; '):line=line[2:]
            output.append(line)
    assert arm is None,'Unterminated SIO selection'
    return ''.join(output)
