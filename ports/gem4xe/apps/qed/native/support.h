/* SPDX-License-Identifier: MIT */
#ifndef QED_SUPPORT_H
#define QED_SUPPORT_H
#include <stddef.h>
int stricmp(const char *a,const char *b);
int strnicmp(const char *a,const char *b,size_t n);
char *strupr(char *s);
char *strlwr(char *s);
char *ltoa(long value,char *out,int radix);
char *ultoa(unsigned long value,char *out,int radix);
#endif
