"""Statically inspect straight-line Lua 5.2 message table declarations.

No Lua code is executed. Unknown instructions reject the audit. Constant keys
distinguish displayed text from speaker lookup identifiers and table names.
"""
import argparse
import json
import struct
from pathlib import Path

from game_text import JAPANESE, parse_resource


def inspect(path):
    return inspect_data(Path(path).read_bytes())


def inspect_data(data, *, include_globals=False):
    parsed = parse_resource(data)
    raw = parsed.raw
    instructions = struct.unpack_from('<I', raw, 29)[0]
    pos = 33 + 4*instructions
    count = struct.unpack_from('<I', raw, pos)[0]
    pos += 4
    constants = []
    for index in range(count):
        kind = raw[pos]
        pos += 1
        if kind == 4:
            size = struct.unpack_from('<Q', raw, pos)[0]
            pos += 8
            value = raw[pos:pos+size-1].decode('utf-8') if size else ''
            pos += size
        elif kind == 3:
            value = struct.unpack_from('<f', raw, pos)[0]
            pos += 4
        elif kind == 1:
            value = bool(raw[pos])
            pos += 1
        elif kind == 0:
            value = None
        else:
            raise ValueError(f'Unknown constant type {kind}')
        constants.append({'key':f'0:k{index}', 'value':value})
    registers, globals_ = {}, {}
    def value(item):
        return item.get('value') if isinstance(item, dict) else item
    def rk(operand):
        return constants[operand & 255] if operand & 256 else registers[operand]
    for pc in range(instructions):
        word = struct.unpack_from('<I', raw, 33+4*pc)[0]
        op, a, b, c = word & 63, (word>>6)&255, (word>>23)&511, (word>>14)&511
        if op == 0:
            registers[a] = registers[b]
        elif op == 1:
            registers[a] = constants[word>>14]
        elif op == 3:
            if c:
                raise ValueError('Conditional LOADBOOL not supported')
            registers[a] = {'value':bool(b)}
        elif op == 4:
            for reg in range(a,a+b+1):
                registers[reg] = {'value':None}
        elif op == 6:
            name = value(rk(c))
            registers[a] = globals_.get(name, {'value':name})
        elif op == 7:
            parent, key = value(registers[b]), value(rk(c))
            registers[a] = {'value':f'{parent}.{key}'}
        elif op == 8:
            globals_[value(rk(b))] = rk(c)
        elif op == 10:
            registers[a]['fields'][value(rk(b))] = rk(c)
        elif op == 11:
            registers[a] = {'fields':{}}
        elif op == 36:
            if b == 0 or c == 0:
                raise ValueError('Variable SETLIST not supported')
            for index in range(1,b+1):
                registers[a]['fields'][(c-1)*50+index] = registers[a+index]
        elif op == 31:
            break
        else:
            raise ValueError(f'Unsupported instruction {op} at {pc}')
    # Read-only view for auditing other declarative resources (speaker and
    # mission tables). The default message audit remains unchanged.
    if include_globals:
        return globals_
    messages = []
    for name, table in globals_.items():
        fields = table.get('fields', {})
        if 3 not in fields:
            continue
        mode = value(fields.get(1))
        if not isinstance(mode,str) or not mode.startswith('MessageWindowDef.MES_TYPE_'):
            continue
        text = fields[3]
        messages.append({'message_id':name,'mode':mode.split('.')[-1],
                         'speaker':fields.get(2), 'text':text, 'extra':fields.get(4)})
    if not messages:
        raise ValueError('No message tables found')
    return messages


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('resource', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    messages = inspect(args.resource)
    args.output.write_text(json.dumps(messages,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    japanese = {m['text']['key'] for m in messages if isinstance(m['text'].get('value'),str) and JAPANESE.search(m['text']['value'])}
    print(f'{len(messages)} message declarations; {len(japanese)} distinct Japanese text constants.')


if __name__ == '__main__':
    main()
