"""Apply the English v1.0 translation to matching, already extracted 1.03 game files.

Only the Python standard library is required. Source files are read-only.
Run through Apply-English.ps1 or directly with Python 3.11 or later.
"""
import argparse
import zlib
import hashlib
import json
import re
import shutil
import struct
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

from game_text import parse_resource, unwrap, rewrap
from psarc import Psarc
from rebuild_psarc import rebuild
from build_menu_binary_text import verify
import build_text_resources
import generated_resources

KIT = Path(__file__).resolve().parent.parent


def read_json(path):
    return json.loads(path.read_text('utf-8'))


def sha(data):
    return hashlib.sha256(data).hexdigest()


def safe(root, relative):
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError(f'Path leaves its root: {relative}')
    return path


def sfo_values(data):
    magic, version, keys, values, count = struct.unpack_from('<4s4I', data)
    if magic != b'\0PSF' or count > 1024:
        raise ValueError('Invalid PARAM.SFO')
    result = {}
    for i in range(count):
        k, kind, length, maximum, v = struct.unpack_from('<HHIII', data, 20+i*16)
        name = data[keys+k:data.index(0, keys+k)].decode('utf-8')
        value = data[values+v:values+v+length]
        if kind == 0x204:
            result[name] = value.rstrip(b'\0').decode('utf-8')
    return result


def base_identity(path):
    with path.open('rb') as f:
        header = f.read(4096)
        if header[:4] != b'\x7fCNT':
            raise ValueError('Base file is not a PS4 PKG')
        count = int.from_bytes(header[16:20], 'big')
        if not 0 < count < 100000:
            raise ValueError('Invalid base PKG entry count')
        f.seek(int.from_bytes(header[24:28], 'big'))
        entries = [struct.unpack('>8I', f.read(32)) for _ in range(count)]
        entry = next(e for e in entries if e[0] == 0x1000)
        f.seek(entry[4])
        return sfo_values(f.read(entry[5]))


def prepare_project(source, output, base, template):
    tree = ET.parse(template)
    volume = tree.getroot().find('volume')
    volume.find('volume_ts').text = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
    volume.find('package').set('app_path', str(base))
    for entry in tree.getroot().find('files'):
        rel = entry.get('targ_path')
        file = safe(output/'overlay', rel) if rel in {'DAT/common.psarc','eboot.bin'} else safe(source, rel)
        if not file.is_file():
            raise ValueError(f'Missing project file: {rel}')
        entry.set('orig_path', str(file))
    ET.indent(tree, space='  ')
    path = output/'English-v1.0-1.03.gp4'
    tree.write(path, encoding='utf-8', xml_declaration=True)
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--update-folder', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--base-package', type=Path)
    parser.add_argument('--check-only', action='store_true')
    parser.add_argument('--edited-translations', action='store_true', help='Permit revised English text; source and structural checks remain mandatory')
    args = parser.parse_args()
    source = args.update_folder.resolve()
    index = read_json(KIT/'data/source-index.json')
    english = read_json(KIT/'translations/english.json')
    binaries = read_json(KIT/'translations/binary-english.json')['files']
    expected = {r['path']:r for r in index['tables']}
    if set(english) != set(expected):
        raise ValueError('Translation resource list differs from the approved source index')
    if any(set(english[p]) != set(expected[p]['keys']) for p in english):
        raise ValueError('Translation keys differ from the approved display-key list')
    if len(binaries) != len(index['binary_files']):
        raise ValueError('Binary file list differs from the approved source index')
    # Translated values may be edited, but offsets and original literals may not.
    for record, approved in zip(binaries, index['binary_files'], strict=True):
        structure = dict(record, changes=[{k:v for k,v in c.items() if k!='english'} for c in record['changes']])
        if sha(json.dumps(structure,ensure_ascii=False,sort_keys=True).encode()) != approved['structure_sha256']:
            raise ValueError(f'Binary edit locations changed: {record["path"]}')
    if not args.edited_translations:
        for rel, digest in index['translation_sha256'].items():
            if sha(safe(KIT, rel).read_bytes()) != digest:
                raise ValueError('Translation source changed. Use --edited-translations for an intentional revision.')
    template = KIT/'data/project-template.gp4'
    project_paths = [e.get('targ_path') for e in ET.parse(template).getroot().find('files')]
    base = args.base_package.resolve() if args.base_package else None
    if base:
        for rel in project_paths:
            file = safe(source, rel)
            if not file.is_file():
                raise ValueError(f'Full extracted update required to generate GP4; missing {rel}')
        values = sfo_values(safe(source,'sce_sys/param.sfo').read_bytes())
        if (values.get('TITLE_ID'), values.get('APP_VER'), values.get('CATEGORY')) != ('CUSA03562','01.03','gp'):
            raise ValueError('Expected extracted CUSA03562 update 01.03 (category gp)')
        base_values = base_identity(base)
        if base_values.get('TITLE_ID')!='CUSA03562' or base_values.get('CATEGORY')!='gd':
            raise ValueError('Expected the matching CUSA03562 base application PKG, not an update')
    inputs = {}
    with safe(source,'DAT/common.psarc').open('rb') as stream:
        archive = Psarc(stream)
        entries = {e.get('path'):e for e in archive.entries}
        for record in list(expected.values()) + [r for r in binaries if r['kind']=='hud_utf8_property'] + index.get('generated', []) + index.get('textures', []):
            rel = record['path']
            key = rel.removeprefix('common/')
            if key not in entries:
                raise ValueError(f'Missing original archive resource: {rel}')
            data = archive.read(entries[key])
            if sha(data) != record['source_sha256']:
                raise ValueError(f'Incompatible original resource: {rel}. Use an untranslated matching 1.03 update.')
            inputs[rel] = data
    original_eboot = safe(source,'eboot.bin').read_bytes()
    exe_record = next(r for r in binaries if r['path']=='eboot.bin')
    if sha(original_eboot) != exe_record['source_sha256']:
        raise ValueError('Incompatible eboot.bin: this executable/backport differs from the tested 1.03 source.')
    inputs['eboot.bin'] = original_eboot
    print(f'Compatible sources: {len(inputs)-1} archive resources and eboot.bin.', flush=True)
    if args.check_only:
        print('Compatibility check only; no files written.')
        return
    if args.output is None:
        raise ValueError('--output is required unless --check-only is used')
    output = args.output.resolve()
    if output.exists() or output.is_relative_to(source) or source.is_relative_to(output):
        raise ValueError('Output must be a new directory separate from the original update folder')
    output.mkdir(parents=True)
    catalog=[]
    for rel, record in expected.items():
        original = inputs[rel]
        parsed = {s['key']:s['text'] for s in parse_resource(original).strings}
        destination = safe(output/'extracted/update103',rel)
        destination.parent.mkdir(parents=True,exist_ok=True)
        destination.write_bytes(original)
        for key, review_class in record['keys'].items():
            catalog.append(dict(id=f'{rel}::{key}',file=rel,key=key,review_class=review_class,source_version='1.03',source_sha256=record['source_sha256'],japanese=parsed[key],english='',status='untranslated'))
    build_text_resources.ROOT = output
    validation = build_text_resources.build(english,catalog,output)
    binary_report=[]
    for record in binaries:
        original = inputs[record['path']]
        hud=record['kind']=='hud_utf8_property'
        raw=bytearray(unwrap(original) if hud else original)
        for change in record['changes']:
            before,after=change['japanese'].encode(),change['english'].encode()
            if len(after)>len(before):raise ValueError('English exceeds original binary slot')
            offset=change['offset']
            raw[offset:offset+len(before)]=after+(b' ' if hud else b'\0')*(len(before)-len(after))
        result=rewrap(original,raw) if hud else bytes(raw)
        checks=verify(record,original,result)
        destination=safe(output/('resources' if hud else 'overlay'),record['path'])
        destination.parent.mkdir(parents=True,exist_ok=True)
        destination.write_bytes(result)
        binary_report.append(dict(record,output_sha256=sha(result),translations=len(record['changes']),verification=checks))
    # Whole resources regenerated from the original plus a translation file
    # (e.g. SpeakerTable.luc). Each generator validates its own output.
    generated_report=[]
    for record in index.get('generated', []):
        result, checks = generated_resources.generate(record, inputs[record['path']], KIT)
        destination=safe(output/'resources',record['path'])
        destination.parent.mkdir(parents=True,exist_ok=True)
        destination.write_bytes(result)
        generated_report.append(dict(path=record['path'],generator=record['generator'],source_sha256=record['source_sha256'],
                                     output_sha256=sha(result),verification=checks))
        if not args.edited_translations and sha(unwrap(result)) != record['expected_raw_sha256']:
            raise ValueError(f'v1.0 generated resource differs: {record["path"]}')
    validation['generated']=generated_report
    # Replacement textures (UI art redrawn with English lettering). Each file is
    # pinned by the hash of its original and of the replacement.
    texture_report=[]
    for record in index.get('textures', []):
        patch=safe(KIT, record['patch']).read_bytes()
        if sha(patch)!=record['patch_sha256'] or patch[:5]!=b'XTEX1':
            raise ValueError(f'Texture patch changed: {record["patch"]}')
        original=inputs[record['path']]
        raw=unwrap(original); delta=zlib.decompress(patch[5:])
        if len(delta)!=len(raw):
            raise ValueError(f'Texture patch size mismatch: {record["path"]}')
        new_raw=(int.from_bytes(raw,'little')^int.from_bytes(delta,'little')).to_bytes(len(raw),'little')
        if sha(new_raw)!=record['raw_output_sha256']:
            raise ValueError(f'Texture output differs: {record["path"]}')
        data=rewrap(original,new_raw)
        destination=safe(output/'resources',record['path'])
        destination.parent.mkdir(parents=True,exist_ok=True)
        destination.write_bytes(data)
        texture_report.append(dict(path=record['path'],source_sha256=record['source_sha256'],output_sha256=sha(data),raw_output_sha256=record['raw_output_sha256']))
    validation['textures']=texture_report
    # Compare logical resource bytes, allowing harmless zlib-version differences.
    if not args.edited_translations:
        for record in validation['files']:
            if sha(unwrap(safe(output/'resources',record['path']).read_bytes())) != expected[record['path']]['expected_raw_sha256']:
                raise ValueError(f'v1.0 resource differs: {record["path"]}')
        for record, approved in zip(binary_report,index['binary_files'],strict=True):
            data=safe(output/('resources' if record['kind']=='hud_utf8_property' else 'overlay'),record['path']).read_bytes()
            if sha(unwrap(data) if record['kind']=='hud_utf8_property' else data)!=approved['expected_raw_sha256']:
                raise ValueError(f'v1.0 binary output differs: {record["path"]}')
    replacements={}
    for record in validation['files']+[r for r in binary_report if r['kind']=='hud_utf8_property']+generated_report+texture_report:
        replacements[record['path'].removeprefix('common/')]=dict(record,data=safe(output/'resources',record['path']).read_bytes())
    print('Rebuilding common.psarc and verifying its copied body and changed resources...',flush=True)
    archive_report=rebuild(safe(source,'DAT/common.psarc'),output/'overlay/DAT/common.psarc',replacements)
    project=prepare_project(source,output,base,template) if base else None
    for name,value in [('validation.json',validation),('binary-text-validation.json',dict(files=binary_report)),('archive-validation.json',archive_report),('translations.json',english)]:
        (output/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    summary=dict(status='resources_and_archive_verified_pkg_not_built',kit='v1.0',edited_translations=args.edited_translations,table_entries=validation['translated_entries'],binary_edits=sum(len(r['changes']) for r in binary_report),generated_resources=len(generated_report),changed_archive_resources=len(replacements),project=str(project) if project else None,overlay=['DAT/common.psarc','eboot.bin'],input_files_modified=False,console_tested=False)
    (output/'result.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':
    try:main()
    except (ValueError,KeyError,FileNotFoundError) as e:
        sys.exit(f'ERROR: {e}')
