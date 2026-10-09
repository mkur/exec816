"""Focused synchronous-form lifetime faults and physical interaction checks."""
from pathlib import Path
from native_program import ROOT, require, sha256


def instrument(out):
    """Replace only this fixture's form resource boundaries, never production."""
    import build_bitmap_console as builder
    original=builder.emit
    source=(ROOT/'c/calypsi/aes-form.c').read_text()
    prototypes='''
void *AESFormAlloc(ULONG,ULONG);
WORD AESFormCreate(WORD,WORD,WORD,WORD,WORD);
WORD AESFormOpen(WORD,WORD,WORD,WORD,WORD);
void AESFormVDIOpen(WORD *,WORD *,WORD *);
WORD AESFormClose(WORD);
WORD AESFormDelete(WORD);
BOOL AESFormVDIClose(struct ExecAESContext *);
'''
    source=source.replace('#include "aes-form-private.h"',
        '#include "'+str(ROOT/'c/calypsi/aes-form-private.h')+'"'+prototypes)
    source=source.replace('#include "vdi-private.h"',
        '#include "'+str(ROOT/'c/calypsi/vdi-private.h')+'"')
    for name,replacement in [('AllocMem','AESFormAlloc'),('wind_create','AESFormCreate'),
        ('wind_open','AESFormOpen'),('v_opnvwk','AESFormVDIOpen'),('wind_close','AESFormClose'),
        ('wind_delete','AESFormDelete'),('ExecVDIClose','AESFormVDIClose')]:
        source=source.replace(name+'(',replacement+'(')
    path=out/'aes-form-fault.c';path.write_text(source)
    def emit(output,sources,*args,**kwargs):
        sources=[path if p==ROOT/'c/calypsi/aes-form.c' else p for p in sources]
        foreign=original(output,sources,*args,**kwargs)
        foreign['provenance']['form_fault_source_sha256']=sha256(path)
        return foreign
    builder.emit=emit
    return original
