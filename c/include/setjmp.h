/****************************************************************************
 *
 * Copyright Håkan Thörngren
 *
 * This file is part of the Calypsi C library.
 * Permission to use with the Calypsi tool chain is hereby granted.
 *
 ****************************************************************************/

#ifndef __INCLUDE_SETJMP_H
#define __INCLUDE_SETJMP_H

/* Exec816 large-code/huge-data context: S, Vfp, return PC/bank, and DP8–15. */
#if !defined(__CALYPSI_CODE_MODEL_LARGE__) || !defined(__CALYPSI_DATA_MODEL_HUGE__)
#error "Exec816 jump context requires Calypsi large code and huge data"
#endif
typedef struct __exec_c_jump_buf { unsigned short saved[8]; } jmp_buf[1];

int setjmp(jmp_buf env);
void longjmp(jmp_buf env, int value);


#endif /* __INCLUDE_SETJMP_H */
