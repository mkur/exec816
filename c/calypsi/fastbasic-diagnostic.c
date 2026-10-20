/* SPDX-License-Identifier: MIT */
#include <exec816/fastbasic-diagnostic.h>

WORD ExecFastBasicDiagnosticMatches(const struct ExecFastBasicDiagnostic *d,
    ULONG bytes,ULONG job,CONST_STRPTR source)
{
    UWORD i;
    if (bytes!=FBD_BYTES || d->magic[0]!='F' || d->magic[1]!='B' ||
        d->magic[2]!='D' || d->magic[3]!='1' || d->version!=FBD_VERSION ||
        d->bytes!=FBD_BYTES || !job || d->job!=job || d->reserved ||
        d->stage<FBD_STAGE_SOURCE || d->stage>FBD_STAGE_COMPLETE ||
        !d->source_bytes || d->source_bytes>=FBD_SOURCE_CAPACITY ||
        !d->message_bytes || d->message_bytes>=FBD_MESSAGE_CAPACITY ||
        d->source[d->source_bytes] || d->message[d->message_bytes] ||
        d->byte_column>255) return 0;
    for (i=0;i<d->source_bytes;++i)
        if (!source[i] || source[i]!=d->source[i]) return 0;
    return source[i]==0;
}
