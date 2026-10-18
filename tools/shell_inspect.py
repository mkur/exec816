"""Inspect a caller-owned shell context using the generated native layout."""
import re
import struct

from generate_shell_sessions import layout
from native_program import require

CONTEXT = layout()['ShellContext']


def address(image, name, module=None):
    field = name if name in CONTEXT['fields'] else None
    symbol_name = 'context' if field else name
    pattern = (('_'+module+'_') if module else r'(?:^|_)') + re.escape(symbol_name) + '_'
    matches = [s for s in image['data'] if s['kind'] == 'global'
               and re.search(pattern, s['name'], re.IGNORECASE)]
    require(len(matches) == 1, 'Missing/ambiguous shell inspection symbol: '+name)
    symbol = matches[0]
    if field:
        require(symbol['size'] == CONTEXT['size'], 'Changed emitted shell context size')
    return symbol['address'] + (CONTEXT['fields'][field] if field else 0)


def data(bridge, image, name, words=False):
    start = address(image, name)
    size = CONTEXT['widths'][name]
    raw = bytes(bridge.eval_expr(f'db(${start+i:x})') & 255 for i in range(size))
    return list(struct.unpack('<'+'H'*(size//2), raw)) if words else list(raw)
