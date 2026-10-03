/* Host-directed operation corpus through the real public client transport. */
#include "gem-vbxe.h"
#include "gem-drawing.h"
#include <hardware/vbxe.h>
#include <string.h>
volatile UWORD stage, checkpoint, gate, opcode, subopcode, pairs, words;
volatile UWORD answer, completed, replyWords, finished, failures, checks;
volatile UWORD snapshot, inject, stopped, commandCount, boundary;
volatile UWORD batch, batchCalls, commonKind;
UBYTE fontMasks[18432], palette[48];
static UWORD captureFont;
WORD points[32], ints[64], reply[57];
struct GemServer server;
struct GemClient client;
UBYTE *capture;

UBYTE ProbeBusy(void)
{
    if (inject && !stopped) return 2;
    return *(volatile UBYTE *)0xd653UL;
}
static const ULONG guardAddress[]={0x12c00UL,0x2ffe0UL,0x3000cUL,0x30115UL,
    0x30fe0UL,0x35800UL,0x35fe0UL,0x37000UL,0x7ffe0UL};
void ProbeAcquired(struct VbxeDisplay *display)
{
    UBYTE bytes[32];
    UWORD i;
    /* Hardware row steps are signed 13-bit, despite the unsigned API type. */
    if (VbxeBlit(display,0,4096,0x36000UL,1,1,2,0,42,0)!=DISPLAY_BAD_ARGUMENT) ++failures;
    if (VbxeBlit(display,0,1,0x36000UL,8191,1,2,0,42,0)!=DISPLAY_BAD_ARGUMENT) ++failures;
    if (VbxeFill(display,0,4096,1,2,42)!=DISPLAY_BAD_ARGUMENT) ++failures;
    if (VbxeBlit(display,0x7ffffUL,1,0,1,2,1,255,0,0)!=DISPLAY_BAD_ARGUMENT) ++failures;
    if (VbxeBlit(display,0,1,0x7ffffUL,1,2,1,255,0,0)!=DISPLAY_BAD_ARGUMENT) ++failures;
    if (VbxeBlit(display,0,1,0,1,513,1,0,42,0)!=DISPLAY_BAD_ARGUMENT) ++failures;
    if (VbxeBlit(display,0,1,0,1,1,257,0,42,0)!=DISPLAY_BAD_ARGUMENT) ++failures;
    if (VbxeBlit(display,0,1,0,1,0,1,0,42,0)!=DISPLAY_BAD_ARGUMENT) ++failures;
    if (VbxeBlit(display,0,1,0,1,1,0,0,42,0)!=DISPLAY_BAD_ARGUMENT) ++failures;
    if (VbxeBlit(display,0,1,0,1,1,1,0,42,7)!=DISPLAY_BAD_ARGUMENT) ++failures;
    if (VbxeBlit(display,0,4095,0x36000UL,4095,1,2,0,42,0)!=DISPLAY_OK) ++failures;
    memset(bytes,0xa5,sizeof(bytes));
    for (i=0;i<9;i++)
        if (VbxeWrite(display,guardAddress[i],bytes,sizeof(bytes))) ++failures;
    captureFont=1;
}
void ProbePalette(const UBYTE *rgb) { memcpy(palette,rgb,48); }
void ProbeCommand(void)
{
    static const UBYTE text[]={'A','B',' ','C'};
    if (commonKind==1 && GemDrawingFill(32,180,80,200,5)!=DISPLAY_OK) ++failures;
    if (commonKind==2 && GemDrawingText(33,184,text,4,0,5)!=DISPLAY_OK) ++failures;
    if (commonKind==3) {
        if (GemDrawingFill(40,180,39,190,1)!=DISPLAY_BAD_ARGUMENT) ++failures;
        if (GemDrawingText(635,184,text,4,1,0)!=DISPLAY_BAD_ARGUMENT) ++failures;
        if (GemDrawingText(640,184,0,0,1,0)!=DISPLAY_OK) ++failures;
        if (GemDrawingOpen(reply)!=DISPLAY_BUSY) ++failures;
    }
    if (batch==2 && ++batchCalls==2) inject=1;
}
void ProbeSnapshot(struct VbxeDisplay *display)
{
    UBYTE bytes[32];
    UWORD i,j;
    for (i=0;i<9;i++) {
        if (VbxeRead(display,guardAddress[i],bytes,sizeof(bytes))) ++failures;
        for (j=0;j<32;j++) if (bytes[j]!=0xa5) ++failures;
    }
    if (captureFont) {
        if (VbxeRead(display,0x31000UL,fontMasks,sizeof(fontMasks))) ++failures;
        captureFont=0;
    }
    ULONG offset;
    UWORD n;
    if (!snapshot) return;
    for (offset=0;offset<76800UL;offset+=4096) {
        n=(76800UL-offset>4096) ? 4096 : (UWORD)(76800UL-offset);
        if (VbxeRead(display,offset,capture+offset,n)!=DISPLAY_OK) ++failures;
    }
}
static void check(UWORD good) { ++checks; if (!good) ++failures; }
UWORD main(void)
{
    UWORD i;
    struct GemRequest *original;
    struct GemCommand *commands;
    if (!stage) {
        capture=AllocMem(76800UL,MEMF_PUBLIC|MEMF_LINEAR|MEMF_CLEAR);
        check(capture!=0);
        check(GemServiceStart(&server,&GemVbxeBackend)==GEM_OK);
        check(GemClientInit(&client,&server)==GEM_OK);
        return failures;
    }
    if (stage==1) {
        for (;;) {
            ++checkpoint;
            while (gate<checkpoint) { }
            if (opcode==0xffff) break;
            original=client.packet;
            if (boundary) {
                client.packet=(struct GemRequest *)((((ULONG)capture+GEM_LIMIT_PACKET_BYTES+65535UL)&~65535UL)
                    -GEM_LIMIT_PACKET_BYTES+(boundary==2 ? 2 : 0));
            }
            if (batch) {
                check(GemPrepare(&client,GEM_OP_SUBMIT,2,34)==GEM_OK);
                commands=(struct GemCommand *)(client.packet+1);
                commands[0].opcode=batch==1 ? 11 : 25;
                commands[0].subopcode=batch==1 ? 1 : 0;
                commands[0].point_pairs=batch==1 ? 2 : 0;
                commands[0].points_offset=batch==1 ? GEM_REQUEST_BYTES+24 : 0;
                commands[0].int_words=batch==1 ? 0 : 1;
                commands[0].ints_offset=batch==1 ? 0 : GEM_REQUEST_BYTES+32;
                commands[1].opcode=batch==1 ? 100 : 11;
                commands[1].subopcode=batch==1 ? 0 : 1;
                commands[1].point_pairs=batch==1 ? 0 : 2;
                commands[1].points_offset=batch==1 ? 0 : GEM_REQUEST_BYTES+24;
                memcpy((UBYTE *)(commands+2),points,8);
                *(WORD *)((UBYTE *)client.packet+GEM_REQUEST_BYTES+32)=5;
                batchCalls=0;
                answer=GemSubmit(&client);
                if (answer==GEM_OK) answer=GemCollect(&client);
            }
            else if (opcode==1) answer=GemOpen(&client);
            else if (opcode==2) answer=GemClose(&client);
            else answer=GemCall(&client,opcode,subopcode,pairs,words,points,ints);
            completed=client.packet->completed_count;
            replyWords=client.packet->reply_words;
            for (i=0;i<57;i++) reply[i]=client.packet->reply[i];
            client.packet=original;
            ++commandCount;
        }
        check(GemServiceStop(&server)==GEM_OK);
        check(GemClientDispose(&client)==GEM_OK);
        FreeMem(capture,76800UL);
        finished=1;
    }
    return failures;
}
