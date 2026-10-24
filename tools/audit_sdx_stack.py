#!/usr/bin/env python3
"""Reproduce scoped stack envelopes for the pinned resident guest inputs.

This is an abstract stack/control-flow audit with explicitly reviewed summaries,
not a CPU emulator, arbitrary-binary verifier or hosted qualification claim.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path
from sdx_file import parse, place
from sdx_patch import manifests, prepare, select
import sdx_md5_audit as md5
from sdx_edx_audit import decode, dispatch_tables, word, RAWCON
from sdx_arc_audit import audit as arc_audit
ROOT = Path(__file__).resolve().parents[1]
OPCODES = {
    **md5.OPCODES,
    0x6c: ('JMP', 'ind', 3), 0x80: ('BRA', 'rel', 2),
    0xbb: ('TYX', 'imp', 1),
    0x97: ('STA', 'indlongy', 2), 0xb7: ('LDA', 'indlongy', 2),
    0x87: ('STA', 'indlong', 2), 0xa7: ('LDA', 'indlong', 2),
    0xa3: ('LDA', 'stack', 2), 0x83: ('STA', 'stack', 2),
    0x17: ('ORA', 'indlongy', 2), 0x37: ('AND', 'indlongy', 2),
    0x57: ('EOR', 'indlongy', 2), 0x77: ('ADC', 'indlongy', 2),
    0xd7: ('CMP', 'indlongy', 2), 0xf7: ('SBC', 'indlongy', 2),
}

def root_path(name):
    return ROOT / name

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def walk(mem, roots, imp, *, name='', leaf='', code=None, branches=None, veneers=None, inline=None, tables=(), labels=None, endpoints=()):
    """Track physical pushes and typed returns; fail on unsummarized control flow."""
    code = code or {}
    branches = branches or {}
    veneers = veneers or {}
    inline = inline or {}
    labels = labels or {}
    base = 12288
    pending = [(r, (('hi', -1, None), ('lo', -1, None)), (r,), (None,) * 7) for r in roots]
    seen = set()
    peak = (0, None)
    servicepeak = 0
    while pending:
        pc, st, path, regs = pending.pop()
        a, x, y, c, z, n, v = regs
        if pc in endpoints:
            continue
        if (pc, st, regs) in seen:
            continue
        seen.add((pc, st, regs))
        depth = len(st)
        if depth > peak[0]:
            peak = (depth, path + (pc,))
        if depth > 112 or len(seen) > 3000000:
            raise RuntimeError(repr(('LIMIT', len(seen), depth, [hex(x - base) for x in path])))
        if name == 'ARC' and pc == 13566:
            peak = max(peak, (len(st) + 2, path + (pc,)))
            op = 'RTS'
            mode = 'imp'
            size = 1
            arg = 0
            a = x = y = c = z = n = v = None
        elif pc in imp or pc in veneers:
            servicepeak = max(servicepeak, len(st) + 11 + (2 if name=='ARC' and pc in (0x31a8,0x31b0,0x3959,0x395c) else 0))
            if imp.get(pc) == 'STACK_CHECK':
                if 495 - len(st) - 11 < 416:
                    continue
            else:
                a = x = y = c = z = n = v = None
            if imp.get(pc) == 'U_FAIL':
                continue
            op = 'RTS'
            mode = 'imp'
            size = 1
            arg = 0
        elif pc not in code:
            if mem[pc] not in OPCODES:
                raise RuntimeError(repr(('UNKNOWN', hex(pc), hex(mem[pc]), [hex(x - base) for x in path])))
            op, mode, size = OPCODES[mem[pc]]
            arg = int.from_bytes(mem[pc + 1:pc + size], 'little')
        else:
            item = code[pc]
            op, mode, size, arg = (item[k] for k in ('instruction', 'mode', 'bytes', 'operand'))
        nxt = pc + size
        if leaf == 'ARCADD.OVL' and pc == 20835:
            st += (('data', None, 20838),) * 3
            pending.append((20851, st, path, (None, 3, y - 3 & 255 if y is not None else None, None, 1, 0, v)))
            continue
        if op == 'RTS':
            if len(st) == 0:
                if name!='ARC':raise RuntimeError(('Unreviewed nonlocal return',hex(pc)))
                continue
            if len(st) < 2 or not isinstance(st[-1], tuple) or st[-1][0] != 'lo' or (st[-2][0] != 'hi') or (st[-2][1:] != st[-1][1:]):
                raise RuntimeError(repr(('DYNAMIC RTS', hex(pc), st, [hex(x - base) for x in path])))
            if st[-1][1] >= 0:
                pending.append((st[-1][1], st[:-2], path[:-1], (a, x, y, c, z, n, v)))
            continue
        if op == 'PHA':
            st += (('data', a, pc),)
        if op == 'PHP':
            st += (('p', c, z, n, v),)
        if op in ('PLA', 'PLP'):
            if not st:
                if name!='ARC':raise RuntimeError(('Unreviewed nonlocal pop',hex(pc)))
                continue
            q = st[-1]
            st = st[:-1]
            if op == 'PLP':
                c, z, n, v = q[1:] if isinstance(q, tuple) and q[0] == 'p' else (None,) * 4
            else:
                a = q[1] if isinstance(q, tuple) and q[0] == 'data' else None
                z, n = (int(a == 0), int(a >= 128)) if a is not None else (None, None)
        if op in ('LDA', 'LDX', 'LDY'):
            value = arg if mode == 'imm' else None
            if op == 'LDA':
                a = value
            if op == 'LDX':
                x = value
            if op == 'LDY':
                y = value
            z, n = (int(value == 0), int(value >= 128)) if value is not None else (None, None)
        if op in ('CLC', 'SEC'):
            c = int(op == 'SEC')
        if op in ('CLV',):
            v = 0
        if op in ('TAX', 'TAY', 'TXA', 'TYA', 'TSX', 'TYX'):
            value = {'TAX': a, 'TAY': a, 'TXA': x, 'TYA': y, 'TYX': y, 'TSX': 239 - len(st) & 255}[op]
            if op in ('TAX', 'TSX', 'TYX'):
                x = value
            elif op == 'TAY':
                y = value
            else:
                a = value
            z, n = (int(value == 0), int(value >= 128)) if value is not None else (None, None)
        if op in ('INX', 'DEX', 'INY', 'DEY'):
            value = x if op.endswith('X') else y
            value = value + (1 if op.startswith('IN') else -1) & 255 if value is not None else None
            if op.endswith('X'):
                x = value
            else:
                y = value
            z, n = (int(value == 0), int(value >= 128)) if value is not None else (None, None)
        if op in ('CMP', 'CPX', 'CPY'):
            value = {'CMP': a, 'CPX': x, 'CPY': y}[op]
            if mode == 'imm' and value is not None:
                c, z, n = (int(value >= arg), int(value == arg), int(value - arg & 255 >= 128))
            else:
                c = z = n = None
        if op in ('ADC', 'SBC', 'AND', 'ORA', 'EOR', 'ASL', 'LSR', 'ROL', 'ROR', 'INC', 'DEC', 'BIT'):
            z = n = None
            if op in ('ADC','SBC','AND','ORA','EOR') or (op in ('ASL','LSR','ROL','ROR') and mode=='imp'):
                a = None
            if op in ('ADC', 'SBC', 'ASL', 'LSR', 'ROL', 'ROR'):
                c = None
            if op in ('ADC', 'SBC', 'BIT'):
                v = None
            if op == 'BIT':
                n = None
        regs = (a, x, y, c, z, n, v)
        if op == 'TXS':
            raise RuntimeError(repr(('TXS', hex(pc), [hex(x - base) for x in path])))
        if op in ('JMP', 'JSR'):
            if leaf == 'ARCADD.OVL' and op == 'JSR' and (pc in (22263, 22291)):
                servicepeak = max(servicepeak, len(st) + 15)
                pending.append((nxt, st, path, (None,) * 7))
                continue
            if mode == 'ind':
                if name!='EDX' or pc!=0x3242 or arg!=0x87 or not tables:
                    raise RuntimeError(('Unreviewed indirect transfer',hex(pc)))
                dispatch_mode = next((q[2] for q in reversed(st) if isinstance(q, tuple) and len(q) == 3 and (q[0] == 'lo') and (q[2] is not None)), None)
                selected = tables[dispatch_mode:dispatch_mode + 1] if dispatch_mode in (0, 1, 2) else tables
                targets = [e['target'] for t in selected for e in t['entries']] + [t['fallback'] for t in selected]
                for r in targets:
                    pending.append((r, st, path, regs))
                continue
            if name == 'ARC' and arg == 13566:
                nxt += 6
            if pc in inline:
                rec = inline[pc]
                nxt = pc + 3 + len(bytes.fromhex(rec['format_hex'])) + 1 + 2 * len(rec['arguments'])
            if op == 'JSR':
                st += (('hi', nxt, a if name == 'EDX' and arg == 12798 else None), ('lo', nxt, a if name == 'EDX' and arg == 12798 else None))
                path += (pc,)
            pending.append((arg, st, path, regs))
            continue
        if mode == 'rel':
            test = {'BCC': c, 'BCS': c, 'BEQ': z, 'BNE': z, 'BMI': n, 'BPL': n, 'BVC': v, 'BVS': v}.get(op)
            expect = op in ('BCS', 'BEQ', 'BMI', 'BVS')
            if name == 'BASIC' and pc == labels['E_ELSEIF'] + 14:
                test = 0
            if name == 'EDX' and pc in (15489, 13504, 16308):
                test = 0
            if op == 'BRA' or test is None or bool(test) == expect:
                for arg in branches.get(pc, [arg]):
                    target = nxt + (arg if arg < 128 else arg - 256)
                    taken = list(regs)
                    if op != 'BRA':
                        taken[{'BCC': 3, 'BCS': 3, 'BEQ': 4, 'BNE': 4, 'BMI': 5, 'BPL': 5, 'BVC': 6, 'BVS': 6}[op]] = int(expect)
                    if name == 'BASIC' and target <= pc:
                        taken[:3] = [None] * 3
                    pending.append((target, st, path, tuple(taken)))
            if op == 'BRA' or (test is not None and bool(test) == expect):
                continue
            fall = list(regs)
            fall[{'BCC': 3, 'BCS': 3, 'BEQ': 4, 'BNE': 4, 'BMI': 5, 'BPL': 5, 'BVC': 6, 'BVS': 6}[op]] = int(not expect)
            regs = tuple(fall)
        pending.append((nxt, st, path, regs))
    return dict(cpu_bytes=peak[0], service_frame_bytes=servicepeak, states=len(seen), peak_path=[hex(pc - base) for pc in peak[1]])

def legacy(name):
    abi = json.loads(root_path('abi/sdx.json').read_text())
    symbols = {k: v['address'] for k, v in abi['guest_services'].items()}
    imp = {v: k for k, v in symbols.items() if k not in ('COMTAB', 'FILE_P')}
    imp[62080] = 'CHECKPOINT'
    raw = root_path('build/sdx-inputs/' + ('edx/EDX.COM' if name == 'EDX' else 'md5/MD5.COM')).read_bytes()
    select(raw,manifests(root_path("compat/sdx")))
    p = parse(raw)
    mem, layout = place(p, 12288, 57344, symbols)
    base = layout['blocks'][1]
    if name == 'MD5':
        mem = prepare(raw, manifests(root_path('compat/sdx')), 12288, 57344, symbols).image
        audit = md5.audit(raw)
        roots = [base, base + 192]
        code = {}
        branches = {base + int(k): v for k, v in audit['dynamic_branches'].items()}
        inline = {base + int(k): v for k, v in audit['inline'].items()}
        veneers = {}
        indirect = {}
    else:
        roots = [base, word(mem, base + 5150)]
        tables = dispatch_tables(mem, base + 5331, base + 5337, base, base + p.blocks[0].size)
        callbacks = []
        for t in tables:
            callbacks += [e['target'] for e in t['entries']] + [t['fallback']]
        roots += callbacks
        veneers = {base + off: dict(table_offset=slot, function=n) for off, (slot, n) in RAWCON.items()}
        indirect = {base + 578: 135}
        code, _ = decode(mem, base, base + p.blocks[0].size, roots, imp, veneers, indirect)
        branches = {}
        inline = {}
    return walk(mem, roots, imp, name=name, code=code, branches=branches, veneers=veneers, inline=inline, tables=tables if name == 'EDX' else ())

def archive(leaf,roots_override=None):
    abi = json.loads(root_path('abi/sdx.json').read_text())
    symbols = {k: v['address'] for k, v in abi['guest_services'].items()}
    imp = {v: k for k, v in symbols.items() if k not in ('COMTAB', 'FILE_P')}
    imp[62080] = 'CHECKPOINT'
    name = 'ARC'
    symbols['_ARC'] = 14681
    report = arc_audit(root_path('build/sdx-inputs/arc'))['modules']
    main = prepare(root_path('build/sdx-inputs/arc/ARC.COM').read_bytes(), manifests(root_path('compat/sdx')), 12288, 57344, symbols)
    mem = bytearray(main.image)
    base = 12288
    if leaf != 'ARC.COM':
        module = prepare(root_path('build/sdx-inputs/arc/' + leaf).read_bytes(), manifests(root_path('compat/sdx')), 19052, 57344, symbols)
        for b in parse(root_path('build/sdx-inputs/arc/' + leaf).read_bytes()).blocks:
            if b.number in module.layout['blocks']:
                at = module.layout['blocks'][b.number]
                mem[at:at + b.size] = module.image[at:at + b.size]
    roots = [12288, 12826, 13766] + list(range(14681, 14747, 3)) if leaf == 'ARC.COM' else [19052]
    if leaf == 'ARCEXT.OVL':
        roots += [int.from_bytes(mem[a:a + 2], 'little') for a in range(20423, 20431, 2)]
    code = {}
    branches = {}
    veneers = {}
    indirect = {}
    inline = {}
    for n in ('ARC.COM', leaf):
        lo = report[n]['layout']['blocks'][1]
        for off, rec in report[n]['inline'].items():
            inline[lo + int(off)] = dict(format_hex=rec['text_hex'], arguments=rec['sites'])
    imp[63168] = 'STACK_CHECK'
    for pc in [1795, symbols['PRINTF'], symbols['VPRINTF'], 12712, 12720, 14681, 14684, 62848]:
        imp[pc] = 'PRINTER_OR_LEAF'
    return walk(mem, roots_override or roots, imp, name=name, leaf=leaf, inline=inline)

def basic(variant):
    abi = json.loads(root_path('abi/sdx.json').read_text())
    symbols = {k: v['address'] for k, v in abi['guest_services'].items()}
    imp = {v: k for k, v in symbols.items() if k not in ('COMTAB', 'FILE_P')}
    imp[62080] = 'CHECKPOINT'
    import re
    name = 'BASIC'
    base = 12288
    stem = {'FB':'fbrun','FBI':'fbirun','FBC':'fbc','FBCI':'fbci'}[variant]
    labels = {m[2]: int(m[1], 16) for line in root_path('build/fastbasic/source/build/bin/' + stem + '.lbl').read_text().splitlines() if (m := re.match('al ([0-9A-Fa-f]+) \\.(\\w+)$', line))}
    raw = root_path('build/fastbasic/' + variant + '.COM').read_bytes()
    mem = bytes(12288) + raw[16:] + bytes(65536 - 12288 - len(raw[16:]))
    roots = sorted({v for k, v in labels.items() if k.startswith(('E_', 'EXE_')) and (not k.startswith('EXE_USR'))})
    # Error output runs only after retiring the parser continuation with TXS.
    # Audit the printer tail against its trusted caller, not the deep parser S.
    at=labels['parser_error']
    if mem[at]!=0x8c:raise RuntimeError('Changed parser diagnostic entry')
    at+=3
    if mem[at] not in (0xa6,0xae):raise RuntimeError('Missing saved parser S load')
    at+=2 if mem[at]==0xa6 else 3
    if mem[at]!=0x9a:raise RuntimeError('Parser error must retire its stack before output')
    roots += [at+1]
    abi_basic = json.loads(root_path('abi/fastbasic.json').read_text())
    services = abi_basic['services']
    for i in range(16):
        imp[63488 + i * 32] = 'BASIC_SERVICE'
    for value in services.values():
        if isinstance(value, int) and value >= 61440:
            imp[value] = 'BASIC_SERVICE'
    code = {}
    branches = {}
    veneers = {}
    inline = {}
    tables = []
    endpoints = {labels[k] for k in ('next_instruction', 'EXE_END','parser_error')}
    return walk(mem, roots, imp, name=name, labels=labels, endpoints=endpoints)

def rom_editor():
    rom = root_path('build/firmware/altirraos-816.rom').read_bytes()
    mem = bytes(49152) + rom
    labels = {m[2].upper(): int(m[1], 16) for l in root_path('build/firmware/altirraos-816.lab').read_text().splitlines() if (m := re.match('00\\s+([0-9A-F]{4})\\s+(\\S+)', l))}
    rev = {v: k for k, v in labels.items()}
    dec = {**md5.OPCODES,108:('JMP','ind',3), 128: ('BRA', 'rel', 2), 90: ('PHY', 'imp', 1), 122: ('PLY', 'imp', 1), 218: ('PHX', 'imp', 1), 250: ('PLX', 'imp', 1), 100: ('STZ', 'dp', 2), 116: ('STZ', 'dpx', 2), 156: ('STZ', 'abs', 3), 158: ('STZ', 'absx', 3), 26: ('INC', 'imp', 1), 58: ('DEC', 'imp', 1), 108: ('JMP', 'ind', 3), 124: ('JMP', 'absix', 3), 137: ('BIT', 'imm', 2), 52: ('BIT', 'dpx', 2), 60: ('BIT', 'absx', 3), 18: ('ORA', 'inddp', 2), 50: ('AND', 'inddp', 2), 82: ('EOR', 'inddp', 2), 114: ('ADC', 'inddp', 2), 146: ('STA', 'inddp', 2), 178: ('LDA', 'inddp', 2), 210: ('CMP', 'inddp', 2), 242: ('SBC', 'inddp', 2)}
    root = 'EDITORPUTBYTE'
    pending = [(labels[root], (('hi', -1), ('lo', -1)), ())]
    seen = set()
    peak = (0, None)
    limit = 400000
    while pending:
        pc, st, path = pending.pop()
        if (pc, st) in seen:
            continue
        seen.add((pc, st))
        depth = len(st) - 2
        if depth > peak[0]:
            peak = (depth, path + (pc,))
        if depth > 112 or len(seen) > limit:
            raise RuntimeError(repr(('LIMIT', len(seen), depth, [(hex(x), rev.get(x, '')) for x in path])))
        if pc < 0:
            continue
        if pc < 49152 or pc >= 65536:
            raise RuntimeError(repr(('OUT', hex(pc), rev.get(pc), [hex(x) for x in path])))
        if mem[pc] not in dec:
            raise RuntimeError(repr(('UNKNOWN', hex(pc), hex(mem[pc]), rev.get(pc))))
        name, mode, size = dec[mem[pc]]
        arg = int.from_bytes(mem[pc + 1:pc + size], 'little')
        nxt = pc + size
        if name == 'RTS':
            if pc == 64616:
                table = labels['EDITORPUTBYTE.SPECIAL_DISPATCH_LO_TAB']
                hi = labels['EDITORPUTBYTE.SPECIAL_ESCAPE'] & 65280
                for i in range(15):
                    pending.append(((hi | mem[table + i]) + 1, st[:-2], path))
                continue
            if len(st) < 2 or not isinstance(st[-1], tuple) or st[-1][0] != 'lo' or (st[-2] != ('hi', st[-1][1])):
                raise RuntimeError(repr(('DYNAMIC RTS', hex(pc), rev.get(pc), [hex(x) for x in path])))
            if st[-1][1] >= 0:
                pending.append((st[-1][1], st[:-2], path[:-1]))
            continue
        if name in ('PHA', 'PHX', 'PHY', 'PHP'):
            st = st + ('x',)
        if name in ('PLA', 'PLX', 'PLY', 'PLP'):
            if not st:
                raise RuntimeError(repr(('RETURN POP', hex(pc), rev.get(pc), [hex(x) for x in path])))
            st = st[:-1]
        if name == 'TXS':
            raise RuntimeError(repr(('TXS', hex(pc))))
        if name in ('JSR', 'JMP'):
            if mode not in ('abs',):
                raise RuntimeError(repr(('INDIRECT', hex(pc), hex(arg), [hex(x) for x in path])))
            if name == 'JSR':
                if pc == 62542 and path.count(pc) >= 1:
                    continue
                st = st + (('hi', nxt), ('lo', nxt))
                path = path + (pc,)
            pending.append((arg, st, path))
            continue
        if mode == 'rel':
            pending.append((nxt + (arg if arg < 128 else arg - 256), st, path))
            if name == 'BRA':
                continue
        pending.append((nxt, st, path))
    return dict(body_bytes=peak[0], states=len(seen), path=[dict(address=hex(pc), symbol=rev.get(pc)) for pc in peak[1]])


def entry_inventory():
    """Every controlled OS-top selection must have an explicit lifetime class."""
    classes={
        'hosted.s': ('boot/final-return',3),
        'sdx-runtime-probe.s': ('runtime shared selector, no resident anchor',1),
        'sdx-stack.inc': ('non-SDX runtime selector',1),
        'boot-diagnostics.s': ('terminal fault, no resumable guest',1),
        'sio.s': ('test-only emulation import',1),
        'blitter.s': ('test-only emulation import',1),
    }
    result=[]
    for path in sorted((ROOT/'platform/altirraos').glob('*')):
        if path.suffix not in ('.s','.inc'):continue
        lines=[i for i,line in enumerate(path.read_text().splitlines(),1)
               if re.match(r'\s*lda\s+#OS_STACK_TOP\b',line)]
        if not lines:continue
        if path.name not in classes or len(lines)!=classes[path.name][1]:
            raise RuntimeError('Unreviewed OS stack selection: '+str(path))
        result.append(dict(path=str(path.relative_to(ROOT)),lines=lines,lifetime=classes[path.name][0]))
    if len(result)!=len(classes):raise RuntimeError('Missing reviewed stack-entry site')
    return result


def audit():
    """Compose reviewed envelopes; observed canaries are separate corroboration."""
    abi=json.loads(root_path('abi/sdx.json').read_text())['runtime']
    guests={name:legacy(name) for name in ('MD5','EDX')}
    guests.update({name:archive(name) for name in ('ARC.COM','ARCLST.OVL','ARCEXT.OVL','ARCADD.OVL')})
    engines={name:basic(name) for name in ('FB','FBI','FBC','FBCI')}
    body=archive('ARCADD.OVL',[0x5684])
    # Root RTS=2, gate JSR=2 and the native veneer prefix=11 at function entry.
    recursive_drop=max(body['cpu_bytes']+13,body['service_frame_bytes'])-15
    if recursive_drop!=4:raise RuntimeError('Changed Huffman descent/body bound')
    basic_abi=json.loads(root_path('abi/fastbasic.json').read_text())['guest_layout']
    parser_floor=basic_abi['CPU_STACK_FLOOR']
    leaf=max(max(item['cpu_bytes']+13,item['service_frame_bytes']) for item in engines.values())
    # Conservative parser envelope: two temporary bytes, nested returns and NMI.
    # Grammar backtracking records are in the guest's bounded BSS buffer.
    # Action entry restores its three temporary bytes before the leaf call.
    basic_min=min(0x100+parser_floor-19,
                  0x100+basic_abi['CPU_STACK_ACTION_FLOOR']+3-leaf)
    # The legacy extra root allowance covers a dispatcher/trap continuation.
    minimum=dict(MD5=0x1ef-(2*guests['MD5']['cpu_bytes']+13),
                 EDX=0x1ef-(2*guests['EDX']['cpu_bytes']+13),
                 ARC=min(0x1ef-(guests['ARC.COM']['cpu_bytes']+
                     max(guests[n]['cpu_bytes'] for n in ('ARCLST.OVL','ARCEXT.OVL','ARCADD.OVL'))+15),
                     abi['arc_stack_minimum_s']-recursive_drop),
                 FastBasic=basic_min)
    editor=rom_editor()
    if editor['body_bytes']!=13:raise RuntimeError('Changed ROM editor body envelope')
    rom_components=dict(cio_wrapper_cop_and_body=16+4+editor['body_bytes'],
                        nested_emulation_vbi=13+3+3+3,
                        owned_or_rom_irq_envelope=48,
                        acknowledge_only_nmi=13,
                        retired_vbi_return_tail=6)
    rom_peak=sum(rom_components.values())
    if rom_peak>abi['rom_reserve']:raise RuntimeError('ROM reserve below reviewed envelope')
    for name,stack in minimum.items():
        if stack-abi['rom_reserve']<abi['stack_floor']:
            raise RuntimeError('Insufficient admitted headroom: '+name)
    pin=json.loads(root_path('toolchain/altirra.json').read_text())
    rom=root_path('build/firmware/altirraos-816.rom')
    if digest(rom)!=pin['rom']['sha256']:raise RuntimeError('Unpinned ROM')
    paths=[Path(__file__),root_path('abi/sdx.json'),root_path('abi/fastbasic.json'),
           root_path('compat/sdx/arc-450.json'),root_path('ports/fastbasic/patches/resident-stack.patch'),
           root_path('platform/altirraos/sdx-runtime-probe.s'),root_path('platform/altirraos/sdx-stack.inc'),
           root_path('platform/altirraos/hosted.s'),root_path('platform/altirraos/signal-irq.s'),
           root_path('platform/altirraos/sio.s'),root_path('platform/altirraos/input.s')]
    binaries=[root_path('build/sdx-inputs/md5/MD5.COM'),root_path('build/sdx-inputs/edx/EDX.COM')]
    binaries +=[root_path('build/sdx-inputs/arc/'+name) for name in guests if name.endswith(('.COM','.OVL'))]
    binaries +=[root_path('build/fastbasic/'+name+'.COM') for name in engines]
    return dict(status='scoped-source-bound-established',tier='development',qualification=False,
        scope='Pinned admitted profiles and reviewed ROM chains; not arbitrary guest code or third-party interrupt handlers',
        guest_walks=guests,basic_leaf_walks=engines,huffman_body=body,
        minimum_complete_s=minimum,stack_floor=abi['stack_floor'],rom_reserve=abi['rom_reserve'],
        minimum_borrow_anchor=abi['stack_floor']+abi['rom_reserve'],
        rom=dict(sha256=digest(rom),editor=editor,components=rom_components,peak_bytes=rom_peak),
        assumptions=[
            'Both branch arms are traversed unless abstract register/flag state or a reviewed invariant fixes the branch. Unknown control transfers fail closed.',
            'EDX JMP ($87) selects only its current mode table. $34C0/$3C81 see a nonzero high byte of a live document pointer; $3FB4 sees a nonnegative row index at admitted height <=30.',
            'ARC inline-six is the checked no-push helper, with one nested JSR and a six-byte return adjustment. Printer summaries include an extra two-byte wrapper allowance.',
            'ARCADD $5163..$5171 executes the initialized three-byte compare loop exactly three times. Recursive edges $56F7/$5713 are summarized compositionally against the real native entry check at $5684.',
            'ARCADD entry frame >=$01A0 permits the next four-byte descent; a failing entry remains >=$019C and returns SDX 158 before deeper execution. Rooted overlay continuations compose with the bounded main region.',
            'BASIC token/action leaf roots terminate at next_instruction or EXE_END. Arbitrary USR is excluded by public syntax. Bootstrap USR has one word and only the fixed argument/error/diagnostic/parser callbacks.',
            'BASIC E_ELSEIF patches a live nonzero bytecode address. Grammar records use 256 private-bank bytes plus three bookkeeping bytes, bounded to 63 live states; they do not accumulate CPU frames. Pure parser states check $01A4 (conservative 19-byte envelope). Action entry checks $01A7 after three temporary saves, then restores them before its 26-byte leaf/interrupt envelope. Parser errors restore saved_cpu_stack before output; pinned callers provide S >=$01D0.',
            'ROM CIO is IOCB0 PUT CHARACTERS to the standard E: handler. ScreenOpenGr0 can retry only once after selecting mode zero. Native VBI/clock hooks, owned IRQ handlers and no third-party vectors form the reviewed interrupt chain.',
            'One nested CIO VBI uses the direct emulation dispatcher. Deeper NMIs only acknowledge. The six-byte return tail retires within one PAL VBI interval under the selected IRQ budget; no Task switch occurs across ROM.',
        ],entry_inventory=entry_inventory(),
        source_sha256={str(p.resolve().relative_to(ROOT)):digest(p) for p in paths},
        binary_sha256={str(p.relative_to(ROOT)):digest(p) for p in binaries},
        reserved_bank_zero_delta=dict(fixed=0,root_kernel=0,per_public_task=[0]*12,idle=0))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();result=audit()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(result['status'],result['minimum_complete_s'],'ROM',result['rom']['peak_bytes'],'of',result['rom_reserve'])
