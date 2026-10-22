# Remaining Japanese outside dialogue: developer notes, test stages, placeholder
# strings that the game overwrites at runtime, and debug output. None of this is
# normally seen in play; it is translated so no Japanese is left anywhere safe.
import re

Z2H = str.maketrans('０１２３４５６７８９％：／ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ！？＋',
                    '0123456789%:/ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz!?+')
MONTHS = 'Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec'.split()

# ---------------- Lua constants (translations/english.json) ----------------
LUA = {
 'common/lua/ChoiceList.luc': {'0.12:k10': '[WARNING]ChoiceList: an empty table was passed to Open'},
 'common/lua/TextData.luc': {'0:k25': 'Test 1', '0:k29': 'Test 2', '0:k33': 'Test 3'},
 'common/lua/Text_Heroine.luc': {'0:k856': 'Unused'},
 'common/lua/Text_Mail.luc': {
   '0:k22': 'Mail 0 reply 5', '0:k24': 'Mail 0 reply 6', '0:k43': 'Mail 1 title', '0:k45': 'Mail 1 sender',
   '0:k47': 'Mail 1 body', '0:k49': 'Mail 1 reply 1', '0:k51': 'Mail 1 reply 2', '0:k53': 'Mail 1 reply 3',
   '0:k55': 'Mail 1 reply 4', '0:k57': 'Mail 1 reply 5', '0:k59': 'Mail 1 reply 6', '0:k63': 'HO'},
 'common/lua/Text_Stage_201.luc': {
   '0:k146': '?!',
   '0:k278': '(The shop menu opens here.\\nYou will be able to buy fried chicken, umbrellas, etc.)',
   '0:k777': '(Not yet implemented: after the fade, carry them on your back)'},
 'common/lua/Text_Stage_202.luc': {
   '0:k571': '!...............',
   '0:k862': '[In development]\\nLegion\'s voice and Misaki\'s scream are heard,\\nand Misaki\'s body appears',
   '0:k864': '[In development]\\nYou carry Nanami on your back here',
   '0:k866': '[In development]\\nYou put Nanami down here',
   '0:k1064': '(The hero tries to imitate a Legion\'s posture to get by; being attacked is still being implemented)',
   '0:k1072': 'Currently, even choosing the wrong option\\nlets you get past the small Legion',
   '0:k1074': 'In the next build, a Legion will drop from\\nthe stairwell ceiling and block the way'},
 'common/lua/Text_Stage_204.luc': {
   '0:k1076': 'I need to describe the fire extinguisher\\nin a way Miho will understand.\\n* For development, answers are marked O/X',
   '0:k1078': "It's red...  O", '0:k1080': "It's blue...  X", '0:k1082': "It's yellow...  X",
   '0:k1084': 'Shaped like a water bottle...  O', '0:k1086': "It's cylindrical...  X", '0:k1088': "It's round...  X",
   '0:k1090': 'It has a nozzle  O', '0:k1092': 'It has a handle  X', '0:k1094': 'You can grip it  X',
   '0:k1219': 'For choice 10',
   '0:k1639': '3...!', '0:k1641': '2...!', '0:k1643': '1!', '0:k1726': '...!'},
 'common/lua/Text_Stage_206.luc': {'0:k206': '... (after "Observation Ship in Peril")', '0:k208': '... (after "The Vanished Shadow")'},
 'common/lua/Text_Stage_207.luc': {
   '0:k4': '(Test)...', '0:k11': '(Test)...1', '0:k13': '(Test)...2', '0:k15': '(Test)...3',
   '0:k17': '(Test)...4', '0:k19': '(Test)...5', '0:k22': '(Test)...speech bubble'},
 'common/lua/Text_Stage_210.luc': {
   '0:k515': '<Here the hero flees into a bus,\\nbut Gyaos attack and the bus overturns, knocking them out>',
   '0:k517': '<The sequence leading up to the hero passing out is still in production>',
   '0:k519': '<Here you tackle through whatever blocks the way and press on>',
   '0:k521': '<A door is placed here as a temporary model;\\nit will be replaced with a different model>'},
 'common/lua/Text_Stage_210_2.luc': {
   '0:k214': '<This NPC is for a sub-event from Stage 10>',
   '0:k403': 'abcdefghi1jklmnopqr2stuvwxyzabc3', '0:k405': 'abcdefghijklmnopqrstuvwxy',
   '0:k407': '12345678901234567890', '0:k409': 'abcde\\nfghij'},
 'common/lua/Text_Stage_210_3.luc': {'0:k312': '<An insert song plays here>'},
 'common/lua/Text_Stage_211.luc': {
   '0:k25': 'Message 1: Otsuka', '0:k27': 'Message 2: Otsuka', '0:k29': 'Message 3: Otsuka',
   '0:k32': 'Message 1: Chief Researcher', '0:k34': 'Message 2: Chief Researcher', '0:k36': 'Message 3: Chief Researcher',
   '0:k39': 'Message 1: Researcher B', '0:k41': 'Message 2: Researcher B', '0:k43': 'Message 3: Researcher B',
   '0:k141': '........................!'},
 'common/lua/Text_Stage_213.luc': {'0:k419': 'Unused', '0:k479': '[#ffff0000]ERROR[/#]'},
 'common/lua/Text_Stage_214.luc': {'0:k595': '.........!'},
 'common/lua/ad_text.luc': {'0:k11': '~Narcist~', '0:k20': '~Self-Conscious~'},
 'common/lua/map_goal_text.luc': {'0:k4': 'Goal Point 000', '0:k10': 'Goal Point 001', '0:k215': 'S',
                                  '0:k245': 'Inside the building (not set)'},
 'common/lua/mission_text.luc': {
   '0:k2': 'Mission test', '0:k3': 'Location 6', '0:k4': 'Description 6',
   '0:k5': 'Progress text 1', '0:k6': 'Progress text 2', '0:k7': 'Progress text 3', '0:k48': 'Progress text 4',
   '0:k49': 'Progress text 5', '0:k50': 'Progress text 6', '0:k51': 'Progress text 7', '0:k52': 'Progress text 8'},
 'common/lua/script_cmn.luc': {f'0:k{242 + i}': str(i) for i in range(10)},
 'common/lua/stage_201.luc': {
   '0:k516': 'Battle event planned (after motion capture)', '0:k517': 'Event planned (after motion capture)',
   '0:k518': 'Meeting-the-writer event planned (after motion capture)'},
 'common/lua/stage_201_demo.luc': {'0.29:k245': 'Outfit branch end'},
 'common/lua/stage_202_check.luc': {'0:k23': '??????'},
 'common/lua/stage_203.luc': {'0.174:k5': 'SetEscapeParamB065:8900x4', '0.174:k14': 'SetEscapeParamB065:8900x3',
                              '0.174:k18': 'SetEscapeParamB065:8900x2', '0.174:k21': 'SetEscapeParamB065:8900x1',
                              '0.174:k22': 'SetEscapeParamB065:-----'},
 'common/lua/stage_204_check.luc': {
   '0.2:k5': 'You searched the safe! You got a lot of money and documents! (This event is planned to give items from the safe.)',
   '0.79:k162': 'Safe choice', '0.79:k163': 'time(s)'},
 'common/lua/stage_204_check_old.luc': {
   '0.1:k5': 'You searched the safe! You got a lot of money and documents! (This event is planned to give items from the safe.)'},
 'common/lua/stage_214_check.luc': {'0:k68': '??????'},
 'common/lua/stage_chr_test.luc': {'0:k111': 'Activate'},
 'common/lua/stage_chr_test_check.luc': {'0:k11': 'Look up there', '0:k13': 'Look down there', '0:k14': '*Well, look'},
 'common/lua/stage_chr_test_item.luc': {'0:k11': "??? looks like I can almost reach it, but can't"},
 'common/lua/stage_chr_test_npc.luc': {
   '0:k17': 'This here is Sarufutsu Village...', '0:k20': 'This is Sarufutsu Village...',
   '0:k22': 'This be Sarufutsu Village, y\'know...', '0:k24': 'This is Sarufutsu Village... heh heh',
   '0:k26': 'This is Sarufutsu Village?', '0:k28': 'Carry me on your back', '0:k30': "I can't",
   '0:k31': 'No way', '0:k32': '1 million yen', '0:k33': 'Please!', '0:k71': 'Activate'},
 'common/lua/stage_gui_test.luc': {
   '0:k214': 'Broken cup', '0.104:k4': 'Head to the park where you are meeting your friend (placeholder text)',
   '0.122:k3': 'Upper playable message', '0.122:k6': 'Lower playable message', '0.142:k3': 'Upper playable message'},
}

# ---------------- CSH tables (translations/english.json) ----------------
CSH = {
 'common/csv/loading_image_and_text.csh': {'r125:c2': 'Stage 217 title', 'r125:c3': 'Stage 217 text', 'r125:c4': 'Stage 217 text'},
 'common/csv/reading_material.csh': {
   'r0:c3': 'Page 1 (placeholder text)', 'r1:c3': 'Page 1 (placeholder text)',
   'r0:c4': 'Page 2\\nLine 2\\nLine 3\\nLine 4\\nLine 5\\nLine 6\\nLine 7\\nLine 8\\nLine 9\\nLine 10\\n',
   'r1:c4': 'Page 2\\n' + ''.join(f'Line {i}\\n' for i in range(2, 31)),
   'r0:c5': 'Page 3 (placeholder text)\\n', 'r1:c5': 'Page 3 (placeholder text)\\n',
   'r0:c6': 'Reading text, page 4', 'r1:c6': 'Reading text, page 4',
   'r43:c9': 'Page 7', 'r43:c10': 'Page 8'},
}

def news_placeholders(path, strings):
    """'見出しN' / '本文N' default entries in stage_*_news_text.luc."""
    out = {}
    for k, v in strings.items():
        m = re.fullmatch(r'(見出し|本文)([０-９0-9]+)', v)
        if m:
            n = m.group(2).translate(Z2H)
            out[k] = f'Headline {n}' if m.group(1) == '見出し' else f'Body text {n}'
    return out

# ---------------- HUD placeholder text (binary-english.json) ----------------
HUD_FIXED = {
 '警官の帽子/男性警官の服/男性警官の靴': 'Police Cap/Police Uniform/Police Shoes',
 '1.1（自己評価★3）（評価指数120）': '1.1 (Self-rated ★3) (Score 120)',
 '（自己評価★３）（評価数１２０）': '(Self-rated ★3) (120 ratings)',
 'ｗｗｗｗｗｗｗｗｗさん': 'WWWWWWWWW',
 '【動画】突然現れた巨大怪獣衝撃の瞬間': '[Video] The Moment a Giant Monster Appeared',
 '【動画】突然街に現れた巨大怪獣！衝撃の瞬間': '[Video] Giant Monster Suddenly Appears in Town!',
 '旺盛な食欲をもって飛来する影': 'A Shadow That Flies In, Ravenous',
 '夜の街に現れた巨大な影': 'Giant Shadow in the Night City',
 'Stage１：夜の街（まち）に現れた巨大な影': 'Stage 1: Giant Shadow in the Night City',
 'Stage10後編a': 'St10 Pt2a', 'St10後編b': 'St10 Pt2b', 'Stage 10前半': 'Stage 10 P1',
 '光の巨人現る！': 'Giant of Light!', '？？？？': '????',
 'カラアゲ大臣（ぶどうシャーベット味）を使用しますか？': 'Use Chicken Minister (Grape Sherbet)?',
 '2個→1個': '2 -> 1', 'タイプ': 'Type', 'パラメーター1': 'Parameter 1', 'パラメーター2': 'Parameter 2',
 'パラメーター3あああああ': 'Parameter 3', 'アイテム名': 'Item', 'アイテムタイプ': 'Item type',
 '主人公性別': 'Gender', '男': 'M', 'ＨＰ+000000': 'HP+000000', 'ＳＴ+000000': 'ST+000000',
 '最大全角二十文字ああああああああああ': 'Sender', '送主最大全角八 字': 'Sender', '名前最大八文字あ': 'Name',
 '受注場所最大全角十一字': 'Location',
 '＜カラアゲ大臣ぶどうシャーベット味＞を＜○○＞  購入します。      よろしいでしょうか。':
     'Buy Chicken Minister (Grape Sherbet) x 00? Are you sure?',
}

def hud_en(jp):
    """English for a HUD placeholder; None to leave the string alone."""
    s = jp.strip()
    if '�' in jp or '?' in jp:          # damaged bytes in the original; skip
        return None
    if s in HUD_FIXED:
        return HUD_FIXED[s]
    t = s.translate(Z2H)
    m = re.fullmatch(r'(?:(\d{4})年\s*)?(\d+)月\s*(\d+)日\s*(?:\((.)\)|（(.)）)?\s*(?:(\d+):(\d+))?\s*(配信|掲載)?', t.replace('　', ' '))
    if m:
        y, mo, d, _, _, hh, mm, kind = m.groups()
        out = f'{MONTHS[int(mo) - 1]} {int(d)}' + (f', {y}' if y else '') + (f' {hh}:{mm}' if hh else '')
        return out
    if re.fullmatch(r'[\d\s:%./+\[\]℃]+', t):
        return t.replace('℃', 'C')
    if '[~]' in s:
        page = re.match(r'([０-９\d]|あ)ページ', s)
        n = page.group(1).translate(Z2H) if page and page.group(1) != 'あ' else '1'
        return f'Page {n} text' + '[~]' * s.count('[~]')
    rules = [('記事内容', 'Article text'), ('記事', 'Article title'), ('タイトル', 'Title'), ('内容', 'Article text'), ('アイテム名', 'Item name'),
             ('アイテム', 'Item'), ('説明', 'Description'), ('ミッション', 'Mission description'),
             ('進捗', 'Progress'), ('メール', 'Mail title'), ('場所', 'Location'), ('項目', 'Item description area'),
             ('最大', 'Text'), ('２８日', 'Article text'), ('ヒロインの服', 'Heroine outfit item'), ('あ', 'Text'), ('PR', '[PR] Text')]
    for key, eng in rules:
        if key in s:
            if s.startswith('[PR]'): return '[PR] Text'
            if s.startswith('記事') and ('タイトル' in s): return 'Article title'
            if s.startswith('記事一覧'): return 'Article list text...'
            return eng
    return None
