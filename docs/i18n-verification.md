# v0.2 bilingual verification

Date: 2026-10-26. These are assistant-run development checks, not evidence of the user's independent work or detection accuracy on production datasets.

## Environment and command

- Windows, Python 3.12.3.
- Streamlit 1.66.1, Pandas 3.1.0, OpenPyXL 3.1.5.
- Reused the isolated task virtual environment; no model, API key, or external translation service.

```bash
python -m unittest discover -s tests -v
```

Result: **29 tests passed** (the existing 24 tests plus five bilingual regression tests). GitHub Actions uses this same command and discovers the new unittest test class automatically. CI status must be checked on the actual published commit.

## Coverage added

1. Chinese / English dictionaries have the same keys and format placeholders; English messages contain no untranslated Chinese application text; unsupported locales deterministically fall back to Chinese.
2. English detection reasons, removal markers, report text, and input errors work together. Original source data stays unchanged. JSON top-level and summary keys, including legacy Chinese category-count keys, match across languages.
3. The English Streamlit sample workflow scans 12 candidates, defaults to 11 processed / 1 retained, provides two downloads, and renders the fragment-removal mode and original comparison.
4. Language-dependent source/rule/method controls receive distinct frontend widget identities, translated option strings, and explicitly synchronized selected values. The scan revision and data fingerprint remain unchanged during a language switch.
5. A simulated active CSV upload retains its original Chinese filename, selected phone-only rule, removal mode, fingerprint, scan revision, and deselected candidate when switching Chinese to English and back. Streamlit's recorded data-editor edit payload is used to exercise the real application state path.

The bilingual test module first failed because the new i18n module did not exist, then passed after implementation. A real-browser review then exposed stale Chinese selected tags and unmatched radio selections when only `format_func` changed under a stable widget key. Streamlit 1.66 preserved the widget identity and did not send `set_value` because Python values were unchanged. Locale-specific display keys plus independent canonical choices address this case; the added regression checks identity, option strings, and forced translated `raw_value` / `raw_values` messages as well as Python values. All existing tests remain unchanged and pass. AppTest prints the standard bare-mode `missing ScriptRunContext` warning; it reports no application exceptions.

## Browser review checklist

The root assistant also ran the actual English browser workflow: the selected rule tags and source/method radio indicators refreshed correctly, the synthetic scan displayed 12 candidates / 11 processed / 1 retained, and the review controls rendered in English while original table fields remained unchanged. The current English screenshot is [screenshot-en.jpg](screenshot-en.jpg).

The automated workflow validates state and content. An actual browser review should additionally inspect the English sidebar, hero, translated review-column headings, long ID category labels, responsive table width, download controls, and the removal-mode display. Source filenames, columns, and table values remain in their original language. The language selector intentionally displays both native language names.

The historical screenshot and demo exports remain v0.1 Chinese artifacts and are labeled as such in both READMEs. Third-party reference files, source records, NOTICE, and LICENSE remain unchanged.
