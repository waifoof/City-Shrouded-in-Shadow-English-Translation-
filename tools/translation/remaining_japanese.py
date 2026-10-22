"""List every Japanese string the current translation does not cover yet.

Put this file in the kit's scripts/ folder and run it against your ORIGINAL
Japanese 1.03 files (read-only; nothing is modified):

    python scripts/remaining_japanese.py --update-folder 'D:\\Work\\Original103' --out 'D:\\Work\\remaining'

It reads DAT/common.psarc with the kit's own parsers, and eboot.bin if present.
Outputs, in --out:
  remaining.csv   one row per Japanese string still untranslated
  covered.csv     Japanese strings the translation already replaces
  summary.md      per-file counts, sorted by remaining work, plus an archive
                  inventory by extension (where art/textures live)

Strings are counted as covered when their key (tables/Lua) or byte offset
(HUD/executable) appears in translations/english.json, csh_append.json or
binary-english.json. Speaker IDs listed in speakers.json count as covered:
they stay Japanese in the scripts and SpeakerTable.luc names them in English.
"Remaining" includes internal identifiers too; the `looks_internal` column
flags likely non-display strings (file names, IDs, debug text) to skip.
"""
import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from game_text import Csh, Lua52, parse_resource, unwrap  # noqa: E402
from psarc import Psarc  # noqa: E402

KIT = HERE.parent
JP = re.compile(r'[\u3040-\u30ff\u3400-\u9fff\uff01-\uff5e\uff61-\uff9f]')
# Runs of printable UTF-8 containing Japanese, for HUD files and the executable.
UTF8_RUN = re.compile(rb'(?:[\xe3-\xe9\xef][\x80-\xbf]{2}|[\xc2-\xdf][\x80-\xbf]|[\x20-\x7e\t\n])+')
TEXT_EXT = {'.csh', '.luc', '.hud'}
MAX_OTHER = 4 * 1024 * 1024  # scan other small files (<4 MB) for stray UTF-8 text

FILE_EXT = re.compile(r'\.(png|dds|gnf|lua|luc|csh|hud|wav|at9|bnk|fsb|txt|bin)\b', re.I)
DEBUG_WORDS = re.compile(r'デバッグ|テスト用|ダミー|未使用|^(DEBUG|TEST|dbg)', re.I)
DEV_FILES = re.compile(r'/(Flag|BannedWords_\w+|\w+_param|material_\w+|\w*test\w*|\w+_old)\.(csh|luc|hud)$', re.I)
JP_PUNCT = re.compile(r'[、。！？「」…]')


def looks_internal(text):
    """Heuristic only: flags identifiers/debug strings so they can be skipped."""
    t = text.strip()
    if not t:
        return True
    if DEBUG_WORDS.search(t) or FILE_EXT.search(t):
        return True
    # identifier-shaped: no spaces, no line breaks, no Japanese punctuation,
    # and joined with ASCII separators, e.g. "item_鍵01" or "stage/名前"
    return (' ' not in t and '\\n' not in t and '\n' not in t and not JP_PUNCT.search(t)
            and bool(re.search(r'[A-Za-z0-9]', t)) and bool(re.search(r'[_/.:]', t)))


def utf8_strings(raw, base=0):
    """Loose scan, only used for --include-other."""
    for m in UTF8_RUN.finditer(raw):
        try:
            s = m.group(0).decode('utf-8')
        except UnicodeDecodeError:
            continue
        if len(JP.findall(s)) >= 2:
            lead = len(s) - len(s.lstrip(' \t\n'))
            yield base + m.start() + len(s[:lead].encode('utf-8')), s.strip(' \t\n')


HUD_PROP = bytes.fromhex('f6287f44')
JP_OK_EXTRA = set('\u3000')


def hud_strings(raw):
    """HUD text properties: magic, 8 bytes, u32 length, then the UTF-8 text
    (the same layout build_menu_binary_text.py verifies)."""
    pos = raw.find(HUD_PROP)
    while pos >= 0:
        if pos + 16 <= len(raw):
            length = int.from_bytes(raw[pos + 12:pos + 16], 'little')
            start = pos + 16
            if 0 < length < 4096 and start + length <= len(raw):
                try:
                    s = raw[start:start + length].decode('utf-8')
                except UnicodeDecodeError:
                    s = ''
                if JP.search(s):
                    yield start, s
        pos = raw.find(HUD_PROP, pos + 4)


C_STRING = re.compile(rb'(?<=\x00)(?:[\xe2-\xe9\xef][\x80-\xbf]{2}|[\xc2-\xdf][\x80-\xbf]|[\x20-\x7e\t\n\r])+(?=\x00)')


def _cp932(c):
    try:
        return c.encode('cp932')
    except UnicodeEncodeError:
        return None


def _common(c):
    """Kana or JIS level-1 kanji (the everyday set)."""
    b = _cp932(c)
    if not b or len(b) != 2:
        return False
    v = int.from_bytes(b, 'big')
    return 0x829F <= v <= 0x8396 or 0x889F <= v <= 0x9872


def plausible_c(s):
    if re.search(r'[\x00-\x08\x0b-\x1f\x7f]', s) or s != s.strip('\t\r') or '\r' in s:
        return False
    jp = JP.findall(s)
    if not jp or any(_cp932(c) is None for c in s):   # e.g. Chinese-only hanzi from code bytes
        return False
    if len(jp) >= 2:
        return True
    rest = s.replace(jp[0], '', 1)
    # a lone character: alone, or with a format token (%d, [i1]) or a label like St10
    token = re.search(r'%[0-9.]*[sdfx]|%ITEM|\[i?\d+\]|\[#|(?<![A-Za-z])[A-Z][A-Za-z]+\d+', rest)
    return _common(jp[0]) and (rest == '' or bool(token))


def c_strings(raw):
    """Complete NUL-terminated UTF-8 strings containing Japanese. Requiring a
    NUL on both sides and fully valid UTF-8 filters out code bytes."""
    for m in C_STRING.finditer(raw):
        try:
            s = m.group(0).decode('utf-8')
        except UnicodeDecodeError:
            continue
        if plausible_c(s):
            yield m.start(), s


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--update-folder', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--english', type=Path, default=KIT / 'translations/english.json')
    ap.add_argument('--binary-english', type=Path, default=KIT / 'translations/binary-english.json')
    ap.add_argument('--include-other', action='store_true',
                    help='also scan non-text files (textures etc.); very noisy, off by default')
    a = ap.parse_args()

    english = json.loads(a.english.read_text('utf-8'))
    binary = json.loads(a.binary_english.read_text('utf-8'))['files']
    covered_keys = {p: set(d) for p, d in english.items()}
    # Pooled CSH tables translated by appending (translations/csh_append.json).
    append_file = a.english.parent / 'csh_append.json'
    if append_file.exists():
        for p_, d in json.loads(append_file.read_text('utf-8')).items():
            covered_keys.setdefault(p_, set()).update(d)
    # Speaker IDs stay Japanese in the scripts; SpeakerTable.luc gives each an
    # English display name (translations/speakers.json).
    speakers_file = a.english.parent / 'speakers.json'
    speaker_ids = set(json.loads(speakers_file.read_text('utf-8'))) if speakers_file.exists() else set()
    covered_offsets = defaultdict(set)
    for f in binary:
        for c in f['changes']:
            covered_offsets[f['path']].add(c['offset'])

    a.out.mkdir(parents=True, exist_ok=True)
    rows = []          # (path, kind, key, covered, internal, text)
    ext_inventory = Counter()
    ext_bytes = Counter()
    errors = []

    psarc_path = a.update_folder / 'DAT' / 'common.psarc'
    with psarc_path.open('rb') as stream:
        archive = Psarc(stream)
        entries = archive.entries[1:]
        print(f'{psarc_path}: {len(entries)} entries', flush=True)
        for n, entry in enumerate(entries, 1):
            name = entry['path'].lstrip('/')
            path = 'common/' + name
            ext = Path(name).suffix.lower()
            ext_inventory[ext or '(none)'] += 1
            ext_bytes[ext or '(none)'] += entry['size']
            if ext not in TEXT_EXT and (not a.include_other or entry['size'] > MAX_OTHER):
                continue
            if n % 500 == 0:
                print(f'  {n}/{len(entries)}', flush=True)
            try:
                data = archive.read(entry)
            except Exception as exc:  # noqa: BLE001
                errors.append(f'{path}: read failed: {exc}')
                continue
            is_bilz = data[128:132] == b'BILZ'
            try:
                if is_bilz and data[:4] in (b'\x00hsc', b'\x00cul'):
                    res = parse_resource(data)
                    kind = 'csh' if isinstance(res, Csh) else 'lua'
                    for s in res.strings:
                        if JP.search(s['text']):
                            done = (s['key'] in covered_keys.get(path, ())
                                    or (speaker_ids and (path == 'common/lua/SpeakerTable.luc'
                                                         or s['text'] in speaker_ids)))
                            rows.append((path, kind, s['key'], done,
                                         looks_internal(s['text']), s['text']))
                    continue
                raw = unwrap(data) if is_bilz else data
            except Exception as exc:  # noqa: BLE001
                errors.append(f'{path}: parse failed: {exc}')
                raw = data
            kind = 'hud' if ext == '.hud' else ('bilz_other' if is_bilz else 'raw_other')
            for off, s in (hud_strings(raw) if ext == '.hud' else utf8_strings(raw)):
                rows.append((path, kind, off, off in covered_offsets.get(path, ()), looks_internal(s), s))

    eboot = a.update_folder / 'eboot.bin'
    if eboot.exists():
        print('Scanning eboot.bin', flush=True)
        for off, s in c_strings(eboot.read_bytes()):
            rows.append(('eboot.bin', 'executable', off, off in covered_offsets.get('eboot.bin', ()),
                         looks_internal(s), s))

    header = ['path', 'kind', 'key_or_offset', 'looks_internal', 'japanese']
    with (a.out / 'remaining.csv').open('w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f); w.writerow(header)
        for p, k, key, cov, internal, t in rows:
            if not cov:
                w.writerow([p, k, key, 'yes' if internal else '', t.replace('\n', '\\n')])
    with (a.out / 'covered.csv').open('w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f); w.writerow(header)
        for p, k, key, cov, internal, t in rows:
            if cov:
                w.writerow([p, k, key, 'yes' if internal else '', t.replace('\n', '\\n')])

    per = defaultdict(lambda: [0, 0, 0, 0])  # covered, remaining_display, remaining_internal, remaining_chars
    for p, k, key, cov, internal, t in rows:
        r = per[p]
        if cov:
            r[0] += 1
        elif internal:
            r[2] += 1
        else:
            r[1] += 1; r[3] += len(t)
    tot = [sum(v[i] for v in per.values()) for i in range(4)]
    devp = {p for p in per if DEV_FILES.search(p)}
    play = [sum(v[i] for p, v in per.items() if p not in devp) for i in range(4)]
    L = ['# Remaining Japanese text', '',
         f'Translated: **{tot[0]:,}** strings. Remaining in player-facing files: **{play[1]:,}** strings '
         f'(~{play[3]:,} Japanese characters). Developer/data tables: {tot[1] - play[1]:,}. '
         f'Strings flagged internal: {tot[2]:,}.', '',
         'The executable also holds many debug and editor strings; expect a share of its rows to be skippable.', '',
         'Note: art drawn into textures is not text and does not appear here; see the inventory below.', '',
         '## Files with remaining display text', '',
         '| File | Done | Remaining | Internal? | JP chars left |', '|---|---:|---:|---:|---:|']
    dev = {p for p in per if DEV_FILES.search(p)}
    for p, (c, rd, ri, ch) in sorted(per.items(), key=lambda kv: -kv[1][3]):
        if rd and p not in dev:
            L.append(f'| `{p}` | {c} | {rd} | {ri} | {ch:,} |')
    L += ['', '## Developer/data tables (probably never shown to players)', '',
          'Flag names, banned-word filters, tuning parameters and test files. Review before translating.', '',
          '| File | Done | Remaining | JP chars left |', '|---|---:|---:|---:|']
    for p, (c, rd, ri, ch) in sorted(per.items(), key=lambda kv: -kv[1][3]):
        if rd and p in dev:
            L.append(f'| `{p}` | {c} | {rd} | {ch:,} |')
    L += ['', '## Fully covered files', '']
    L += [f'- `{p}` ({c})' for p, (c, rd, ri, ch) in sorted(per.items()) if c and not rd]
    L += ['', '## Archive inventory by extension', '', '| Ext | Files | Size (MB) |', '|---|---:|---:|']
    for ext, cnt in sorted(ext_inventory.items(), key=lambda kv: -ext_bytes[kv[0]]):
        L.append(f'| {ext} | {cnt} | {ext_bytes[ext] / 1e6:,.1f} |')
    if errors:
        L += ['', '## Errors', ''] + [f'- {e}' for e in errors[:200]]
    (a.out / 'summary.md').write_text('\n'.join(L) + '\n', encoding='utf-8')
    print(f'\nTranslated {tot[0]:,} | remaining display {tot[1]:,} | internal {tot[2]:,}')
    print(f'Wrote {a.out / "summary.md"}, remaining.csv, covered.csv')


if __name__ == '__main__':
    main()
