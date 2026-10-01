#!/usr/bin/env python3
"""Generate isolated Action/assembly/JSON memory definitions for a kernel build."""
import adapter_state as adapter
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


def reservation_maps(memory, loading=None, initialization=None, runtime=None):
    """Publish checked phase ownership, including full reserved table capacity."""
    if runtime is None:
        live = [dict(r) for r in memory['profile']['regions']]
        loading = live
        initialization = [r for r in live if r['name'] not in ('loader','staging')]
        runtime = [r for r in initialization if r['name'] != 'manifest']
    phases = dict(loading=loading, initialization=initialization, runtime=runtime)
    for phase,regions in phases.items():
        regions.sort(key=lambda r:r['address'])
        require(all(type(r['address']) is int and type(r['size']) is int and
                    0 <= r['address'] < r['address']+r['size'] <= 65536 for r in regions),
                'Invalid bank-zero extent: '+phase)
        require(all(a['address']+a['size'] <= b['address'] for a,b in zip(regions,regions[1:])),
                'Bank-zero reservations overlap: '+phase)
    scratch = sorted((dict(r) for r in memory['profile']['test_scratch']), key=lambda r:r['address'])
    adapter.diagnostic_addresses(memory['profile'])
    require(all(a['address']+a['size'] <= b['address'] for a,b in zip(scratch,scratch[1:])),
            'Diagnostic scratch overlaps')
    for r in scratch:
        require(all(r['address']+r['size'] <= s['address'] or r['address'] >= s['address']+s['size']
                    for regions in phases.values() for s in regions),
                'Diagnostic scratch overlaps live storage: '+r['name'])
    free = []
    end = 0
    for r in runtime:
        if end < r['address']:
            free.append(dict(address=end,size=r['address']-end))
        end = r['address']+r['size']
    if end < 65536:
        free.append(dict(address=end,size=65536-end))
    memory.update(phase_reservations=phases,runtime_reservations=runtime,
                  runtime_free_ranges=free,diagnostic_scratch=scratch)


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
    require(adapter.resident_addresses(platform) == adapter.resident_addresses(),
            'Resident layout differs from generated hosted bindings')
    dp = adapter.direct_pages(platform)
    require(dp == adapter.direct_pages(), 'DP placement differs from generated hosted bindings')
    fixed = {'os-low':[0,adapter.STATE], 'state':[adapter.STATE,adapter.STATE+256],
             'task0-dp':[dp['TASK0_DP'],dp['TASK0_DP']+256],
             'task1-dp':[dp['TASK1_DP'],dp['TASK1_DP']+256],
             'kernel-dp':[dp['KERNEL_DP'],dp['KERNEL_DP']+256],
             'vbxe-aperture':[0x8000,0x9000],
             'os-high':[0x9000,0x10000]}
    stacks = adapter.stack_addresses()
    fixed.update({owner+'-stack':[stacks[owner.upper()+'_STACK_BASE']-16,
                                 stacks[owner.upper()+'_STACK_CEILING']+17]
                  for owner in ('task0','task1','kernel')})
    require(all(regions.get(k) == v for k,v in fixed.items()),
            'Fixed OS/adapter reservation differs from hosted layout')
    integer(platform['image_data_bytes'], 1, 65536, 'image data capacity')
    require(platform['memlo_limit'] == adapter.STATE and platform['memtop_required'] == 0x9000,
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
    c = {'VERSION': abi['version'], 'KERNEL_BANK':kernel, 'MAX_BANKS': count, 'TABLE': table,
         'TABLE_BYTES': count * abi['record_size'], 'MANIFEST': regions['manifest'][0],
         'MANIFEST_CAPACITY': regions['manifest'][1] - regions['manifest'][0],
         'MAX_EXTENTS': cfg['max_extents'], 'EXTENTS': regions['manifest'][0] + abi['manifest']['header_size'] + count * abi['record_size'],
         'LOADER': regions['loader'][0], 'LOADER_BYTES': regions['loader'][1] - regions['loader'][0],
         'STAGE': regions['staging'][0], 'PAYLOAD': regions['staging'][0] + abi['record']['size'],
         'CHUNK': cfg['staging_bytes'],
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
    memory = {'adapter_state':adapter.addresses(platform), 'abi':abi, 'config':cfg, 'profile':platform, 'constants':c,
            'upper_reservations':([{'name':'bank-table','address':table,'size':c['TABLE_BYTES']}] if upper_table else []),
            'regions':regions, 'usable_banks':[b for b in usable if b < count]}
    from boot_config import describe
    memory['boot_config'] = describe(memory)
    memory['reclaimed_after_startup'] = ['manifest']
    memory['startup_retirement'] = dict(address=c['RETIRED'], value=1,
        boundary='startup_complete', ranges=['manifest'])
    reservation_maps(memory)
    require(adapter.diagnostic_addresses(platform) == adapter.diagnostic_addresses(),
            'Diagnostic placement differs from generated hosted bindings')
    return memory


def reserve_image_data(memory):
    """Finalize compiled data after all metadata and before emitted code."""
    require('image_data' not in memory, 'Image data placement already finalized')
    profile = memory['profile']
    previous = profile['code_origin']
    start = (previous+255)//256*256
    size = profile['image_data_bytes']
    end = start+size
    bank = memory['config']['kernel_bank']
    require(start >> 16 == bank and end <= (bank+1)*65536,
            'Image data arena exceeds kernel bank')
    require(bank in memory['usable_banks'], 'Image data bank unavailable')
    require(all(end <= r['address'] or start >= r['address']+r['size']
                for r in memory['upper_reservations']), 'Image data overlaps metadata')
    if start > previous:
        memory['upper_reservations'].append(dict(name='image-data-alignment',
            address=previous,size=start-previous))
    memory['image_data'] = dict(address=start,size=size)
    profile.update(data_origin=start,code_origin=end)
    memory['constants'].update(IMAGE_DATA_BASE=start,IMAGE_DATA_END=end)


def validate_compiled_data(image, memory):
    """Bound ordinary compiler data before adding separately placed bindings."""
    arena = memory['image_data']
    low,high = arena['address'],arena['address']+arena['size']
    for region in [s for s in image['segments'] if not s['executable']]+image['zero_fill']:
        size = len(region['bytes']) if 'bytes' in region else region['size']
        require(low <= region['address'] < region['address']+size <= high,
                'Compiled data outside upper image arena')


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
