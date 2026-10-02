#ifndef EXEC816_ADDRESS_H
#define EXEC816_ADDRESS_H
#include <exec/types.h>

/* Compare a stored 24-bit ABI address and a huge C pointer at full width.
 * Calypsi 5.18's implicit far24 comparison with a symbol emits an incorrect
 * .byte2(.byte0 symbol) bank relocation. Explicit ULONG conversion preserves
 * both the bank and the fourth byte; it never truncates an invalid huge value.
 * The out-of-line boundary also avoids a 5.18 constant-folding failure for
 * the address of an embedded record. This helper makes no kernel call. */
UBYTE EXEC_CALL ExecSameAddress(const void *left, const void *right);
#endif
