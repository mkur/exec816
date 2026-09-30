#ifndef EXEC_NODES_H
#define EXEC_NODES_H
#include <exec/types.h>

/* The stored links are 24-bit; ordinary C pointers may still be 32-bit. */
struct MinNode {
    struct MinNode EXEC_PTR *mln_Succ;
    struct MinNode EXEC_PTR *mln_Pred;
};

struct Node {
    struct Node EXEC_PTR *ln_Succ;
    struct Node EXEC_PTR *ln_Pred;
    UBYTE ln_Type;
    BYTE ln_Pri;
    char EXEC_PTR *ln_Name;
};

#endif
