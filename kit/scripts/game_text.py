"""Read and rebuild the game's BILZ-wrapped CSH tables and Lua 5.2 strings."""
import re
import struct
import zlib

JAPANESE = re.compile(r'[\u3040-\u30ff\u3400-\u9fff]')


def unwrap(data):
    if data[128:132] != b'BILZ':
        raise ValueError('Unsupported resource wrapper')
    raw_size, compressed_size, flags = struct.unpack_from('>III', data, 132)
    if compressed_size != len(data) - 144:
        raise ValueError('Unexpected BILZ length')
    raw = zlib.decompress(data[144:])
    if len(raw) != raw_size:
        raise ValueError('BILZ decompressed size mismatch')
    return raw


def rewrap(original, raw):
    compressed = zlib.compress(raw, 9)
    return original[:132] + struct.pack('>II', len(raw), len(compressed)) + original[140:144] + compressed


class Csh:
    def __init__(self, raw):
        self.raw = raw
        self.flags, self.columns, self.rows = struct.unpack_from('>III', raw)
        count = self.columns * self.rows
        end = 12 + count * 8
        if end > len(raw):
            raise ValueError('CSH table exceeds resource size')
        self.cells = []
        self.strings = []
        for index in range(count):
            offset, descriptor = struct.unpack_from('>II', raw, 12+index*8)
            kind, words = descriptor >> 30, descriptor & 0x1fffffff
            extra_flag = descriptor & 0x20000000
            if kind == 3 or words == 0:
                if offset != 0 or words != 0:
                    raise ValueError('Unsupported CSH null cell')
                value = b''
            else:
                if offset < end or offset + words*4 > len(raw):
                    raise ValueError('Invalid CSH cell bounds')
                value = raw[offset:offset+words*4]
            self.cells.append((kind, extra_flag, words, value))
            if kind == 0:
                string_bytes = value.split(b'\0', 1)[0]
                encoding = 'utf-8'
                try:
                    text = string_bytes.decode(encoding)
                except UnicodeDecodeError:
                    encoding = 'cp932'
                    text = string_bytes.decode(encoding)
                self.strings.append(dict(key=f'r{index//self.columns}:c{index%self.columns}', text=text,
                                         index=index, row=index//self.columns, column=index%self.columns, encoding=encoding))

    def rebuild(self, translations):
        output = bytearray(self.raw[:12]) + bytearray(len(self.cells)*8)
        for index, (kind, extra_flag, words, value) in enumerate(self.cells):
            key = f'r{index//self.columns}:c{index%self.columns}'
            if key in translations:
                if kind != 0:
                    raise ValueError('Cannot translate a non-string cell')
                encoding = next(s['encoding'] for s in self.strings if s['key'] == key)
                value = translations[key].encode(encoding) + b'\0'
                value += bytes((-len(value)) % 4)
                words = len(value)//4
            offset = len(output) if kind != 3 and words else 0
            struct.pack_into('>II', output, 12+index*8, offset, kind << 30 | extra_flag | words)
            output.extend(value)
        return bytes(output)


class Lua52:
    def __init__(self, raw):
        self.raw, self.position, self.strings = raw, 18, []
        if raw[:18] != b'\x1bLua\x52\x00\x01\x04\x08\x04\x04\x00\x19\x93\r\n\x1a\n':
            raise ValueError('Unsupported Lua bytecode header')
        self.function('0')
        if self.position != len(raw):
            raise ValueError(f'Unparsed Lua data at {self.position}/{len(raw)}')

    def take(self, size):
        if size < 0 or self.position+size > len(self.raw):
            raise ValueError('Truncated Lua chunk')
        result = self.raw[self.position:self.position+size]
        self.position += size
        return result

    def number(self, width=4):
        return int.from_bytes(self.take(width), 'little')

    def string(self, key=None):
        start = self.position
        size = self.number(8)
        value = self.take(size)
        if size and value[-1] != 0:
            raise ValueError('Lua string lacks terminator')
        if key is not None:
            self.strings.append(dict(key=key, text=value[:-1].decode('utf-8') if size else '',
                                     start=start, end=self.position))

    def function(self, key):
        self.take(11)  # line range and parameter/vararg/stack counts
        self.take(self.number()*4)  # instructions
        for index in range(self.number()):
            kind = self.number(1)
            if kind == 0:
                pass
            elif kind == 1:
                self.take(1)
            elif kind == 3:
                self.take(4)
            elif kind == 4:
                self.string(f'{key}:k{index}')
            else:
                raise ValueError(f'Unsupported Lua constant {kind}')
        for index in range(self.number()):
            self.function(f'{key}.{index}')
        self.take(self.number()*2)  # upvalue descriptors
        self.string()  # debug source
        self.take(self.number()*4)  # debug lines
        for _ in range(self.number()):
            self.string()
            self.take(8)
        for _ in range(self.number()):
            self.string()

    def rebuild(self, translations):
        result = bytearray()
        previous = 0
        for string in self.strings:
            if string['key'] not in translations:
                continue
            result.extend(self.raw[previous:string['start']])
            value = translations[string['key']].encode('utf-8') + b'\0'
            result.extend(struct.pack('<Q', len(value)))
            result.extend(value)
            previous = string['end']
        result.extend(self.raw[previous:])
        return bytes(result)


def parse_resource(data):
    raw = unwrap(data)
    if data[:4] == b'\x00hsc':
        return Csh(raw)
    if data[:4] == b'\x00cul':
        return Lua52(raw)
    raise ValueError('Unsupported resource type')
