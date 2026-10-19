"""Inspect a caller-owned shell context using the generated native layout."""
import re
import struct

from generate_shell_sessions import layout
from native_program import require

CONTEXT = layout()['ShellContext']


def address(image, name, module=None, session=0):
    field = name if name in CONTEXT['fields'] else None
    symbol_name = 'context' if field else name
    pattern = (('_'+module+'_') if module else r'(?:^|_)') + re.escape(symbol_name) + '_'
    matches = [s for s in image['data'] if s['kind'] == 'global'
               and re.search(pattern, s['name'], re.IGNORECASE)]
    if field and not matches:
        pattern = (('_'+module+'_') if module else r'(?:^|_)') + 'contexts_'
        matches = [s for s in image['data'] if s['kind'] == 'global'
                   and re.search(pattern, s['name'], re.IGNORECASE)]
    require(len(matches) == 1, 'Missing/ambiguous shell inspection symbol: '+name)
    symbol = matches[0]
    offset = 0
    if field:
        require(symbol['size'] % CONTEXT['size'] == 0
                and 0 <= session < symbol['size'] // CONTEXT['size'],
                'Changed emitted shell context extent or missing session')
        offset = session * CONTEXT['size'] + CONTEXT['fields'][field]
    return symbol['address'] + offset


def data(bridge, image, name, words=False):
    start = address(image, name)
    size = CONTEXT['widths'][name]
    raw = bytes(bridge.eval_expr(f'db(${start+i:x})') & 255 for i in range(size))
    return list(struct.unpack('<'+'H'*(size//2), raw)) if words else list(raw)


def process_slot(bridge, program, identity=1):
    """Find the live resident shell by its admitted entry and identity text."""
    from generate_process import ABI
    fields = {name: offset for name, _, offset in ABI['record']}
    callbacks = {r['address'] for r in program['image']['routines']
                 if re.search(r'_SHELLPROCESSENTRY_[0-9A-F]+$', r['name'])}
    storage = program['build']['memory']['process_storage']
    matches = []
    for index in range(storage['CAPACITY']):
        record = bridge.memdump(storage['BASE']+index*ABI['record_bytes'], ABI['record_bytes'])
        number = lambda field, size: int.from_bytes(record[fields[field]:fields[field]+size], 'little')
        if number('entry', 3) not in callbacks or number('state', 1) != ABI['states']['RUNNING']:
            continue
        args = number('arguments', 3)
        if args and bridge.memdump(args, 9) == f'{identity:08x}\0'.encode():
            matches.append(number('slot', 1))
    require(len(matches) == 1, 'Missing/ambiguous live shell Process')
    return matches[0]
