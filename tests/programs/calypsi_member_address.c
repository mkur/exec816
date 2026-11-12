#include <exec/types.h>
struct Object { ULONG spec; WORD x; };
struct Ted { ULONG text; WORD colour; };
struct Fields { struct Object object; struct Ted ted; char text[64]; };
void MemberAddress(struct Fields *field)
{
#if DIRECT_MEMBER_CAST
    field->object.spec=(ULONG)&field->ted;
#else
    const struct Ted *displayTed=&field->ted;
    field->object.spec=(ULONG)displayTed;
#endif
}
