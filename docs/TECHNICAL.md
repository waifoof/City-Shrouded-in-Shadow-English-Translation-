# Technical notes

## Where the text lives
- `DAT/common.psarc`: zlib PSARC with 64 KiB blocks. Resources are wrapped in a 0x80-byte header followed by a `BILZ` block (big-endian raw size, compressed size and flags, then zlib data).
  - `.csh`: string tables. Line breaks are the two characters `\n`.
  - `.luc`: Lua 5.2 bytecode (float numbers). Strings are addressed as `0:k{n}`.
  - `.hud`: UTF-8 layout files. Strings are fixed-size slots, padded with spaces.
- `eboot.bin`: NUL-terminated UTF-8 strings in fixed slots. English must fit in the original byte budget.
- Speaker names come from `lua/SpeakerTable.luc`, which is regenerated with an English name for every speaker ID. The IDs inside the dialogue are left alone because they also drive voice and lip-sync lookups.
- Display limits:
  - loading recaps: up to 58 characters × 7 lines
  - ending lines: up to 60 characters
  - speaker names: up to 40 characters
  - interaction prompts: up to 11 ASCII characters

## Textures (`.tex`)
- The file starts with a 0x80-byte header (`\0xet`) followed by a `BILZ` body.
- The body begins with a 12-byte header: width and height as u16, then format bytes.
- If the low nibble of byte 7 is `d`, the data is BC3/DXT5 with a mip chain. If it is `1`, the data is raw RGBA8. BC1 is rare.
- The redrawn images are encoded with the encoder in `tools/textures/bc3.py`. Their mip chains are regenerated, and each file is padded or trimmed to the original data length.
- Releases ship each image as `XTEX1` + zlib(original raw body XOR new raw body). `apply_translation.py` reads the original from your archive, applies the XOR, checks the SHA-256 of the result, and rewraps it.

## Packaging
- **Full-game route** (tested on PS5). `scripts/make_full_gp4.py` writes a `pkg_ps4_app` GP4 over a merged base + 1.03 folder, takes the English files from the overlay, and patches a copy of `param.sfo` to category `gd`. LibOrbisPkg generates the license, keystone, PlayGo and other system files itself, so those are left out of the project.
- **Update route.** `Apply-English.ps1 -BasePackage ... -Publisher ...` builds a 19-chunk `pkg_ps4_patch` project for orbis-pub-cmd.
