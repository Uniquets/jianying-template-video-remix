# jianying-template-video-remix

面向 Agent 的剪映专业版模板混剪技能：从已有草稿提取字幕 / 标题 / BGM 风格，默认读取历史草稿文案并仿写口播风格，撰写或复用解说词，按素材文件名匹配画面，可使用剪映 TTS 或 FishAPI 声音克隆生成连续配音，并输出新的可编辑草稿（默认不导出 MP4，需在剪映内自行导出）。

使用本技能时，Agent 会先核对参考模板、文案/主题、素材目录、历史文案风格来源、配音来源并展示确认单，**用户明确确认后**才会开始分析。若按主题写稿，Agent 还必须先展示生成的新文案，等用户确认后才继续剪映 TTS 或 FishAPI 配音与混剪。

## 功能概览

- 模板风格分析（加密草稿可通过 `--jy-install` 解密）
- 短句单行字幕（不对 TTS 做加减速拉伸）
- 配音来源二选一：剪映/模板 TTS，或 FishAPI 声音克隆配音
- 区分 BGM 与配音素材（避免把「配音」轨道误当背景音乐）
- 默认抽取历史草稿文案，固定到 `history_scripts/`，用于仿写口播风格
- 按内容节点添加弹窗标题与音效：标题只取附近口播里的完整关键词，不做总结、不硬截断
- 弹窗标题保留模板样式与阴影，支持颜色轮换，并避免画面显示时间重叠或连续爆闪
- 默认对主视频轨道做轨道级禁音（`Template_Main_Video.attribute=1`），不把每个视频片段音量归零
- 输出素材编排表 `media_plan.json` 便于核对

## 快速开始

```powershell
cd scripts
python bootstrap_assets.py

python analyze_template_style.py `
  --template-draft "F:\JianyingPro Drafts\YourTemplate" `
  --jy-install "F:\JianyingPro\10.7.0.14095" `
  --output ..\build\template_style.json

python prepare_historical_style.py `
  --topic "Your Topic" `
  --media-dir "D:\clips" `
  --output-dir ..\build `
  --limit 20 `
  --jy-install "F:\JianyingPro\10.7.0.14095"

# FishAPI 分支：只在用户确认 narration.txt 后运行
$env:FISH_API_KEY = "<provided-key-for-this-shell-only>"
python prepare_fish_voice.py `
  --script-file ..\build\narration.txt `
  --voice-sample "D:\voice-samples\sample.wav" `
  --voice-title "Jianying Remix Voice" `
  --output-dir ..\build

python remix_draft.py `
  --template-draft "F:\JianyingPro Drafts\YourTemplate" `
  --style-profile ..\build\template_style.json `
  --media-dir "D:\clips" `
  --script-file ..\build\narration.txt `
  --draft-name "My_Remix" `
  --output-dir ..\build `
  --jy-install "F:\JianyingPro\10.7.0.14095"

# 使用 FishAPI 配音时，在 remix_draft.py 中额外传入：
# --voice-file ..\build\fish_voice\narration_full.wav
# --voice-groups-file ..\build\fish_voice\voice_groups.json
# --voice-provider fish_audio

python validate_draft.py --draft-name "My_Remix"
```

## 目录结构

| 路径 | 说明 |
|------|------|
| `SKILL.md` | Agent 技能说明（工作流与规则） |
| `scripts/` | 命令行脚本与单元测试 |
| `vendor/jianying-editor-skill/` | 内置草稿编辑辅助库 |
| `vendor/jianying-draft-text-extractor/` | 内置历史草稿文案抽取脚本 |
| `defaults/` | 便携回退资源（需先运行 `bootstrap_assets.py` 生成字体 / BGM） |
| `references/` | 工作流示例与风格配置说明 |

## 环境要求

- Windows（剪映草稿路径；可选 `videoeditor.dll` 解密）
- Python 3.10+
- 建议将 `ffmpeg`、`ffprobe` 加入 PATH
- 已安装剪映专业版，用于打开生成后的草稿

## 许可说明

可自行用于个人工作流。`vendor/` 下的第三方代码仍遵循其原有许可条款。
