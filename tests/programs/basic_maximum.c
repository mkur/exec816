/* Physical maximum-document fixture; production editor implementation. */
#include "../../examples/gem-basic/editor.h"
#include <string.h>
struct BasicEditor Basic;
static UBYTE line[256];
int main(void)
{
    WORD i,result;
    if (BasicDocumentInit(&Basic.document)) return 20;
    memset(line,'a',255);line[255]=10;
    for (i=0;i<127;++i)
        if (BasicReplace(&Basic.document,Basic.document.bytes,0,line,256)) return 20;
    if (BasicReplace(&Basic.document,Basic.document.bytes,0,line,255)) return 20;
    result=BasicEditorRun(&Basic);
    BasicDocumentDispose(&Basic.document);
    return result;
}
