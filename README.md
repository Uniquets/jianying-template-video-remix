# jianying-template-video-remix

面向 Agent 的剪映专业版模板混剪技能：从已有草稿提取字幕 / 标题 / BGM 风格，撰写或复用解说词，按素材文件名匹配画面，生成连续 TTS 配音，并输出新的可编辑草稿（默认不导出 MP4，需在剪映内自行导出）。

使用本技能时，Agent 会先核对参考模板、文案/主题、素材目录并展示确认单，**用户明确确认后**才会开始分析与生成。

## 功能概览

- 模板风格分析（加密草稿可通过 `--jy-install` 解密）
- 短句单行字幕（不对 TTS 做加减速拉伸）
- 区分 BGM 与配音素材（避免把「配音」轨道误当背景音乐）
- 按内容节点添加弹窗标题与音效
- 输出素材编排表 `media_plan.json` 便于核对

## 快速开始

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

## 目录结构

| 路径 | 说明 |
|------|------|
| `SKILL.md` | Agent 技能说明（工作流与规则） |
| `scripts/` | 命令行脚本与单元测试 |
| `vendor/jianying-editor-skill/` | 内置草稿编辑辅助库 |
| `defaults/` | 便携回退资源（需先运行 `bootstrap_assets.py` 生成字体 / BGM） |
| `references/` | 工作流示例与风格配置说明 |

## 环境要求

- Windows（剪映草稿路径；可选 `videoeditor.dll` 解密）
- Python 3.10+
- 建议将 `ffmpeg`、`ffprobe` 加入 PATH
- 已安装剪映专业版，用于打开生成后的草稿

## 许可说明

可自行用于个人工作流。`vendor/` 下的第三方代码仍遵循其原有许可条款。
