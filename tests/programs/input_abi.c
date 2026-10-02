#include <exec/input.h>
#include <proto/exec.h>
#include <string.h>

struct InputLease lease;
struct InputConfig config;
struct InputEvent event;
volatile UWORD stage, checks, failures, first_failure, progress;
volatile ULONG checksum;
ULONG tag = 0xdeadbeefUL;
UWORD pending = 0xa55a;

static void check(UWORD good)
{
    ++checks;
    if (!good) {
        if (!failures) first_failure = checks;
        ++failures;
    }
}

UWORD main(void)
{
    UBYTE *bank;
    UWORD i;
    ULONG a = 0x12345678UL, b = 0x87654321UL;
    if (stage) {
        check(event.acquisition == 0x12345678UL && event.route == 0xabcdef03UL);
        check(event.tick == 0xfffe && event.kind == INPUT_EVENT_BUTTON);
        check(event.flags == INPUT_INJECTED && event.code == INPUT_LEFT);
        check(event.qualifiers == 3 && event.x == -123 && event.y == 239);
        check(event.buttons == 1 && event.reserved == 0);
        return failures;
    }
    config.version = INPUT_VERSION;
    config.source = INPUT_SOURCE_KEYBOARD;
    config.wakeMask = 0x92345678UL;
    config.filter0Value = 0x1c; config.filter0Mask = 0x3f;
    config.filter1Value = 0x92; config.filter1Mask = 0xbf;
    config.filterCount = 2; config.flags = INPUT_CAPTURE_BREAK;
    memset(&event, 0xa5, sizeof(event));
    check(InputAcquire(&lease, &config) == INPUT_BAD_ARGUMENT);
    check(InputCreateRoute(&lease, 0, &tag) == INPUT_INVALID_OWNER && tag == 0xdeadbeefUL);
    check(InputCreateRoute(&lease, 1, &tag) == INPUT_BAD_ARGUMENT);
    check(InputPublishRoute(&lease, 0x1234567fUL) == INPUT_INVALID_OWNER);
    check(InputRetireRoute(&lease, 0x1234567fUL) == INPUT_INVALID_OWNER);
    check(InputDiscard(&lease, 0x1234567fUL) == INPUT_INVALID_OWNER);
    check(InputPending(&lease, &pending) == INPUT_INVALID_OWNER && pending == 0xa55a);
    check(InputTake(&lease, &event) == INPUT_INVALID_OWNER);
    for (i = 0; i < sizeof(event); ++i) check(((UBYTE *)&event)[i] == 0xa5);
    check(InputRelease(&lease) == INPUT_INVALID_OWNER);
    check(InputAcquire((struct InputLease *)0x010d0000UL, &config) == INPUT_BAD_ARGUMENT);
    check(InputAcquire(&lease, (struct InputConfig *)0x010d0000UL) == INPUT_BAD_ARGUMENT);
    check(InputAcquire((struct InputLease *)0xdfff0UL, &config) == INPUT_BAD_ARGUMENT);
    check(InputAcquire((struct InputLease *)((UBYTE *)&lease+1), &config) == INPUT_BAD_ARGUMENT);
    check(InputAcquire(NULL, &config) == INPUT_BAD_ARGUMENT);
    check(InputTake(&lease, (struct InputEvent *)0xfffff0UL) == INPUT_BAD_ARGUMENT);
    check(InputTake(&lease, (struct InputEvent *)0x1000UL) == INPUT_BAD_ARGUMENT);
    check(InputPending(&lease, (UWORD *)0x100d0000UL) == INPUT_BAD_ARGUMENT);
    check(InputCreateRoute(&lease, 0, (ULONG *)0x010d0000UL) == INPUT_BAD_ARGUMENT);
    check(InputRelease((struct InputLease *)0xffffffUL) == INPUT_BAD_ARGUMENT);
    config.reserved = 1;
    check(InputAcquire(&lease, &config) == INPUT_BAD_ARGUMENT);
    config.reserved = 0; config.filterCount = 3;
    check(InputAcquire(&lease, &config) == INPUT_BAD_ARGUMENT);
    config.filterCount = 2; config.filter0Mask = 0;
    check(InputAcquire(&lease, &config) == INPUT_BAD_ARGUMENT);
    config.filter0Mask = 0x3f; config.filter0Value = 0x80;
    check(InputAcquire(&lease, &config) == INPUT_BAD_ARGUMENT);
    config.filter0Value = 0x1c; config.flags = 2;
    check(InputAcquire(&lease, &config) == INPUT_BAD_ARGUMENT);
    config.flags = INPUT_CAPTURE_BREAK;
    bank = AllocMem(65536UL, MEMF_PUBLIC|MEMF_CLEAR);
    check(bank != NULL && ((ULONG)bank & 0xffffUL) == 0);
    if (bank) {
        check(InputAcquire((struct InputLease *)(bank+65504UL), &config) == INPUT_BAD_ARGUMENT);
        check(InputAcquire((struct InputLease *)(bank+65506UL), &config) == INPUT_BAD_ARGUMENT);
        check(InputTake(&lease, (struct InputEvent *)(bank+65512UL)) == INPUT_INVALID_OWNER);
        check(InputTake(&lease, (struct InputEvent *)(bank+65514UL)) == INPUT_BAD_ARGUMENT);
        memcpy(bank+65520UL, &config, sizeof(config));
        check(InputAcquire(&lease, (struct InputConfig *)(bank+65520UL)) == INPUT_BAD_ARGUMENT);
        check(InputAcquire(&lease, (struct InputConfig *)(bank+65522UL)) == INPUT_BAD_ARGUMENT);
        FreeMem(bank, 65536UL);
    }
    /* Exercise successful calls through the same checked huge-pointer bridge. */
    check(AllocSignal(16) == 16);
    config.wakeMask = 0x10000UL;
    check(InputAcquire(&lease, &config) == INPUT_OK);
    check(InputCreateRoute(&lease, 0, &tag) == INPUT_OK && tag != 0);
    check(InputPublishRoute(&lease, tag) == INPUT_OK);
    check(InputPending(&lease, &pending) == INPUT_OK && pending == 0);
    check(InputTake(&lease, &event) == INPUT_EMPTY);
    check(InputRetireRoute(&lease, tag) == INPUT_BUSY);
    check(InputPublishRoute(&lease, 0) == INPUT_OK);
    check(InputDiscard(&lease, tag) == INPUT_OK);
    check(InputRetireRoute(&lease, tag) == INPUT_OK);
    check(InputRelease(&lease) == INPUT_OK);
    FreeSignal(16);
    config.wakeMask = 0x92345678UL;
    /* Layout-only values, never submitted as a live lease. */
    lease.owner.task = (struct Task EXEC_PTR *)0x061234UL;
    lease.owner.pad = 0xab;
    lease.owner.incarnation = 0x55667788UL;
    lease.owner.identity = (void EXEC_PTR *)0x089abcUL;
    lease.owner.pad2 = 0xcd;
    lease.acquisition = 0x11223344UL;
    lease.route = 0x89abcdefUL;
    lease.wakeMask = 0x80706050UL;
    lease.state = 0x1234; lease.flags = 0xbeef; lease.reserved = 0xfedcba98UL;
    for (i = 0; i < 30000; ++i) {
        a = ((a << 1) ^ (a >> 31)) ^ b;
        b += a ^ i;
        progress = i+1;
    }
    checksum = a ^ b;
    return failures;
}
