/* SPDX-License-Identifier: MIT */
#ifndef BASIC_FILES_H
#define BASIC_FILES_H
#include "document.h"
#include <proto/dos.h>
enum { BASIC_EOL_ATASCII=0,BASIC_EOL_LF=1,BASIC_EOL_CRLF=2,BASIC_EOL_CR=3 };
struct BasicFile { char path[128];UBYTE eol; };
struct BasicFileJob {
    struct BasicDocument candidate;
    struct BasicFile named;
    UBYTE *snapshot;
    ULONG bytes,at,generation;
    BPTR handle;
    LONG error,warning;
    UWORD phase,save,cr,seen,complete,moved,attempts,pending,offset;
    char temporary[128],backup[128];
    UBYTE buffer[1024],input[1023];
};
/* Jobs own candidate/snapshot/handle until terminal Step or Cancel. The paths
 * remain available afterwards for reporting complete recovery copies. */
WORD BasicLoadBegin(struct BasicFileJob *,const char *);
WORD BasicSaveBegin(struct BasicFileJob *,const struct BasicDocument *,const struct BasicFile *,const char *);
WORD BasicFileStep(struct BasicFileJob *,struct BasicDocument *,struct BasicFile *);
void BasicFileCancel(struct BasicFileJob *);
#endif
