---
name: jianying-template-video-remix
description: Create same-style Jianying/CapCut drafts from a template draft and new content. Use when the user wants to analyze a Jianying template draft for subtitle style, pop-up title style, TTS voice, BGM, sound effects, text animations, transitions, and then generate a new video draft from a new topic/script plus a media folder while reusing or extending the template style with jianying-editor-skill assets.
---

# Jianying Template Video Remix

## Purpose

Use this skill to turn one Jianying template draft into a reusable style source, then apply that style to a new script and media folder. The output is a new Jianying draft, not an exported MP4 unless the user explicitly asks for export.

This skill is template-driven, but not template-locked: preserve the template's visual identity, then use the bundled Jianying editor helper under `vendor/jianying-editor-skill` for video assembly, asset search, text animations, transitions, and suitable sound effects.

## Required Inputs

- `template_draft`: Jianying draft folder or draft name used as the style source.
- `media_dir`: Folder containing new video/image assets.
- One of:
  - `script`: Final narration copy.
  - `topic`: Topic/instructions for Codex to write narration copy.
- `draft_name`: New draft name.
- Optional `target_duration`: Rough script-length hint for the agent when writing narration. Final timeline follows natural TTS length (+/- drift is fine). **Never** time-stretch (speed up/slow down) generated TTS to hit a target; rewrite the script instead.

## Workflow

0. **Portable setup (once per machine)**
   - Run `python scripts/bootstrap_assets.py` to populate `defaults/assets/` with bundled fonts and fallback BGM.
   - Optional: `python scripts/init_fallbacks.py` to write `defaults/default_fallbacks.local.json` (gitignored) with machine-specific paths.
   - Never store user narration, style profiles, or `media_plan.json` inside the skill directory. Use `--output-dir` on remix or a user project folder.

1. **First-use orientation and confirmation**
   - Before generating a draft for a user who has not already confirmed these choices in the current thread, briefly explain what will be reused from the template: subtitle style, title style when extractable, title/text animations when extractable, BGM, reusable sound effects, TTS speaker when present, timeline pacing cues, and safe text placement rules.
   - Also explain what may use defaults when the template lacks extractable values: TTS voice, fallback BGM, generated fallback sound effects, fallback pop-up title style, and conservative media/title placement.
   - Ask the user to confirm how narration copy should be obtained: use a provided final script, let Codex draft from a topic, or let Codex revise a rough script.
   - Ask whether automatic TTS voiceover should be generated. If the user declines TTS, require a voice/audio file or clarify that the draft will be assembled without generated narration.
   - Keep this orientation concise. Do not proceed to generation until the user has answered the narration-source and TTS questions, unless the user already provided an explicit final script and explicitly requested automatic TTS.

2. **Locate dependencies**
   - Use the bundled editor helper at `vendor/jianying-editor-skill` by default.
   - Pass `--jianying-skill <path-to-jianying-editor-skill>` only when intentionally overriding the bundled helper.
   - If the template draft JSON is encrypted, provide `--jy-install <JianyingPro install dir>` so `videoeditor.dll` can decrypt it.

3. **Analyze template style**
   - Run `scripts/analyze_template_style.py`.
   - Extract subtitle style, title style, title animations, subtitle transform, TTS speaker, BGM, and reusable local sound effects.
   - **Distinguish narration/dub audio from BGM**: paths or names containing hints like `配音`, `旁白`, `解说`, `口播` are voiceover assets, not background music. Prefer `music`/`music_id` or `背景`/`配乐`/`bgm` tracks with long timeline span. If no trustworthy BGM is found, leave BGM empty so remix uses bundled `defaults/assets/bgm/fallback_bgm.mp3`.
   - Save a style profile JSON when the user may reuse the same template later.

4. **Prepare the new script**
   - If the user gave a topic, write a concise creator-style narration as a **new** script file.
   - Do not reuse narration from other drafts on disk unless the user explicitly asks to reuse that script.
   - Do not read `temp_assets/media_plan.json` or subtitle text from unrelated drafts to copy wording.
   - Save narration outside the skill directory (for example the user's `--output-dir` or project folder).
   - Split narration into **short single-line** subtitle chunks: usually **4-14 Chinese characters** (or one compact English phrase). Prefer more lines over long lines that wrap to two rows on screen.
   - Keep narration continuous; do not generate independent TTS clips on the timeline.
   - If natural TTS length drifts from a rough target, adjust the script text — do not apply `atempo`/speed change to the voice track.

5. **Build the new draft**
   - Run `scripts/remix_draft.py` with the template, content, media folder, target duration, and `--output-dir` for handoff artifacts.
   - Pass `--script-file` or `--script` only. Do not pass `--topic` to the remix CLI.
   - Generate TTS using the template speaker when available.
   - For long text, generate TTS in chunks, merge to one stable WAV, and place it as one continuous voice track.
   - Analyze media filenames before arranging clips. Treat descriptive filenames as scene labels, then map narration windows to matching clips instead of round-robin placement.
   - Do not extract frames by default. Frame analysis can consume a lot of token/attention budget; only pass `--analyze-frames` after the user explicitly asks for or approves frame analysis.
   - If media filenames are too generic to infer scene/action labels, stop and ask the user to rename the files with descriptive scene names, or to approve conservative frame analysis.
   - When `ffprobe` is available, probe media duration without frame extraction; use duration only to avoid dead starts and choose a reasonable `source_start`.
   - Arrange media clips from a saved `temp_assets/media_plan.json` so the handoff can verify which narration window used which source video.
   - Add subtitles using the template subtitle style.
   - Add pop-up titles and sound effects by content events, not by a fixed every-clip pattern.
   - Choose text animations and sound effects from both the template style and bundled editor-helper asset data.

6. **Patch and validate**
   - Patch `draft_content.json` after save so Jianying recognizes the template-derived font IDs, subtitle type, TTS metadata, BGM metadata, and text styles.
   - Run `scripts/validate_draft.py`.
   - Check duration, voice track count, subtitle count, subtitle style, title/sfx counts, and track overlaps.

## Event Design Rules

- Match clip choice to narration meaning. If media filenames include scene or action labels such as opening, tutorial, interaction, emotion, failure, recovery, comparison, or reveal, those names are first-class editorial signals and must drive the clip plan.
- Do not fill the timeline by simply cycling sorted media files. Every major narration claim should have either a matched named clip or an explicit fallback reason in `media_plan.json`.
- Do not use frame extraction as an automatic fallback. Prefer asking for better filenames first; use frame extraction only after user confirmation.
- Use pop-up titles only where the narration introduces a new claim, surprise, interaction, system, or call-to-action.
- Write pop-up title copy as an editor's concise takeaway, not a direct leading-character slice from the subtitle. Prefer 3-8 Chinese characters that name the core idea, such as `初次登场`, `关键变量`, or `系统看点`.
- Place title text inside a conservative safe frame. Keep long titles closer to the horizontal center, avoid edges, avoid covering subtitles, and never let animated text start or end outside the visible frame.
- Match animation to intent:
  - Observation/system: `打字机_I`, `扫描`, `辉光扫描`, `鼠标点击`.
  - Cute/interaction: `弹入跳动`, `弹性伸缩`, `随机弹跳`.
  - Alert/emotion: `放大震动`, `故障闪动`, `电光`.
  - Transition/exploration: `向右滑动`, `冲屏位移`, `圆柱体滚动`.
- Match sound to animation and content:
  - Soft/cute actions: soft pop, sparkle, light marimba.
  - UI/system points: tech prompt, click, page flip.
  - Impact/emotion: low hit, alert, short whoosh.
- Avoid the repeated formula `sound + pop title + hard cut` on every clip.

## Scripts

- `scripts/bootstrap_assets.py`: Copy portable fallback fonts/BGM into `defaults/assets/`.
- `scripts/init_fallbacks.py`: Generate gitignored `defaults/default_fallbacks.local.json` on this machine.
- `scripts/decrypt_jianying_draft.py`: Decrypt encrypted Jianying JSON with `videoeditor.dll`.
- `scripts/analyze_template_style.py`: Build a reusable style profile from a template draft.
- `scripts/remix_draft.py`: Create a new same-style draft from content and media.
- `scripts/validate_draft.py`: Validate timing, style, and track overlap.

## References

- Read `references/workflow.md` for detailed command examples.
- Read `references/style-profile.md` for the style profile schema.
- Read `references/jianying-editor-skill-usage.md` when adapting or extending the scripts with asset search, transitions, or animations.

## Handoff

Tell the user the new draft path, duration, voice speaker, subtitle count, title/sfx counts, and whether validation passed. Do not claim an MP4 export unless export was actually run and verified.
