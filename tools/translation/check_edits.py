"""Check proposed edits: python check_edits.py edits.json [more.json ...]
edits.json = {"common/lua/Text_Stage_204.luc": {"0:k236": "New English", ...}, ...}
Prints every problem; exit code 1 if any."""
import json, sys, glob
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from review_rules import check
sheets = {}
for f in glob.glob(str(HERE / 'review/*.json')):
    d = json.load(open(f, encoding='utf-8')); sheets[d['path']] = {r['key']: r for r in d['rows']}
bad = 0; n = 0
for f in sys.argv[1:]:
    for rel, edits in json.load(open(f, encoding='utf-8')).items():
        if rel not in sheets: print(f'{f}: unknown file {rel}'); bad += 1; continue
        for k, v in edits.items():
            n += 1
            row = sheets[rel].get(k)
            if row is None: print(f'{rel} {k}: unknown key'); bad += 1; continue
            for e in check(rel, row, v):
                print(f'{rel} {k}: {e}\n    {v!r}'); bad += 1
print(f'{n} edits checked, {bad} problems')
sys.exit(1 if bad else 0)
