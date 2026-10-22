# Authoring tools

You don't need any of these to install the translation; the `kit/` folder does that. They're the scripts used to produce the kit, kept here so the work can be continued.

## `translation/`
- **English sources for content outside the main tables:**
  - `recaps.py`: loading-screen recaps
  - `ending.py`: ending monologue
  - `eboot_tl.py`, `eboot_debug_tl.py`: executable strings, keyed by offset
  - `hud_tl.py`, `hud_placeholders_tl.py`: HUD files
  - `credits_tl.py`: staff credits
  - `names_tl.py`: shop and star names
  - `speakers_tl.py`: speaker names
  - `leftovers_tl.py`: developer and placeholder text
- **`merge.py`** rebuilds the kit's translation data from these sources and validates every changed resource. It also applies the line-by-line review corrections (`review_out/*.json`).
- **Helpers:**
  - `build_speaker_table.py`, `speaker_scan.py`, `generated_resources.py`: the regenerated speaker table and pooled tables
  - `remaining_japanese.py`: lists Japanese text not yet covered
  - `check_edits.py`, `review_rules.py`: layout and token checks for review batches
  - `luadis.py`, `mini_psarc.py`: Lua disassembly and building small test archives

## `textures/`
- `tex.py`: decodes `.tex` files to PNG.
- `bc3.py`: BC3 encoder and mip chain; `rebuild_tex` writes a `.tex` with the same layout as the original.
- `relabel.py`, `gen.py`, `tabs.py`, `cards.py`: erase Japanese lettering and draw English in the original style.
- `detect*.py`, `sheet.py`: find text and make contact sheets.
- `pack2.py`: encodes redrawn PNGs and records them in the kit's source index. Release builds then convert them to XOR patches.

The fonts used are Inter and Noto Serif CJK.
