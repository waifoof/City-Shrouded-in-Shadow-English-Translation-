"""Regenerate SpeakerTable.luc with English speaker names.

MessageWindow.SetText shows SpeakerTable[speaker][1] when the speaker ID has an
entry, and the raw ID otherwise. This rebuilds the table so every speaker ID used
by the game maps to an English display name. Speaker IDs in the dialogue
scripts are never changed, so voice/lip-sync and other lookups are unaffected.

The original entries keep their keys, order and second field; only their
display value changes. New entries are appended. Standard library only.
"""
import json
import re
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from game_text import unwrap, rewrap  # noqa: E402

HEADER = b'\x1bLua\x52\x00\x01\x04\x08\x04\x04\x00\x19\x93\r\n\x1a\n'
# Entries whose display value is a name token. They keep the original value unless
# names gives a reordering of the same tokens (English given-name-first order).
TOKEN_KEYS = {'主人公姓', '主人公名', '主人公姓名', 'ヒロイン姓', 'ヒロイン名', 'ヒロイン姓名'}


class Reader:
    def __init__(self, raw):
        self.raw, self.pos = raw, 0
    def take(self, n):
        b = self.raw[self.pos:self.pos + n]; self.pos += n; return b
    def u32(self):
        return struct.unpack('<I', self.take(4))[0]
    def string(self):
        n = struct.unpack('<Q', self.take(8))[0]
        return self.take(n)[:-1].decode('utf-8') if n else None


def read_original(raw):
    """Return (source name, [(key, value, second)]) by executing the straight-line
    table builder symbolically; anything unexpected raises."""
    if raw[:18] != HEADER:
        raise ValueError('Unexpected Lua header')
    r = Reader(raw); r.pos = 18
    r.take(8); np_, va, ms = r.take(3)
    code = [r.u32() for _ in range(r.u32())]
    k = []
    for _ in range(r.u32()):
        t = r.take(1)[0]
        if t == 4: k.append(r.string())
        elif t == 0: k.append(None)
        elif t == 1: k.append(bool(r.take(1)[0]))
        elif t == 3: k.append(struct.unpack('<f', r.take(4))[0])
        else: raise ValueError('constant type')
    if r.u32() != 0: raise ValueError('SpeakerTable has nested functions')
    upv = [r.take(2) for _ in range(r.u32())]
    src = r.string()
    lines = [r.u32() for _ in range(r.u32())]
    if r.u32() != 0: raise ValueError('unexpected locals')
    upnames = [r.string() for _ in range(r.u32())]
    if r.pos != len(raw) or upv != [b'\x01\x00'] or upnames != ['_ENV']:
        raise ValueError('Unexpected SpeakerTable layout')
    regs, entries, done = {}, [], False
    for w in code:
        op, a, c, b, bx = w & 63, (w >> 6) & 255, (w >> 14) & 511, (w >> 23) & 511, w >> 14
        if op == 11: regs[a] = []                                  # NEWTABLE
        elif op == 1: regs[a] = k[bx]                              # LOADK
        elif op == 36:                                             # SETLIST
            if c != 1: raise ValueError('SETLIST block')
            regs[a] = [regs[a + i] for i in range(1, b + 1)]
        elif op == 10:                                             # SETTABLE
            if a != 0 or not (b & 256) or c & 256: raise ValueError('SETTABLE form')
            key, val = k[b & 255], regs[c]
            if len(val) != 2: raise ValueError('entry length')
            entries.append((key, val[0], val[1]))
        elif op == 8:                                              # SETTABUP
            if k[(w >> 23) & 255] != 'SpeakerTable': raise ValueError('global name')
            done = True
        elif op == 31: break                                       # RETURN
        else: raise ValueError(f'unexpected opcode {op}')
    if not done: raise ValueError('table never assigned')
    return src, entries


def build(raw, names):
    """names: {speaker ID: English}. Returns new raw bytecode."""
    src, entries = read_original(raw)
    base = lambda s: re.sub(r'＿\d+$', '', s)
    def english(key, old):
        if key in TOKEN_KEYS:
            new = names.get(key, old)
            if sorted(re.findall(r'<\w+>', new)) != sorted(re.findall(r'<\w+>', old)):
                raise ValueError(f'Name tokens changed: {key}')
            return new
        for cand in (key, base(key)):
            if cand in names: return names[cand]
        raise ValueError(f'No English name for speaker ID {key}')
    table, seen = [], set()
    for key, val, second in entries:
        if key in seen:
            continue                      # later duplicate assignments are identical
        seen.add(key)
        table.append((key, english(key, val), second))
    for key in sorted(names):
        if key not in seen:
            seen.add(key); table.append((key, names[key], ''))
    consts, index = [], {}
    def K(s):
        if s not in index: index[s] = len(consts); consts.append(s)
        return index[s]
    K('SpeakerTable')
    ins = lambda op, a=0, b=0, c=0: op | (a << 6) | (c << 14) | (b << 23)
    insbx = lambda op, a, bx: op | (a << 6) | (bx << 14)
    code = [ins(11, 0, 0, 0)]
    for key, val, second in table:
        code += [ins(11, 1, 2, 0), insbx(1, 2, K(val)), insbx(1, 3, K(second)), ins(36, 1, 2, 1),
                 insbx(1, 2, K(key)), ins(10, 0, 2, 1)]
    code += [ins(8, 0, 256 + K('SpeakerTable'), 0), ins(31, 0, 1, 0)]
    if len(consts) >= 1 << 18: raise ValueError('too many constants')
    out = bytearray(HEADER)
    out += struct.pack('<II', 0, 0) + bytes([0, 1, 4])           # line info, params, vararg, stack
    out += struct.pack('<I', len(code)) + b''.join(struct.pack('<I', w) for w in code)
    out += struct.pack('<I', len(consts))
    for s in consts:
        e = s.encode('utf-8') + b'\0'
        out += b'\x04' + struct.pack('<Q', len(e)) + e
    out += struct.pack('<I', 0)                                     # nested functions
    out += struct.pack('<I', 1) + b'\x01\x00'                       # upvalue _ENV
    e = src.encode('utf-8') + b'\0'
    out += struct.pack('<Q', len(e)) + e
    out += struct.pack('<I', len(code)) + struct.pack('<I', 1) * len(code)   # line info
    out += struct.pack('<I', 0)                                     # locals
    e = b'_ENV\0'
    out += struct.pack('<I', 1) + struct.pack('<Q', len(e)) + e     # upvalue names
    return bytes(out), table


def build_resource(original, names):
    raw, table = build(unwrap(original), names)
    return rewrap(original, raw), table


if __name__ == '__main__':
    original = Path(sys.argv[1]).read_bytes()
    names = json.loads(Path(sys.argv[2]).read_text('utf-8'))
    data, table = build_resource(original, names)
    Path(sys.argv[3]).write_bytes(data)
    print(f'{len(table)} speaker entries written to {sys.argv[3]}')
