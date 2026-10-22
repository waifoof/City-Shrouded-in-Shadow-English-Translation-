"""Rebuild the Test8 translation data from the Test7 kit plus the new English.

Usage: python merge.py <Test7 kit> <Test8 kit> <folder of extracted originals> <eboot.bin> <speaker_ids.json>

Reads Test7's english.json, binary-english.json and source-index.json, adds the
new entries, validates every changed resource with the kit's own code against
the original files, and writes the three data files into the Test8 kit
(scripts and docs there are left alone). Pinned hashes are regenerated.
"""
import sys, json, hashlib, shutil, struct
from pathlib import Path
T7, T8, ORIG, EBOOT = map(Path, sys.argv[1:5])  # argv[5]: speaker IDs from speaker_scan.py
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(T8/'scripts')]
from game_text import parse_resource, unwrap, rewrap, JAPANESE
import build_text_resources
from build_menu_binary_text import verify
from recaps import R
from ending import E
from eboot_tl import B
import names_tl, hud_tl
from credits_tl import C as CREDITS
from speakers_tl import S as SPEAKER_NAMES
import re, generated_resources, build_speaker_table
import leftovers_tl, hud_placeholders_tl, eboot_debug_tl

sha = lambda b: hashlib.sha256(b).hexdigest()
en = json.loads((T7/'translations/english.json').read_text('utf-8'))
binfile = json.loads((T7/'translations/binary-english.json').read_text('utf-8'))
idx = json.loads((T7/'data/source-index.json').read_text('utf-8'))
tables = {t['path']: t for t in idx['tables']}
orig = lambda rel: (ORIG/rel.removeprefix('common/')).read_bytes()
strings = lambda rel: {s['key']: s['text'] for s in parse_resource(orig(rel)).strings}

def br(s): return s.replace('|', '\\n')            # CSH line breaks are literal \n
def fit(src, eng):                                  # match the source's trailing break
    eng = eng.rstrip()
    while eng.endswith('\\n'): eng = eng[:-2]
    return eng + ('\\n' if src.endswith('\\n') else '')

# ---------- table resources ----------
new = {}
rel = 'common/csv/loading_image_and_text.csh'; src = strings(rel); add = {}
for row, (title, male, female) in R.items():
    for col, text in ((2, title), (3, male), (4, female or male)):
        k = f'r{row}:c{col}'
        if JAPANESE.search(src[k]):
            add[k] = fit(src[k], br(text)) if col > 2 else text
new[rel] = add
rel = 'common/csv/staffroll_image.csh'; src = strings(rel)
new[rel] = {f'r{r}:c7': fit(src[f'r{r}:c7'], br(t)) for r, t in E.items()}
new['common/csv/store_text_data.csh'] = dict(names_tl.STORE_TEXT)
new['common/csv/staffroll.csh'] = {f'r{r}:c3': t for r, t in CREDITS.items()}
rel = 'common/csv/BrightStars.csh'; src = strings(rel)
stars = dict(names_tl.STARS_HEADER)
for k, v in src.items():
    row, col = k.split(':')
    if col == 'c0' and row != 'r0' and JAPANESE.search(v):
        stars[k] = src[f'{row}:c1']
# Developer notes, test stages, placeholders and debug output (rarely or never seen).
for rel, add in {**leftovers_tl.LUA, **leftovers_tl.CSH}.items():
    new.setdefault(rel, {}).update(add)
for f in sorted((ORIG/'lua').glob('stage_*_news_text.luc')):
    rel = 'common/lua/' + f.name
    add = leftovers_tl.news_placeholders(rel, strings(rel))
    if add: new.setdefault(rel, {}).update(add)
# store_data.csh and BrightStars.csh share pooled string slots, so they go through
# the append-only csh_append generator instead of the table writer.
append = {'common/csv/store_data.csh': dict(names_tl.STORE_DATA), 'common/csv/BrightStars.csh': stars}

for rel, add in new.items():
    data = orig(rel); src = strings(rel)
    for k in add: assert JAPANESE.search(src[k]) or not src[k].isascii(), f'not Japanese: {rel} {k}'
    if rel in tables:
        assert tables[rel]['source_sha256'] == sha(data), f'original differs from kit pin: {rel}'
        assert not set(add) & set(en[rel]), f'overlap with existing keys: {rel}'
    else:
        tables[rel] = dict(path=rel, source_sha256=sha(data), expected_raw_sha256='', keys={})
        idx['tables'].append(tables[rel]); en[rel] = {}
    en[rel].update(add)
    tables[rel]['keys'].update({k: 'dialogue_or_ui_candidate' for k in add})

# Line-by-line review pass (review_out/b*.json): corrections to existing English.
for f in sorted((HERE/'review_out').glob('b*.json')):
    for rel, ed in json.loads(f.read_text('utf-8')).items():
        for k, v in ed.items():
            assert k in en[rel], f'review key not translated: {rel} {k}'
            en[rel][k] = v
        new.setdefault(rel, {})

work = HERE/'_validate'; shutil.rmtree(work, ignore_errors=True)
catalog = []
for rel in new:
    data = orig(rel); dest = work/'extracted/update103'/rel
    dest.parent.mkdir(parents=True, exist_ok=True); dest.write_bytes(data)
    parsed = strings(rel)
    for k, cls in tables[rel]['keys'].items():
        catalog.append(dict(id=f'{rel}::{k}', file=rel, key=k, review_class=cls, source_version='1.03',
                            source_sha256=tables[rel]['source_sha256'], japanese=parsed[k], english='',
                            status='untranslated'))
build_text_resources.ROOT = work
report = build_text_resources.build({rel: en[rel] for rel in new}, catalog, work)
for f in report['files']:
    tables[f['path']]['expected_raw_sha256'] = sha(unwrap((work/'resources'/f['path']).read_bytes()))
    print(f"table OK {f['path']}: +{len(new[f['path']])} ({f['translations']} total)")

# ---------- binary (eboot + HUD) ----------
records = binfile['files']; approved = idx['binary_files']
by_path = {r['path']: i for i, r in enumerate(records)}
def add_changes(path, kind, data, changes):
    if path in by_path:
        rec = records[by_path[path]]
        assert rec['source_sha256'] == sha(data), f'binary source differs from pin: {path}'
        have = {c['offset'] for c in rec['changes']}
        assert not have & {c['offset'] for c in changes}, f'overlap: {path}'
        rec['changes'] = sorted(rec['changes'] + changes, key=lambda c: c['offset'])
    else:
        rec = dict(path=path, kind=kind, source_sha256=sha(data), changes=sorted(changes, key=lambda c: c['offset']))
        records.append(rec); approved.append({}); by_path[path] = len(records)-1
    return rec

raw = EBOOT.read_bytes()
def cstring(o):
    end = raw.index(b'\0', o); return raw[o:end].decode('utf-8')
assert not set(B) & set(eboot_debug_tl.D), 'eboot overlap'
eb = [dict(offset=o, japanese=cstring(o), english=e) for o, e in sorted({**B, **eboot_debug_tl.D}.items())]
add_changes('eboot.bin', 'nul_utf8', raw, eb)
huds = {p: dict(c) for p, c in hud_tl.H.items()}
for p, c in hud_placeholders_tl.H.items():
    assert not set(c) & set(huds.get(p, {})), f'HUD overlap {p}'
    huds.setdefault(p, {}).update(c)
for path, changes in huds.items():
    data = orig(path); body = unwrap(data)
    ch = []
    for o, e in changes.items():
        n = struct.unpack_from('<I', body, o-4)[0]
        ch.append(dict(offset=o, japanese=body[o:o+n].decode('utf-8'), english=e))
    add_changes(path, 'hud_utf8_property', data, ch)

for i, rec in enumerate(records):
    data = raw if rec['path'] == 'eboot.bin' else orig(rec['path'])
    hud = rec['kind'] == 'hud_utf8_property'
    body = bytearray(unwrap(data) if hud else data)
    for c in rec['changes']:
        j, e = c['japanese'].encode(), c['english'].encode()
        assert len(e) <= len(j), f"too long: {rec['path']} {c['offset']}"
        body[c['offset']:c['offset']+len(j)] = e + (b' ' if hud else b'\0')*(len(j)-len(e))
    out = rewrap(data, bytes(body)) if hud else bytes(body)
    verify(rec, data, out)                       # kit's own strict check
    structure = dict(rec, changes=[{k: v for k, v in c.items() if k != 'english'} for c in rec['changes']])
    approved[i] = dict(structure_sha256=sha(json.dumps(structure, ensure_ascii=False, sort_keys=True).encode()),
                       expected_raw_sha256=sha(bytes(body)))
print(f"binary OK: {len(records)} files, {sum(len(r['changes']) for r in records)} edits "
      f"(eboot {len(records[by_path['eboot.bin']]['changes'])})")

# ---------- generated resources ----------
st_rel = 'common/lua/SpeakerTable.luc'
_, st_entries = build_speaker_table.read_original(unwrap(orig(st_rel)))
ids = set(json.loads(Path(sys.argv[5]).read_text('utf-8'))) | {k for k, _, _ in st_entries}
def speaker_name(i):
    b = re.sub(r'＿\d+$', '', i)
    for c in (i, b, i.strip('　 '), b.strip('　 ')):
        if c in SPEAKER_NAMES: return SPEAKER_NAMES[c]
    raise KeyError(f'No English speaker name: {i}')
speakers = {i: speaker_name(i) for i in sorted(ids - build_speaker_table.TOKEN_KEYS)}
speakers.update({k: SPEAKER_NAMES[k] for k in build_speaker_table.TOKEN_KEYS if k in SPEAKER_NAMES})
for rel in (*append, st_rel):
    assert rel not in tables, f'generated resource also in tables: {rel}'
for rel, ed in append.items():
    src = strings(rel)
    for k in ed: assert JAPANESE.search(src[k]) or k in names_tl.STARS_HEADER, f'not Japanese: {rel} {k}'
(T8/'translations/speakers.json').write_text(json.dumps(speakers, ensure_ascii=False, indent=1)+'\n', encoding='utf-8')
(T8/'translations/csh_append.json').write_text(json.dumps(append, ensure_ascii=False, indent=1)+'\n', encoding='utf-8')
idx['generated'] = []
for rel, kind in [(st_rel, 'speaker_table')] + [(r, 'csh_append') for r in append]:
    data = orig(rel)
    rec = dict(path=rel, generator=kind, source_sha256=sha(data))
    out, info = generated_resources.generate(rec, data, T8)
    rec['expected_raw_sha256'] = sha(unwrap(out))
    idx['generated'].append(rec)
    print(f'generated OK {rel}: {info}')

# ---------- write ----------
idx['kit'] = 'English Test9'
(T8/'translations/english.json').write_text(json.dumps(en, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
(T8/'translations/binary-english.json').write_text(json.dumps(binfile, ensure_ascii=False, indent=1)+'\n', encoding='utf-8')
for rel in ('translations/english.json', 'translations/binary-english.json',
            'translations/speakers.json', 'translations/csh_append.json'):
    idx['translation_sha256'][rel] = sha((T8/rel).read_bytes())
(T8/'data/source-index.json').write_text(json.dumps(idx, ensure_ascii=False, indent=1)+'\n', encoding='utf-8')
hud_count = sum(r['kind'] == 'hud_utf8_property' for r in records)
print(f"tables {len(idx['tables'])}, table entries {sum(len(v) for v in en.values())}, "
      f"archive resources to verify {len(idx['tables'])+len(idx['generated'])+hud_count}")
