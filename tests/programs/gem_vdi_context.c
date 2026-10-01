/* Exec types stay separate from the imported GEM records. */
#include <proto/exec.h>
#include <clib/alib_protos.h>

extern UWORD GemProbeRun(void);
static struct Task *supervisor;
volatile UWORD failures, completed, progress[2];
volatile ULONG peer_checksum;

static void finish(void)
{
    Forbid();
    ++completed;
    Signal(supervisor, 1UL << 31);
    RemTask(NULL);
}

void Renderer(void)
{
    UWORD i;
    for (i = 0; i < 128; ++i) {
        failures += GemProbeRun();
        progress[0] = i + 1;
    }
    finish();
}

void Peer(void)
{
    ULONG a = 0x12345678UL, b = 0x87654321UL;
    UWORD i;
    for (i = 0; i < 30000; ++i) {
        a = ((a << 1) ^ (a >> 31)) ^ b;
        b += a ^ i;
        progress[1] = i + 1;
    }
    peer_checksum = a ^ b;
    finish();
}

int main(void)
{
    UWORD count = 0;
    supervisor = FindTask(NULL);
    if (AllocSignal(31) != 31)
        return 1;
    Forbid();
    if (CreateTask("GEM probe", 0, (APTR)Renderer, 2560UL))
        ++count;
    if (CreateTask("GEM peer", 0, (APTR)Peer, 2560UL))
        ++count;
    Permit();
    /* Retire every admitted worker even after partial admission. */
    while (completed != count)
        Wait(1UL << 31);
    FreeSignal(31);
    return failures != 0 || count != 2;
}
