"""Build and independently audit pinned, fixed-size UI display-string edits."""
import argparse
import hashlib
import json
import re
import struct
from pathlib import Path

from game_text import rewrap, unwrap

ROOT = Path(__file__).resolve().parent.parent
CONTROL = re.compile(r'\[(?:i\d+|s\d+|/s|~|#[0-9a-fA-F]+|/#)\]|<[A-Za-z_][A-Za-z_0-9]*>|%ITEM|%%|%[0-9.]*[sdf]')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def source_bytes(record):
    p = (ROOT/record['source']).resolve()
    if not p.is_relative_to((ROOT/'extracted').resolve()):
        raise ValueError('Source must be a workspace extraction')
    data = p.read_bytes()
    if sha(data) != record['source_sha256']:
        raise ValueError(f'Stale binary source: {p}')
    return data


def verify(record, original, output):
    """Restoring the original strings must recreate every original byte."""
    is_hud = record['kind'] == 'hud_utf8_property'
    before = unwrap(original) if is_hud else original
    after = unwrap(output) if is_hud else output
    if len(before) != len(after):
        raise ValueError('Raw resource length changed')
    restored = bytearray(after)
    previous_end = 0
    for change in sorted(record['changes'], key=lambda c:c['offset']):
        start = change['offset']
        jp, en = change['japanese'].encode('utf-8'), change['english'].encode('utf-8')
        end = start+len(jp)
        if not en or b'\0' in en or start < previous_end or end > len(before) or len(en) > len(jp):
            raise ValueError('Invalid or overlapping display edit')
        if before[start:end] != jp:
            raise ValueError('Original display literal differs')
        if CONTROL.findall(change['japanese']) != CONTROL.findall(change['english']):
            raise ValueError('Format/control tokens or their order changed')
        if is_hud:
            if before[start-16:start-12] != bytes.fromhex('f6287f44'):
                raise ValueError('Not a HUD text property')
            if struct.unpack_from('<I', before, start-4)[0] != len(jp):
                raise ValueError('HUD text length field differs')
            padding = b' '
        else:
            if before[start-1] != 0 or before[end] != 0:
                raise ValueError('Executable edit is not a complete isolated C string')
            # All reviewed strings lie in the original uncompressed SELF data
            # entry. That PT_LOAD contains both code and constant data; do not
            # describe it as a separate non-executable section.
            if not 0x9b50 <= start < end <= 0x9b50+0x1249f6c:
                raise ValueError('Literal is outside the reviewed SELF segment')
            padding = b'\0'
        expected = en+padding*(len(jp)-len(en))
        if after[start:end] != expected:
            raise ValueError('English bytes or padding differ')
        restored[start:end] = jp
        previous_end = end
    if bytes(restored) != before:
        raise ValueError('Bytes outside the pinned display strings changed')
    if is_hud and (original[:132] != output[:132] or original[140:144] != output[140:144]):
        raise ValueError('HUD wrapper identity or flags changed')
    if not is_hud:
        if before[:24].hex() != '4f153d1d0001011201010000800470047cc24f0100000000':
            raise ValueError('Unexpected original SELF header')
        count = struct.unpack_from('<H', before, 0x18)[0]
        if count != 10 or before[0x160:0x164] != b'\x7fELF':
            raise ValueError('Unexpected SELF/ELF structure')
        for index in [0, 2, 4, 6, 8]:
            flags, offset, size, memory = struct.unpack_from('<4Q', before, 0x20+32*index)
            if any(before[offset:offset+size]):
                raise ValueError('Nonzero SELF hash blocks require a separate signing workflow')
        if after[:0x8f0] != before[:0x8f0]:
            raise ValueError('SELF/ELF metadata changed')
    return {'only_pinned_text_bytes_changed': True,
            'original_bytes_restored_exactly': True,
            'format_token_order_preserved': True, 'raw_length_preserved': len(before)}


def build(name, manifest_name='translation/menu-binary-english.json'):
    if not re.fullmatch(r'test[0-9]+', name):
        raise ValueError('Expected a numbered test build')
    target = ROOT/'build'/name
    manifest_path = (ROOT/manifest_name).resolve()
    if not manifest_path.is_relative_to((ROOT/'translation').resolve()):
        raise ValueError('Manifest must be a workspace translation file')
    manifest = json.loads(manifest_path.read_text('utf-8'))
    files = []
    for record in manifest['files']:
        original = source_bytes(record)
        hud = record['kind'] == 'hud_utf8_property'
        raw = bytearray(unwrap(original) if hud else original)
        for change in record['changes']:
            jp, en = change['japanese'].encode('utf-8'), change['english'].encode('utf-8')
            if len(en) > len(jp):
                raise ValueError('Replacement exceeds original slot')
            offset = change['offset']
            raw[offset:offset+len(jp)] = en+(b' ' if hud else b'\0')*(len(jp)-len(en))
        output = rewrap(original, raw) if hud else bytes(raw)
        checks = verify(record, original, output)
        destination = target/('resources' if hud else 'payload')/record['path']
        if not destination.resolve().is_relative_to(target.resolve()):
            raise ValueError('Unsafe output path')
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(output)
        files.append(dict(record, output_sha256=sha(output), output_bytes=len(output),
                          translations=len(record['changes']), verification=checks))
    report = dict(status='pinned_binary_display_edits_verified_not_console_tested',
                  source_manifest_sha256=sha(manifest_path.read_bytes()), files=files,
                  translated_entries=sum(r['translations'] for r in files))
    (target/'binary-text-validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n', encoding='utf-8')
    print(f'Verified {report["translated_entries"]} display edits across {len(files)} binary files.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--name', required=True)
    parser.add_argument('--manifest', default='translation/menu-binary-english.json')
    args = parser.parse_args()
    build(args.name, args.manifest)
