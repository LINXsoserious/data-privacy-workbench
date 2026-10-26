# Changelog

## 0.2.0 — 2026-10-26

- Add selectable Chinese / English interface text, validation messages, and report descriptions using explicit local dictionaries.
- Preserve active uploads, detection rules, treatment modes, scan results, and human review decisions across language changes.
- Keep original data and JSON protocol keys unchanged, including legacy category-count keys; localize only application-generated text.
- Provide complete English and Chinese READMEs and regression coverage for both languages and state preservation.

## 0.1.0 — 2026-10-25

- Initial working version with CSV / XLSX upload and a synthetic sample.
- Detect mobile numbers, common email addresses, and 18-character Chinese ID candidates.
- Review individual candidates, mask or remove fragments, and compare original and processed data.
- Dedicated CSV / JSON downloads with spreadsheet-formula prefix protection.
- Input fidelity and resource limits, minimized reports, and GitHub Actions tests.
- Preserve upstream reference code, provenance, and the Apache-2.0 license.
