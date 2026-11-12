/* SPDX-License-Identifier: MIT
 * The pinned minimal TOS/libc SDK omits these two standard string functions. */
#ifndef REFERENCE_STRING_H
#define REFERENCE_STRING_H
#include_next <string.h>
char *strcpy(char *destination,const char *source);
char *strcat(char *destination,const char *source);
#endif
