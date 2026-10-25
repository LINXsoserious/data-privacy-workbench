import unittest

import pandas as pd

from privacy_workbench.detection import apply_redactions, scan_dataframe
from privacy_workbench.reporting import build_report


class DetectionTests(unittest.TestCase):
    def setUp(self):
        self.frame = pd.DataFrame({"备注": ["电话13800001234，邮件 alice@example.com", "证件11010519491231002X"]})

    def test_finds_three_non_overlapping_candidates(self):
        findings = scan_dataframe(self.frame)
        self.assertEqual([f.kind for f in findings], ["phone", "email", "id_card"])
        self.assertTrue(all(f.recommended for f in findings))

    def test_mask_multiple_fragments_without_changing_other_text_or_source(self):
        findings = scan_dataframe(self.frame)
        output = apply_redactions(self.frame, findings, {f.id for f in findings})
        self.assertEqual(output.iloc[0, 0], "电话138****1234，邮件 a***@example.com")
        self.assertEqual(output.iloc[1, 0], "证件110105********002X")
        self.assertIn("13800001234", self.frame.iloc[0, 0])

    def test_rejected_false_positive_is_preserved(self):
        findings = scan_dataframe(self.frame)
        selected = {f.id for f in findings if f.kind != "phone"}
        output = apply_redactions(self.frame, findings, selected)
        self.assertIn("13800001234", output.iloc[0, 0])
        self.assertNotIn("alice@", output.iloc[0, 0])

    def test_redact_removes_only_matched_fragments(self):
        findings = scan_dataframe(self.frame)
        output = apply_redactions(self.frame, findings, {f.id for f in findings}, "redact")
        self.assertEqual(output.iloc[0, 0], "电话[已删除]，邮件 [已删除]")

    def test_phone_inside_email_is_not_double_counted(self):
        found = scan_dataframe(pd.DataFrame({"x": ["13800001234@example.com"]}))
        self.assertEqual([f.kind for f in found], ["email"])

    def test_email_followed_by_sentence_period_is_detected(self):
        found = scan_dataframe(pd.DataFrame({"x": ["Contact alice@example.com."]}))
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].value, "alice@example.com")

    def test_invalid_id_checksum_is_candidate_but_not_selected_by_default(self):
        found = scan_dataframe(pd.DataFrame({"x": ["110105194912310021"]}))
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].kind, "id_card")
        self.assertFalse(found[0].recommended)
        self.assertIn("校验位", found[0].reason)

    def test_invalid_birth_date_is_not_recommended(self):
        found = scan_dataframe(pd.DataFrame({"x": ["11010519990231002X"]}))
        self.assertEqual(len(found), 1)
        self.assertFalse(found[0].recommended)
        self.assertIn("日期", found[0].reason)

    def test_phone_country_code_and_long_number_boundaries(self):
        found = scan_dataframe(pd.DataFrame({"x": ["+86 13800001234", "991380000123499"]}))
        self.assertEqual(len(found), 1)
        output = apply_redactions(pd.DataFrame({"x": ["+86 13800001234", "991380000123499"]}), found, {found[0].id})
        self.assertEqual(output.iloc[0, 0], "+86 138****1234")

    def test_rule_selection_is_respected(self):
        self.assertEqual([f.kind for f in scan_dataframe(self.frame, {"email"})], ["email"])
        self.assertEqual(scan_dataframe(self.frame, set()), [])

    def test_unknown_selection_or_stale_cell_is_rejected(self):
        found = scan_dataframe(self.frame)
        with self.assertRaises(ValueError):
            apply_redactions(self.frame, found, {"unknown"})
        changed = self.frame.copy()
        changed.iloc[0, 0] = "已替换的内容"
        with self.assertRaises(ValueError):
            apply_redactions(changed, found, {f.id for f in found})

    def test_report_omits_original_full_values_and_tracks_retained_candidates(self):
        import json

        found = scan_dataframe(self.frame)
        report = build_report(self.frame, found, {f.id for f in found if f.kind != "phone"})
        self.assertEqual(report["summary"]["retained_candidates"], 1)
        encoded = json.dumps(report, ensure_ascii=False)
        for sensitive in ["13800001234", "alice@example.com", "11010519491231002X"]:
            self.assertNotIn(sensitive, encoded)


if __name__ == "__main__":
    unittest.main()
