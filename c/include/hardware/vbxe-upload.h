/* Private C/assembly upload packet. Callers use VbxeSubmit, never this helper. */
#ifndef EXEC_VBXE_UPLOAD_H
#define EXEC_VBXE_UPLOAD_H
#include <exec/types.h>
struct VbxeUpload { ULONG records; UWORD count; };
void EXEC_CALL _VbxeUpload(const struct VbxeUpload *upload);
#endif
