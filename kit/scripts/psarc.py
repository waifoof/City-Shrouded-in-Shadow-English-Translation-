"""Strict reader for unencrypted zlib PSARC archives; source files are read-only."""
import argparse
import hashlib
import json
import re
import struct
import zlib
from pathlib import Path


class Psarc:
    def __init__(self, stream):
        self.stream = stream
        stream.seek(0)
        magic, self.version, codec, toc_size, entry_size, count, self.block_size, self.flags = struct.unpack('>4sI4s5I', stream.read(32))
        if magic != b'PSAR' or codec != b'zlib' or entry_size != 30:
            raise ValueError('Unsupported PSARC header')
        self.entries = []
        for _ in range(count):
            raw = stream.read(entry_size)
            self.entries.append(dict(md5=raw[:16].hex(), block=int.from_bytes(raw[16:20], 'big'),
                                     size=int.from_bytes(raw[20:25], 'big'), offset=int.from_bytes(raw[25:30], 'big')))
        width = max(1, ((self.block_size - 1).bit_length() + 7) // 8)
        raw = stream.read(toc_size - stream.tell())
        self.blocks = [int.from_bytes(raw[n:n+width], 'big') for n in range(0, len(raw), width)]
        manifest = self.read(self.entries[0]).decode('utf-8')
        names = manifest.rstrip('\x00').split('\x00') if '\x00' in manifest else manifest.splitlines()
        lookup = {hashlib.md5((name.upper() if self.flags & 1 else name).encode()).hexdigest(): name for name in names}
        if len(names) != count - 1:
            raise ValueError('Manifest count mismatch')
        for entry in self.entries[1:]:
            entry['path'] = lookup[entry['md5']]

    def read(self, entry):
        self.stream.seek(entry['offset'])
        result = bytearray()
        index = entry['block']
        while len(result) < entry['size']:
            expected = min(self.block_size, entry['size'] - len(result))
            stored = self.blocks[index] or self.block_size
            raw = self.stream.read(stored)
            if len(raw) != stored:
                raise ValueError('Truncated PSARC data')
            if stored == expected:
                data = raw
            else:
                data = zlib.decompress(raw)
            if len(data) != expected:
                raise ValueError('PSARC block length mismatch')
            result.extend(data)
            index += 1
        return bytes(result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('--manifest', type=Path)
    parser.add_argument('--extract', type=Path)
    parser.add_argument('--pattern', default='.*')
    args = parser.parse_args()
    with args.archive.open('rb') as stream:
        archive = Psarc(stream)
        entries = archive.entries[1:]
        if args.manifest:
            args.manifest.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f'{args.archive}: {len(entries)} entries; flags={archive.flags:#x}')
        if args.extract:
            root = args.extract.resolve()
            for entry in entries:
                if not re.search(args.pattern, entry['path']):
                    continue
                destination = (root / entry['path'].lstrip('/')).resolve()
                if not destination.is_relative_to(root):
                    raise ValueError('Unsafe archive path')
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(archive.read(entry))


if __name__ == '__main__':
    main()
