#ifndef EXEC_TYPES_H
#define EXEC_TYPES_H

#include <stddef.h>
#include <stdint.h>

#if !defined(__CALYPSI_CORE_65816__) || !defined(__CALYPSI_DATA_MODEL_HUGE__) || !defined(__CALYPSI_CODE_MODEL_LARGE__)
#error "Exec816 C requires Calypsi 65816, large code and huge data"
#endif

#define EXEC816 1
#define EXEC_CALL __simple_call
#define EXEC_PTR __far24

typedef int8_t BYTE;
typedef uint8_t UBYTE;
typedef int16_t WORD;
typedef uint16_t UWORD;
typedef int32_t LONG;
typedef uint32_t ULONG;
/* Opaque DOS handle. Exec816 uses its native identity, not a BCPL address. */
typedef LONG BPTR;
typedef void *APTR;
typedef char *STRPTR;
typedef const char *CONST_STRPTR;
typedef WORD BOOL;

#define TRUE 1
#define FALSE 0

#endif
