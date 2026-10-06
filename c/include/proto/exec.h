#ifndef PROTO_EXEC_H
#define PROTO_EXEC_H
#include <exec816/abi.h>
#include <exec/tasklease.h>
#include <exec/io.h>

/* This is the implemented classic Exec subset, not an Amiga binary ABI. */
APTR EXEC_CALL AllocMem(ULONG bytes, ULONG attributes);
void EXEC_CALL FreeMem(APTR memory, ULONG bytes);
ULONG EXEC_CALL AvailMem(ULONG attributes);
void EXEC_CALL NewList(struct List *list);

struct Task *EXEC_CALL AddTask(struct Task *task, void (*entry)(void), void (*finalizer)(void));
void EXEC_CALL RemTask(struct Task *task);
struct Task *EXEC_CALL FindTask(CONST_STRPTR name);
void EXEC_CALL Forbid(void);
void EXEC_CALL Permit(void);
BYTE EXEC_CALL AllocSignal(BYTE requested);
void EXEC_CALL FreeSignal(BYTE number);
ULONG EXEC_CALL SetSignal(ULONG signals, ULONG mask);
void EXEC_CALL Signal(struct Task *task, ULONG signals);
ULONG EXEC_CALL Wait(ULONG signals);

struct MsgPort *EXEC_CALL CreateMsgPort(void);
void EXEC_CALL DeleteMsgPort(struct MsgPort *port);
void EXEC_CALL PutMsg(struct MsgPort *port, struct Message *message);
struct Message *EXEC_CALL GetMsg(struct MsgPort *port);
struct Message *EXEC_CALL WaitPort(struct MsgPort *port);
void EXEC_CALL ReplyMsg(struct Message *message);
void EXEC_CALL AddPort(struct MsgPort *port);
void EXEC_CALL RemPort(struct MsgPort *port);
struct MsgPort *EXEC_CALL FindPort(CONST_STRPTR name);

struct IORequest *EXEC_CALL CreateIORequest(struct MsgPort *port, ULONG bytes);
void EXEC_CALL DeleteIORequest(struct IORequest *request);
LONG EXEC_CALL OpenDevice(CONST_STRPTR name, ULONG unit, struct IORequest *request, ULONG flags);
void EXEC_CALL CloseDevice(struct IORequest *request);
void EXEC_CALL BeginIO(struct IORequest *request);
void EXEC_CALL SendIO(struct IORequest *request);
LONG EXEC_CALL DoIO(struct IORequest *request);
struct IORequest *EXEC_CALL CheckIO(struct IORequest *request);
LONG EXEC_CALL WaitIO(struct IORequest *request);
void EXEC_CALL AbortIO(struct IORequest *request);

#endif
