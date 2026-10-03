"""Select INPUT audit instrumentation before Action! compilation.

The handwritten source contains the checked path. Explicit audit blocks are
omitted from production source, including raw builds; queue code is shared.
"""

BEGIN = '; INPUT_DIAGNOSTIC_BEGIN'
END = '; INPUT_DIAGNOSTIC_END'


def select(source, enabled):
    if type(enabled) is not bool:
        raise ValueError('Input diagnostics option must be boolean')
    result = []
    inside = False
    for line in source.replace('\r\n', '\n').splitlines(keepends=True):
        marker = line.strip()
        if marker == BEGIN:
            if inside:
                raise ValueError('Nested input diagnostic block')
            inside = True
        elif marker == END:
            if not inside:
                raise ValueError('Unmatched input diagnostic end')
            inside = False
        elif not inside or enabled:
            result.append(line)
    if inside:
        raise ValueError('Unclosed input diagnostic block')
    return ''.join(result)
