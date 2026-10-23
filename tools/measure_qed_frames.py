#!/usr/bin/env python3
"""Port-specific emitted source frame ledger with explicit callback/control contexts.

This does not qualify missing GEM or claim a whole-system C stack analyzer.
"""
from pathlib import Path
import re, json, argparse
from build_qed import object_symbols
from native_program import require, sha256

def emitted_instructions(chunk):
    pattern=r'^\s*\\ ([a-f0-9]{6}) ([a-f0-9.]+)\s+(?:(?:`?[^\s:`]+`?):[ \t]*)?(\w+)[ \t]*([^\n]*)'
    return [(int(a,16),b,op,arg) for a,b,op,arg in re.findall(pattern,chunk,re.M)]


def frame_cost(instructions):
    pushes=sum(1 if op in ('php','phb') else 2 for pc,b,op,arg in instructions
        if op in ('pei','pea','per','pha','phx','phy','php','phb','phd'))
    reserves=0
    for n,(_,b,op,arg) in enumerate(instructions):
        if op!='tsc':continue
        window=instructions[n+1:n+5]
        amount=next((arg for _,_,op,arg in window if op=='sbc' and arg.startswith('##')),None)
        if amount and any(op=='tcs' for _,_,op,arg in window):
            try:reserves+=int(amount[2:],0)
            except ValueError:raise RuntimeError('Unclassified frame reservation: '+amount)
    return reserves,pushes


def source_listings(image):
    paths=[Path(obj).with_suffix('.lst') for obj in image['provenance']['link_objects']
           if not Path(obj).stem.endswith('-asm')]
    require(all(path.is_file() for path in paths),'Missing linked source listing')
    return paths


def measure(out,destination=None):
    options=set(json.loads((out / 'layout.json').read_text())['selection']['compiler_options'])
    require({'--no-cross-call','--no-interprocedural-cross-jump'}<=options
            and options<={'--no-cross-call','--no-interprocedural-cross-jump','--no-inline'},
            'Frame ledger needs stable function boundaries')
    report = json.loads((out / 'layout.json').read_text())
    listings=source_listings(report['image'])
    require(sha256(out/'program.elf')==report.get('elf_sha256',report.get('analysis_elf_sha256')),
            'QED build is incomplete or changed')
    sym = report['image']['symbols']
    graph = {}
    addresses = {}
    pat = "([^\\n]+?) in section 'farcode'\\s+placed at address ([a-f0-9]+)-([a-f0-9]+) of size [a-f0-9]+\\n\\([^\\n]*?unit (\\d+) section index (\\d+)\\)"
    for m in re.finditer(pat, (out / 'link.lst').read_text()):
        k = (int(m[4]), int(m[5]))
        addresses[k] = (int(m[2], 16), int(m[3], 16) + 1, m[1].strip())

    def targetaddr(address):
        return next((k for k, (a, b, n) in addresses.items() if a <= address < b), None)
    for p in listings:
        obj = object_symbols(p.with_suffix('.o'))
        unit = int(p.name.split('-')[0])
        chunks = re.split('\\\\ [0-9a-f]{6}\\s+\\.section ', p.read_text(errors='replace'))
        for chunk in chunks:
            if not chunk.startswith('farcode,text'):
                continue
            labels = re.findall('\\\\ ([0-9a-f]{6})\\s+(?:[a-f0-9.]+\\s+)?(`?[^\\s:`]+`?):', chunk, re.M)
            head = next((n.strip('`') for at, n in labels if at == '000000' and n.strip('`') in obj), None)
            if head is None:
                continue
            k = (unit, obj[head]['section'])
            if k not in addresses:
                continue
            instructions = emitted_instructions(chunk)
            reserves,pushes = frame_cost(instructions)
            edges = []
            for pc, b, op, arg in instructions:
                if op not in ('jsl', 'jsr', 'jmp', 'jml'):
                    continue
                name = arg.removeprefix('long:').removeprefix('a:').strip('`')
                dest = (unit, obj[name]['section']) if name in obj and obj[name]['section'] else targetaddr(sym[name]) if name in sym else None
                if dest and dest != k:
                    edges.append(dest)
            graph[k] = dict(name=head, weight=reserves + pushes, reserves=reserves, pushes=pushes, edges=sorted(set(edges)), source=p.name)
    source_units={int(p.stem.split('-')[0]) for p in listings}
    require(all(k in graph for k in addresses if k[0] in source_units),
            'Retained source section missing from frame ledger')
    visiting = []
    done = {}
    cycles = set()

    def bound(k):
        if k in done:
            return done[k]
        if k in visiting:
            cycles.add(tuple((graph[n]['name'] if n in graph else addresses[n][2] for n in visiting[visiting.index(k):] + [k])))
            return (0, [])
        if k not in graph:
            return (0, [])
        visiting.append(k)
        v = graph[k]
        children = [bound(e) for e in v['edges']]
        value, path = max(children, default=(0, []))
        visiting.pop()
        res = (v['weight'] + value + 3, [v['name']] + path)
        done[k] = res
        return res
    callbacks = {'QedRuntimeRun': ['editor_body'], 'do_icon': ['e_icon_test', 'e_icon_edit'], 'icon_test': ['e_icon_test'], 'icon_edit': ['e_icon_edit'], 'icon_exist': ['e_icon_exist'], 'do_all_window': ['do_absatz', 'do_color_change'], 'snap_window': [], 'redraw_window': ['wi_draw'], 'uniconify_window': ['wi_uniconify'], 'ontop_window': ['wi_top'], 'untop_window': [], 'top_window': ['wi_top'], 'create_window': ['crt_edit'], 'close_window': [], 'click_window': ['wi_click'], 'unclick_window': [], 'key_window': ['wi_key'], 'select_file': ['open_multi'], 'cf_form_keybd': [], 'handle_mdial_msg': ['handle_msg'], 'suche1': ['STRSTR', 'STRSTR1']}
    # Retired donor helpers are absent from later images. Unknown indirect
    # sites and changed contracts in functions still linked remain errors.
    callbacks = {name: [target for target in targets if target in sym]
                 for name, targets in callbacks.items() if name in sym}
    indirect = {v['name'] for v in graph.values() if any((addresses[e][2] == '_JmpIndLong' for e in v['edges']))}
    require(indirect == set(callbacks), 'Unclassified or stale indirect callback contract: ' + str(indirect ^ set(callbacks)))
    for v in graph.values():
        if any((addresses[e][2] == '_JmpIndLong' for e in v['edges'])):
            for n in callbacks[v['name']]:
                if n in sym:
                    v['edges'].append(targetaddr(sym[n]))
    redraw = targetaddr(sym['handle_msg'])
    fake = (999, 0)
    graph[fake] = {**graph[redraw], 'name': 'handle_msg(redraw-only)', 'edges': [targetaddr(sym[n]) for n in ['redraw_window', 'move_window', 'size_window'] if n in sym]}
    for k, v in graph.items():
        if v['name'] in ('handle_mdial_msg', 'do_aktion', 'end_aktion'):
            v['edges'] = [fake if e == redraw else e for e in v['edges']]
    seq = 1000
    byname = {v['name']: k for k, v in graph.items()}

    def clone(name, label, allowed=None):
        nonlocal seq
        seq += 1
        k = (999, seq)
        v = graph[byname[name]]
        graph[k] = {**v, 'name': label, 'edges': v['edges'][:] if allowed is None else [byname[n] for n in allowed if n in byname]}
        return k
    if 'select_file' in byname:
        selectnone = clone('select_file', 'select_file(NULL)', [])
        graph[selectnone]['edges'] = [e for e in graph[byname['select_file']]['edges'] if e != byname.get('open_multi')]
        for v in list(graph.values()):
            if v['name'] != 'select_multi':
                v['edges'] = [selectnone if e == byname['select_file'] else e for e in v['edges']]
    saveedit = clone('e_icon_edit', 'e_icon_edit(Save)')
    savetest = clone('e_icon_test', 'e_icon_test(Save)', [])
    savedispatch = clone('do_icon', 'do_icon(Save)', [])
    graph[savedispatch]['edges'] = [saveedit, savetest]
    graph[byname['delete_edit']]['edges'] = [savedispatch if e == byname['do_icon'] else e for e in graph[byname['delete_edit']]['edges']]
    update = clone('do_icon', 'do_icon(Update): disabled', [])
    graph[update]['weight'] += graph[byname['e_icon_test']]['weight'] + 3
    graph[byname['wi_top']]['edges'] = [update if e == byname['do_icon'] else e for e in graph[byname['wi_top']]['edges']]
    openedit = clone('e_icon_edit', 'e_icon_edit(Open)', ['open_edit'])
    opentest = clone('e_icon_test', 'e_icon_test(Open)', [])
    opendispatch = clone('do_icon', 'do_icon(Open)', [])
    graph[opendispatch]['edges'] = [openedit, opentest]
    deleteedit = clone('e_icon_edit', 'e_icon_edit(Delete)', ['destruct'])
    deletedispatch = clone('icon_edit', 'icon_edit(Delete)', [])
    graph[deletedispatch]['edges'] = [deleteedit]
    for name in ['load_edit', 'new_edit', 'restore_edit']:
        if name not in byname:
            continue
        graph[byname[name]]['edges'] = [opendispatch if e == byname['do_icon'] else deletedispatch if e == byname['icon_edit'] else e for e in graph[byname[name]]['edges']]
    visiting = []
    done = {}
    cycles = set()
    source_bytes, chain = bound(targetaddr(sym['main']))
    require(not cycles, 'Unbounded source call cycle: ' + str(cycles))
    continuation_cap = 768
    required = source_bytes + continuation_cap + 256 + 128
    require(required <= report['selection']['minimum_stack_bytes'], 'Conditional stack budget exceeds admission')
    result = dict(status='conditional-source-bound', source_chain_bytes=source_bytes, chain=chain, continuation_cap_bytes=continuation_cap, interrupt_reserve_bytes=256, required_headroom_bytes=128, admission_bytes=report['selection']['minimum_stack_bytes'], margin_bytes=report['selection']['minimum_stack_bytes'] - required, method='For each retained emitted source section, sum immediate TSC/SBC/TCS reservations and all static push sites at 16-bit width, plus three bytes at each call/tail edge. This overcounts disjoint branches. Compiler-balanced loops reuse their stack. Cross-call and cross-function tail sharing are disabled. Typed callbacks and finite action contexts are audited below; new indirect sites or cycles reject the report.', limit='Source-frame bound only. The continuation cap includes bridge and library/native/GEM work below an application call; executed startup/lifecycle chains check that cap separately. Editing/dialog/file paths must establish it when implemented; current samples are not a bound on those future paths.', callbacks=callbacks, contexts=['Nested action/dialog messages: REDRAW/MOVED/SIZED only', ('select_single/select_path pass NULL; only select_multi invokes open_multi' if 'open_multi' in sym else 'Legacy path/Save selector callers pass NULL; the multi-file callback is retired'), ('Native deletion follows the outer asynchronous decision; saving borrows a frozen ring' if 'QedSavingStep' in sym else 'Native delete_edit uses Discard/Cancel; Save remains disabled'), 'Linked new_edit/restore_edit use Open or unchecked Delete', 'wi_top invokes disabled Update, whose test returns false'], source_nodes=[{**v, 'key': k} for k, v in graph.items()], analysis_sha256=sha256(out / 'layout.json'), listings={p.name: sha256(p) for p in listings}, compiler_options=report['selection']['compiler_options'])
    (destination or out / 'stack-frames.json').write_text(json.dumps(result, indent=2) + '\n')
    return result
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--layout', type=Path, required=True)
    parser.add_argument('--output',type=Path)
    args = parser.parse_args()
    result = measure(args.layout.resolve(),args.output)
    print('QED source frame bound:', result['source_chain_bytes'], 'bytes; conditional margin:', result['margin_bytes'])
