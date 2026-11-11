#include <exec/types.h>
extern volatile UWORD GeoPoint;
void GeoCallBegin(void) { GeoPoint=1; }
void GeoCallEnd(void) { GeoPoint=2; }
