# Workflow

## Step 1 — 确认环境（必须先做）

在运行下方任何命令前，Agent 必须：

1. 收齐：**剪映参考草稿名称/路径**、**素材文件夹**、**主题或最终文案**、**新草稿名**、**是否 TTS**。
2. 用中文说明将从模板参考哪些样式、以及 analyze → 写稿/TTS → 排素材 → remix → validate 的流程。
3. 输出确认单，等用户回复 **「确认开始」** 后再继续。

缺必填项或用户未确认时，不得执行 `analyze_template_style.py` / `remix_draft.py`。

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

## Create a new draft

Write narration to a file **outside** the skill directory first when the user only provides a topic.

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
