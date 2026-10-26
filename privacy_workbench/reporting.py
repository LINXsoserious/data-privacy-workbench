"""Reports describe operations without copying original full matched values."""

from collections import Counter
from datetime import datetime, timezone

from . import __version__
from .detection import LABELS, mask_value
from .i18n import labels, localize_reason, translate


def build_report(frame, findings, selected_ids, mode="mask", lang="zh"):
    selected_ids = set(selected_ids)
    if mode not in {"mask", "redact"} or not selected_ids <= {finding.id for finding in findings}:
        raise ValueError(translate("invalid_report", lang))
    selected = [finding for finding in findings if finding.id in selected_ids]
    display_labels = labels(lang)
    return {
        "application": translate("report_application", lang),
        "version": __version__,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "summary": {
            "rows": len(frame), "columns": len(frame.columns),
            "candidates": len(findings), "processed_fragments": len(selected),
            "retained_candidates": len(findings) - len(selected),
            "affected_cells": len({(f.row, f.column_index) for f in selected}),
            "categories": dict(Counter(LABELS[f.kind] for f in findings)),
        },
        "entries": [{
            "data_row": f.row + 1, "column_number": f.column_index + 1,
            "category": display_labels[f.kind], "masked_preview": mask_value(f.kind, f.value),
            "action": mode if f.id in selected_ids else "retained",
            "rule_check": localize_reason(f.reason, lang),
        } for f in findings],
        "scope": translate("report_scope", lang),
        "report_content": translate("report_content", lang),
    }
