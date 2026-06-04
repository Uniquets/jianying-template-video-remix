# Using jianying-editor-skill

This remix skill bundles the Jianying editor helper under `vendor/jianying-editor-skill` for draft creation and asset APIs.

## Bundled Helper

Normal runs do not need `--jianying-skill`. The script uses:

```text
vendor/jianying-editor-skill
```

Pass an external helper root only when intentionally overriding the bundled helper:

```powershell
--jianying-skill "C:\path\to\jianying-editor-skill"
```

The bundled helper must contain:

- `scripts/jy_wrapper.py`
- `scripts/universal_tts.py`
- `scripts/asset_search.py`
- `data/cloud_sound_effects.csv`
- `data/text_animations.csv`
- `data/video_intro_animations.csv`
- `data/video_outro_animations.csv`

## Asset search

Use `asset_search.py` or the CSV files to choose cloud sound effects, transitions, and animations. If cloud assets are not synced locally, use fallback generated WAV effects and keep the style profile's template effects.

## Draft building APIs

Use `JyProject` methods:

- `add_media_safe` for video/image/audio placement.
- `add_audio_safe` for BGM, SFX, and merged voice WAV.
- `add_text_simple` for subtitles and pop-up titles.
- `add_transition_simple` when transitions are appropriate.

Patch the resulting `draft_content.json` when pyJianYingDraft cannot preserve all template metadata exactly.
