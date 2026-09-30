#!/usr/bin/env python3
"""Execute intrusive Lists against independent ordered-node models on Altirra."""
from library_paths import read_source
import argparse
import json
from pathlib import Path
import random
import re

from native_program import (ROOT, build, compiler, execute, platform_files,
                            require, sha256, verify_machine)
from os_boundary import emulator
from test_banked import PIN, changed_image
from test_cooperative import data
from banked_test_memory import read as far_read

SEED = 0x81650
STRIDE = 512
SNAPSHOT_BYTES = 325
PAIR_ADDRESSES = [0x048e01, 0x058e01, 0x05fffe, 0x068e02]


def instrument(source):
    """Insert test calls after scalar link writes, retaining LF/CRLF semantics."""
    source = source.replace('\r\n','\n')
    require(source.count('MODULE EXECLISTS\n') == 1, 'Missing Lists module')
    source = source.replace('MODULE EXECLISTS\n', 'MODULE EXECLISTS\nUSE LISTSPROBE\n',1)
    result,sites = [],[]
    for line in source.splitlines():
        result.append(line)
        if re.fullmatch(r'\s+[a-z]+\.(?:lh_Head|lh_Tail|lh_TailPred|ln_Pred|ln_Succ)=[^\n]+',line):
            sites.append(line.strip())
            result.append(f'  LISTSPROBE.Checkpoint({len(sites)-1})')
    require(len(sites) == 17, f'Unexpected link-write sites: {len(sites)}')
    return '\n'.join(result)+'\n',sites


def pointer(value):
    return value.to_bytes(3, 'little')


def validate_snapshot(snapshot, model):
    """Bounded independent forward/backward walks of target-produced links."""
    memory,offset = {},5
    for address,size in model.regions:
        memory.update((address+i,snapshot[offset+i]) for i in range(size))
        offset += size
    def read(address):
        return int.from_bytes(bytes(memory[address+i] for i in range(3)),'little')
    used = set()
    orders = []
    for header in model.headers:
        head,tail = read(header),read(header+6)
        require(read(header+3) == 0, 'Nonzero tail sentinel successor')
        cursor,previous,forward = head,header,[]
        while cursor != header+3:
            require(cursor in model.nodes and cursor not in used and len(forward)<8,
                    'Unknown, duplicate or cyclic node in forward traversal')
            require(read(cursor+3) == previous,'Broken previous link')
            used.add(cursor);forward.append(cursor)
            previous,cursor = cursor,read(cursor)
        require(previous == tail,'Wrong tail or inconsistent empty header')
        cursor,following,backward = tail,header+3,[]
        while cursor != header:
            require(cursor in model.nodes and cursor not in backward and len(backward)<8,
                    'Unknown or cyclic node in backward traversal')
            require(read(cursor) == following,'Broken next link')
            backward.append(cursor)
            following,cursor = cursor,read(cursor+3)
        require(following == head and backward == forward[::-1],'Traversal directions disagree')
        orders.append([model.nodes.index(a) for a in forward])
    return orders


class Model:
    """Sequence semantics; derive links afresh rather than imitating rewiring."""
    def __init__(self, far_header=False):
        self.headers = [0x048d11 if far_header else 0x008d11, 0x04fffe]
        self.nodes = PAIR_ADDRESSES + [a+8 for a in PAIR_ADDRESSES]
        self.regions = [(self.headers[0]-17, 32), (0x04fff0, 32),
                        (0x048df0, 48), (0x058df0, 48), (0x05fff0, 48),
                        (0x068df0, 48), (0x008df0, 64)]
        self.initial = {a+i: 0xa5 for a,n in self.regions for i in range(n)}
        for a in self.nodes:
            for i in range(6):
                self.initial[a+i] = 0
        self.queues = [[], []]
        self.state = dict(self.initial)
        self.render()
        self.trace = []
        self.expected = bytearray()

    def render(self):
        # Derive only live links from sequence order. Detached nodes retain the
        # bytes from their last membership, matching Exec's unspecified links.
        def put(address, value):
            for i,b in enumerate(pointer(value)):
                self.state[address+i] = b
        for address,order in zip(self.headers, self.queues):
            put(address, self.nodes[order[0]] if order else address+3)
            put(address+3, 0)
            put(address+6, self.nodes[order[-1]] if order else address)
            for i,member in enumerate(order):
                put(self.nodes[member], self.nodes[order[i+1]] if i+1 < len(order) else address+3)
                put(self.nodes[member]+3, self.nodes[order[i-1]] if i else address)

    def apply(self, op, q=0, node=255, after=255):
        queue = self.queues[q]
        result = 0
        if op == 0:
            assert not queue
        elif op == 1:
            pass
        elif op in (2, 3, 4, 9, 10):
            assert node < 8 and all(node not in other for other in self.queues)
            at = 0 if op in (2,9) or (op == 4 and after == 255) else (
                len(queue) if op in (3,10) else queue.index(after)+1)
            queue.insert(at, node)
        elif op == 5:
            queue.remove(node)
        elif op in (6, 7):
            if queue:
                result = self.nodes[queue.pop(0 if op == 6 else -1)]
        elif op == 8:
            while queue:
                queue.pop(0)
                self.render()
        else:
            raise ValueError(op)
        self.render()
        snapshot = pointer(result)+bytes(int(not order) for order in self.queues)
        snapshot += bytes(self.state[a+i] for a,n in self.regions for i in range(n))
        assert len(snapshot) == SNAPSHOT_BYTES
        self.expected += snapshot + bytes([0xa5])*(STRIDE-len(snapshot))
        self.trace.append([op,q,node,after])

    def fixture(self):
        for q in (0, 1):
            self.apply(0,q); self.apply(0,q); self.apply(1,q)
            self.apply(6,q); self.apply(7,q)
        for insert in (2,3,4,9,10):
            for remove in (5,6,7):
                self.apply(insert,0,0)
                self.apply(1,0)
                self.apply(remove,0,0)
        # Two nodes embedded in each payload belong to independent queues.
        for n in range(8):
            self.apply(3,n//4,n)
        self.apply(5,0,1); self.apply(4,0,1,0)  # middle
        self.apply(5,0,3); self.apply(4,0,3,2)  # after last
        self.apply(5,0,0); self.apply(4,0,0)    # null predecessor
        self.apply(5,1,6); self.apply(2,0,6)    # transfer between lists
        self.apply(8,0); self.apply(8,1)       # saved-next traversal
        self.apply(9,1,0); self.apply(10,1,3)
        self.apply(9,1,2); self.apply(10,1,1)
        self.apply(8,1)
        rng = random.Random(SEED)
        for _ in range(32):
            q = rng.randrange(2)
            free = [n for n in range(8) if all(n not in order for order in self.queues)]
            op = rng.choice([1,6,7] + ([2,3,4] if free else []) + ([5] if self.queues[q] else [0]))
            n = rng.choice(free) if op in (2,3,4) else (
                rng.choice(self.queues[q]) if op == 5 else 255)
            after = rng.choice([255]+self.queues[q]) if op == 4 else 255
            self.apply(op,q,n,after)
        for q in (0,1):
            while self.queues[q]:
                self.apply(6 if len(self.queues[q]) & 1 else 7,q)
            self.apply(6,q); self.apply(7,q)
        return self


def sequential_build(toolchain, output, optimize, far_header):
    output.mkdir(parents=True, exist_ok=True)
    model = Model(far_header).fixture()
    constants = {'HEADER0':model.headers[0], 'HEADER1':model.headers[1],
                 'HEADER0_BASE':model.regions[0][0], 'HEADER1_BASE':model.regions[1][0],
                 'STEP_COUNT':len(model.trace)}
    for i,address in enumerate(PAIR_ADDRESSES):
        constants[f'PAIR{i}'] = address
        constants[f'PAIR{i}_BASE'] = model.regions[2+i][0]
    (output/'lists-case.inc').write_text(''.join(f'CONST T_{k}=${v:06x}\n' for k,v in constants.items()))
    (output/'lists.act').write_text((ROOT/'tests/programs/lists.act').read_text())
    program = build(toolchain, output/'lists.act', output, optimize=optimize,
                    banked=True, kernel_init_name='LISTSTEST.KernelInit')
    for address,size in model.regions:
        program['image']['segments'].append({'address':address,
            'bytes':[model.initial[address+i] for i in range(size)],'writable':True,'executable':False})
    program['image']['segments'].append({'address':0x070000,
        'bytes':[x for step in model.trace for x in step], 'writable':False,'executable':False})
    program['image']['segments'].append({'address':0x07fff0,
        'bytes':[0xa5]*(len(model.trace)*STRIDE+32), 'writable':True,'executable':False})
    changed_image(program)
    (output/'trace.json').write_text(json.dumps({'seed':SEED,'operations':model.trace},indent=2)+'\n')
    (output/'expected.bin').write_bytes(model.expected)
    return program, model


def library_facts(program):
    routines = [r for r in program['image']['routines'] if r['name'].startswith('M_EXECLISTS_')]
    require(len(routines) == 12, 'Lists API routines missing')
    for r in routines:
        require(all(a['size'] == 3 and a['alignment'] == 1 for a in r['arguments']),
                f'Non-native Lists pointer argument: {r}')
        if r['name'].startswith(('M_EXECLISTS_REMHEAD_', 'M_EXECLISTS_REMTAIL_', 'M_EXECLISTS_FINDNAME_')):
            require(r['result_bytes'] == 3, 'Truncated Lists result')
    return routines


def ownership(bridge, program):
    c = program['build']['memory']['constants']
    seed = (program['output']/'manifest.bin').read_bytes()[32:32+c['TABLE_BYTES']]
    require(bridge.memdump(c['TABLE'],len(seed)) == seed, 'Lists altered bank ownership')
    require(bridge.memdump(c['ADOPTED'],2) == b'\1\0', 'Kernel adoption failed')


def sequential_case(bridge, toolchain, output, optimize, far_header):
    program,model = sequential_build(toolchain,output,optimize,far_header)
    facts = library_facts(program)
    result,screen = execute(bridge,program,frame_limit=1200,timeout=60)
    require(data(bridge,program['image'],'completed',True) == [len(model.trace)], 'Trace incomplete')
    require(data(bridge,program['image'],'writeStatus',True) == [1], 'Console failed')
    raw = bytes(data(bridge,program['image'],'layoutFacts'))
    observed_layout = [int.from_bytes(raw[i:i+3],'little') for i in range(0,len(raw),3)]
    require(observed_layout == [6,9,3,3,0,8,14,model.nodes[6],6,11,11,6,7,8,6,9,10], f'Wrong record layout: {observed_layout}')
    ownership(bridge,program)
    observed = far_read(bridge,0x07fff0,len(model.expected)+32,output)
    (output/'observed.bin').write_bytes(observed)
    for index in range(len(model.trace)):
        at = 16+index*STRIDE
        validate_snapshot(observed[at:at+SNAPSHOT_BYTES],model)
    expected = bytes([0xa5])*16+model.expected+bytes([0xa5])*16
    if observed != expected:
        offset = next(i for i,(a,b) in enumerate(zip(observed,expected)) if a != b)
        raise RuntimeError(f'Trace mismatch at byte {offset}, step {(offset-16)//STRIDE}: '
                           f'{observed[offset]:02x} != {expected[offset]:02x}')
    require(bytes([44,41,51,52,51]) in screen, 'Lists output missing')
    require(result['clock_start'] != result['clock_end'], 'OS clock stopped')
    return {'build':program['build'], 'runtime':result, 'layout':observed_layout,
            'regions':model.regions,'steps':len(model.trace),'seed':SEED,
            'trace_sha256':sha256(output/'trace.json'),'expected_sha256':sha256(output/'expected.bin'),
            'observed_sha256':sha256(output/'observed.bin'),'library_routines':facts}


def preemptive_case(bridge,toolchain,output,optimize,shared,probe,timeout=60):
    output.mkdir(parents=True,exist_ok=True)
    (output/'lists_preemptive.act').write_text((ROOT/'tests/programs/lists_preemptive.act').read_text())
    (output/'listsprobe.act').write_text((ROOT/'tests/programs/lists_probe.act').read_text())
    rounds = 1 if shared or probe else 16
    (output/'lists-mode.inc').write_text(f'CONST T_SHARED={int(shared)}\nCONST T_PROBE={int(probe)}\nCONST T_ROUNDS={rounds}\n')
    source = read_source(ROOT/'lib/exec/execlists.act')
    if probe:
        source,sites = instrument(source)
    else:
        sites = []
    (output/'execlists.act').write_text(source)
    program = build(toolchain,output/'lists_preemptive.act',output,optimize=optimize,
                    banked=True,preemptive=True,kernel_init_name='LISTSPREEMPT.KernelInit')
    regions = [(0x048cf0,64),(0x058cf0,64)]
    for address,size in regions:
        program['image']['segments'].append({'address':address,'bytes':[0xa5]*size,
                                             'writable':True,'executable':False})
    changed_image(program)
    facts = library_facts(program)
    result,screen = execute(bridge,program,frame_limit=1200,timeout=timeout,timer_irq=probe)
    observed = {}
    for name,expected in [('failures',[0,0]),('rounds',[rounds,rounds]),
                          ('outputStatus',[1,1]),('probeFailures',[0,0])]:
        observed[name] = data(bridge,program['image'],name,True)
        require(observed[name] == expected, f'{name}: {observed[name]} != {expected}')
    if shared:
        observed['pendingProof'] = data(bridge,program['image'],'pendingProof',True)
        require(observed['pendingProof'] == [1,0], 'Outermost unlock did not deliver pending peer work')
        require(data(bridge,program['image'],'mutations',True) == [2], 'Shared transfers lost')
    require(result['vbi_dispatches'] > 0 and result['switches'] >= 2,'No preemption')
    require(result['clock_start'] != result['clock_end'],'OS clock stopped')
    require(result['os_calls'] == result['forwarded_cops'] == 2,'OS console forwarding failed')
    if probe:
        observed['probeVisits'] = data(bridge,program['image'],'probeVisits',True)
        observed['probeOverlaps'] = data(bridge,program['image'],'probeOverlaps',True)
        require(min(observed['probeVisits']) > 30,'Link-write checkpoints missed')
        require(result['native_irq_count'] > 0,'No timer IRQ in checkpoint case')
        if shared:
            require(observed['probeOverlaps'] == [0,0],'Locked mutation overlapped a peer')
            observed['sites'] = data(bridge,program['image'],'sites',True)[:len(sites)]
            require(min(observed['sites']) > 0,'A link-write checkpoint was not reached')
            require(sum(observed['sites']) == sum(observed['probeVisits']),'Checkpoint counts lost')
        else:
            require(sum(observed['probeOverlaps']) > 0,'Private invocations never overlapped')
    ownership(bridge,program)
    for n,(address,size) in enumerate(regions):
        expected = bytearray([0xa5]*size)
        if not shared or n == 0:
            header = address+17
            expected[17:26] = pointer(header+3)+pointer(0)+pointer(header)
            a,b,c,d = (header+10+i*6 for i in range(4))
            links = [(c,d),(d,header),(header+3,d),(header+3,header)]
            for i,(succ,pred) in enumerate(links):
                expected[27+i*6:33+i*6] = pointer(succ)+pointer(pred)
        actual = far_read(bridge,address,size,output)
        require(actual == expected,f'List storage/guards differ at {address:x}: {actual.hex()}')
    require(bytes([44,16]) in screen and bytes([44,17]) in screen,'Task output missing')
    return {'build':program['build'],'runtime':result,'program':observed,'regions':regions,
            'probe':probe,'shared':shared,'checkpoint_sites':sites,
            'compiled_lists_sha256':sha256(output/'execlists.act'),'library_routines':facts}


def named_case(bridge,toolchain,output,optimize):
    """Exercise full Node metadata, signed priority, borrowed far names and guards."""
    output.mkdir(parents=True,exist_ok=True)
    header = 0x04fffe
    nodes = [0x048e01,0x058e01,0x05fffd,0x068e01,0x048e41,0x058e41,0x068e41,0x078e41]
    priorities = [0,127,-128,-1,127,1,0,-128]
    order = sorted(range(8),key=lambda i:-priorities[i])  # Stable sort gives FIFO ties.
    # Equal low words in different banks and a string crossing $06:FFFF.
    strings = {0x048d01:b'alpha\0',0x058d01:b'alpha\0',0x06fffe:b'beta\0'}
    queries = [b'alpha',b'ALPHA',b'Alpha',b'',b'beta',b'alp',b'alphabet',b'gamma',b'missing']
    strings.update({0x078d00+i*16:q+b'\0' for i,q in enumerate(queries)})
    names = [0x078d30,0x048d01,0x078d60,0x06fffe,0x058d01,0x078d10,0,0x078d70]
    initial = {a-1:bytes([0xa5])+bytes([0xa5])*6+bytes([i+1,pri & 255])+pointer(name)+bytes([0xa5])
               for i,(a,pri,name) in enumerate(zip(nodes,priorities,names))}
    initial[header-14] = bytes([0xa5])*32
    initial.update(strings)
    (output/'lists-named.inc').write_text(f'CONST T_HEADER=${header:06x}\n'+
        'ADDRESS ARRAY nodeAddresses=['+' '.join(f'${a:06x}' for a in nodes)+']\n')
    (output/'lists_named.act').write_text((ROOT/'tests/programs/lists_named.act').read_text())
    program = build(toolchain,output/'lists_named.act',output,optimize=optimize,
                    banked=True,kernel_init_name='LISTSNAMED.KernelInit')
    for address,blob in initial.items():
        program['image']['segments'].append({'address':address,'bytes':list(blob),
                                             'writable':True,'executable':False})
    changed_image(program)
    result,screen = execute(bridge,program,frame_limit=1200,timeout=60)
    require(data(bridge,program['image'],'completed',True) == [1], 'Named list did not drain')
    observed = {}
    for name,expected in [('ordered',[nodes[i] for i in order]),('removed',[nodes[i] for i in order]),
                          ('found',[0,nodes[1],nodes[4],0,nodes[5],0,nodes[0],nodes[3],0,nodes[2],nodes[7],0])]:
        raw = bytes(data(bridge,program['image'],name))
        observed[name] = [int.from_bytes(raw[i:i+3],'little') for i in range(0,len(raw),3)]
        require(observed[name] == expected, f'{name}: {observed[name]} != {expected}')
    expected_memory = dict(initial)
    raw = bytearray(expected_memory[header-14])
    raw[14:23] = pointer(header+3)+pointer(0)+pointer(header)
    expected_memory[header-14] = bytes(raw)
    for position,i in enumerate(order):
        raw = bytearray(expected_memory[nodes[i]-1])
        raw[1:7] = pointer(nodes[order[position+1]] if position+1<len(order) else header+3)+pointer(header)
        expected_memory[nodes[i]-1] = bytes(raw)
    for address,expected in expected_memory.items():
        actual = far_read(bridge,address,len(expected),output)
        require(actual == expected, f'Named list data/guard changed at {address:x}: {actual.hex()}')
    ownership(bridge,program)
    return {'build':program['build'],'runtime':result,'program':observed,
            'priorities':priorities,'order':order,'nodes':nodes,'header':header,
            'regions':[(a,len(b)) for a,b in initial.items()],'library_routines':library_facts(program)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler-dir',type=Path,required=True)
    parser.add_argument('--bridge-dir',type=Path,required=True)
    parser.add_argument('--rom',type=Path,default=ROOT/'build/firmware/altirraos-816.rom')
    parser.add_argument('--case')
    parser.add_argument('--allow-compiler-override',action='store_true')
    args = parser.parse_args()
    toolchain = compiler(args.compiler_dir,args.allow_compiler_override)
    bridge_dir,rom = args.bridge_dir.resolve(),args.rom.resolve()
    platform_files(bridge_dir,rom)
    output = ROOT/'build/lists-tests'; output.mkdir(parents=True,exist_ok=True)
    cases = [(f'{"far" if far else "near"}-{mode}','sequential',optimize,far,False)
             for mode,optimize in (('raw',False),('opt',True)) for far in (False,True)]
    cases += [(f'{"shared" if shared else "private"}{"-probe" if probe else ""}-{mode}',
               'preemptive',optimize,shared,probe)
              for mode,optimize in (('raw',False),('opt',True))
              for shared in (False,True) for probe in (False,True)]
    cases += [(f'named-{mode}','named',optimize,False,False)
              for mode,optimize in (('raw',False),('opt',True))]
    if args.case:
        cases = [c for c in cases if c[0] == args.case]
        require(cases,f'Unknown case: {args.case}')
    report = {'schema_version':1,'platform':PIN,'status':'running','cases':[],
              'inputs':{str(p.relative_to(ROOT)):sha256(p) for folder in ('tools','tests','tests/programs','lib','abi','config','platform/altirraos','toolchain')
                        for p in sorted((ROOT/folder).glob('**/*' if folder=='lib' else '*')) if p.is_file()}}
    report_file = output/(f'{args.case}.json' if args.case else 'results.json')
    try:
        with emulator(bridge_dir,rom,output,pin=PIN) as bridge:
            report['emulator_config'] = verify_machine(bridge,rom,PIN)
            for name,kind,optimize,flag,probe in cases:
                print(f'Running {name}...',flush=True)
                if kind == 'sequential':
                    observed = sequential_case(bridge,toolchain,output/name,optimize,flag)
                elif kind == 'named':
                    observed = named_case(bridge,toolchain,output/name,optimize)
                else:
                    observed = preemptive_case(bridge,toolchain,output/name,optimize,flag,probe)
                report['cases'].append({'name':name,'status':'pass','observed':observed})
        report['status'] = 'pass'
    except Exception as error:
        report['status'] = 'fail'; report['error'] = str(error)
        raise
    finally:
        report_file.write_text(json.dumps(report,indent=2)+'\n')
    print(f'Passed {len(cases)} Lists cases; report: {report_file}')


if __name__ == '__main__':
    main()
