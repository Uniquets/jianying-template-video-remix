# jianying-template-video-remix

Agent skill for remixing **Jianying Pro / CapCut** template drafts: extract subtitle/title/BGM style from an existing draft, write or reuse narration, match media clips by filename, generate continuous TTS, and output a new editable draft (not MP4 unless you export manually).

## Features

- Template style analysis (encrypted drafts supported via `--jy-install`)
- Short single-line subtitles (no forced TTS time-stretch)
- BGM vs voiceover/dub classification (avoids using `配音` tracks as background music)
- Event-driven pop-up titles and SFX
- Media plan handoff (`media_plan.json`)

## Quick start

```powershell
cd scripts
python bootstrap_assets.py

python analyze_template_style.py `
  --template-draft "F:\JianyingPro Drafts\YourTemplate" `
  --jy-install "F:\JianyingPro\10.7.0.14095" `
  --output ..\build\template_style.json

python remix_draft.py `
  --template-draft "F:\JianyingPro Drafts\YourTemplate" `
  --style-profile ..\build\template_style.json `
  --media-dir "D:\clips" `
  --script-file ..\build\narration.txt `
  --draft-name "My_Remix" `
  --output-dir ..\build `
  --jy-install "F:\JianyingPro\10.7.0.14095"

python validate_draft.py --draft-name "My_Remix"
```

## Layout

| Path | Purpose |
|------|---------|
| `SKILL.md` | Agent skill instructions |
| `scripts/` | CLI tools and tests |
| `vendor/jianying-editor-skill/` | Bundled draft editor helper |
| `defaults/` | Portable fallbacks (run `bootstrap_assets.py` for fonts/BGM) |
| `references/` | Workflow and schema docs |

## Requirements

- Windows (Jianying Pro paths, optional `videoeditor.dll` decrypt)
- Python 3.10+
- `ffmpeg` / `ffprobe` on PATH (recommended)
- Jianying Pro installed for opening generated drafts

## Publish to GitHub (git only)

1. Create an empty public repo: [github.com/new](https://github.com/new?name=jianying-template-video-remix) (no README/license).
2. Run:

```powershell
cd C:\Users\11709\.codex\skills\jianying-template-video-remix
.\scripts\publish_to_github.ps1
```

Default remote: `https://github.com/uniquets/jianying-template-video-remix.git`

## License

Use and modify for your own workflows. Third-party code under `vendor/` retains its original terms.
