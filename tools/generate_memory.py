#!/usr/bin/env python3
"""Generate isolated Action/assembly/JSON memory definitions for a kernel build."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ABI = ROOT / 'abi/memory-v1.json'
CONFIG = ROOT / 'config/kernel.json'
PROFILE = ROOT / 'platform/altirraos/memory-1m.json'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def integer(value, low, high, name):
    require(type(value) is int and low <= value <= high, f'Invalid {name}')
    return value


def layout(config=CONFIG, profile=PROFILE, max_banks=None, kernel_bank=None, upper_table=False):
    cfg = json.loads(Path(config).read_text())
    platform = json.loads(Path(profile).read_text())
    abi = json.loads(ABI.read_text())
    # Version 1 is a fixed wire contract, not a runtime-selectable schema.
    # Struct packing and the Action record declaration below must agree with it.
    require(abi['version'] == 1 and abi['record_size'] == 4
            and abi['bank_fields'] == {'state':0,'reserved':1,'owner':2}
            and abi['manifest']['header_size'] == 32 and abi['manifest']['extent_size'] == 8
            and abi['manifest']['fields'] == {'magic':0,'version':4,'banks':6,'extents':8,
                                             'entry':10,'reserved':13,'size':14,'identity':16}
            and abi['manifest']['extent_fields'] == {'address':0,'kind':3,'size':4,'owner':6}
            and [abi['manifest'][k] for k in ('copy','zero','executable')] == [0,1,2]
            and abi['states'] == {'UNAVAILABLE':0,'FREE':1,'RESERVED':2,'OWNED':3}
            and abi['owners'] == {'SYSTEM':1,'IMAGE':2,'CLIENT_A':3,'CLIENT_B':4,'HEAP':5}
            and abi['record'] == {'size':8,'extent':0,'offset':2,'count':4,'kind':6,'reserved':7},
            'Unsupported memory wire layout')
    if max_banks is not None:
        cfg['max_banks'] = max_banks
    cfg['kernel_bank'] = cfg.get('kernel_bank',1) if kernel_bank is None else kernel_bank
    count = integer(cfg['max_banks'], 1, 256, 'MAX_BANKS')
    integer(cfg['max_extents'], 1, 64, 'extent capacity')
    integer(cfg['staging_bytes'], 1, 1024, 'staging capacity')
    regions = {}
    spans = []
    for region in platform['regions']:
        name = region['name']
        require(name not in regions, 'Duplicate region name')
        address = integer(region['address'], 0, 65535, 'region address')
        size = integer(region['size'], 1, 65536, 'region size')
        require(address + size <= 65536, 'Region wraps bank zero')
        regions[name] = [address, address + size]
        spans.append((address, address + size, name))
    spans.sort()
    require(all(a[1] <= b[0] for a, b in zip(spans, spans[1:])), 'Overlapping regions')
    table = regions['table'][0]
    require(table % 2 == 0 and count * abi['record_size'] <= regions['table'][1] - table,
            'Bank table does not fit')
    require(abi['manifest']['header_size'] + count * abi['record_size'] + cfg['max_extents'] * abi['manifest']['extent_size']
            <= regions['manifest'][1] - regions['manifest'][0], 'Manifest does not fit')
    require(cfg['staging_bytes'] + abi['record']['size']
            <= regions['staging'][1] - regions['staging'][0], 'Staging does not fit')
    require(regions['boot-state'][1] - regions['boot-state'][0] >= 256,
            'Boot state/work area does not fit')
    require(regions['resident'] == [0x3000,0x4000], 'Resident layout differs from hosted.cfg')
    fixed = {'os-low':[0,0x2000], 'state':[0x2000,0x2100],
             'task0-dp':[0x21f0,0x2310], 'task1-dp':[0x23f0,0x2510],
             'kernel-dp':[0x25f0,0x2710], 'task0-stack':[0x41f0,0x4810],
             'kernel-stack':[0x49f0,0x5010], 'task1-stack':[0x51f0,0x5810],
             'os-high':[0x9000,0x10000]}
    require(all(regions.get(k) == v for k,v in fixed.items()),
            'Fixed OS/adapter reservation differs from hosted layout')
    require(platform['image_near'] == [0x8800,0x9000]
            and platform['memlo_limit'] == 0x2000 and platform['memtop_required'] == 0x9000,
            'Memory bounds differ from hosted console/launch contract')
    usable = platform['usable_banks']
    require(len(usable) == len(set(usable)), 'Duplicate usable bank')
    for bank in usable:
        integer(bank, 1, 255, 'usable bank')
    kernel = integer(cfg['kernel_bank'],1,255,'KERNEL_BANK')
    require(kernel < count and kernel in usable,'Kernel bank is not usable')
    if upper_table:
        table = kernel << 16
        regions.pop('table')
        platform['regions'] = [r for r in platform['regions'] if r['name']!='table']
    platform['code_origin'] = (kernel << 16) + (count*abi['record_size'] if upper_table else 0)
    near_start, near_end = platform['image_near']
    require(0 < near_start < near_end <= 65536, 'Invalid near image arena')
    require(all(near_end <= a or near_start >= b for a, b, _ in spans),
            'Near image overlaps a reservation')
    c = {'VERSION': abi['version'], 'KERNEL_BANK':kernel, 'MAX_BANKS': count, 'TABLE': table,
         'TABLE_BYTES': count * abi['record_size'], 'MANIFEST': regions['manifest'][0],
         'MANIFEST_CAPACITY': regions['manifest'][1] - regions['manifest'][0],
         'MAX_EXTENTS': cfg['max_extents'], 'EXTENTS': regions['manifest'][0] + abi['manifest']['header_size'] + count * abi['record_size'],
         'LOADER': regions['loader'][0], 'LOADER_BYTES': regions['loader'][1] - regions['loader'][0],
         'STAGE': regions['staging'][0], 'PAYLOAD': regions['staging'][0] + abi['record']['size'],
         'CHUNK': cfg['staging_bytes'], 'NEAR_BASE': near_start, 'NEAR_END': near_end,
         'MEMLO_LIMIT': platform['memlo_limit'], 'MEMTOP_REQUIRED': platform['memtop_required']}
    boot = regions['boot-state'][0]
    for name, offset in abi['boot_fields'].items():
        c[name] = boot + offset
    for group, prefix in [('states','STATE'), ('errors','ERROR'), ('owners','OWNER'), ('boot_errors','BOOT_ERROR')]:
        c.update({f'{prefix}_{k}':v for k,v in abi[group].items()})
    c.update({'HEADER_BYTES':abi['manifest']['header_size'],
              'EXTENT_BYTES':abi['manifest']['extent_size'], 'RECORD_BYTES':abi['record']['size']})
    for fields, prefix in [(abi['record'], 'RECORD'), (abi['manifest']['fields'], 'HEADER'),
                           (abi['manifest']['extent_fields'], 'EXTENT')]:
        c.update({f'{prefix}_{k.upper()}':v for k,v in fields.items() if k != 'size' or prefix != 'RECORD'})
    # The table uses only the selected record count; the platform describes its
    # maximum arena so other build limits cannot collide with fixed adapters.
    if not upper_table:
        regions['table'] = [table, table + c['TABLE_BYTES']]
    memory = {'abi':abi, 'config':cfg, 'profile':platform, 'constants':c,
            'upper_reservations':([{'name':'bank-table','address':table,'size':c['TABLE_BYTES']}] if upper_table else []),
            'regions':regions, 'usable_banks':[b for b in usable if b < count]}
    from boot_config import describe
    memory['boot_config'] = describe(memory)
    return memory


def generate(output, memory, check=False):
    output = Path(output)
    c = memory['constants']
    assembly = '; Generated by tools/generate_memory.py; do not edit.\n'
    assembly += ''.join(f'M_{k} = ${v:04x}\n' for k,v in c.items())
    action = '; Generated by tools/generate_memory.py; do not edit.\n'
    action += ''.join(f'CONST M_{k}=${v:04x}\n' for k,v in c.items())
    action += 'PUBLIC TYPE BankRecord=[BYTE state BYTE reserved CARD owner]\n'
    text = json.dumps(memory, sort_keys=True, indent=2) + '\n'
    memory_hash = hashlib.sha256(text.encode()).hexdigest()
    files = {'memory.inc':assembly, 'memory-action.inc':action, 'memory.json':text}
    from boot_config import files as boot_files
    files.update(boot_files(memory['boot_config']))
    for name, content in files.items():
        path = output / name
        if check:
            require(path.is_file() and path.read_text().replace('\r\n','\n') == content,
                    f'Stale generated file: {path}')
        else:
            output.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
    return memory_hash


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=CONFIG)
    parser.add_argument('--profile', type=Path, default=PROFILE)
    parser.add_argument('--max-banks', type=int)
    parser.add_argument('--kernel-bank', type=int)
    parser.add_argument('--upper-table', action='store_true')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    generate(args.output, layout(args.config, args.profile, args.max_banks, args.kernel_bank, args.upper_table), args.check)


if __name__ == '__main__':
    main()
