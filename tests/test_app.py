import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parents[1]


class AppTests(unittest.TestCase):
    def test_demo_scan_generates_review_and_two_downloads(self):
        app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=20).run()
        self.assertEqual(len(app.exception), 0)
        self.assertIn("开始检查", [button.label for button in app.button])
        app.button(key="scan").click().run()
        self.assertEqual(len(app.exception), 0)
        values = {metric.label: metric.value for metric in app.metric}
        self.assertEqual(values["识别候选"], "12")
        self.assertEqual(values["本次处理"], "11")
        self.assertEqual(values["保留候选"], "1")
        self.assertEqual(len(app.get("download_button")), 2)

    def test_removal_mode_and_original_comparison_render(self):
        app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=20).run()
        app.radio(key="strategy").set_value("移除片段").run()
        app.button(key="scan").click().run()
        app.checkbox(key="show_original").check().run()
        self.assertEqual(len(app.exception), 0)
        tables = [element.value for element in app.dataframe]
        self.assertTrue(any("[已删除]" in table.to_string() for table in tables))

    def test_changing_rules_discards_old_findings(self):
        app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=20).run()
        app.button(key="scan").click().run()
        app.multiselect(key="rules").set_value(["电子邮箱"]).run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.metric), 0)
        app.button(key="scan").click().run()
        self.assertEqual({metric.label: metric.value for metric in app.metric}["识别候选"], "4")


if __name__ == "__main__":
    unittest.main()
