"""Layout/token rules shared by the review sheets and the edit checker."""
import re
TOKENS = re.compile(r'\[i\d+\]|\[#[0-9a-fA-F]+\]|\[/#\]|<[A-Za-z_][A-Za-z_0-9]*>|%[0-9.]*[sdf]')
ACTION_LABEL = re.compile(r'^(?:(?:Talk|Check)(?:Cmnd_|_\d+_Command_)|(?:TkLabel|ChkLabel|Cmnd)_\d+_|Fuki_213_)')
ACTION_KEYS = {'common/lua/Text_Stage_204.luc': {f'0:k{k}' for k in list(range(1309, 1353, 2)) + [1355, 1362, 1364, 1367, 1369]}}
CAPS = {  # (max chars per line, fixed?) by resource; None = auto-wrapped field
    'common/csv/loading_image_and_text.csh': 58, 'common/csv/staffroll_image.csh': 60, 'common/csv/staffroll.csh': 44,
    'common/lua/place_text.luc': 38, 'common/csv/LoadingTips.csh': 64, 'common/lua/intermission_result_data.luc': 27,
    'common/csv/store_text_data.csh': 37, 'common/lua/map_goal_text.luc': 73, 'common/csv/reading_material.csh': 63,
    'common/lua/option_menu_text.luc': 50,
}
WRAPPED = re.compile(r'news_text|item_ad_text|mission_text|item_data|ad_text|news_data')
def br(s, rel):  # split into display lines
    parts = s.split('\\n') if rel.endswith('.csh') else s.split('\n')
    while len(parts) > 1 and parts[-1] == '':
        parts.pop()
    return parts
def limits(rel, row):
    """Return dict describing what an edit of this row may do."""
    en, jp = row['en'], row['jp']
    el, jl = br(en, rel), br(jp, rel)
    if row.get('prompt'):
        return dict(kind='prompt', max_line=11, max_lines=1, ascii=True)
    if WRAPPED.search(rel):
        return dict(kind='wrapped', max_total=int(len(en) * 1.2) + 15, max_lines=len(el))
    cap = CAPS.get(rel, 65)
    if rel == 'common/csv/loading_image_and_text.csh':
        return dict(kind='layout', max_line=58, max_lines=7)
    n = max(len(el), len(jl))
    if row.get('mode') and rel.startswith('common/lua/Text'):
        n = max(n, 3)                     # dialogue window holds three lines
    return dict(kind='layout', max_line=max(cap, max(len(x) for x in el)), max_lines=n)
def check(rel, row, new):
    """List of problems with replacing row['en'] by new."""
    errs = []
    if not isinstance(new, str) or not new.strip(): return ['empty']
    if '\0' in new: errs.append('NUL')
    if sorted(TOKENS.findall(new)) != sorted(TOKENS.findall(row['jp'])) and sorted(TOKENS.findall(new)) != sorted(TOKENS.findall(row['en'])):
        errs.append(f"tokens {TOKENS.findall(row['en'])} -> {TOKENS.findall(new)}")
    if rel.endswith('.csh') and '\n' in new: errs.append('CSH needs literal \\n, not a newline')
    if rel.endswith('.luc') and '\\n' in new and '\\n' not in row['en']: errs.append('Lua text uses a real newline, not literal \\n')
    if rel.endswith('.csh') and ',' in new and rel.endswith('staffroll.csh'): errs.append('credits: write commas as 0x2C')
    if re.search(r'[\u3040-\u30ff\u4e00-\u9fff]', new) and not re.search(r'[\u3040-\u30ff\u4e00-\u9fff]', row['en']): errs.append('Japanese characters')
    if re.search(r'[“”‘’…]', new): errs.append('use straight quotes and "..." (font safety)')
    lim = limits(rel, row); lines = br(new, rel)
    if len(lines) > lim['max_lines']: errs.append(f"{len(lines)} lines > {lim['max_lines']}")
    vis = lambda l: len(re.sub(r'\[#[0-9a-fA-F]+\]|\[/#\]', '', l))   # colour tags take no space
    if 'max_line' in lim and max(vis(l) for l in lines) > lim['max_line']: errs.append(f"line of {max(vis(l) for l in lines)} chars > {lim['max_line']}")
    if 'max_total' in lim and len(new) > lim['max_total']: errs.append(f"{len(new)} chars > {lim['max_total']}")
    if lim.get('ascii') and not new.isascii(): errs.append('prompt must be ASCII')
    if row['jp'].endswith(('\\n', '\n')) != new.endswith(('\\n', '\n')) and row['en'].endswith(('\\n','\n')) != new.endswith(('\\n','\n')):
        errs.append('trailing line break must match')
    return errs
