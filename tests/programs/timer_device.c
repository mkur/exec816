#include <proto/exec.h>
#include <devices/timer.h>

volatile UWORD timer_checks;
#define REQUIRE(test) do { if (!(test)) return timer_checks + 1; ++timer_checks; } while (0)

UWORD main(void)
{
    ULONG available = AvailMem(0);
    struct MsgPort *port = CreateMsgPort();
    struct TimerClockRequest *clock;
    struct TimerRequest *wait;
    REQUIRE(port != NULL);
    clock = (struct TimerClockRequest *)CreateIORequest(port, sizeof(*clock));
    wait = (struct TimerRequest *)CreateIORequest(port, sizeof(*wait));
    REQUIRE(clock != NULL && wait != NULL);
    REQUIRE(OpenDevice("timer.device", UNIT_VBLANK, &clock->tc_Request, 0) == 0);
    wait->tr_Request.io_Device = clock->tc_Request.io_Device;
    wait->tr_Request.io_Unit = clock->tc_Request.io_Unit;
    clock->tc_Request.io_Command = TD_READCLOCK;
    REQUIRE(DoIO(&clock->tc_Request) == 0);
    REQUIRE(clock->ticks_per_second == 50);
    wait->tr_Request.io_Command = TR_ADDREQUEST;
    wait->seconds = 0;
    wait->microseconds = 0;
    SendIO(&wait->tr_Request);
    REQUIRE(WaitIO(&wait->tr_Request) == 0);
    REQUIRE(wait->tr_Request.io_Message.mn_Node.ln_Type == NT_FREEMSG);
    wait->seconds = 3600;
    wait->tr_Request.io_Flags = IOF_QUICK;
    BeginIO(&wait->tr_Request);
    REQUIRE((wait->tr_Request.io_Flags & IOF_QUICK) == 0);
    REQUIRE(CheckIO(&wait->tr_Request) == NULL);
    REQUIRE(DoIO(&clock->tc_Request) == 0);
    AbortIO(&wait->tr_Request);
    REQUIRE(CheckIO(&wait->tr_Request) != NULL);
    REQUIRE(WaitIO(&wait->tr_Request) == IOERR_ABORTED);
    REQUIRE(WaitIO(&wait->tr_Request) == IOERR_ABORTED);
    wait->seconds = 0;
    REQUIRE(DoIO(&wait->tr_Request) == 0);
    wait->microseconds = 1000000;
    REQUIRE(DoIO(&wait->tr_Request) == TIMERERR_BADTIME);
    REQUIRE(GetMsg(port) == NULL);
    CloseDevice(&clock->tc_Request);
    wait->tr_Request.io_Device = NULL;
    wait->tr_Request.io_Unit = NULL;
    DeleteIORequest(&wait->tr_Request);
    DeleteIORequest(&clock->tc_Request);
    DeleteMsgPort(port);
    REQUIRE(AvailMem(0) == available);
    return 0;
}
