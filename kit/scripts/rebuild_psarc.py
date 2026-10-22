"""Rebuild this game's PSARC index and append changed resources in a new file.

Existing physical data is copied verbatim. New block-table slots allow resources
to grow and keep aliases to the old data intact. The original archive is read-only.
"""
import argparse
import hashlib
import json
import os
import struct
import zlib
from pathlib import Path

from psarc import Psarc

ROOT = Path(__file__).resolve().parent.parent
CHUNK = 8 * 1024 * 1024


def copy_exact(source, target, count):
    digest = hashlib.sha256()
    while count:
        data = source.read(min(count, CHUNK))
        if not data:
            raise ValueError('Truncated archive body')
        if target is not None:
            target.write(data)
        digest.update(data)
        count -= len(data)
    return digest.hexdigest()


def rebuild(source_path, output_path, replacements):
    source_path, output_path = Path(source_path).resolve(), Path(output_path).resolve()
    if source_path == output_path or output_path.exists():
        raise ValueError('Output must be a new file, separate from the source')
    temporary = output_path.with_suffix(output_path.suffix + '.partial')
    if temporary.exists():
        raise ValueError(f'An earlier partial output exists: {temporary}')
    with source_path.open('rb') as source:
        archive = Psarc(source)
        source.seek(0)
        header = list(struct.unpack('>4sI4s5I', source.read(32)))
        old_toc = header[3]
        file_size = os.fstat(source.fileno()).st_size
        if old_toc > file_size or not replacements:
            raise ValueError('Invalid source archive or empty replacement set')
        width = max(1, ((archive.block_size-1).bit_length()+7)//8)
        if archive.block_size != 65536 or width != 2:
            raise ValueError('This writer has been validated for 64 KiB blocks only')
        paths = {e.get('path'): i for i, e in enumerate(archive.entries)}
        entries = [dict(e) for e in archive.entries]
        blocks = list(archive.blocks)
        additions, changes, retained = [], [], []
        for name, spec in replacements.items():
            if name not in paths or name is None:
                raise ValueError(f'Missing resource: {name}')
            i = paths[name]
            entry = entries[i]
            data = spec['data']
            output_hash = hashlib.sha256(data).hexdigest()
            original_hash = hashlib.sha256(archive.read(archive.entries[i])).hexdigest()
            if output_hash != spec['output_sha256']:
                raise ValueError(f'Replacement hash mismatch: {name}')
            if original_hash == output_hash:
                retained.append(name)
                continue
            if original_hash != spec['source_sha256']:
                raise ValueError(f'Source hash mismatch: {name}')
            if not data:
                raise ValueError('Empty replacements are unsupported')
            first_block = len(blocks)
            stored = bytearray()
            for start in range(0, len(data), archive.block_size):
                raw = data[start:start+archive.block_size]
                compressed = zlib.compress(raw, 9)
                packed = compressed if len(compressed) < len(raw) else raw
                blocks.append(0 if len(packed) == archive.block_size else len(packed))
                stored.extend(packed)
            entry.update(block=first_block, size=len(data))
            additions.append((i, bytes(stored)))
            changes.append(dict(path=name, source_sha256=original_hash,
                                output_sha256=output_hash, bytes=len(data),
                                blocks=len(blocks)-first_block, stored_bytes=len(stored)))
        if not additions:
            raise ValueError('All requested resources already match the source')
        new_toc = 32 + 30*len(entries) + width*len(blocks)
        delta = new_toc - old_toc
        if delta < 0:
            raise ValueError('Unexpected index shrink')
        for e in entries:
            if e['offset'] < old_toc:
                raise ValueError('Resource overlaps the source index')
            e['offset'] += delta
        end = file_size + delta
        for i, stored in additions:
            entries[i]['offset'] = end
            end += len(stored)
        header[3] = new_toc
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with temporary.open('xb') as target:
            target.write(struct.pack('>4sI4s5I', *header))
            for e in entries:
                target.write(bytes.fromhex(e['md5']) + e['block'].to_bytes(4, 'big')
                             + e['size'].to_bytes(5, 'big') + e['offset'].to_bytes(5, 'big'))
            for length in blocks:
                target.write(length.to_bytes(width, 'big'))
            if target.tell() != new_toc:
                raise ValueError('Index length mismatch')
            source.seek(old_toc)
            body_hash = copy_exact(source, target, file_size-old_toc)
            for _, stored in additions:
                target.write(stored)
            if target.tell() != end:
                raise ValueError('Archive length mismatch')
            target.flush()
            os.fsync(target.fileno())
        with temporary.open('rb') as target:
            result = Psarc(target)
            target.seek(new_toc)
            if copy_exact(target, None, file_size-old_toc) != body_hash:
                raise ValueError('Copied source data failed verification')
            if result.entries != entries or result.blocks != blocks:
                raise ValueError('Reopened index differs from the intended index')
            for name, spec in replacements.items():
                if hashlib.sha256(result.read(result.entries[paths[name]])).hexdigest() != spec['output_sha256']:
                    raise ValueError(f'Reopened resource failed verification: {name}')
        temporary.rename(output_path)
    return dict(status='archive_verified_not_console_tested', source=str(source_path),
                output=str(output_path), source_bytes=file_size, output_bytes=end,
                source_body_sha256=body_hash, copied_body_verified=True,
                entry_count=len(entries)-1, index_growth_bytes=delta,
                unchanged_entries=len(entries)-1-len(changes), changed=changes,
                already_translated_and_retained=retained)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--build', type=Path, required=True)
    parser.add_argument('--archive', default='common')
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to((ROOT/'build').resolve()):
        raise ValueError('Write rebuilt archives only inside the workspace build directory')
    validation = json.loads((args.build/'validation.json').read_text('utf-8'))
    replacements = {}
    records = list(validation['files'])
    binary_report = args.build/'binary-text-validation.json'
    if binary_report.exists():
        binary = json.loads(binary_report.read_text('utf-8'))
        if binary['status'] != 'pinned_binary_display_edits_verified_not_console_tested':
            raise ValueError('Binary display edits are not validated')
        records += [r for r in binary['files'] if r['kind'] == 'hud_utf8_property']
    for row in records:
        prefix, rel = row['path'].split('/', 1)
        if prefix != args.archive:
            continue
        file = (args.build/'resources'/row['path']).resolve()
        if not file.is_relative_to((args.build/'resources').resolve()):
            raise ValueError('Unsafe resource path')
        replacements[rel] = dict(row, data=file.read_bytes())
    report = rebuild(args.source, output, replacements)
    report['translated_entries'] = validation['translated_entries']
    (args.build/'archive-validation.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
