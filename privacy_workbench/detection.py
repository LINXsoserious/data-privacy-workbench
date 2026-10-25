"""Deterministic candidates, explicitly reviewed before any replacement."""

from dataclasses import dataclass
from datetime import date
import re

import pandas as pd


LABELS = {"phone": "手机号", "email": "电子邮箱", "id_card": "18位身份证候选"}
MAX_FINDINGS = 10000
PATTERNS = {
    "id_card": re.compile(r"(?<![0-9A-Za-z])[1-9][0-9]{16}[0-9Xx](?![0-9A-Za-z])"),
    "email": re.compile(
        r"(?<![A-Za-z0-9._%+-])[A-Za-z0-9][A-Za-z0-9._%+-]*@"
        r"(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+"
        r"[A-Za-z]{2,63}(?![A-Za-z0-9_-])"
    ),
    "phone": re.compile(r"(?<![0-9])(?:\+?86[ -]?)?1[3-9][0-9]{9}(?![0-9])"),
}


@dataclass(frozen=True)
class Finding:
    id: str
    row: int
    column_index: int
    kind: str
    start: int
    end: int
    value: str
    reason: str
    recommended: bool


def _id_check(value: str) -> tuple[bool, str]:
    try:
        birthday = date(int(value[6:10]), int(value[10:12]), int(value[12:14]))
        if birthday > date.today():
            return False, "出生日期在未来，仅列为疑似"
    except ValueError:
        return False, "出生日期无效，仅列为疑似"
    weights = (7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2)
    check = "10X98765432"[sum(int(n) * w for n, w in zip(value[:17], weights)) % 11]
    if value[-1].upper() != check:
        return False, "校验位不匹配，仅列为疑似"
    return True, "日期与校验位通过；未核实行政区或真实身份"


def mask_value(kind: str, value: str) -> str:
    if kind == "phone":
        return value[:-11] + value[-11:-8] + "****" + value[-4:]
    if kind == "email":
        local, domain = value.rsplit("@", 1)
        return (local[0] + "***" if len(local) > 1 else "*") + "@" + domain
    if kind == "id_card":
        return value[:6] + "********" + value[-4:]
    raise ValueError("不支持的敏感信息类型")


def scan_dataframe(frame: pd.DataFrame, enabled: set[str] | None = None) -> list[Finding]:
    enabled = set(LABELS) if enabled is None else set(enabled)
    if not enabled <= set(LABELS):
        raise ValueError("存在不支持的识别规则")
    findings = []
    for row_index, row in enumerate(frame.itertuples(index=False, name=None)):
        for column_index, cell in enumerate(row):
            text = str(cell)
            cell_findings = []
            for kind, pattern in PATTERNS.items():
                if kind not in enabled:
                    continue
                for match in pattern.finditer(text):
                    if kind == "email" and len(match.group()) > 254:
                        continue
                    if any(match.start() < f.end and f.start < match.end() for f in cell_findings):
                        continue
                    if kind == "id_card":
                        recommended, reason = _id_check(match.group())
                    else:
                        recommended = True
                        reason = "符合手机号格式；仍需结合字段用途确认" if kind == "phone" else "符合常见邮箱格式"
                    cell_findings.append(Finding(
                        id=f"r{row_index}-c{column_index}-{kind}-{match.start()}-{match.end()}",
                        row=row_index, column_index=column_index, kind=kind,
                        start=match.start(), end=match.end(), value=match.group(),
                        reason=reason, recommended=recommended,
                    ))
            findings.extend(sorted(cell_findings, key=lambda finding: finding.start))
            if len(findings) > MAX_FINDINGS:
                raise ValueError("候选超过 10,000 个，请拆分文件后再检查；本次未生成部分结果。")
    return findings


def apply_redactions(frame: pd.DataFrame, findings: list[Finding], selected_ids: set[str], mode: str = "mask") -> pd.DataFrame:
    if mode not in {"mask", "redact"}:
        raise ValueError("处理方式必须为 mask 或 redact")
    selected_ids = set(selected_ids)
    if not selected_ids <= {finding.id for finding in findings}:
        raise ValueError("复核记录与当前候选不一致，请重新检查。")
    grouped = {}
    for finding in findings:
        if finding.id in selected_ids:
            if finding.row >= len(frame) or finding.column_index >= len(frame.columns):
                raise ValueError("数据已变化，请重新检查。")
            text = str(frame.iat[finding.row, finding.column_index])
            if text[finding.start:finding.end] != finding.value:
                raise ValueError("数据已变化，请重新检查。")
            grouped.setdefault((finding.row, finding.column_index), []).append(finding)
    output = frame.copy(deep=True).astype(object)
    for (row, column), matches in grouped.items():
        text = str(output.iat[row, column])
        for finding in sorted(matches, key=lambda f: f.start, reverse=True):
            replacement = mask_value(finding.kind, finding.value) if mode == "mask" else "[已删除]"
            text = text[:finding.start] + replacement + text[finding.end:]
        output.iat[row, column] = text
    return output
