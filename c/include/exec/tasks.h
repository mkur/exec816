#ifndef EXEC_TASKS_H
#define EXEC_TASKS_H
#include <exec/lists.h>

/* Named padding keeps the native layout independent of C's default alignment. */
struct Task {
    struct Node tc_Node;
    UBYTE tc_Flags;
    volatile UBYTE tc_State;
    BYTE tc_IDNestCnt;
    BYTE tc_TDNestCnt;
    UBYTE _pad15;
    ULONG tc_SigAlloc;
    ULONG tc_SigWait;
    ULONG tc_SigRecvd;
    ULONG tc_SigExcept;
    void EXEC_PTR *tc_SPReg;
    UBYTE _pad35;
    void EXEC_PTR *tc_SPLower;
    UBYTE _pad39;
    void EXEC_PTR *tc_SPUpper;
    struct List tc_MemEntry;
    void EXEC_PTR *tc_UserData;
    UBYTE _pad57;
    void EXEC_PTR *tc_ExecPrivate;
    UBYTE _pad61;
};

#endif
