"""Fixture controls for actual QED acquisition failures; no production protocol."""
import json,struct
from native_program import require

CASES=['Stop warm-up','application AES acquisition','workstation acquisition',
       'resource acquisition','menu publication','window creation','window opening',
       'missing resource','malformed resource','private allocation 1',
       'private allocation 2','private allocation 3','private allocation 4','Stop reuse']


def interact(bridge,program,app,record,owner):
    cycle_at=next(d['address'] for d in program['image']['data']
                  if d['name'].startswith('M_CPROCESSTEST_CYCLE_'))
    cycle=int.from_bytes(bridge.memdump(cycle_at,2),'little')
    delta=owner['image_base']-(app['abi']['link_bank']<<16)
    symbols={n:a+delta for n,a in app['image']['symbols'].items()}
    def get(name,size=2):return int.from_bytes(bridge.memdump(symbols[name],size),'little')
    # The loaded image is owned but its ordinary entry has not run yet.
    # Check partial-window rollback immediately after warm-up.
    point=[0,6,1,2,3,4,5,7,8][cycle] if cycle<=8 else 0
    at=cycle-8 if 9<=cycle<=12 else 0
    bridge.memload(symbols['QedFailurePoint'],struct.pack('<H',point))
    bridge.memload(symbols['QedFailureAt'],struct.pack('<H',at))
    scene=dict(cycle=cycle,name=CASES[point if point else cycle],process=owner['identity'],point=point,allocation_at=at)
    record.setdefault('qed_failures',[]).append(scene)
    print('QED lifecycle:',scene['name'],flush=True)
    def retired():
        scene.update(hits=get('QedFailureHits'),allocation_calls=get('QedFailureCalls'),
                     heap=list(struct.unpack('<4I',bridge.memdump(symbols['totals'],16))))
        require(scene['hits']>0 if point or at else scene['hits']==0,'Fault did not execute: '+str(scene))
        require(not any(scene['heap'][:3]) and get('owned',4)==0,'QED private heap survived retirement')
        require(get('__menu_tree',4)==0 and get('rsc_init')==0 and get('used_list',4)==0,
                'QED retained a menu/resource/window owner')
        provider=json.loads((program['output'].parent/'c-image.json').read_text())
        from generate_aes_server import ABI
        require(not any(bridge.memdump(provider['symbols']['contexts'],ABI['constants']['CONTEXTS']*4)),
                'A native AES context survived retirement')
    return retired
