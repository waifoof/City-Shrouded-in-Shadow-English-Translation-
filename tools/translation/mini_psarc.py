"""Build a small PSARC (64 KiB zlib blocks, same layout the kit reads) from a folder."""
import sys, os, struct, zlib, hashlib
src, out = sys.argv[1], sys.argv[2]
names = sorted(os.path.relpath(os.path.join(d, f), src).replace(os.sep, '/') for d, _, fs in os.walk(src) for f in fs)
blobs = ['\n'.join(names).encode()] + [open(os.path.join(src, n), 'rb').read() for n in names]
BS = 65536
stored, blocks, ents = [], [], []
for i, data in enumerate(blobs):
    first, packed_all = len(blocks), bytearray()
    for s in range(0, max(len(data), 1), BS):
        raw = data[s:s+BS]; c = zlib.compress(raw, 9); p = c if len(c) < len(raw) else raw
        blocks.append(0 if len(p) == BS else len(p)); packed_all += p
    ents.append((b'\0'*16 if i == 0 else hashlib.md5(names[i-1].encode()).digest(), first, len(data))); stored.append(bytes(packed_all))
toc = 32 + 30*len(ents) + 2*len(blocks)
body, off, table = bytearray(), toc, bytearray()
for (md5, first, size), st in zip(ents, stored):
    table += md5 + first.to_bytes(4, 'big') + size.to_bytes(5, 'big') + off.to_bytes(5, 'big'); off += len(st); body += st
hdr = struct.pack('>4sI4s5I', b'PSAR', 0x10004, b'zlib', toc, 30, len(ents), BS, 0)
open(out, 'wb').write(hdr + table + b''.join(b.to_bytes(2, 'big') for b in blocks) + body)
print(out, len(names), 'entries')
