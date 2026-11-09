/* SPDX-License-Identifier: MIT */
#include "internal.h"
#include <proto/dos.h>
#include <errno.h>
#include <stdlib.h>
#include <string.h>

static int bad_arguments(int error)
{
    errno=error;SetIoErr(ERROR_BAD_ARGUMENTS);return 0;
}

int ExecCRuntimeArguments(const char *tail,const char *name,int *argc,char ***argv)
{
    const char *source;
    char **vector,*text;
    unsigned int length=0,nameLength=0,count=0,textBytes=0,index=1;
    int quoted,active;
    *argc=0;*argv=NULL;
    if (!tail) tail="";
    if (!name) name="";
    while (length<=EXEC_CRT_ARGUMENT_BYTES && tail[length]) ++length;
    while (nameLength<=EXEC_CRT_ARGUMENT_BYTES && name[nameLength]) ++nameLength;
    if (length>EXEC_CRT_ARGUMENT_BYTES || nameLength>EXEC_CRT_ARGUMENT_BYTES)
        return bad_arguments(E2BIG);
    source=tail;quoted=active=0;
    while (*source) {
        char byte=*source++;
        if (!quoted && (byte==' ' || byte=='\t')) {
            if (active) { ++textBytes;active=0; }
        } else {
            if (!active) { ++count;active=1; }
            if (byte=='"') quoted=!quoted;
            else ++textBytes;
        }
    }
    if (quoted) return bad_arguments(EINVAL);
    if (active) ++textBytes;
    vector=malloc((count+2)*sizeof(char *)+nameLength+1+textBytes);
    if (!vector) return 0;
    text=(char *)(vector+count+2);
    vector[0]=text;memcpy(text,name,nameLength+1);text+=nameLength+1;
    source=tail;quoted=active=0;
    while (*source) {
        char byte=*source++;
        if (!quoted && (byte==' ' || byte=='\t')) {
            if (active) { *text++=0;active=0; }
        } else {
            if (!active) { vector[index++]=text;active=1; }
            if (byte=='"') quoted=!quoted;
            else *text++=byte;
        }
    }
    if (active) *text=0;
    vector[index]=NULL;*argc=index;*argv=vector;
    return 1;
}
