/* SPDX-License-Identifier: MIT. The production phased entry owns this main. */
#include "internal.h"
#include <exec816/runtime.h>
#include <calypsi/stubs.h>
#include <exec816/program.h>
#include <proto/dos.h>
#include <gem.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
struct RuntimeReport { UWORD callbacks,order,writes,closes; APTR title; ULONG runs; };
struct RuntimeReport report;
__attribute__((section("exec_layout"))) const UWORD RuntimeLayout[]={
    sizeof(struct RuntimeReport),offsetof(struct RuntimeReport,title),offsetof(struct RuntimeReport,runs)};
static char mode;
static volatile ULONG computing;
APTR ExecCRTTestAllocMem(ULONG bytes,ULONG flags)
{
    const char *tail=ExecGetArgStr();
    UWORD i;
    if (tail && *tail=='I') return NULL;
    if (tail && *tail=='E') for (i=0;i<256;++i) ExecYield();
    return AllocMem(bytes,flags);
}
BPTR ExecCRTTestOpen(const char *path,LONG nativeMode) { return Open(path,nativeMode); }
LONG ExecCRTTestRead(BPTR fd,void *data,LONG bytes) { return Read(fd,data,bytes); }
LONG ExecCRTTestWrite(BPTR fd,const void *data,LONG bytes)
{
    ++report.writes;
    if (mode=='F' || mode=='P') { SetIoErr(0x0000c219L);return -1; }
    return Write(fd,data,bytes);
}
LONG ExecCRTTestClose(BPTR fd)
{
    LONG result=Close(fd);
    ++report.closes;
    if (mode=='C') { SetIoErr(0x0000c219L);return 0; }
    return result;
}
static void first(void) { ++report.callbacks;report.order=report.order*10+1;ExecYield(); }
static void second(void) { ++report.callbacks;report.order=report.order*10+2;ExecYield(); }
static void third(void) { ++report.callbacks;report.order=report.order*10+3;ExecYield(); }
static void flood(void) { ++report.callbacks;ExecYield(); }
static void stop_handler(void) { ++report.callbacks;report.order=9;_Exit(0); }
static void nested(int depth)
{
    volatile UWORD canary[8];
    UWORD i;
    for (i=0;i<8;++i) canary[i]=depth+i;
    ExecYield();
    if (depth) nested(depth-1);
    else if (mode=='N') exit(-321);
    else if (mode=='X') _Exit(7);
    else if (mode=='A') abort();
    else if (mode=='T') _Stub_assert("runtime-fixture",123);
}
int main(int argc,char **argv)
{
    FILE *stream;
    WORD window;
    UWORD i,j;
    if (argc!=2 || argv[1][1] || argv[2]) return 90;
    mode=argv[1][0];++report.runs;
    report.callbacks=report.order=report.writes=report.closes=0;
    if (errno || ExecCRuntimeFileCount() || __global_streams.sl_head) return 91;
    report.title=malloc(17);if (!report.title) return 20;
    strcpy(report.title,"Runtime retained");
    stream=fopen("NIL:","wb");
    if (!stream || fwrite("pending",1,7,stream)!=7) return 92;
    window=wind_create(NAME|CLOSER|MOVER,0,0,128,64);
    if (window<0 || !wind_set_str(window,WF_NAME,report.title) ||
        !wind_open(window,32,32,128,64)) return 93;
    /* Leave the real window and heap-backed title for resident retirement. */
    if (mode=='H') {
        for (i=0;i<32;++i) if (atexit(flood)) return 94;
        if (!atexit(flood)) return 95;
    } else if (mode=='B') {
        if (atexit(first) || atexit(stop_handler)) return 96;
    } else if (atexit(first) || atexit(second) || atexit(third)) return 97;
    errno=91;
    for (i=0;i<32;++i) {
        for (j=0;j<64;++j) computing=computing*1664525UL+1013904223UL;
        ExecYield();
        if (errno!=91) return 98;
    }
    if (mode=='N' || mode=='X' || mode=='A' || mode=='T') { nested(3);return 99; }
    if (mode=='P') { SetIoErr(ERROR_OBJECT_NOT_FOUND);return -7; }
    return 0;
}
