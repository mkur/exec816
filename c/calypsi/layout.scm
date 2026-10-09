; Initial standalone C target: code and globals occupy separate upper banks.
; DirectPage and HostInfo are virtual link ranges, never XEX load addresses.
(define memories
 '((memory Code (address (#xc0000 . #xcffff))
            (section farcode switch))
   (memory Data (address (#xd0000 . #xdffff))
            (placement-group initialized (section huge chuge))
            (placement-group zeroed (section zhuge)))
   (memory ExtraCode (address (#xe0000 . #xeffff))
            (section farcode switch))
   (memory GemTables (address (#xf0000 . #xfffff))
            (section gemtables))
   (memory MoreCode (address (#x100000 . #x10ffff))
            (section farcode switch))
   (memory DirectPage (address (#x0 . #x7f)) (section registers))
   (memory HostInfo (address (#x100 . #x10f)) (section execinfo))
   (base-address _DirectPageStart DirectPage 0)
   (base-address _NearBaseAddress DirectPage 0)))
