import sys, collections
sys.path.insert(0, sys.argv[3])
import fsdump
d = open(sys.argv[1], 'rb').read(); off = int(sys.argv[2], 16)
# 8-bit opcode -> (name, operand bytes) from ScummVM detokeniser_freescape.cpp kFreescapeOpcodes (maxArgs)
OPS = {0:('NOP',0),1:('ADDSCORE',3),2:('ADDENERGY',1),3:('TOGVIS',1),4:('VIS',1),5:('INVIS',1),6:('RTOGVIS',2),7:('RVIS',2),8:('RINVIS',2),
 9:('INCVAR',1),10:('DECVAR',1),11:('IFVAR!=',2),12:('SETBIT',1),13:('CLRBIT',1),14:('IFBIT!=',2),15:('SOUND',1),16:('DESTROY',1),17:('RDESTROY',2),
 18:('GOTO',2),19:('ADDSHIELD',1),20:('SETVAR',2),21:('SWAPJET',1),25:('SPFX',1),26:('REDRAW',0),27:('DELAY',1),28:('SYNCSND',1),29:('TOGBIT',1),
 30:('IFINVIS',1),31:('IFVIS',1),32:('IFRINVIS',2),33:('IFRVIS',2),34:('PRINT',1),35:('SCREEN',1),36:('SETFLAGS',1),37:('STARTANIM',1),
 41:('LOOP',1),42:('AGAIN',0),44:('ELSE',0),45:('ENDIF',0),46:('IFGTE',2),47:('IFLTE',2),48:('EXECUTE',1)}
EV = ['collided', 'timer', 'shot', 'activated']
ops = collections.Counter(); evs = collections.Counter(); nbytes = 0; bad = 0
def decode(code):
    global nbytes, bad
    nbytes += len(code); i = 0
    while i < len(code):
        b = code[i]; i += 1
        op = b & 0x3f
        if op not in OPS: bad += 1; return
        ops[OPS[op][0]] += 1; evs[EV[b >> 6]] += 1; i += OPS[op][1]
db = fsdump.parse_db(d, off)
# re-walk raw bytes for object FCL and area conditions
for i in range(db['n_areas']):
    ao = off + (d[off+0xc8+2*i] | (d[off+0xc9+2*i] << 8))
    nobj = d[ao+1]; q = ao + 25
    for k in range(nobj):
        o, nq = fsdump.parse_object(d, q)
        if o.get('fcl', 0) > 0: decode(d[nq - o['fcl']:nq])
        q = nq
    r = ao + (d[ao+3] | (d[ao+4] << 8)); nc = d[r]; r += 1
    for k in range(nc):
        ln = d[r]; decode(d[r+1:r+1+ln]); r += 1 + ln
g = off + (d[off+0x48] | (d[off+0x49] << 8)); ng = d[g]; g += 1
for k in range(ng):
    ln = d[g]; decode(d[g+1:g+1+ln]); g += 1 + ln
print('FCL bytes', nbytes, 'undecodable streams', bad)
print('events', dict(evs))
print('opcodes', ops.most_common())
