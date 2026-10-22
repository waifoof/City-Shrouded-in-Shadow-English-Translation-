CITY SHROUDED IN SHADOW (巨影都市) - ENGLISH TRANSLATION v1.0
CUSA03562, Japanese PS4 release with update 01.03
Unofficial fan translation.

This kit turns YOUR OWN untranslated Japanese 1.03 game files into English.
It contains no game files: only the English text, small binary patches for
redrawn menu images, and the scripts that apply them. The game itself, its
update and any packaging tools must come from you.

WHAT IS TRANSLATED
  * All story dialogue, NPC lines, choices and speaker names
  * Items, readable materials, mail, missions, shop, records, save data
  * In-game news site articles, loading-screen story recaps, ending monologue
  * Menus, HUD, interaction prompts, error/system messages, staff credits
  * 168 redrawn images: options menu, all controller layouts, item menu tabs,
    stage title and stage-clear cards, struggle/shake-off prompts, intermission
    screen buttons, boot notices
  Left in Japanese on purpose: signage inside scene artwork and photos, logos,
  developer placeholder images, internal names never shown in play.

WHAT YOU NEED
  * Your own CUSA03562 base game PKG and the original Japanese 1.03 update PKG
  * Python 3.11+ (standard library only) and PowerShell 7.4+ (Windows)
  * A PKG extractor (e.g. PS4 PKG Tool) to unpack the 1.03 update
  * To repackage: LibOrbisPkg PkgTool (open source) or Sony's orbis-pub-cmd

STEP 1 - MAKE THE ENGLISH FILES
  Extract eboot.bin and DAT/common.psarc from the ORIGINAL 1.03 update into a
  folder (here called Original103), then in PowerShell 7 inside this kit:

    Set-ExecutionPolicy -Scope Process Bypass
    .\Apply-English.ps1 -UpdateFolder 'X:\Original103' -WorkDirectory 'X:\Work'

  Every input is checked against the expected hashes first; a different region,
  version or an already-modified file is refused. Output:
    X:\Work\overlay\eboot.bin
    X:\Work\overlay\DAT\common.psarc
  (Python directly: python scripts/apply_translation.py --update-folder ... --output ...)

STEP 2 - PACKAGE FOR YOUR CONSOLE
  A) PS5 (jailbroken, ShadowMountPlus) or PS4, as ONE full-game PKG.
     This is the tested route.
     1. Install the base PKG and the original 1.03 update PKG into one merged
        folder. PS4 PKG Tool: right-click each -> "Install to shadPS4"; the
        update is merged into the base folder.
     2. Write the build project (the English files are read from the overlay;
        the merged folder is not modified):
          python scripts/make_full_gp4.py --game-folder 'X:\...\CUSA03562'
                 --overlay 'X:\Work\overlay' --output 'X:\WorkFull'
     3. Build:
          PkgTool.exe pkg_build 'X:\WorkFull\CUSA03562-English-Full.gp4' 'X:\WorkFull\package'
        Optional check: PkgTool.exe pkg_validate <the .pkg>
     4. PS5: PS4 PKG Tool -> right-click the new PKG -> Convert to FFPFSC
        (PS5 ShadowMountPlus), copy it over and mount as usual.
        PS4: install the PKG with your usual fake-PKG installer.
     Needs about 35 GB free.

  B) PS4, as a replacement 1.03 UPDATE PKG (needs orbis-pub-cmd).
     Extract the COMPLETE 1.03 update, then:
       .\Apply-English.ps1 -UpdateFolder 'X:\Update103Full' -WorkDirectory 'X:\WorkUpd'
           -BasePackage 'X:\base.pkg' -Publisher 'X:\orbis-pub-cmd.exe'
     Install the result in place of the original 1.03 update.

  C) Already-extracted setups: copy the two overlay files over the matching
     files of your installed 1.03 game. Keep backups of the originals.

CONTENTS
  translations/english.json          14,986 English table entries (118 resources)
  translations/binary-english.json   1,036 fixed-size text edits (eboot.bin + 53 HUD files)
  translations/speakers.json         874 speaker names
  translations/csh_append.json       shop data and star names
  translations/texture-patches/      168 image patches (XOR deltas; useless without the original files)
  data/source-index.json             expected hashes of every input and output
  scripts/                           apply, rebuild and validation code; make_full_gp4.py
  Apply-English.ps1, Extract-Update.ps1, Verify-Package.ps1
  CONSOLE-CHECKLIST.txt              what to look at when testing
  CHECKSUMS.sha256                   checksums of this kit

EDITING THE ENGLISH
  Edit values in translations/english.json (or "english" fields in
  binary-english.json), then run Apply-English with -EditedTranslations
  (Python: --edited-translations). Keys, offsets, tokens such as [i1],
  <P_FNAME> and %d, and fixed byte budgets are still enforced.

Game names, text and artwork belong to their respective owners
(Bandai Namco Entertainment / Granzella and the licensors of the featured
series). This is an unofficial, non-commercial fan project. Please support the
official release.
