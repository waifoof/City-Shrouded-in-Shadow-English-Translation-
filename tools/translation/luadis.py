"""Minimal Lua 5.2 bytecode disassembler for the game's BILZ-wrapped .luc files."""
import struct, sys
OPS = ['MOVE','LOADK','LOADKX','LOADBOOL','LOADNIL','GETUPVAL','GETTABUP','GETTABLE','SETTABUP',
       'SETUPVAL','SETTABLE','NEWTABLE','SELF','ADD','SUB','MUL','DIV','MOD','POW','UNM','NOT','LEN',
       'CONCAT','JMP','EQ','LT','LE','TEST','TESTSET','CALL','TAILCALL','RETURN','FORLOOP','FORPREP',
       'TFORCALL','TFORLOOP','SETLIST','CLOSURE','VARARG','EXTRAARG']

class Fn:
    pass

def parse(raw):
    pos = [18]
    def take(n):
        b = raw[pos[0]:pos[0]+n]; pos[0] += n; return b
    def u32(): return struct.unpack('<I', take(4))[0]
    def string():
        n = struct.unpack('<Q', take(8))[0]
        return take(n)[:-1].decode('utf-8', 'replace') if n else None
    def func(path):
        f = Fn(); f.path = path
        f.line, f.lastline = struct.unpack('<II', take(8)); f.np, f.va, f.ms = take(3)
        f.code = [struct.unpack('<I', take(4))[0] for _ in range(u32())]
        f.k = []
        for _ in range(u32()):
            t = take(1)[0]
            if t == 0: f.k.append(None)
            elif t == 1: f.k.append(bool(take(1)[0]))
            elif t == 3: f.k.append(struct.unpack('<f', take(4))[0])
            elif t == 4: f.k.append(string())
        f.sub = [func(f'{path}.{i}') for i in range(u32())]
        f.upv = [take(2) for _ in range(u32())]
        f.src = string()
        f.lines = [u32() for _ in range(u32())]
        f.locs = []
        for _ in range(u32()):
            name = string(); a, b = struct.unpack('<II', take(8)); f.locs.append((name, a, b))
        f.upnames = [string() for _ in range(u32())]
        return f
    return func('0')

def rk(f, x):
    return repr(f.k[x & 255]) if x & 256 else f'R{x}'

def dis(f, out=print):
    out(f'--- function {f.path} line {f.line} params {f.np} upvals {f.upnames} locals {[l[0] for l in f.locs]}')
    for pc, w in enumerate(f.code):
        op = w & 63; a = (w >> 6) & 255; c = (w >> 14) & 511; b = (w >> 23) & 511; bx = w >> 14; sbx = bx - 131071
        n = OPS[op]
        if n in ('LOADK',): s = f'R{a} = {f.k[bx]!r}'
        elif n in ('GETTABUP',): s = f'R{a} = U{b}[{rk(f,c)}]'
        elif n in ('GETTABLE',): s = f'R{a} = R{b}[{rk(f,c)}]'
        elif n in ('SETTABUP',): s = f'U{a}[{rk(f,b)}] = {rk(f,c)}'
        elif n in ('SETTABLE',): s = f'R{a}[{rk(f,b)}] = {rk(f,c)}'
        elif n == 'SELF': s = f'R{a+1}=R{b}; R{a}=R{b}[{rk(f,c)}]'
        elif n in ('EQ','LT','LE'): s = f'if ({rk(f,b)} {n} {rk(f,c)}) ~= {a} then pc++'
        elif n == 'JMP': s = f'pc += {sbx}'
        elif n in ('CALL','TAILCALL'): s = f'R{a}..R{a+c-2} = R{a}(R{a+1}..R{a+b-1})'
        elif n == 'CLOSURE': s = f'R{a} = closure {f.path}.{bx}'
        elif n in ('MOVE',): s = f'R{a} = R{b}'
        elif n == 'GETUPVAL': s = f'R{a} = U{b}'
        elif n == 'CONCAT': s = f'R{a} = R{b}..R{c}'
        else: s = f'{a} {b} {c}'
        out(f'  {pc:4d} {n:9s} {s}')
    for g in f.sub: dis(g, out)

if __name__ == '__main__':
    sys.path.insert(0, sys.argv[2])
    from game_text import unwrap
    dis(parse(unwrap(open(sys.argv[1], 'rb').read())))
