"""Validate an English draft against catalogued sources and build resource files.

This only builds resources. It does not change an archive, create a package,
or establish that these new strings have been tested on a console.
"""
import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

from game_text import Csh, parse_resource, rewrap, unwrap
from audit_message_tables import inspect_data as inspect_messages

ROOT = Path(__file__).resolve().parent.parent
TOKENS = re.compile(r'\[i\d+\]|\[#[0-9a-fA-F]+\]|\[/#\]|<[A-Za-z_][A-Za-z_0-9]*>|%[0-9.]*[sdf]')
ACTION_LABEL = re.compile(r'^(?:(?:Talk|Check)(?:Cmnd_|_\d+_Command_)|(?:TkLabel|ChkLabel|Cmnd)_\d+_|Fuki_213_)')
# Chapter 204 uses Sin/Chk names for its interaction prompts, and also
# uses those prefixes for ordinary text. Pin only the reviewed prompt keys.
ACTION_KEYS = {'common/lua/Text_Stage_204.luc': {
    f'0:k{k}' for k in list(range(1309, 1353, 2)) + [1355, 1362, 1364, 1367, 1369]
}}


def contained(root, relative):
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError(f'Path leaves its source/output root: {relative}')
    return path


def build(edits, catalog, output_root):
    by_id = {row['id']: row for row in catalog}
    pending = []
    prompt_checks = []
    message_checks = []
    for rel, replacements in edits.items():
        if not replacements:
            raise ValueError(f'Empty translation set: {rel}')
        rows = {key: by_id[f'{rel}::{key}'] for key in replacements}
        versions = {row['source_version'] for row in rows.values()}
        if len(versions) != 1:
            raise ValueError(f'Mixed source versions: {rel}')
        label = {'1.00': 'base100', '1.03': 'update103'}[versions.pop()]
        source = contained(ROOT / 'extracted' / label, rel)
        original = source.read_bytes()
        digest = hashlib.sha256(original).hexdigest()
        resource = parse_resource(original)
        strings = {s['key']: s['text'] for s in resource.strings}
        messages = None
        if (rel == 'common/lua/TextData.luc'
                or re.fullmatch(r'common/lua/Text_Stage_\d+(?:_\d+)?\.luc', rel)
                or rel in {f'common/lua/Text_{name}.luc' for name in
                           ['Common', 'Heroine', 'Kasiwagi', 'Mail', 'Plan00', 'EpilogueText']}):
            # Conservative project budget from Test 2 console screenshots.
            # This is not a reverse-engineered engine limit or a pixel-fit test.
            messages = inspect_messages(original)
            for message in messages:
                if (not ACTION_LABEL.match(message['message_id'])
                        and message['text'].get('key') not in ACTION_KEYS.get(rel, set())):
                    continue
                key = message['text']['key']
                if key not in replacements:
                    continue
                english = replacements[key]
                if not isinstance(english, str) or not english.isascii() or len(english) > 11 or '\n' in english:
                    raise ValueError(f'Interaction prompt exceeds the 11-character budget: {key}: {english}')
                prompt_checks.append(dict(path=rel, message=message['message_id'], key=key, english=english))
        for key, english in replacements.items():
            row = rows[key]
            if row['source_sha256'] != digest or row['japanese'] != strings[key]:
                raise ValueError(f'Stale source: {rel}::{key}')
            if row['review_class'] == 'internal_or_filter_preserve':
                raise ValueError(f'Internal string must be preserved: {rel}::{key}')
            if not isinstance(english, str) or not english or '\0' in english:
                raise ValueError(f'Invalid English value: {rel}::{key}')
            if Counter(TOKENS.findall(strings[key])) != Counter(TOKENS.findall(english)):
                raise ValueError(f'Control/format token mismatch: {rel}::{key}')
            if isinstance(resource, Csh) and '\\n' in strings[key] and '\n' in english:
                raise ValueError(f'CSH line breaks must remain literal \\n: {key}')
        rebuilt = resource.rebuild(replacements)
        wrapped = rewrap(original, rebuilt)
        if unwrap(wrapped) != rebuilt:
            raise ValueError('Compression round trip failed')
        reread = parse_resource(wrapped)
        if {s['key']: s['text'] for s in reread.strings} != strings | replacements:
            raise ValueError('Reparsed strings differ from the requested edits')
        restored = reread.rebuild({key: strings[key] for key in replacements})
        if restored != resource.raw:
            raise ValueError(f'Non-text bytes changed: {rel}')
        if messages is not None:
            after_messages = inspect_messages(wrapped)
            if len(messages) != len(after_messages):
                raise ValueError(f'Message table count changed: {rel}')
            for before, after in zip(messages, after_messages, strict=True):
                for field in ['message_id', 'mode', 'speaker', 'extra']:
                    expected = before[field]
                    # Preserve the exact legacy pilot edit carried by Test 4.
                    # It occupies field 2 of a generic command declaration,
                    # and predates this expanded shared-table audit. This is
                    # a single pinned compatibility exception, not permission
                    # to translate other speaker identifiers.
                    if (rel == 'common/lua/Text_Common.luc'
                            and before['message_id'] == 'DEFAULT_CMND_ITEM'
                            and field == 'speaker'
                            and replacements.get('0:k87') == 'Items'):
                        expected = {'key': '0:k87', 'value': 'Items'}
                    if expected != after[field]:
                        raise ValueError(f'Protected message field changed: {rel}: {before["message_id"]}: {field}')
            message_checks.append(dict(path=rel, declarations=len(messages),
                                       protected_fields_match_expected=True,
                                       legacy_field_exceptions=(['DEFAULT_CMND_ITEM.speaker: Items']
                                           if rel == 'common/lua/Text_Common.luc' and replacements.get('0:k87') == 'Items' else [])))
        if isinstance(resource, Csh):
            for before, after in zip(resource.cells, reread.cells, strict=True):
                if before[0] != 0 and before != after:
                    raise ValueError('Numeric or null CSH cell changed')
        record = dict(path=rel, source_version=rows[next(iter(rows))]['source_version'],
                      source_sha256=digest, output_sha256=hashlib.sha256(wrapped).hexdigest(),
                      translations=len(replacements), input_bytes=len(original),
                      output_bytes=len(wrapped), untouched_strings=len(strings)-len(replacements))
        pending.append((contained(output_root / 'resources', rel), wrapped, record))
    # Validate the entire batch before writing anything or changing the catalog.
    for path, data, record in pending:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        for key, english in edits[record['path']].items():
            row = by_id[f"{record['path']}::{key}"]
            if row['english'] != english or not row['status'].startswith('console_verified_'):
                row['status'] = 'draft_not_console_tested'
            row['english'] = english
    return dict(status='validated_draft_resources_not_packaged',
                translated_entries=sum(r['translations'] for _, _, r in pending),
                interaction_prompt_budget=11, interaction_prompts_checked=prompt_checks,
                message_tables_checked=message_checks,
                files=[r for _, _, r in pending])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--translations', type=Path, action='append', required=True)
    parser.add_argument('--name', required=True)
    args = parser.parse_args()
    if not re.fullmatch(r'[a-z0-9][a-z0-9_-]*', args.name) or args.name == 'pilot':
        raise ValueError('Use a new build name, separate from the tested pilot')
    edits = {}
    for path in args.translations:
        for rel, replacements in json.loads(path.read_text('utf-8')).items():
            target = edits.setdefault(rel, {})
            for key, english in replacements.items():
                if key in target and target[key] != english:
                    raise ValueError(f'Conflicting translations: {rel}::{key}')
                target[key] = english
    catalog_path = ROOT / 'translation/catalog.jsonl'
    catalog = [json.loads(line) for line in catalog_path.read_text('utf-8').splitlines()]
    output = ROOT / 'build' / args.name
    report = build(edits, catalog, output)
    report['translation_files'] = [str(path) for path in args.translations]
    (output / 'translations.json').write_text(json.dumps(edits, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    (output / 'validation.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    catalog_path.write_text(''.join(json.dumps(row, ensure_ascii=False)+'\n' for row in catalog), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
