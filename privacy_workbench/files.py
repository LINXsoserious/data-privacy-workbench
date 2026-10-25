"""Bounded table loading. Uploaded data is never written to disk."""

import csv
from datetime import date, datetime
import io
from pathlib import PurePath
import re
import zipfile

import pandas as pd
from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException
from xml.etree.ElementTree import ParseError

MAX_BYTES = 5 * 1024 * 1024
MAX_ROWS = 20000
MAX_COLUMNS = 50
MAX_CELLS = 100000
MAX_CELL_LENGTH = 10000
MAX_XLSX_UNCOMPRESSED = 50 * 1024 * 1024


def _string(value) -> str:
    if value is None:
        return ""
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)


def _table(rows) -> pd.DataFrame:
    iterator = iter(rows)
    try:
        header = [_string(value) for value in next(iterator)]
    except StopIteration as exc:
        raise ValueError("文件为空，首行应是列名。") from exc
    if not header or any(not name.strip() for name in header):
        raise ValueError("首行存在空列名，请先补全表头。")
    if any(len(name) > MAX_CELL_LENGTH for name in header):
        raise ValueError(f"单个列名最多支持 {MAX_CELL_LENGTH:,} 字符。")
    if len(header) != len(set(header)):
        raise ValueError("存在重复列名，请先改成唯一列名。")
    if len(header) > MAX_COLUMNS:
        raise ValueError(f"最多支持 {MAX_COLUMNS} 列，请拆分文件。")
    body = []
    for row in iterator:
        if not row:
            continue
        values = [_string(value) for value in row]
        if len(values) != len(header):
            raise ValueError("数据列数与表头不一致，请检查分隔符和空列。")
        if any(len(value) > MAX_CELL_LENGTH for value in values):
            raise ValueError(f"单个单元格最多支持 {MAX_CELL_LENGTH:,} 字符。")
        body.append(values)
        if len(body) > MAX_ROWS or len(body) * len(header) > MAX_CELLS:
            raise ValueError(f"最多支持 {MAX_ROWS:,} 行、{MAX_CELLS:,} 个数据单元格，请拆分文件。")
    if not body:
        raise ValueError("文件只有表头，没有可检查的数据。")
    return pd.DataFrame(body, columns=header, dtype=object)


def read_dataset(data: bytes, filename: str) -> pd.DataFrame:
    if not data:
        raise ValueError("文件为空，请选择包含表头和数据的文件。")
    if len(data) > MAX_BYTES:
        raise ValueError("文件超过 5 MB，请拆分后上传。")
    suffix = PurePath(filename).suffix.lower()
    if suffix == ".csv":
        try:
            if data.startswith((b"\xff\xfe", b"\xfe\xff")):
                text = data.decode("utf-16")
            else:
                try:
                    text = data.decode("utf-8-sig")
                except UnicodeDecodeError:
                    text = data.decode("gb18030")
            if "\x00" in text:
                raise ValueError("CSV 包含不支持的空字符，请重新导出为 UTF-8 CSV。")
            return _table(csv.reader(io.StringIO(text, newline=""), strict=True))
        except (UnicodeError, csv.Error) as exc:
            raise ValueError("无法读取 CSV，请检查编码、逗号分隔符与引号。") from exc
    if suffix != ".xlsx":
        raise ValueError("仅支持 .csv 和 .xlsx 文件；不支持旧版 .xls。")
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            if len(archive.infolist()) > 1000 or sum(info.file_size for info in archive.infolist()) > MAX_XLSX_UNCOMPRESSED:
                raise ValueError("Excel 解压后体积或内部文件数超限，请简化文件。")
        workbook = load_workbook(io.BytesIO(data), read_only=True, data_only=False, keep_links=False)
        try:
            sheet = workbook.worksheets[0]
            if sheet.max_column and sheet.max_column > MAX_COLUMNS:
                raise ValueError(f"最多支持 {MAX_COLUMNS} 列，请移除空白格式列或拆分文件。")
            return _table(sheet.iter_rows(max_row=min(sheet.max_row or 1, MAX_ROWS + 2), values_only=True))
        finally:
            workbook.close()
    except (zipfile.BadZipFile, InvalidFileException, KeyError, ParseError, IndexError) as exc:
        raise ValueError("无法读取 XLSX，请确认文件未损坏且包含工作表。") from exc


def _safe_cell(value) -> str:
    text = _string(value)
    if text.startswith(("\t", "\r", "\n")) or re.match(r"^\s*[=+\-@]", text):
        return "'" + text
    return text


def export_csv(frame: pd.DataFrame) -> bytes:
    """Prefix potential spreadsheet formulas, including formulas in headers."""
    safe = frame.map(_safe_cell)
    safe.columns = [_safe_cell(column) for column in frame.columns]
    return safe.to_csv(index=False, lineterminator="\n").encode("utf-8-sig")
