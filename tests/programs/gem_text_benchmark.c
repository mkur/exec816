#include "gem-vbxe.h"
#include <hardware/vbxe.h>
#include <exec/input.h>
#include <string.h>

volatile UWORD stage, checkpoint, gate, finished, failures, checks;
volatile UWORD elapsedTicks, testPhase, testCase;
struct GemServer server;
struct GemClient client;
struct InputLease mouse __attribute__((aligned(2)));
struct InputConfig config __attribute__((aligned(2)));
WORD points[4], ints[64];
struct VbxeDisplay directDisplay;
WORD bit;
struct Result { UWORD phase, kind, glyphs, calls, start, end, ticks, status; };
struct Result results[26];
UWORD resultCount;

static void check(UWORD good) { ++checks; if (!good) ++failures; }
static UWORD text(UWORD n, WORD x, WORD y)
{
    points[0]=x; points[1]=y;
    return GemCall(&client,8,0,1,n,points,ints);
}
extern void BenchmarkStart(void);
extern void BenchmarkEnd(void);

static void measure(UWORD kind, UWORD n, UWORD repetitions, WORD x)
{
    UWORD j, status=0, start=DisplayTicks();
    struct Result *r=&results[resultCount++];
    BenchmarkStart();
    if (kind==5) {
        for (j=0;j<30 && !status;++j) {
            status=text(64,0,(WORD)(j*8+6));
            if (!status) status=text(16,512,(WORD)(j*8+6));
        }
    } else if (kind==11) {
        for (j=0;j<repetitions && !status;++j)
            status=GemCall(&client,11,1,2,0,points,ints);
    } else if (kind==12) {
        status=VbxeBlit(&directDisplay,2560,320,0,320,320,232,255,0,0);
    } else {
        for (j=0;j<repetitions && !status;++j)
            status=text(n,x,64);
    }
    BenchmarkEnd();
    r->end=DisplayTicks(); r->start=start; r->ticks=(UWORD)(r->end-start);
    r->phase=testPhase; r->kind=kind; r->glyphs=kind==5 ? 2400 : n*repetitions;
    r->calls=kind==5 ? 60 : repetitions; r->status=status;
    check(status==GEM_OK);
}
UWORD main(void)
{
    UWORD i;
    if (!stage) {
        check(GemServiceStart(&server,&GemVbxeBackend)==GEM_OK);
        check(GemClientInit(&client,&server)==GEM_OK);
        return failures;
    }
    check(GemOpen(&client)==GEM_OK);
    for (i=0;i<64;++i) ints[i]='A'+i%26;
    for (testPhase=0;testPhase<2;++testPhase) {
        if (testPhase) {
            bit=AllocSignal(-1); check(bit>=16);
            memset(&config,0,sizeof(config));
            config.version=INPUT_VERSION; config.source=INPUT_SOURCE_POINTER;
            config.wakeMask=1UL<<bit; config.pointerProtocol=INPUT_POINTER_ST;
            config.pointerPort=1; config.initialX=320; config.initialY=120;
            config.maxX=639; config.maxY=239;
            check(InputAcquire(&mouse,&config)==INPUT_OK);
        }
        for (testCase=0;testCase<13;++testCase) {
            for (i=0;i<64;++i) ints[i]='A'+i%26;
            if (testCase<12) check(GemCall(&client,3,0,0,0,points,ints)==GEM_OK);
            if (testCase==0) measure(0,1,8,32);
            if (testCase==1) measure(1,8,8,32);
            if (testCase==2) measure(2,32,8,32);
            if (testCase==3) measure(3,64,8,32);
            if (testCase==4) measure(4,64,8,33);
            if (testCase==5) measure(5,0,1,0);
            if (testCase==6 || testCase==7 || testCase==8) {
                for (i=0;i<64;++i)
                    ints[i]=testCase==6 ? ' ' : testCase==7 ? 'W' : i%2 ? ' ' : 'A'+i%26;
                measure(testCase,64,8,32);
            }
            if (testCase==9) measure(9,8,8,-3);
            if (testCase==10) {
                ints[0]=0; check(GemCall(&client,22,0,0,1,points,ints)==GEM_OK);
                for (i=0;i<64;++i) ints[i]='A'+i%26;
                measure(10,64,8,32);
                ints[0]=1; check(GemCall(&client,22,0,0,1,points,ints)==GEM_OK);
            }
            if (testCase==11) {
                points[0]=0; points[1]=0; points[2]=639; points[3]=239;
                measure(11,0,8,0);
            }
            if (testCase==12) {
                check(GemClose(&client)==GEM_OK);
                check(VbxeOpen(&directDisplay)==DISPLAY_OK);
                for (i=0;i<240;++i)
                    check(VbxeFill(&directDisplay,(ULONG)i*320,320,320,1,(UBYTE)((i%16)*17))==DISPLAY_OK);
                check(VbxeShow(&directDisplay)==DISPLAY_OK);
                measure(12,0,1,0);
            }
            ++checkpoint;
            while (gate<checkpoint) { }
            if (testCase==12) {
                check(VbxeClose(&directDisplay)==DISPLAY_OK);
                check(GemOpen(&client)==GEM_OK);
            }
        }
        if (testPhase) {
            check(InputRelease(&mouse)==INPUT_OK);
            FreeSignal(bit);
        }
    }
    check(GemClose(&client)==GEM_OK);
    check(GemServiceStop(&server)==GEM_OK);
    check(GemClientDispose(&client)==GEM_OK);
    finished=1;
    return failures;
}
