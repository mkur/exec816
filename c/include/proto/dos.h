#ifndef PROTO_DOS_H
#define PROTO_DOS_H

#include <exec/types.h>

BPTR EXEC_CALL Output(void);
LONG EXEC_CALL Write(BPTR file, const void *buffer, LONG length);

#endif
