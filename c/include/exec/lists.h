#ifndef EXEC_LISTS_H
#define EXEC_LISTS_H
#include <exec/nodes.h>
#include <exec816/address.h>

struct MinList {
    struct MinNode EXEC_PTR *mlh_Head;
    struct MinNode EXEC_PTR *mlh_Tail;
    struct MinNode EXEC_PTR *mlh_TailPred;
};

struct List {
    struct Node EXEC_PTR *lh_Head;
    struct Node EXEC_PTR *lh_Tail;
    struct Node EXEC_PTR *lh_TailPred;
    UBYTE lh_Type;
    UBYTE lh_Pad;
};

#define IsListEmpty(list) ExecSameAddress((list)->lh_Head, &(list)->lh_Tail)

#endif
