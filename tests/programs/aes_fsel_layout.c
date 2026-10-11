#include "../../c/calypsi/aes-fsel-private.h"
#include <stddef.h>
#define FIELD(name) offsetof(struct ExecAESFileSelector,name)
__attribute__((section("exec_layout")))
const UWORD FileSelectorLayout[]={sizeof(struct ExecAESFileSelector),sizeof(struct ExecAESForm),
    offsetof(struct ExecAESForm,fileSelector),FIELD(tree),FIELD(ted),FIELD(entries),FIELD(scan),
    FIELD(info),FIELD(indices),FIELD(path),FIELD(file),FIELD(title),FIELD(directory),FIELD(mask),
    FIELD(requested),FIELD(filter),FIELD(savedName),FIELD(labels),FIELD(status),FIELD(count),
    FIELD(first),FIELD(visible),FIELD(selected),FIELD(valid),FIELD(loading),FIELD(result),
    FSEL_CANCEL,FSEL_OK,sizeof(&fsel_input),sizeof(&fsel_exinput)};
