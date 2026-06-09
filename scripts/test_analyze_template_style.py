import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

import analyze_template_style


def text_material(material_id, text, material_type="text", has_shadow=True):
    content = {
        "text": text,
        "styles": [
            {
                "font": {"id": "font-id", "path": "font.ttf"},
                "size": 15.0,
                "fill": {"content": {"render_type": "solid", "solid": {"color": [1.0, 0.0, 0.0]}}},
                "shadows": [
                    {
                        "alpha": 0.8,
                        "distance": 6.0,
                        "diffuse": 0.2,
                        "angle": -45,
                        "content": {"render_type": "solid", "solid": {"color": [0, 0, 0]}},
                    }
                ],
            }
        ],
    }
    return {
        "id": material_id,
        "type": material_type,
        "content": json.dumps(content),
        "font_resource_id": "font-id",
        "font_path": "font.ttf",
        "font_size": 15.0,
        "text_color": "#ff0000",
        "has_shadow": has_shadow,
        "shadow_alpha": 0.8,
        "shadow_color": "#000000",
        "shadow_distance": 6.0,
        "shadow_smoothing": 0.2,
    }


class AnalyzeTemplateStyleTests(unittest.TestCase):
    def test_title_shadow_fields_are_preserved(self):
        data = {
            "materials": {
                "texts": [
                    text_material("subtitle-1", "subtitle text", material_type="subtitle"),
                    text_material("title-1", "Important"),
                ],
                "audios": [],
            },
            "tracks": [
                {"type": "text", "segments": [{"material_id": "subtitle-1"}]},
                {"type": "text", "segments": [{"material_id": "title-1"}]},
            ],
        }

        with patch.object(analyze_template_style, "load_json_maybe_decrypt", return_value=data):
            profile = analyze_template_style.analyze(Path("dummy"))

        title = profile["title"]
        self.assertTrue(title["has_shadow"])
        self.assertEqual(title["shadow_alpha"], 0.8)
        self.assertEqual(title["shadow_color"], "#000000")
        self.assertEqual(title["shadow_distance"], 6.0)
        self.assertEqual(title["shadow_smoothing"], 0.2)


if __name__ == "__main__":
    unittest.main()
