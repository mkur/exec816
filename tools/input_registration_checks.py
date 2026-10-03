"""Inspect emitted INPUT call paths without scanning instruction operands as code."""
import re

from native_program import ROOT, require


def reachable(graph, start):
    pending = [start]
    found = set()
    while pending:
        node = pending.pop()
        if node in found:
            continue
        found.add(node)
        pending.extend(graph.get(node, ()))
    return found


def audit_paths(program, operations=('TAKE', 'PENDING')):
    image = program['image']
    decoder = {'__name__': 'input_decoder'}
    path = ROOT/'build/actionc/tools/disassemble65816.py'
    exec(compile(path.read_text(), str(path), 'exec'), decoder)
    graph = {}
    names = {r['address']: r['name'] for r in image['routines']}
    for label in ('tasks_find_task', 'heap_type_of_mem'):
        names[program['labels'][label]] = label
    for routine in image['routines']:
        segments = []
        for segment in image['segments']:
            lo = max(segment['address'], routine['address'])
            hi = min(segment['address']+len(segment['bytes']), routine['address']+routine['size'])
            if lo < hi:
                segments.append(dict(address=lo, executable=True,
                    bytes=segment['bytes'][lo-segment['address']:hi-segment['address']]))
        listing = decoder['disassemble']({**image, 'version': 3, 'segments': segments})
        graph[routine['name']] = [names.get(int(address, 16), address)
            for address in re.findall(r' (?:JSL|JML) \$([0-9A-Fa-f]{6})', listing)]

    def routine(name):
        matches = [n for n in graph if n.startswith('M_INPUT_'+name+'_')]
        require(len(matches) == 1, 'Missing/ambiguous INPUT routine '+name)
        return matches[0]

    forbidden = lambda n: n.startswith(('M_INPUT_EXTENT_', 'M_INPUT_VALID_',
        'M_TASKMEMORY_WRITABLE_')) or n in ('tasks_find_task', 'heap_type_of_mem')
    roots = [routine(name) for name in operations]
    roots += [n for n in graph if any('_CINPUT'+name+'_' in n for name in operations)]
    observed = {name: sorted(n for n in reachable(graph, name) if forbidden(n)) for name in roots}
    diagnostic = program['build']['input_diagnostics']
    for name, audits in observed.items():
        require(bool(audits) == diagnostic, 'Wrong emitted audit path '+name+': '+str(audits))
    for name in ('ACQUIRE', 'RELEASE'):
        path = reachable(graph, routine(name))
        require(any(n.startswith('M_INPUT_EXTENT_') for n in path), 'Missing lifecycle memory audit')
    require(any(n.startswith('M_INPUT_VALID_') for n in reachable(graph, routine('RELEASE'))),
            'Missing checked Release identity audit')
    return dict(input_diagnostics=diagnostic, ordinary_audits=observed,
                lifecycle_audits_present=True, scope='Decoded Action! and C-bridge direct call graph; native kernel services are terminal boundaries')
