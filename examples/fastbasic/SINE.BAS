' Run with FB SINE.BAS, or open in BASIC.APP and press Ctrl+Return.
' Use floating-point mode in the workbench.

? "EXEC816 FASTBASIC"
? "SINE WAVE - FLOATING POINT"
DEG

FOR ANGLE=0 TO 360 STEP 15
  PHASE%=ANGLE
  COLUMN=18+INT(16.0*SIN(PHASE%))
  LINE$=""
  FOR I=1 TO COLUMN
    LINE$=+" "
  NEXT
  ? LINE$;"*"
NEXT

? "DONE"
