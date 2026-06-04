import unittest

import remix_draft


class EventTitleTests(unittest.TestCase):
    def test_title_copy_captures_core_idea_instead_of_leading_chars(self):
        rows = [
            {"text": "第一次打开产品，先别急着下结论。", "start": 0.0, "end": 2.0},
            {"text": "它更像一个会反馈的小系统。", "start": 2.0, "end": 4.0},
            {"text": "如果趁它休息操作，可能直接触发逃离。", "start": 4.0, "end": 6.0},
            {"text": "时间、距离、状态、节奏，都会影响结果。", "start": 6.0, "end": 8.0},
            {"text": "如果后续加入更多模块和关系，就会变成真正可探索的系统。", "start": 8.0, "end": 10.0},
        ]

        titles = remix_draft.event_title_specs(rows, event_count=5)
        text = [item["text"] for item in titles]

        self.assertEqual(text[0], "初次登场")
        self.assertIn("时机会变", text)
        self.assertIn("关键变量", text)
        self.assertEqual(text[-1], "生态系统")
        self.assertNotIn("第一次打开产品", text)

    def test_title_positions_stay_inside_safe_frame(self):
        long_title = "真正可探索的系统"

        for index in range(12):
            x, y = remix_draft.safe_title_position(index, 12, long_title)
            self.assertGreaterEqual(x, -0.32)
            self.assertLessEqual(x, 0.32)
            self.assertGreaterEqual(y, 0.06)
            self.assertLessEqual(y, 0.56)

    def test_event_titles_cover_generic_script_rows(self):
        rows = [
            {"text": "第一次打开产品，先别急着下结论。", "start": 0.0, "end": 1.0},
            {"text": "它更像一个会反馈的小系统。", "start": 1.0, "end": 2.0},
            {"text": "你靠近、观察、尝试，", "start": 2.0, "end": 3.0},
            {"text": "每一步都会触发不同反应。", "start": 3.0, "end": 4.0},
            {"text": "入门区会先教你看懂界面。", "start": 4.0, "end": 5.0},
            {"text": "哪里能走，哪里有资源，", "start": 5.0, "end": 6.0},
            {"text": "哪里藏着会离开的目标。", "start": 6.0, "end": 7.0},
            {"text": "对象不是静态展示品。", "start": 7.0, "end": 8.0},
            {"text": "它会暂停，会消耗资源，", "start": 8.0, "end": 9.0},
            {"text": "也可能因为你拿走资源而生气。", "start": 9.0, "end": 10.0},
            {"text": "如果趁它休息操作，可能直接触发逃离。", "start": 10.0, "end": 11.0},
            {"text": "如果互动太粗暴，", "start": 11.0, "end": 12.0},
            {"text": "它也会用反馈告诉你边界。", "start": 12.0, "end": 13.0},
            {"text": "这套机制的核心，是让用户在探索中读懂行为。", "start": 13.0, "end": 14.0},
            {"text": "时间、距离、状态、节奏，", "start": 14.0, "end": 15.0},
            {"text": "都会影响结果。", "start": 15.0, "end": 16.0},
            {"text": "你可以带走它，也可能被反馈打断节奏。", "start": 16.0, "end": 17.0},
            {"text": "教程会把规则拆成轻量步骤。", "start": 17.0, "end": 18.0},
            {"text": "从接近到尝试，从失败到修正，", "start": 18.0, "end": 19.0},
            {"text": "慢慢形成自己的操作策略。", "start": 19.0, "end": 20.0},
            {"text": "所以这个系统的价值，不只是完成多少任务。", "start": 20.0, "end": 21.0},
            {"text": "而是每一次互动，", "start": 21.0, "end": 22.0},
            {"text": "都像在和一个会反馈的环境打交道。", "start": 22.0, "end": 23.0},
            {"text": "如果后续加入更多模块、", "start": 23.0, "end": 24.0},
            {"text": "关系和层级，就会从单点功能，", "start": 24.0, "end": 25.0},
            {"text": "变成真正可探索的系统。", "start": 25.0, "end": 26.0},
        ]

        text = [item["text"] for item in remix_draft.event_title_specs(rows)]

        self.assertEqual(text, ["初次登场", "关键看点", "边界反馈", "操作策略", "生态系统"])


if __name__ == "__main__":
    unittest.main()
