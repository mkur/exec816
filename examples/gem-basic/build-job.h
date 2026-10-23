/* SPDX-License-Identifier: MIT */
#ifndef BASIC_BUILD_JOB_H
#define BASIC_BUILD_JOB_H
#include <exec816/program.h>
#include <exec816/fastbasic-diagnostic.h>
#include <exec816/fastbasic-interpreter.h>
struct BasicBuildJob {
    UWORD phase,action,integer,stop,owned,live,opened,recovery;
    ULONG serial,job,generation,child,unit,bytes,at,caret,anchor;
    UWORD first,left;
    APTR loading,image;
    BPTR file,input,output,directory;
    UBYTE *snapshot,*binary;
    ULONG binaryBytes;
    LONG cause,warning;
    struct ExecProgramResult compilerResult,programResult;
    struct ExecFastBasicDiagnostic diagnostic;
    struct ExecBasicResult interpreterResult;
    WORD window;
    char source[17],command[17],diagnostics[17],args[80],hex[9];
    char target[128],pattern[128],leaf[13],project[128],mask[128],notice[384];
    UBYTE buffer[1024];
};
struct BasicInterpreterSession {
    APTR image;
    ULONG child;
    struct MsgPort *replies;
    struct ExecBasicSession channel;
    UBYTE requestAlignment; /* The preceding packed channel occupies 19 bytes. */
    struct ExecBasicRequest request;
    UWORD ready,pending,replied,restart;
};
#endif
