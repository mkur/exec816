#include <proto/exec.h>

/* The native launcher binds a caller-context bridge, not a kernel service. */
void EXEC_PTR *ExecIOEntry;
struct IOArgs { ULONG a, b, c, d; };
ULONG EXEC_CALL _IOCall(UWORD operation, const struct IOArgs *args);

struct IORequest *EXEC_CALL CreateIORequest(struct MsgPort *port, ULONG bytes)
{
    struct IOArgs args = {(ULONG)port, bytes, 0, 0};
    return (struct IORequest *)_IOCall(0, &args);
}

LONG EXEC_CALL OpenDevice(CONST_STRPTR name, ULONG unit, struct IORequest *request, ULONG flags)
{
    struct IOArgs args = {(ULONG)name, unit, (ULONG)request, flags};
    return (LONG)_IOCall(2, &args);
}

#define REQUEST_CALL(name, operation, result, convert) \
result EXEC_CALL name(struct IORequest *request) \
{ \
    struct IOArgs args = {(ULONG)request, 0, 0, 0}; \
    return convert _IOCall(operation, &args); \
}

REQUEST_CALL(DeleteIORequest, 1, void, (void))
REQUEST_CALL(CloseDevice, 3, void, (void))
REQUEST_CALL(BeginIO, 4, void, (void))
REQUEST_CALL(SendIO, 5, void, (void))
REQUEST_CALL(DoIO, 6, LONG, (LONG))
REQUEST_CALL(CheckIO, 7, struct IORequest *, (struct IORequest *))
REQUEST_CALL(WaitIO, 8, LONG, (LONG))
REQUEST_CALL(AbortIO, 9, void, (void))
