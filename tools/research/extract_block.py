import sys, hashlib
sys.path.insert(0, sys.argv[4])
import tap
buf = open(sys.argv[1], 'rb').read()
bl = tap.tzx_blocks(buf) if buf[:7] == b'ZXTape!' else [(0x10, b) for b in tap.tap_blocks(buf)]
idx = int(sys.argv[2])
body = bl[idx][1][1:-1]
open(sys.argv[3], 'wb').write(body)
print(len(body), 'md5(all)=', hashlib.md5(body).hexdigest(), 'md5(5000)=', hashlib.md5(body[:5000]).hexdigest())
