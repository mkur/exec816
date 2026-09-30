"""A checked command whose executable routines span more than one code bank."""
from pathlib import Path
import json
from build_command import compile_command
from o65_fixtures import inspect
from native_program import require


def make(toolchain, directory, mode):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    parts,steps=8,600
    source=['MODULE MULTIBANK','USE COMMAND']
    for part in range(parts):
        source += [f'BYTE FUNC Part{part}()', '  VOLATILE BYTE counter','  counter=0']
        source += ['  counter==+1']*steps
        source += ['RETURN(counter)']
    source += ['LONGINT FUNC Main()','  LONGINT total','  total=0']
    source += [f'  total==+LONGINT(Part{part}())' for part in range(parts)]
    source += ['  COMMAND.SetIoErr(total)','RETURN(COMMAND.RETURN_OK)','ENDMODULE']
    path=directory/'multibank.act';path.write_text('\n'.join(source)+'\n')
    artifact=directory/'BIG'
    record=compile_command(toolchain,path,artifact,mode=='opt')
    info=inspect(artifact.read_bytes())
    require(65536 < info['sections'][0][1] <= 131072,'Fixture must span multiple text banks')
    info['routines']=json.loads(artifact.with_suffix('.profile.json').read_text())['routines']
    require(any(r['offset']>=65536 for r in info['routines']),'No executable routine in the next text bank')
    return artifact,parts*(steps & 255),dict(record,sections=info['sections'],routines=[dict(offset=r['offset'],size=r['size']) for r in info['routines']])
