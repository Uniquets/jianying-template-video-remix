# Style Profile Schema

`analyze_template_style.py` emits a JSON profile with these fields:

```json
{
  "template_path": "...",
  "subtitle": {
    "font_resource_id": "...",
    "font_path": "...",
    "font_size": 9.0,
    "text_color": "#ffffff",
    "background_style": 1,
    "background_color": "#000000",
    "background_alpha": 0.16,
    "has_shadow": true,
    "shadow_alpha": 0.9,
    "shadow_distance": 5.0,
    "shadow_smoothing": 0.45,
    "border_width": 0.08,
    "line_spacing": 0.02,
    "transform": {"x": 0.0, "y": -0.85}
  },
  "title": {
    "font_resource_id": "...",
    "font_path": "...",
    "font_size": 15.0,
    "text_color": "#ffde00",
    "border_color": "#000000",
    "border_width": 0.08,
    "animations": ["弹入", "放大"]
  },
  "audio": {
    "tts": {
      "tone_speaker": "...",
      "tone_platform": "sami",
      "resource_id": "..."
    },
    "bgm": {
      "path": "...",
      "name": "...",
      "music_id": "...",
      "volume": 0.4
    },
    "sound_effects": [
      {"path": "...", "name": "...", "duration": 700000}
    ]
  }
}
```

When fields are missing, the remix script should fall back to `jianying-editor-skill` defaults and local generated sound effects.
