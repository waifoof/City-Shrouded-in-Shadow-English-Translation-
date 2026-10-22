"""Whole-resource generators used by apply_translation.py (standard library only).

speaker_table  SpeakerTable.luc rebuilt with English display names
               (translations/speakers.json). Speaker IDs are unchanged.
csh_append     CSH tables whose cells share pooled strings. The original bytes
               are kept; each translated string is appended after the data and
               only that cell's pointer/length changes (translations/csh_append.json).
"""
import json
import re
import struct
from pathlib import Path

from game_text import Csh, parse_resource, rewrap, unwrap
import build_speaker_table

TOKENS = re.compile(r'\[i\d+\]|\[#[0-9a-fA-F]+\]|\[/#\]|<[A-Za-z_][A-Za-z_0-9]*>|%[0-9.]*[sdf]')


def _speaker_entries(raw):
    """Symbolically run a straight-line table builder that may use register keys."""
    r = build_speaker_table.Reader(raw); r.pos = 18
    r.take(8); r.take(3)
    code = [r.u32() for _ in range(r.u32())]
    k = []
    for _ in range(r.u32()):
        t = r.take(1)[0]
        if t != 4: raise ValueError('unexpected constant type')
        k.append(r.string())
    regs, table = {}, {}
    for w in code:
        op, a, c, b, bx = w & 63, (w >> 6) & 255, (w >> 14) & 511, (w >> 23) & 511, w >> 14
        if op == 11: regs[a] = []
        elif op == 1: regs[a] = k[bx]
        elif op == 36: regs[a] = [regs[a + i] for i in range(1, b + 1)]
        elif op == 10:
            key = k[b & 255] if b & 256 else regs[b]
            table[key] = tuple(regs[c])
        elif op in (8, 31): pass
        else: raise ValueError(f'unexpected opcode {op}')
    return table


def speaker_table(original, kit):
    names = json.loads((kit / 'translations/speakers.json').read_text('utf-8'))
    result, _ = build_speaker_table.build_resource(original, names)
    _, old = build_speaker_table.read_original(unwrap(original))
    new = _speaker_entries(unwrap(result))
    for key, val, second in old:
        if key not in new: raise ValueError(f'Speaker key lost: {key}')
        if new[key][1] != second: raise ValueError(f'Second field changed: {key}')
        if key in build_speaker_table.TOKEN_KEYS and sorted(re.findall(r'<\w+>', new[key][0])) != sorted(re.findall(r'<\w+>', val)):
            raise ValueError(f'Name token changed: {key}')
    for key, eng in names.items():
        if new.get(key, (None,))[0] != eng: raise ValueError(f'Speaker not applied: {key}')
    if original[:132] != result[:132] or original[140:144] != result[140:144]:
        raise ValueError('Resource wrapper changed')
    return result, dict(entries=len(new), original_entries=len(old), english_names=len(names),
                        original_keys_kept=True, second_fields_kept=True)


def csh_append(original, edits):
    csh = parse_resource(original)
    if not isinstance(csh, Csh): raise ValueError('Not a CSH table')
    raw = bytearray(csh.raw)
    strings = {s['key']: s for s in csh.strings}
    raw += bytes((-len(raw)) % 4)
    for key, english in sorted(edits.items()):
        s = strings[key]
        if not english or '\0' in english: raise ValueError(f'Invalid English: {key}')
        if TOKENS.findall(s['text']) != TOKENS.findall(english): raise ValueError(f'Token mismatch: {key}')
        if '\\n' in s['text'] and '\n' in english: raise ValueError(f'Use literal \\n: {key}')
        value = english.encode(s['encoding']) + b'\0'
        value += bytes((-len(value)) % 4)
        kind, extra, _, _ = csh.cells[s['index']]
        struct.pack_into('>II', raw, 12 + s['index'] * 8, len(raw), kind << 30 | extra | len(value) // 4)
        raw += value
    result = rewrap(original, bytes(raw))
    after = parse_resource(result)
    got = {s['key']: s['text'] for s in after.strings}
    for key, s in strings.items():
        want = edits.get(key, s['text'])
        if got[key] != want: raise ValueError(f'Readback differs: {key}')
    for i, (before, now) in enumerate(zip(csh.cells, after.cells, strict=True)):
        if before[0] != 0 and before != now: raise ValueError('Non-string cell changed')
    if bytes(_restore(csh.raw, raw, edits, strings)) != csh.raw:
        raise ValueError('Bytes outside the edited cell entries changed')
    return result, dict(translations=len(edits), appended_bytes=len(raw) - len(csh.raw), readback_ok=True)


def _restore(orig, new, edits, strings):
    out = bytearray(new[:len(orig)])
    for key in edits:
        i = strings[key]['index']
        out[12 + i * 8:20 + i * 8] = orig[12 + i * 8:20 + i * 8]
    return out


def generate(record, original, kit):
    if record['generator'] == 'speaker_table':
        return speaker_table(original, kit)
    if record['generator'] == 'csh_append':
        edits = json.loads((kit / 'translations/csh_append.json').read_text('utf-8'))[record['path']]
        return csh_append(original, edits)
    raise ValueError(f"Unknown generator: {record['generator']}")
