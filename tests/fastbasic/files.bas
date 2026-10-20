S$="FILE BYTES"
open #1,8,0,"RAM:FB.DAT"
? #1,S$
close #1
open #1,4,0,"RAM:FB.DAT"
input #1,T$
? T$
get #1,I
? ERR()
close #1
dim Data(3) byte
for I=0 to 3
  Data(I)=I*85
next
open #1,8,0,"RAM:FB.BIN"
bput #1,adr(Data),4
close #1
mset adr(Data),4,0
open #1,4,0,"RAM:FB.BIN"
bget #1,adr(Data),8
? ERR()
? Data(0)+Data(1)+Data(2)+Data(3)
close #1
