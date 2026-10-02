/* Diagnostic controller. All writes go through the ordinary GEM transport. */
#include "gem-vbxe.h"
#include <hardware/vbxe.h>
volatile UWORD stage, checkpoint, gate, opcode, pairs, words, answer, bad;
volatile UWORD completed, replyWords, finished, failures, checks;
volatile UWORD faultPoint, faultSeen, permanent, inject, stopped, phases, activePhase, starts;
WORD points[32], ints[64];
struct GemServer server;
struct GemClient client;
static void check(UWORD good) { ++checks; if (!good) ++failures; }
UBYTE ProbeBusy(void)
{
    if (inject && (permanent || !stopped)) return 2;
    return *(volatile UBYTE *)0xd653UL;
}
void ProbeCursorPhase(UWORD point)
{
    ++phases;
    activePhase=point;
}
void ProbeStarted(void)
{
    ++starts;
    if (faultPoint && faultPoint==activePhase && !faultSeen) { faultSeen=faultPoint; inject=1; }
}
UWORD main(void)
{
    struct GemCursor *cursor;
    if (!stage) {
        check(GemServiceStart(&server,&GemVbxeBackend)==GEM_OK);
        check(GemClientInit(&client,&server)==GEM_OK);
        return failures;
    }
    for (;;) {
        ++checkpoint;
        while (gate<checkpoint) { }
        if (opcode==0xffff) break;
        if (opcode==0xff00) {
            answer=GemPrepareCursor(&client,points[0],points[1],ints[0]);
            if (!answer) {
                cursor=(struct GemCursor *)(client.packet+1);
                switch (bad) {
                case 1: cursor->x=-1; break;
                case 2: cursor->x=640; break;
                case 3: cursor->y=-1; break;
                case 4: cursor->y=240; break;
                case 5: cursor->visible=2; break;
                case 6: cursor->reserved=1; break;
                case 7: client.packet->command_count=1; break;
                case 8: client.packet->total_bytes=client.packet->message.mn_Length=162; break;
                case 9: client.packet->flags=1; break;
                case 10: client.packet->version=1; break;
                case 11: ++client.packet->session; break;
                case 12: --client.packet->sequence; break;
                case 13: client.packet->operation=99; break;
                }
                answer=GemSubmit(&client);
                if (!answer) answer=GemCollect(&client);
            }
        } else if (opcode==1) answer=GemOpen(&client);
        else if (opcode==2) answer=GemClose(&client);
        else answer=GemCall(&client,opcode,opcode==11 ? 1 : 0,pairs,words,points,ints);
        completed=client.packet->completed_count;
        replyWords=client.packet->reply_words;
    }
    if (client.session) check(GemClose(&client)==GEM_OK);
    check(GemServiceStop(&server)==GEM_OK);
    check(GemClientDispose(&client)==GEM_OK);
    finished=1;
    return failures;
}
