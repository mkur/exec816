/* Exec816 source interface for the selected GEM AES profile. New native
 * declarations, checked against ports/gem4xe/aes-binding-inputs.json. */
#ifndef EXEC816_GEM_H
#define EXEC816_GEM_H
#include <exec/types.h>
#define FAR
#define SIMPLE_CALL EXEC_CALL

typedef struct {
    WORD *control, *global, *int_in, *int_out;
    LONG *addr_in, *addr_out;
} AESPB;

WORD appl_init(void);
WORD appl_exit(void);
void EXEC_CALL aes_call(AESPB *pb);
#endif
