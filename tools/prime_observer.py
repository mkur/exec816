"""Read private loaded PRIMES state for development observations only."""
import json
from native_program import require


def process_record(read, program, identity):
    base = program['build']['memory']['process_storage']['BASE']
    for slot in range(1, 8):
        row = base+128*slot
        if int.from_bytes(read(row+82, 4), 'little') == identity:
            return row
    raise RuntimeError('Missing owned Process identity '+str(identity))


def symbols(read, program, bundle, identity):
    row = process_record(read, program, identity)
    image = int.from_bytes(read(row+118, 3), 'little')
    require(image != 0, 'PRIMES image already collected')
    sections = {name:int.from_bytes(read(image+offset,3),'little')
                for name,offset in [('Data',13),('Bss',16),('Text',36)]}
    profile = json.loads((bundle/'PRIMES.profile.json').read_text())
    return {item['name'].split('_PRIMES_',1)[1].rsplit('_',1)[0].lower():
            (sections[item['location']['section']]+item['location']['offset'],item['size'])
            for item in profile['objects'] if item['kind']==0 and '_PRIMES_' in item['name']}


def state(read, program, bundle, identity):
    objects = symbols(read, program, bundle, identity)
    result = {name:int.from_bytes(read(*objects[name]),'little')
              for name in ('candidate','count','latest','pass','pane','savedcount','savedlatest','savedpass')}
    result['progress'] = max(0,result['pass']-1)*10000+result['candidate']
    return result
