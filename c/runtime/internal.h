/* SPDX-License-Identifier: MIT */
#ifndef EXEC_C_RUNTIME_INTERNAL_H
#define EXEC_C_RUNTIME_INTERNAL_H
#include <exec816/c-runtime.h>

struct ExecCRuntimeState { UWORD state; };
struct ExecCRuntimeOps {
    LONG (*initialize)(struct ExecCRuntimeCall *);
    LONG (*run)(struct ExecCRuntimeCall *);
    void (*finish)(struct ExecCRuntimeCall *);
    void (*release)(struct ExecCRuntimeCall *);
};
LONG ExecCRuntimePhase(struct ExecCRuntimeState *,struct ExecCRuntimeCall *,
                      const struct ExecCRuntimeOps *);

struct ExecCRuntimeHeapStats { ULONG blocks,payload,backing,peakBacking; };
void ExecCRuntimeHeapBegin(void);
void ExecCRuntimeHeapRelease(void);
void ExecCRuntimeHeapSnapshot(struct ExecCRuntimeHeapStats *);
int ExecCRuntimeArguments(const char *,const char *,int *,char ***);

int ExecCRuntimeErrorCode(LONG);
LONG ExecCRuntimeFail(LONG);
LONG ExecCRuntimeFileError(void);
LONG ExecCRuntimeCloseError(void);
UWORD ExecCRuntimeFileCount(void);
void ExecCRuntimeFilesBegin(void);
void ExecCRuntimeAcknowledge(int);
LONG ExecCRuntimeRead(int,void *,LONG);
LONG ExecCRuntimeWrite(int,const void *,LONG);
void ExecCRuntimeFilesCleaning(void);
LONG ExecCRuntimeFilesFinish(void);
void ExecCRuntimeStdioBegin(void);
void ExecCRuntimeStreamError(int);
LONG ExecCRuntimeStdioFinish(int);
void ExecCRuntimeLibraryBegin(void);
#endif
