/* SPDX-License-Identifier: GPL-3.0-only */
#include "qed-runtime.h"
#include <exec816/program.h>
#include <stdlib.h>
#include <string.h>

int QedArguments(const char *tail,const char *name,int *argc,char ***argv)
{
    char **vector,*text,*argument;
    unsigned int length=0,nameLength=0;
    char quote=0;
    *argc=0;*argv=NULL;
    while (length<256 && tail[length]) ++length;
    while (nameLength<256 && name[nameLength]) ++nameLength;
    if (length>255 || nameLength>255) return 0;
    vector=malloc(3*sizeof(char *)+nameLength+1+length+1);
    if (!vector) return 0;
    text=(char *)(vector+3);vector[0]=text;
    memcpy(text,name,nameLength+1);text+=nameLength+1;
    while (*tail==' ' || *tail=='\t') ++tail;
    argument=text;
    if (*tail) {
        if (*tail=='"') { quote=*tail;++tail; }
        while (*tail && (quote ? *tail!=quote:*tail!=' ' && *tail!='\t')) *text++=*tail++;
        if (quote && *tail++!=quote) { free(vector);return 0; }
        while (*tail==' ' || *tail=='\t') ++tail;
        if (*tail) { free(vector);return 0; }
        *text=0;vector[1]=argument;vector[2]=NULL;*argc=2;
    } else { vector[1]=NULL;*argc=1; }
    *argv=vector;
    return 1;
}

int QedRuntimeRun(int (*body)(int,char **))
{
    int argc,result;
    char **argv;
    const char *tail=ExecGetArgStr();
    if (!tail || !QedArguments(tail,FindTask(NULL)->tc_Node.ln_Name,&argc,&argv)) return 20;
    result=body(argc,argv);
    QedHeapCleanup();
    return result;
}
