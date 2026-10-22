"""Find every speaker ID used in message declarations across all .luc files."""
import sys, os, collections, json
import luadis
def scan(root, unwrap):
    spk = collections.defaultdict(set)
    def walk(f, rel):
        regk = {}
        code = f.code
        for pc, w in enumerate(code):
            op = w & 63; a = (w >> 6) & 255; c = (w >> 14) & 511; bx = w >> 14
            key = None
            if op in (6, 7):
                key = f.k[c & 255] if c & 256 else regk.get(c)
            if op == 1:
                regk[a] = f.k[bx]
            elif op not in (36,):
                regk.pop(a, None)
            if isinstance(key, str) and key.startswith('MES_TYPE_'):
                for q in range(pc + 1, min(pc + 6, len(code))):
                    w2 = code[q]
                    if w2 & 63 == 1 and (w2 >> 6) & 255 == a + 1:
                        s = f.k[w2 >> 14]
                        if isinstance(s, str): spk[s].add(rel)
                        break
        for g in f.sub: walk(g, rel)
    for d, _, fs in os.walk(root):
        for fn in fs:
            p = os.path.join(d, fn)
            walk(luadis.parse(unwrap(open(p, 'rb').read())), os.path.relpath(p, root))
    return spk
if __name__ == '__main__':
    sys.path.insert(0, sys.argv[2]); from game_text import unwrap, JAPANESE
    spk = scan(sys.argv[1], unwrap)
    old = set(json.load(open(sys.argv[3])))
    new = {s for s in spk if s} - old
    print('speakers found', len(spk), '| new Japanese IDs not seen before:', len(new))
    print(sorted(new))
    json.dump(sorted(old | {s for s in spk if s}), open(sys.argv[3], 'w'), ensure_ascii=False)
