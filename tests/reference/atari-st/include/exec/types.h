/* SPDX-License-Identifier: MIT
 * Host SDK adapter: GEM scalar types, without the native Exec ABI guards. */
#ifndef EXEC_TYPES_H
#define EXEC_TYPES_H
#include <stddef.h>
#include <stdint.h>
#define EXEC_CALL
#define EXEC_PTR
typedef int8_t BYTE;
typedef uint8_t UBYTE;
typedef int16_t WORD;
typedef uint16_t UWORD;
typedef int32_t LONG;
typedef uint32_t ULONG;
typedef LONG BPTR;
typedef void *APTR;
typedef char *STRPTR;
typedef const char *CONST_STRPTR;
typedef WORD BOOL;
#define TRUE 1
#define FALSE 0
#endif
