/* Minimal Calypsi 5.18 defect reproducer, retained for upstream comparison.
 * fill() makes every element defined before the suspected wrong stack read. */
extern void ArrayFill(short *),ArrayConsume(const short *);
void ArrayExample(short x,short y)
{
    short box[4];
    ArrayFill(box);
    box[0]=x+8; box[1]=y+48;
    box[2]=box[0]+127; box[3]=box[1]+23;
    ArrayConsume(box);
}
