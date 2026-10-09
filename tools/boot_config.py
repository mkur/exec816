"""The shared loader/monitor boot record; settings are captured before admission."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ABI = json.loads((ROOT/'abi/boot-v1.json').read_text())


def valid_blocks(value):
    return type(value) is int and (value == 0 or
        ABI['cache']['minimum'] <= value <= ABI['cache']['maximum'] and
        value & (value-1) == 0)


def describe(memory):
    default = memory['config'].get('cache_blocks', ABI['cache']['default'])
    if not valid_blocks(default):
        raise ValueError('cache_blocks must be zero or a power of two from 16 through 2048')
    low, high = memory['regions']['boot-state']
    address = low + ABI['boot_state_offset']
    # memory-v1 reserves WORK+0..9; all preceding fields end before WORK.
    if not low + memory['abi']['boot_fields']['WORK'] + 10 <= address or address+ABI['size'] > high:
        raise ValueError('Boot parameters overlap loader state or exceed its reservation')
    return dict(abi=ABI, address=address, cache_blocks=default, system_drive=0)


def definitions(record):
    values = dict(ADDRESS=record['address'], MAGIC=ABI['magic'], VERSION=ABI['version'],
                  SETTINGS=record.get('settings', 0),
                  SYSTEM_SLOT=record.get('system_slot', 255), DEFAULT_DRIVE=record['system_drive'],
                  ALLOWED_DRIVES=record.get('allowed_drives', 0),
                  SIZE=ABI['size'], DEFAULT_BLOCKS=record['cache_blocks'],
                  MIN_BLOCKS=ABI['cache']['minimum'], MAX_BLOCKS=ABI['cache']['maximum'],
                  BLOCK_BYTES=ABI['cache']['block_bytes'])
    values.update(DEFAULT_FLAGS=ABI['default_flags'], FLAG_VERBOSE=ABI['flags']['VERBOSE'])
    values.update({'FIELD_'+key.upper(): value for key,value in ABI['fields'].items()})
    return values


def reserve_settings(memory):
    start = memory['profile']['code_origin']
    if start < 65536 or start & 1 or start+4 > (memory['constants']['KERNEL_BANK']+1)*65536:
        raise ValueError('Boot settings do not fit the upper kernel bank')
    memory['upper_reservations'].append(dict(name='boot-settings', address=start, size=4))
    memory['profile']['code_origin'] = start+4
    memory['boot_config']['settings'] = start


def files(record):
    values = definitions(record)
    return {
        'boot-config.inc': '; Generated boot ABI; do not edit.\n'+''.join(
            f'B_{key} = ${value:x}\n' for key,value in values.items()),
        'boot-config-action.inc': '; Generated boot ABI; do not edit.\n'+''.join(
            f'PUBLIC CONST B_{key}=${value:x}\n' for key,value in values.items()),
    }
