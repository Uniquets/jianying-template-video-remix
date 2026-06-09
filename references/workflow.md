# Workflow

## Step 1 — 确认环境（必须先做）

在运行下方任何命令前，Agent 必须：

1. 收齐：**剪映参考草稿名称/路径**、**素材文件夹**、**主题或最终文案**、**新草稿名**、**配音来源**、**历史文案风格来源**。
2. 用中文说明将从模板参考哪些样式；若用户未提供完整文案，默认会读取历史草稿文案进行风格仿写，并把历史文案固定到本次项目输出目录。
3. 用中文说明 analyze → 历史风格抽取 → 写稿确认 → 配音方式确认（剪映 TTS / FishAPI）→ 排素材 → remix → validate 的流程。
4. 输出确认单，等用户回复 **「确认开始」** 后再继续。

缺必填项或用户未确认时，不得执行 `analyze_template_style.py` / `prepare_historical_style.py` / `remix_draft.py`。

## 写稿（按主题时）

- 若用户没有提供完整文案，默认先读取本机历史剪映草稿文案进行风格分析和仿写；除非用户明确关闭历史风格仿写或指定风格文件。
- 历史文案固定到 `<user-project-dir>/history_scripts/`，供以后参考；不要写入 skill 目录。
- 只根据确认单主题 + `media_dir` 文件名新写 `narration.txt`。
- 可以参考历史文案的口吻、结构、句长、开头方式和高频连接词，但**不要**复制历史草稿原句、桥段、其他草稿的 `temp_assets/media_plan.json` 或字幕轨里的 `context`/旁白。
- 模板草稿名（如 `旧活动展示`）只决定**画面风格**，不决定口播题材；口播必须对齐用户给的 topic 与素材文件名。
- 写好 `narration.txt` 后，必须把新文案发给用户确认；用户未确认新文案前，不得生成剪映 TTS、不得调用 FishAPI、不得排时间线、不得运行 `remix_draft.py`。

## 配音来源

用户没有提供现成配音文件时，必须让用户二选一：

1. **剪映配音 / 模板 TTS**
   - 优先使用模板提取的 `tone_speaker`。
   - 如果模板没有可靠音色，询问用户从 `模板音色（若可用）`、`默认女声 zh_female_mizai_saturn_bigtts`、`用户指定 tone_speaker` 中选择。
2. **FishAPI 声音克隆配音**
   - 索要 Fish API key 或确认已设置 `FISH_API_KEY`，以及 10–30 秒左右干净人声样本。
   - API key 只作为环境变量使用，不得写入任何输出文件。
   - Fish TTS 必须按 `narration.txt` 的自然段生成，不按字幕短句逐条生成。

## One-time setup

```powershell
cd <skill-root>/scripts
python bootstrap_assets.py
python init_fallbacks.py
```

`bootstrap_assets.py` fills `defaults/assets/`. `init_fallbacks.py` writes `defaults/default_fallbacks.local.json` (gitignored).

## Analyze a template

```powershell
python scripts/analyze_template_style.py `
  --template-draft "<path-to-template-draft-folder>" `
  --jy-install "<JianyingPro-version-folder>" `
  --output <user-project-dir>/template_style.json
```

If `draft_content.json` is plaintext, `--jy-install` is optional. If it is encrypted, the script uses `scripts/decrypt_jianying_draft.py`.

Draft folders on Windows are usually under:

`%LOCALAPPDATA%\JianyingPro\User Data\Projects\com.lveditor.draft\<draft_name>`

## Prepare historical writing style

When the user provides a topic instead of a final script, historical style imitation is on by default:

```powershell
python scripts/prepare_historical_style.py `
  --topic "<current-topic>" `
  --media-dir "<path-to-media-folder>" `
  --output-dir <user-project-dir> `
  --limit 20 `
  --jy-install "<JianyingPro-version-folder>"
```

Outputs are pinned under `<user-project-dir>/history_scripts/`:

- `jianying_draft_texts_*_full_scripts.md`
- `jianying_draft_texts_*_style_analysis.md`
- `writing_style_profile.json`
- `narration_brief.md`

Use `narration_brief.md` to write a new `narration.txt`, then show the full new narration to the user for confirmation before continuing.

## Prepare Fish cloned voice

Only run after the user has confirmed the new `narration.txt` and selected FishAPI:

```powershell
$env:FISH_API_KEY = "<provided-key-for-this-shell-only>"
python scripts/prepare_fish_voice.py `
  --script-file <user-project-dir>/narration.txt `
  --voice-sample "<path-to-clean-voice-sample.wav>" `
  --voice-title "Jianying Remix Voice" `
  --output-dir <user-project-dir>
```

`prepare_fish_voice.py` writes:

- `<user-project-dir>/fish_voice/narration_full.wav`
- `<user-project-dir>/fish_voice/voice_groups.json`
- `<user-project-dir>/fish_voice/fish_voice_profile.json`

The profile must not include the API key.

## Create a new draft

Write confirmed narration to a file **outside** the skill directory first when the user only provides a topic.

```powershell
python scripts/remix_draft.py `
  --template-draft "<path-to-template-draft-folder>" `
  --style-profile <user-project-dir>/template_style.json `
  --media-dir "<path-to-media-folder>" `
  --script-file <user-project-dir>/narration.txt `
  --draft-name "My_Remix_Draft" `
  # --target-duration is an optional script hint only; TTS is never sped up/slowed down
  --output-dir <user-project-dir>/build `
  --jy-install "<JianyingPro-version-folder>"
```

For FishAPI voice, pass the confirmed external voice:

```powershell
python scripts/remix_draft.py `
  --template-draft "<path-to-template-draft-folder>" `
  --style-profile <user-project-dir>/template_style.json `
  --media-dir "<path-to-media-folder>" `
  --script-file <user-project-dir>/narration.txt `
  --voice-file <user-project-dir>/fish_voice/narration_full.wav `
  --voice-groups-file <user-project-dir>/fish_voice/voice_groups.json `
  --voice-provider fish_audio `
  --draft-name "My_Remix_Draft" `
  --output-dir <user-project-dir>/build `
  --jy-install "<JianyingPro-version-folder>"
```

`--jianying-skill` is optional. Omit it for normal use; the script uses the bundled helper at `vendor/jianying-editor-skill`.

Do not pass `--topic` to `remix_draft.py`.

## Validate

```powershell
python scripts/validate_draft.py --draft-name "My_Remix_Draft"
```

Use validation as evidence before telling the user the draft is finished.

## Practical defaults

- Subtitle chunks: short sentence fragments, one idea each.
- Voice: use template `tone_speaker`, else `defaults/default_fallbacks.local.json`, else bundled `default_fallbacks.json`.
- BGM: reuse template BGM when the file exists; otherwise bundled or local fallback BGM.
- Sound effects: use template effects for continuity, then add event-matched effects from the bundled editor-helper assets or generated fallback tones.
- Titles: event-driven, not one per clip.
