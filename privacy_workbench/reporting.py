"""Reports describe operations without copying original full matched values."""

from collections import Counter
from datetime import datetime, timezone

from . import __version__
from .detection import LABELS, mask_value


def build_report(frame, findings, selected_ids, mode="mask"):
    selected_ids = set(selected_ids)
    if mode not in {"mask", "redact"} or not selected_ids <= {finding.id for finding in findings}:
        raise ValueError("报告参数与当前复核结果不一致。")
    selected = [finding for finding in findings if finding.id in selected_ids]
    return {
        "application": "中文敏感数据体检台",
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
            "category": LABELS[f.kind], "masked_preview": mask_value(f.kind, f.value),
            "action": mode if f.id in selected_ids else "retained",
            "rule_check": f.reason,
        } for f in findings],
        "scope": "规则候选检查；未覆盖姓名、地址、图像或所有敏感信息，不构成匿名化证明。",
        "report_content": "不包含原始完整命中值、原始文件名、原始列名；掩码预览仍保留部分特征。",
    }
