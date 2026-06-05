---
name: jianying-template-video-remix
description: Create same-style Jianying/CapCut drafts from a template draft and new content. Use when the user wants to analyze a Jianying template draft for subtitle style, pop-up title style, TTS voice, BGM, sound effects, text animations, transitions, and then generate a new video draft from a new topic/script plus a media folder while reusing or extending the template style with jianying-editor-skill assets.
---

# Jianying Template Video Remix

## Purpose

Use this skill to turn one Jianying template draft into a reusable style source, then apply that style to a new script and media folder. The output is a new Jianying draft, not an exported MP4 unless the user explicitly asks for export.

This skill is template-driven, but not template-locked: preserve the template's visual identity, then use the bundled Jianying editor helper under `vendor/jianying-editor-skill` for video assembly, asset search, text animations, transitions, and suitable sound effects.

## Required Inputs

All of the following must be collected **before** any analyze/remix command runs (see **Step 1 — 确认环境**):

| 字段 | 必填 | 说明 |
|------|------|------|
| `template_draft` | 是 | **剪映草稿名称**（或草稿文件夹完整路径），作为风格参考模板 |
| `media_dir` | 是 | 新视频/图片素材文件夹路径 |
| `script` 或 `topic` | 二选一 | 最终解说文案，或用于撰写解说的主题/要求 |
| `draft_name` | 是 | 生成的新草稿名称 |

可选：

- `target_duration`: 写稿时的粗略时长参考；成片以 TTS 自然时长为准。**禁止**对生成配音做加减速拉伸，时长不合适则改文案。

## Workflow

0. **Portable setup (once per machine)**
   - Run `python scripts/bootstrap_assets.py` to populate `defaults/assets/` with bundled fonts and fallback BGM.
   - Optional: `python scripts/init_fallbacks.py` to write `defaults/default_fallbacks.local.json` (gitignored) with machine-specific paths.
   - Never store user narration, style profiles, or `media_plan.json` inside the skill directory. Use `--output-dir` on remix or a user project folder.

1. **确认环境（强制门禁，未确认不得执行）**

   **在运行 `analyze_template_style.py`、`remix_draft.py` 或写稿/排素材之前**，必须完成本步。若用户在本轮对话中已逐项给出并明确回复「确认开始」，可视为通过。

   ### 1.1 核对必填项（缺一项就停下追问）

   - **参考模板**：剪映草稿名称（或完整路径）。仅有模糊描述（如「上次那个」）不算齐全；需能唯一定位到草稿文件夹。
   - **主题或文案**：已提供最终 `script`，或已提供 `topic`/改写要求（由 Agent 写稿须在确认单里写明）。
   - **素材文件夹**：`media_dir` 的完整路径；若路径不存在或为空，先告知用户并停止。
   - **新草稿名称**：`draft_name`。
   - **TTS**：是否自动生成配音。若否，需说明使用用户自备音频或无声成片。

   缺项时用简短问句补齐，不要用 AskQuestion 代替用户对整单的确认。

   ### 1.2 向用户说明「会从模板参考什么」

   用中文简要列出（结合模板名，避免空泛）：

   **通常会沿用：**

   - 字幕样式（字体、颜色、底条/阴影、位置）
   - 弹窗标题样式与文字动画（若模板可提取）
   - BGM（仅当识别为背景音乐；名称含「配音/旁白/解说」的轨道**不会**当 BGM）
   - 模板内可复用的音效
   - TTS 音色（模板有则沿用，否则用默认女声）
   - 按解说语义匹配素材文件名、事件化标题与音效（非每镜固定套路）

   **可能使用默认：**

   - 模板无可靠 BGM → 内置 `defaults/assets/bgm/fallback_bgm.mp3`
   - 无 TTS 音色 → `defaults/default_fallbacks.json` 默认发音人
   - 标题样式弱缺失 → 内置弹窗标题样式
   - 素材文件名无法表达场景 → 请你重命名或在你同意后再做抽帧分析

   ### 1.3 向用户说明「将如何操作」

   用 4–6 条说明执行顺序，例如：

   1. 解析模板草稿（加密则需本机剪映安装目录解密）→ 生成 `template_style.json`
   2. 按主题写稿或采用你提供的文案 → 拆成短句字幕 → 生成**连续** TTS（不变速）
   3. 按文件名与解说语义编排 `media_plan.json` 与视频轨
   4. 套用模板字幕/标题/BGM/音效规则写入新草稿
   5. 校验时长、轨道与字幕 → 告知草稿路径（不默认导出 MP4）

   ### 1.4 输出确认单并请用户明确同意

   将已收集信息整理为一张**确认单**（示例）：

   ```
   【剪映模板混剪 — 执行确认单】
   参考模板：<草稿名称或路径>
   新草稿名：<draft_name>
   素材目录：<media_dir>
   文案来源：<用户提供全文 / 按主题「…」撰写>
   TTS：<自动生成 / 不使用，说明…>
   目标时长：<自然时长 / 约 N 秒仅作写稿参考>
   将从模板参考：<一句话摘要>
   将执行：<步骤 1–5 摘要>
   ```

   结尾必须询问：**「请确认以上内容，回复「确认开始」后我再执行。」**

   **硬规则：**

   - 在用户明确确认（如「确认开始」「可以开始」「按确认单执行」）之前，**禁止**运行分析/混剪脚本、禁止创建新草稿、禁止替用户做实质性生成（除为补齐确认单而只读检查路径/草稿是否存在）。
   - 用户中途修改任一项 → 更新确认单并重新确认。
   - 仅当用户已预先给出全部必填项且明确说「直接开始、无需再确认」时，可跳过重复确认，但仍需在执行前复述关键参数。

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

   ### 4.1 文案原创（硬规则，违反即失败）

   用户选择 **按主题写稿**（`topic`，未提供最终 `script`）时：

   - **必须新写**口播：只根据确认单里的主题/要点 + **`media_dir` 内文件名**（场景标签）创作。
   - **禁止**从以下来源复制、改写或「换壳」旁白（哪怕同一游戏、同一系列）：
     - 任意其他剪映草稿下的 `temp_assets/media_plan.json`（含 `context` 字段）
     - 其他草稿的 `draft_content.json` / 字幕轨文案
     - 上一轮对话里已生成过的 `narration.txt`（除非用户明确说「沿用上一版文案」）
   - **参考模板名 ≠ 口播主题**：例如模板叫 `洛克王国异色`，用户主题是 `伊莫生态全解`，口播必须讲用户主题，**不得**因模板名擅自写「异色」「闪光」等未在用户主题或素材文件名中出现的概念。
   - 写稿前用只读方式列出 `media_dir` 中 `*.mp4` 等文件名；口播每个大段至少对应一个**真实存在的**文件名语义（如 `开局`、`捕捉睡着`、`生气`），禁止写素材里不存在的桥段。
   - 将成稿写入 `--output-dir` 或用户项目目录下的 `narration.txt`（或确认单约定的路径），并在执行 `remix_draft.py` **之前**用一句话告知用户：**「口播为本次按主题新写，未复用其他草稿字幕。」**

   用户已提供 **完整 `script` / `script-file`** 时：以用户文稿为准，仅可做短句拆分与标点微调，**不得**擅自替换为用户未确认的新主题内容。

   ### 4.2 格式与时长

   - If the user gave a topic, write a concise creator-style narration as a **new** script file (see §4.1).
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

## Editorial QA Rules

Apply these rules whenever building commentary, analysis, review, or杂谈 videos:

- Prefer real gameplay / in-engine footage over PV or cinematic promo footage. Use PV shots only when the narration is specifically about marketing, announcement promises, concept packaging, or the "pretty shell" of a game.
- Match visuals to the current narration claim. When the script names a game, system, ecology, city, dungeon, map, UI, pet interaction, or failure point, cut to footage that directly supports that claim. For broad argument sections, change shots every few sentences to avoid visual fatigue.
- Do not reuse the same source footage interval in one video. Track used `source_start` / `source_end` ranges per underlying source file, including hardlinks or renamed copies, and choose a new non-overlapping range or another source.
- Do not start clips at source time `0`. Skip black frames, logos, loading cards, and dark intro fades; for PV-like or uncertain sources, inspect brightness or sample frames and move `source_start` until the first visible gameplay/usable frame.
- Keep narration and subtitles synchronized. Do not change subtitle timing after TTS alignment unless the voice timing is changed at the same time. Do not speed-change voiceover to force duration.
- Subtitle text should be short single-line chunks and should not end with punctuation marks.
- Analyze the full script before placing pop-up titles. Put titles where the narration introduces a key claim, contrast, judgment, example, or conceptual turn; for commentary videos, a practical cadence is about every 25-35 seconds unless the template or user says otherwise.
- Pop-up title text must be an exact core phrase from the nearby subtitle/narration window, not an arbitrary summary and not a lazy leading slice of the subtitle. Prefer compact key phrases that the viewer just heard or is about to hear.
- When extracting pop-up title style from the template, preserve the complete extracted title style as a unit: font, size, fill/color treatment, border, transform/position conventions, animation references, and other text material settings. Do not cherry-pick only font/color unless the user explicitly asks to restyle.
- Vary pop-up title colors, positions, and animations when the template/style library supports it. Keep positions inside a safe frame, avoid the center when it blocks gameplay, and never cover subtitles.
- Every pop-up title should have a matching sound effect whose start time aligns with the title start time. Choose sound effects that fit the title intent and animation.
- Final validation must cover: draft structural validation, voice/subtitle/video end alignment, subtitle punctuation, title count and cadence, title text source, title style preservation, title position safety, animation variety, title-sfx start alignment, dark/black clip starts, source interval reuse, and track overlaps.

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
