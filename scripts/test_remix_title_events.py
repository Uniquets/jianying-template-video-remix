import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import remix_draft


class EventTitleTests(unittest.TestCase):
    def test_titles_use_complete_exact_phrases_from_narration(self):
        rows = [
            {"text": "这几天我试了下新作", "start": 0.0, "end": 1.0},
            {"text": "先说结论", "start": 1.0, "end": 2.0},
            {"text": "它最吸引人的不是画面", "start": 2.0, "end": 3.0},
            {"text": "而是宠物互动", "start": 3.0, "end": 4.0},
            {"text": "开局和新手关卡节奏很轻", "start": 4.0, "end": 5.0},
            {"text": "适合慢慢熟悉世界", "start": 5.0, "end": 6.0},
            {"text": "捕捉睡着目标会触发逃跑", "start": 6.0, "end": 7.0},
            {"text": "拿走食物会生气", "start": 7.0, "end": 8.0},
            {"text": "抱走也有反馈", "start": 8.0, "end": 9.0},
            {"text": "说明它不是单纯数值宠物", "start": 9.0, "end": 10.0},
            {"text": "不过战斗传送异常", "start": 10.0, "end": 11.0},
            {"text": "和脱离卡点", "start": 11.0, "end": 12.0},
            {"text": "也暴露了稳定性问题", "start": 12.0, "end": 13.0},
            {"text": "现在的体验", "start": 13.0, "end": 14.0},
            {"text": "有可爱和生态感", "start": 14.0, "end": 15.0},
            {"text": "但还需要继续打磨", "start": 15.0, "end": 16.0},
            {"text": "想入坑的小伙伴", "start": 16.0, "end": 17.0},
            {"text": "可以先期待互动", "start": 17.0, "end": 18.0},
            {"text": "别急着把它当完成品", "start": 18.0, "end": 19.0},
        ]

        titles = remix_draft.event_title_specs(rows, event_count=5)
        text = [item["text"] for item in titles]

        self.assertEqual(text, ["宠物互动", "捕捉睡着目标", "单纯数值宠物", "稳定性问题", "生态感"])
        narration = "".join(row["text"] for row in rows)
        for title in text:
            self.assertIn(title, narration)
        self.assertNotIn("时机会变", text)
        self.assertNotIn("这几天我试了下新", text)

    def test_title_fallback_uses_complete_clause_not_summary(self):
        title = remix_draft.core_title_for_text("它会用反馈告诉你边界")

        self.assertEqual(title, "用反馈告诉你边界")

    def test_event_titles_skip_rows_without_complete_keyword_phrase(self):
        rows = [
            {"text": "这几天我试了一个游戏", "start": 0.0, "end": 1.0},
            {"text": "先说结论", "start": 1.0, "end": 2.0},
            {"text": "它的节奏比较轻", "start": 2.0, "end": 3.0},
        ]

        self.assertEqual(remix_draft.event_title_specs(rows, event_count=3), [])

    def test_title_positions_stay_inside_safe_frame(self):
        long_title = "真正可探索的生态系统"

        for index in range(12):
            x, y = remix_draft.safe_title_position(index, 12, long_title)
            self.assertGreaterEqual(x, -0.32)
            self.assertLessEqual(x, 0.32)
            self.assertGreaterEqual(y, 0.06)
            self.assertLessEqual(y, 0.56)

    def test_title_colors_vary_across_popups(self):
        colors = [remix_draft.title_color_for_index(index) for index in range(6)]

        self.assertGreaterEqual(len(set(colors)), 4)
        self.assertNotEqual(colors[0], colors[1])

    def test_main_video_track_mute_uses_track_attribute_not_clip_volume(self):
        data = {
            "config": {"video_mute": True},
            "tracks": [
                {
                    "name": remix_draft.TARGET_TRACKS["video"],
                    "segments": [{"volume": 1.0}],
                }
            ],
        }

        remix_draft.set_main_video_track_mute(data)

        self.assertEqual(remix_draft.DEFAULT_SOURCE_VOLUME, 1.0)
        self.assertFalse(data["config"]["video_mute"])
        self.assertEqual(data["tracks"][0]["attribute"], 1)
        self.assertEqual(data["tracks"][0]["segments"][0]["volume"], 1.0)

    def test_title_track_names_use_one_timeline_track(self):
        tracks = [remix_draft.title_track_name(index) for index in range(6)]

        self.assertEqual(len(set(tracks)), 1)
        self.assertEqual(tracks[0], remix_draft.TARGET_TRACKS["title"])

    def test_title_specs_have_visible_gap_between_popups(self):
        rows = [
            {"text": "宠物互动", "start": 0.0, "end": 1.0},
            {"text": "新手关卡", "start": 0.8, "end": 1.7},
            {"text": "稳定性问题", "start": 3.0, "end": 4.0},
        ]

        specs = remix_draft.event_title_specs(rows, event_count=3)
        windows = [(spec["start"], spec["start"] + spec["duration"]) for spec in specs]

        for (_, prev_end), (curr_start, _) in zip(windows, windows[1:]):
            self.assertGreaterEqual(curr_start - prev_end, remix_draft.TITLE_MIN_GAP_S)
        self.assertNotIn("新手关卡", [spec["text"] for spec in specs])

    def test_popup_title_color_ids_follow_timeline_order_on_one_track(self):
        data = {
            "tracks": [
                {
                    "name": remix_draft.TARGET_TRACKS["title"],
                    "segments": [
                        {"material_id": "title-a", "target_timerange": {"start": 0}},
                        {"material_id": "title-b", "target_timerange": {"start": 3_000_000}},
                    ],
                },
            ]
        }

        colors = remix_draft.popup_title_color_ids(data)

        self.assertEqual(colors["title-a"], remix_draft.title_color_for_index(0))
        self.assertEqual(colors["title-b"], remix_draft.title_color_for_index(1))
        self.assertNotEqual(colors["title-a"], colors["title-b"])


if __name__ == "__main__":
    unittest.main()
