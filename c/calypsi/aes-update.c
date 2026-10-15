#include "aes-private.h"

/* Bound before clients start; separate from per-application C contexts. */
void EXEC_PTR *ExecAESUpdateEntry;
