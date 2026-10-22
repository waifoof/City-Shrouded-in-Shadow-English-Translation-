> Style guide used for the line-by-line review pass. Paths refer to the authoring setup in `tools/translation/`.

# City Shrouded in Shadow (巨影都市) English: refinement review guide

## The game
PS4, 2017 (Bandai Namco / Granzella). A disaster-survival adventure: an ordinary
person (the player, male or female, name chosen by the player) is caught in
Mitsuna City while giant monsters and heroes from Ultraman, Godzilla, Gamera,
Evangelion and Patlabor fight around them. The story is about surviving,
helping strangers, and the people the hero meets: Yuki Kono (the friend they
were meeting in the park), Risa Kashiwagi (a journalist), Otsuka (a web writer,
her ex-colleague), Miho (a lost child), the W&P mercenaries Muto and Shibata,
Dr. Fukazawa and staff of the Cosmic Ray Research Institute, and many NPCs.
Tone: grounded, a little wry, often comedic NPC chatter, with sincere and
romantic moments with the heroine. News articles are in-world web news.

## Your job
Review an existing English translation line by line against the Japanese and
improve it. This is a polish pass on a translation that already works in-game.
1. Accuracy first: fix mistranslations, omissions, wrong subject/object, wrong
   speaker attitude, misread jokes, numbers, names.
2. Then naturalness: idiomatic, natural English a native speaker would write
   for this character and situation. Remove translationese and stiffness.
   Keep each character's voice (child, old man, rough mercenary, polite clerk).
3. Consistency within your batch (terms, how people address each other).
4. Typos, grammar, punctuation, capitalization.
Do NOT rewrite lines that are already accurate and natural just to vary style.
Do not add content that isn't in the Japanese, and do not drop content. Puns
may be adapted. If a line is fine, leave it out of your output.

## Hard rules (the checker enforces most of them)
- Keep control tokens exactly: [i1] button icons, [#ff44ff44]...[/#] colour,
  <P_FNAME> <P_LNAME> <H_FNAME> <H_LNAME> name tokens, %d %s, <br>.
  You may move them within the sentence where English word order needs it.
  Full names go given-name first: write <P_FNAME> <P_LNAME> (and <H_FNAME> <H_LNAME>),
  never the Japanese order <P_LNAME><P_FNAME>.
- Line breaks: in .luc files a line break is a real newline ("\n" in JSON);
  in .csh files it is the two characters backslash + n ("\\n" in JSON).
  Keep a trailing line break if the current English has one.
- Respect each row's limit (chars per line / number of lines / total length).
  Dialogue boxes show up to 3 lines; break long lines sensibly.
- Rows marked PROMPT are on-screen interaction labels: at most 11 ASCII
  characters, one line (e.g. "Talk", "Check", "Listen in").
- ASCII punctuation only: straight quotes ' and ", three dots "..." for
  ellipses (never the single … character), no curly quotes, no full-width
  characters. "?!" is fine. Dashes: use "-" or "--".
- Credits (staffroll.csh): commas must be written as 0x2C. Only fix clear
  errors there (role names, wrong English company names); keep name romanization
  unless you are sure of the reading.
- Many messages exist as male/female protagonist pairs (IDs ending in "f", or
  male/female columns). The Japanese differs only in gendered speech; keep the
  English of a pair consistent (usually identical) unless the content differs.

## Honorifics: localize
No -san/-kun/-chan/-sama/-sensei/-senpai in English (exception: brand or
mascot names like "Rako-chan" may stay).
- さん on an adult's surname in polite speech -> "Mr./Ms. Surname"
  (e.g. 柏木さん -> "Ms. Kashiwagi", 大塚さん -> "Mr. Otsuka"). Use the bare
  surname when the speaker is rough, hostile, a superior, or in narration/news.
- Given name + さん/ちゃん/くん -> just the given name ("Yuki", "Miho", "Risa").
- 先生 for a doctor/researcher -> "Dr. Surname"; for a teacher -> "Mr./Ms.".
- 様/お客様 -> "sir"/"ma'am"/"Mr./Ms." or drop, as fits.
- Keep the established forms below.

## Fixed glossary (do not change these spellings)
People: Yuki Kono, Risa Kashiwagi (protagonist calls her "Ms. Kashiwagi" until
they're close; "Risa" where the Japanese uses リサ), Otsuka (Mr. Otsuka when
addressed politely), Miho, Muto, Shibata, Fujiwara, Naoki, Kumi, Dr. Fukazawa,
First Officer Oda, Captain Katagiri, Deputy Director Sasaki, Chief Sawada,
Hirai, Mukojima, Kazuya Ichijo, Sakurako, Norio Nakagawa, Busujima, Koji Jinnai,
Sudo, Futamura, Akimoto, Iwabuchi, Senior Officer Yanai, Kuribayashi, Kinoshita,
Ikeuchi, Morimoto, Takebe, Nanami, Misaki, Kyoko, Kiyoshi, Kuro, Toro.
Places/orgs: Miyato City (宮都市, the main city where the game takes place), Mitsuna City (三津奈市, the neighbouring city), Iberis Tower, Yamabuki Building, Hananira,
West Azami Park, Aokiba, Sumire Ward, Hinageshidai Station, Suzuran Boulevard,
Mizuna Shopping Street, Sakuramachi Intersection, Miyato Sky Tower,
Ebine Publishing (editor-in-chief / "the chief"), Cosmic Ray Research Institute,
W&P / W&P Consulting, Kunshiran Construction, NKX, Clover (convenience store
chain), Cafe Yamagobo, KYOEI NEWS, Weekly Giant Shadow, Secret Cosplay Club.
Things: Chicken Minister (fried chicken brand), Giant Shadow Coins, Labor,
Ingram, Grau-Bear, Gyaos, Legion, Angel (Evangelion), giant humanoid weapon,
red giant, giant of light, giant alien, giant shadow(s) (巨影), Type-3 Kiryu,
PANSIE. Disaster Report series: 絶体絶命都市 = Disaster Report, 絶体絶命都市2 = Raw Danger!. Franchise names use official English (Ultraman, Godzilla, Gamera,
Evangelion, Patlabor, NERV, EVA Unit-01, etc.).
If you believe a glossary term is wrong, do not change it; mention it in notes.

## Output
1. Write ONLY the changed entries to review_out/<batch>.json:
   {"common/lua/Text_Stage_201.luc": {"0:k123": "New English", ...}, ...}
   Use the file path and key exactly as shown in the view.
2. Run: python3 check_edits.py review_out/<batch>.json
   Fix every reported problem and re-run until it reports 0 problems.
3. Write review_out/<batch>_notes.md: at most 15 short bullets
   on things worth knowing across the game (glossary doubts, recurring errors,
   cross-file inconsistencies you noticed). No per-line changelog.
Do not edit any other file.
