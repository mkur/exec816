/* Separate translation unit keeps the diagnostic call boundaries observable. */
#include <exec/types.h>
volatile UWORD CounterNotice;
void CounterNoticeOne(void) { CounterNotice=1; }
void CounterNoticeTwo(void) { CounterNotice=2; }
