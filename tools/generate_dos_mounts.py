"""Validate explicit read-only filesystem mounts and encode upper-RAM specs."""
import argparse,json,re,struct
from pathlib import Path
from filesystem_formats import DEFAULT, FORMATS, MYDOS
ALIAS=re.compile(r'[0-9@A-Z_`a-z]{1,31}\Z')
FIELDS={'alias','unit','sectors','sector_bytes','profile','boot','format'}
def require(ok,message):
    if not ok:raise ValueError(message)
def validate_mounts(mounts):
    require(isinstance(mounts,(list,tuple)) and len(mounts)<=8,'Mount list must contain at most eight units')
    aliases=set();units=set();result=[]
    for number,mount in enumerate(mounts):
        require(isinstance(mount,dict),'Mount must be an object')
        require(not set(mount)-FIELDS,'Unknown mount field')
        require({'alias','unit','sectors','sector_bytes'}<=set(mount),'Incomplete mount geometry')
        name=mount['alias'];require(isinstance(name,str) and ALIAS.fullmatch(name),'Invalid mount alias')
        require(name.upper() not in {'NIL','RAW','CON','CONSOLE','SYS'},'Reserved DOS alias')
        spec=dict(profile=1,boot=1,format=DEFAULT);spec.update(mount)
        for key in FIELDS-{'alias'}:require(type(spec[key]) is int,'Mount '+key+' must be an integer')
        require(49<=spec['unit']<=56,'SIO unit must be 49..56')
        require(1<=spec['sectors']<=65535,'Geometry must have 1..65535 sectors')
        if spec['format']==MYDOS: require(spec['sectors']>=368,'MyDOS needs at least 368 sectors')
        require(spec['sector_bytes'] in (128,256),'Data sectors must be 128 or 256 bytes')
        require(spec['boot']==1,'Only three short boot sectors are supported')
        require(spec['format'] in FORMATS,'Unknown filesystem format')
        require(spec['profile'] in (1,2,4) and (spec['profile']!=2 or spec['sector_bytes']==128),'Unqualified profile/sector size')
        require(name.upper() not in aliases,'Duplicate mount alias')
        require(spec['unit'] not in units,'A SIO unit may only be mounted once')
        aliases.add(name.upper());units.add(spec['unit']);result.append(spec)
    return result
def encode(mounts):
    data=bytearray()
    for spec in validate_mounts(mounts):
        data+=struct.pack('<32sHHIHBB',spec['alias'].encode('ascii'),spec['unit'],spec['profile'],spec['sectors'],spec['sector_bytes'],spec['boot'],spec['format'])
    return bytes(data)
def select_system(mounts, name=None):
    """Resolve an explicit system volume; list order is never a default."""
    if name is None:
        return dict(system_slot=255, system_drive=0, allowed_drives=0)
    require(isinstance(name,str), 'system_mount must be a mount name')
    slots=[i for i,m in enumerate(mounts) if m['alias'].upper()==name.upper()]
    require(len(slots)==1, 'system_mount must identify a configured mount')
    slot=slots[0]
    mount=mounts[slot]
    drive=mount['unit']-48
    require(mount['alias'].upper()==f'D{drive}', 'System mount must use D1..D8 matching its SIO unit')
    # The monitor can reject conflicts without retaining filesystem objects.
    allowed=0
    for candidate in range(1,9):
        if all(i==slot or (m['unit']!=48+candidate and m['alias'].upper()!=f'D{candidate}')
               for i,m in enumerate(mounts)):
            allowed |= 1 << (candidate-1)
    return dict(system_slot=slot, system_drive=drive, allowed_drives=allowed)


def load(path):
    config=json.loads(Path(path).read_text())
    require(isinstance(config,dict) and 'mounts' in config and
            not set(config)-{'mounts','system_mount'}, 'Unknown or missing mount configuration field')
    mounts=validate_mounts(config['mounts'])
    select_system(mounts,config.get('system_mount'))
    return dict(mounts=mounts,system_mount=config.get('system_mount'))
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('config',type=Path);p.add_argument('--output',type=Path);a=p.parse_args()
    mounts=load(a.config)['mounts'];data=encode(mounts)
    if a.output:a.output.write_bytes(data)
    print(f'Validated {len(mounts)} mounts ({len(data)} descriptor bytes)')
