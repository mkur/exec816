/* Private C/assembly upload packet. Callers use VbxeSubmit, never this helper. */
#ifndef EXEC_VBXE_UPLOAD_H
#define EXEC_VBXE_UPLOAD_H
#include <exec/types.h>
struct VbxeUpload { ULONG records; UWORD count; };
void EXEC_CALL _VbxeUpload(const struct VbxeUpload *upload);
/* Private validated text packet: 1..32 glyphs, even X, no clipping. */
struct VbxeTextUpload {
    ULONG text, font, destination;
    UWORD count;
    UBYTE ink, paper;
};
void EXEC_CALL _VbxeTextUpload(const struct VbxeTextUpload *upload);
#endif
