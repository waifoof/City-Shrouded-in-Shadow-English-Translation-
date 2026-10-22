"""Write a full-game GP4 project (base game + 1.03 update + English) for LibOrbisPkg PkgTool.

The input is ONE folder holding the base game with the original 1.03 update
merged over it (for example the folder PS4 PKG Tool's "Install to shadPS4"
creates). The English eboot.bin and DAT/common.psarc are taken from the
Apply-English output overlay, so the merged folder itself is never modified.

Usage:
  python scripts/make_full_gp4.py --game-folder <merged CUSA03562 folder>
                                  --overlay <WorkDirectory>/overlay
                                  --output <new folder>

Writes <output>/CUSA03562-English-Full.gp4 and <output>/param.sfo (a copy of
the update's param.sfo marked as a full game, CATEGORY gd). Build with:
  PkgTool.exe pkg_build <output>/CUSA03562-English-Full.gp4 <package folder>
"""
import argparse
import struct
from pathlib import Path
from xml.sax.saxutils import quoteattr

# Files the PKG builder generates itself, and files that only belong to an update package.
SKIP = {
    'sce_sys/keystone', 'sce_sys/license.dat', 'sce_sys/license.info', 'sce_sys/psreserved.dat',
    'sce_sys/playgo-chunk.dat', 'sce_sys/playgo-chunk.sha', 'sce_sys/playgo-manifest.xml',
    'sce_sys/app/playgo-chunk.dat', 'sce_sys/pronunciation.sig', 'sce_sys/origin-deltainfo.dat',
    'sce_sys/about/right.sprx', 'sce_sys/param.sfo', 'sce_discmap.plt', 'sce_discmap_patch.plt',
}
SKIP_DIRS = ('sce_sys/changeinfo/',)
SKIP_SUFFIX = ('.dds',)
OVERLAY = ('eboot.bin', 'DAT/common.psarc')


def sfo_as_full_game(data):
    data = bytearray(data)
    magic, _version, key_table, data_table, count = struct.unpack_from('<IIIII', data, 0)
    if magic != 0x46535000:
        raise ValueError('param.sfo has an unexpected header')
    values = {}
    for i in range(count):
        key_off, fmt, length, _max, data_off = struct.unpack_from('<HHIII', data, 20 + i * 16)
        key = bytes(data[key_table + key_off:data.index(0, key_table + key_off)]).decode()
        values[key] = (data_table + data_off, length)
    if bytes(data[values['TITLE_ID'][0]:values['TITLE_ID'][0] + 9]) != b'CUSA03562':
        raise ValueError('This is not the CUSA03562 param.sfo')
    pos, _ = values['CATEGORY']
    if bytes(data[pos:pos + 3]) not in (b'gp\0', b'gd\0'):
        raise ValueError('Unexpected CATEGORY in param.sfo')
    data[pos:pos + 3] = b'gd\0'
    return bytes(data), bytes(data[values['APP_VER'][0]:values['APP_VER'][0] + 5]).decode()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--game-folder', type=Path, required=True)
    parser.add_argument('--overlay', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    game, overlay, output = args.game_folder.resolve(), args.overlay.resolve(), args.output.resolve()
    for rel in OVERLAY:
        if not (overlay / rel).is_file():
            raise SystemExit(f'Missing English overlay file: {overlay / rel}')
    sfo, app_ver = sfo_as_full_game((game / 'sce_sys/param.sfo').read_bytes())
    if app_ver != '01.03':
        raise SystemExit(f'The game folder must have update 1.03 merged in (found APP_VER {app_ver}).')
    output.mkdir(parents=True, exist_ok=True)
    (output / 'param.sfo').write_bytes(sfo)

    files = []
    for path in sorted(p for p in game.rglob('*') if p.is_file()):
        rel = path.relative_to(game).as_posix()
        if rel in SKIP or rel.startswith(SKIP_DIRS) or rel.endswith(SKIP_SUFFIX):
            continue
        source = overlay / rel if rel in OVERLAY else path
        files.append((rel, source))
    files.append(('sce_sys/param.sfo', output / 'param.sfo'))
    names = {rel for rel, _ in files}
    for rel in ('eboot.bin', 'DAT/common.psarc', 'sce_sys/icon0.png'):
        if rel not in names:
            raise SystemExit(f'{rel} not found in the game folder; is it a complete merged install?')

    tree = {}
    for rel, _ in files:
        node = tree
        for part in rel.split('/')[:-1]:
            node = node.setdefault(part, {})

    def dirs(node, indent):
        out = []
        for name in sorted(node):
            if node[name]:
                out += [f'{indent}<dir targ_name={quoteattr(name)}>'] + dirs(node[name], indent + '  ') + [f'{indent}</dir>']
            else:
                out.append(f'{indent}<dir targ_name={quoteattr(name)} />')
        return out

    lines = [
        "<?xml version='1.0' encoding='utf-8'?>",
        '<psproject fmt="gp4" version="1000">',
        '  <volume>',
        '    <volume_type>pkg_ps4_app</volume_type>',
        '    <volume_id>PS4VOLUME</volume_id>',
        '    <volume_ts>2026-10-21 23:40:00</volume_ts>',
        '    <package content_id="JP0700-CUSA03562_00-E060000000000001" passcode="00000000000000000000000000000000" storage_type="digital50" app_type="full" />',
        '    <chunk_info chunk_count="1" scenario_count="1">',
        '      <chunks>',
        '        <chunk id="0" layer_no="0" label="Chunk #0" />',
        '      </chunks>',
        '      <scenarios default_id="0">',
        '        <scenario id="0" type="sp" initial_chunk_count="1" label="Scenario #0">0</scenario>',
        '      </scenarios>',
        '    </chunk_info>',
        '  </volume>',
        '  <files img_no="0">',
    ]
    lines += [f'    <file targ_path={quoteattr(rel)} orig_path={quoteattr(str(src))} />' for rel, src in files]
    lines += ['  </files>', '  <rootdir>'] + dirs(tree, '    ') + ['  </rootdir>', '</psproject>']
    project = output / 'CUSA03562-English-Full.gp4'
    project.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(f'Wrote {project} ({len(files)} files; English eboot.bin and DAT/common.psarc from {overlay})')


if __name__ == '__main__':
    main()
