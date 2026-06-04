# Bundled fallback assets

Paths in `default_fallbacks.json` are relative to the `defaults/` directory.

Populate this folder on a new machine:

```powershell
cd <skill-root>/scripts
python bootstrap_assets.py
```

Optional machine-specific overrides without editing the repo copy:

```powershell
python init_fallbacks.py
```

This writes `defaults/default_fallbacks.local.json` (gitignored).

Expected files after bootstrap:

- `fonts/popup_title.ttf`
- `fonts/subtitle.ttf`
- `bgm/fallback_bgm.mp3`

If BGM or fonts are missing, remix still runs but may skip BGM or use template-only styles.
