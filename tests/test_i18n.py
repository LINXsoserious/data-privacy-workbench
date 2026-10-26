import json
import re
from pathlib import Path
import unittest

import pandas as pd
from streamlit.testing.v1 import AppTest

from privacy_workbench.detection import apply_redactions, scan_dataframe
from privacy_workbench.files import read_dataset
from privacy_workbench.i18n import MESSAGES, labels, localize_reason, normalize_lang, translate
from privacy_workbench.reporting import build_report


ROOT = Path(__file__).resolve().parents[1]


class I18nTests(unittest.TestCase):
    def test_dictionary_keys_and_format_parameters_match(self):
        from string import Formatter

        self.assertEqual(set(MESSAGES['zh']), set(MESSAGES['en']))
        for key, english in MESSAGES['en'].items():
            with self.subTest(key=key):
                self.assertTrue(english.strip())
                self.assertIsNone(re.search(r'[\u3400-\u9fff]', english))
                fields = lambda value: {name for _, name, _, _ in Formatter().parse(value) if name}
                self.assertEqual(fields(MESSAGES['zh'][key]), fields(english))
        self.assertEqual(normalize_lang('English'), 'en')
        self.assertEqual(normalize_lang('unknown'), 'zh')
        self.assertEqual(translate('scan', 'unknown'), '开始检查')
        self.assertEqual(labels('en')['phone'], 'Mobile phone')
        self.assertEqual(localize_reason('Unchanged source evidence', 'zh'), 'Unchanged source evidence')

    def test_english_processing_report_and_errors_keep_protocol_and_source(self):
        frame = pd.DataFrame({'原字段': ['备注13800001234，邮件 alice@example.com', '证件110105194912310021']})
        original = frame.copy(deep=True)
        found = scan_dataframe(frame, lang='en')
        self.assertTrue(all(re.search(r'[\u3400-\u9fff]', item.reason) is None for item in found))
        selected = {item.id for item in found if item.recommended}
        output = apply_redactions(frame, found, selected, 'redact', lang='en')
        self.assertEqual(output.iloc[0, 0], '备注[REDACTED]，邮件 [REDACTED]')
        pd.testing.assert_frame_equal(frame, original)
        english = build_report(frame, found, selected, 'redact', lang='en')
        chinese = build_report(frame, found, selected, 'redact')
        self.assertEqual(set(english), set(chinese))
        self.assertEqual(set(english['summary']), set(chinese['summary']))
        self.assertEqual(english['summary']['categories'], chinese['summary']['categories'])
        self.assertEqual(english['application'], 'Data Privacy Workbench')
        self.assertEqual(english['entries'][0]['category'], 'Mobile phone')
        self.assertEqual(english['entries'][-1]['action'], 'retained')
        self.assertNotIn('原字段', json.dumps(english, ensure_ascii=False))
        for data, filename in [(b'', 'input.csv'), (b'bad', 'input.xls'), (b'a,a\n1,2', 'input.csv'), (b'bad', 'input.xlsx')]:
            with self.subTest(filename=filename), self.assertRaises(ValueError) as caught:
                read_dataset(data, filename, lang='en')
            self.assertIsNone(re.search(r'[\u3400-\u9fff]', str(caught.exception)))

    def test_english_ui_scan_review_download_and_removal(self):
        app = AppTest.from_file(str(ROOT / 'app.py'), default_timeout=20).run()
        app.selectbox(key='ui_language').set_value('English').run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(app.button(key='scan').label, 'Start inspection')
        self.assertIn('Add a review before sharing data.', '\n'.join(item.value for item in app.markdown))
        app.button(key='scan').click().run()
        self.assertEqual(len(app.exception), 0)
        metrics = {metric.label: metric.value for metric in app.metric}
        self.assertEqual(metrics['Candidates found'], '12')
        self.assertEqual(metrics['Processed fragments'], '11')
        self.assertEqual(metrics['Retained candidates'], '1')
        self.assertEqual(len(app.get('download_button')), 2)
        self.assertIn('Review candidates', [item.value for item in app.subheader])
        review = app.dataframe[0].value
        self.assertEqual(review.iloc[0]['category'], 'Mobile phone')
        self.assertIsNone(re.search(r'[\u3400-\u9fff]', '\n'.join(review['rule_check'])))
        app.radio(key='strategy_en').set_value('移除片段').run()
        app.checkbox(key='show_original').check().run()
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(any('[REDACTED]' in item.value.to_string() for item in app.dataframe))

    def test_locale_option_widgets_remount_with_translated_options_and_saved_selections(self):
        app = AppTest.from_file(str(ROOT / 'app.py'), default_timeout=20).run()
        app.multiselect(key='rules').set_value(['电子邮箱']).run()
        app.radio(key='strategy').set_value('移除片段').run()
        app.button(key='scan').click().run()
        original_ids = {
            'source': app.radio(key='source').proto.id,
            'rules': app.multiselect(key='rules').proto.id,
            'strategy': app.radio(key='strategy').proto.id,
        }
        fingerprint = app.session_state['active_fingerprint']
        revision = app.session_state['scan_revision']
        app.selectbox(key='ui_language').set_value('English').run()
        self.assertEqual(len(app.exception), 0)
        # A new widget identity prevents the browser from retaining old formatted strings.
        self.assertNotEqual(app.multiselect(key='rules_en').proto.id, original_ids['rules'])
        self.assertNotEqual(app.radio(key='source_en').proto.id, original_ids['source'])
        self.assertNotEqual(app.radio(key='strategy_en').proto.id, original_ids['strategy'])
        self.assertEqual(list(app.multiselect(key='rules_en').proto.options), list(labels('en').values()))
        self.assertTrue(app.multiselect(key='rules_en').proto.set_value)
        self.assertEqual(list(app.multiselect(key='rules_en').proto.raw_values), ['Email address'])
        self.assertEqual(app.multiselect(key='rules_en').value, ['电子邮箱'])
        self.assertEqual(list(app.radio(key='source_en').proto.options), ['Synthetic sample', 'Upload a file'])
        self.assertTrue(app.radio(key='source_en').proto.set_value)
        self.assertEqual(app.radio(key='source_en').proto.raw_value, 'Synthetic sample')
        self.assertEqual(list(app.radio(key='strategy_en').proto.options), ['Mask', 'Remove fragments'])
        self.assertTrue(app.radio(key='strategy_en').proto.set_value)
        self.assertEqual(app.radio(key='strategy_en').proto.raw_value, 'Remove fragments')
        self.assertEqual(app.session_state['active_fingerprint'], fingerprint)
        self.assertEqual(app.session_state['scan_revision'], revision)
        app.radio(key='strategy_en').set_value('掩码').run()
        app.selectbox(key='ui_language').set_value('简体中文').run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(app.multiselect(key='rules').value, ['电子邮箱'])
        self.assertEqual(app.radio(key='strategy').value, '掩码')
        self.assertEqual(app.session_state['scan_revision'], revision)

    def test_switch_language_preserves_review_rules_mode_and_active_upload(self):
        from unittest.mock import patch
        from streamlit.runtime.uploaded_file_manager import UploadedFile, UploadedFileRec

        upload = UploadedFile(UploadedFileRec('test-upload', '原文件.csv', 'text/csv', b'phone,email\n13812345678,alice@example.com\n'), None)
        with patch('streamlit.file_uploader', return_value=upload):
            app = AppTest.from_file(str(ROOT / 'app.py'), default_timeout=20).run()
            app.radio(key='source').set_value('上传文件').run()
            app.multiselect(key='rules').set_value(['手机号']).run()
            app.radio(key='strategy').set_value('移除片段').run()
            app.button(key='scan').click().run()
            self.assertEqual(len(app.exception), 0)
            fingerprint = app.session_state['active_fingerprint']
            revision = app.session_state['scan_revision']
            editor_key = app.session_state['review_active_editor']
            app.session_state[editor_key] = {'edited_rows': {0: {'process': False}}, 'added_rows': [], 'deleted_rows': []}
            app.run()
            self.assertEqual({metric.label: metric.value for metric in app.metric}['本次处理'], '0')
            app.selectbox(key='ui_language').set_value('English').run()
            self.assertEqual(len(app.exception), 0)
            self.assertEqual(app.session_state['active_fingerprint'], fingerprint)
            self.assertEqual(app.session_state['scan_revision'], revision)
            self.assertEqual(app.multiselect(key='rules_en').value, ['手机号'])
            self.assertEqual(app.radio(key='source_en').value, '上传文件')
            self.assertEqual(app.radio(key='strategy_en').value, '移除片段')
            self.assertEqual({metric.label: metric.value for metric in app.metric}['Processed fragments'], '0')
            self.assertFalse(bool(app.dataframe[0].value.iloc[0]['process']))
            self.assertEqual(app.dataframe[-1].value.iloc[0, 0], '13812345678')
            self.assertIn('原文件.csv', '\n'.join(item.value for item in app.caption))
            app.selectbox(key='ui_language').set_value('简体中文').run()
            self.assertEqual({metric.label: metric.value for metric in app.metric}['本次处理'], '0')
            self.assertFalse(bool(app.dataframe[0].value.iloc[0]['process']))


if __name__ == '__main__':
    unittest.main()
