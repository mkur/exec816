/* SPDX-License-Identifier: GPL-3.0-only */
#include "support.h"
#include <ctype.h>
int strnicmp(const char *a,const char *b,size_t n)
{
    while(n--){unsigned char x=tolower((unsigned char)*a++),y=tolower((unsigned char)*b++);
        if(x!=y)return x<y?-1:1;
        if(!x)break;}
    return 0;
}
int stricmp(const char *a,const char *b)
{
    while(*a && tolower((unsigned char)*a)==tolower((unsigned char)*b)){a++;b++;}
    return (int)tolower((unsigned char)*a)-(int)tolower((unsigned char)*b);
}
char *strupr(char *s){char *p=s;while(*p){*p=toupper((unsigned char)*p);p++;}return s;}
char *strlwr(char *s){char *p=s;while(*p){*p=tolower((unsigned char)*p);p++;}return s;}
char *ultoa(unsigned long value,char *out,int radix)
{
    char digits[32],*p=out;unsigned n=0;
    if(radix<2 || radix>36){*out=0;return out;}
    do{unsigned d=value%radix;digits[n++]=d<10?'0'+d:'a'+d-10;value/=radix;}while(value);
    while(n)*p++=digits[--n];
    *p=0;return out;
}
char *ltoa(long value,char *out,int radix)
{
    if(value<0 && radix==10){*out='-';ultoa(0UL-(unsigned long)value,out+1,radix);}
    else ultoa((unsigned long)value,out,radix);
    return out;
}
