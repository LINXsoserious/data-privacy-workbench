import io
import unittest
from unittest.mock import patch

import pandas as pd
from openpyxl import Workbook

from privacy_workbench.files import export_csv, read_dataset


class FileTests(unittest.TestCase):
    def test_csv_keeps_leading_zeros_empty_values_and_literal_na(self):
        frame = read_dataset("编号,备注\n00123,NA\n00000,\n".encode("utf-8-sig"), "样例.csv")
        self.assertEqual(frame.values.tolist(), [["00123", "NA"], ["00000", ""]])

    def test_gb18030_csv_is_supported(self):
        frame = read_dataset("名称,备注\n示例,测试\n".encode("gb18030"), "测试.CSV")
        self.assertEqual(frame.iloc[0, 0], "示例")

    def test_oversized_header_is_rejected(self):
        with patch("privacy_workbench.files.MAX_CELL_LENGTH", 3), self.assertRaises(ValueError):
            read_dataset(b"abcd\n1\n", "input.csv")

    def test_duplicate_and_empty_headers_are_rejected(self):
        for text in ["姓名,姓名\n甲,乙", "姓名,\n甲,乙"]:
            with self.subTest(text=text), self.assertRaises(ValueError):
                read_dataset(text.encode(), "data.csv")

    def test_unsupported_empty_and_oversized_inputs_are_rejected(self):
        for data, filename in [(b"", "a.csv"), (b"abc", "a.xls")]:
            with self.subTest(filename=filename), self.assertRaises(ValueError):
                read_dataset(data, filename)
        with patch("privacy_workbench.files.MAX_BYTES", 2), self.assertRaises(ValueError):
            read_dataset(b"abc", "a.csv")

    def test_row_and_column_limits_are_enforced(self):
        with patch("privacy_workbench.files.MAX_ROWS", 1), self.assertRaises(ValueError):
            read_dataset(b"a\n1\n2\n", "a.csv")
        with patch("privacy_workbench.files.MAX_COLUMNS", 1), self.assertRaises(ValueError):
            read_dataset(b"a,b\n1,2\n", "a.csv")

    def test_xlsx_keeps_text_identifiers_and_treats_formulas_as_text(self):
        workbook = Workbook()
        workbook.active.append(["编号", "公式"])
        workbook.active.append(["00123", "=1+1"])
        buffer = io.BytesIO()
        workbook.save(buffer)
        frame = read_dataset(buffer.getvalue(), "input.xlsx")
        self.assertEqual(frame.values.tolist(), [["00123", "=1+1"]])
        self.assertIn("'=1+1", export_csv(frame).decode("utf-8-sig"))

    def test_corrupt_xlsx_is_rejected(self):
        with self.assertRaises(ValueError):
            read_dataset(b"not a workbook", "input.xlsx")

    def test_csv_export_guards_formula_cells_and_headers(self):
        frame = pd.DataFrame({"=bad_header": ["=1+1", "  @SUM(A1)", "-1+2", "普通文本", "00123"]})
        output = export_csv(frame).decode("utf-8-sig")
        self.assertTrue(output.startswith("'=bad_header"))
        self.assertIn("'=1+1", output)
        self.assertIn("'  @SUM(A1)", output)
        self.assertIn("'-1+2", output)
        self.assertIn("普通文本", output)
        self.assertIn("00123", output)


if __name__ == "__main__":
    unittest.main()
