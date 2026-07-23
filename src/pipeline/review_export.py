"""Append one review sheet per real (LLM-verified) scan run to a single
review workbook (data/scan_viz/review.xlsx), instead of a separate CSV per
run — so ground truth can be hand-filled per sheet and accumulate across
runs in one file. Never overwrites an existing sheet: it may already have
hand-filled ground truth (correct/true_sku_id columns).
"""
import os
from typing import Dict, List

import openpyxl

COLUMNS = [
    "index", "crop_file", "predicted_sku_id", "score", "llm_reasoning", "correct", "true_sku_id", "depth",
]

LOCKED_FILE_MESSAGE = "{path} đang mở, đóng file rồi chạy lại."


def _unique_sheet_name(existing_names: List[str], sheet_name: str) -> str:
    if sheet_name not in existing_names:
        return sheet_name
    n = 2
    while f"{sheet_name}_{n}" in existing_names:
        n += 1
    return f"{sheet_name}_{n}"


def append_review_sheet(xlsx_path: str, sheet_name: str, rows: List[Dict]) -> str:
    """Create xlsx_path if missing, else load and add a new sheet to it.

    Returns the sheet name actually used — suffixed with _2, _3, ... if
    sheet_name already exists in the workbook, so a re-run never clobbers a
    sheet that may already have hand-filled ground truth.
    """
    try:
        if os.path.exists(xlsx_path):
            wb = openpyxl.load_workbook(xlsx_path)
        else:
            wb = openpyxl.Workbook()
            wb.remove(wb.active)
    except PermissionError:
        raise RuntimeError(LOCKED_FILE_MESSAGE.format(path=xlsx_path))

    actual_sheet_name = _unique_sheet_name(wb.sheetnames, sheet_name)
    ws = wb.create_sheet(title=actual_sheet_name)
    ws.append(COLUMNS)
    for row in rows:
        ws.append([row.get(col, "") for col in COLUMNS])

    try:
        wb.save(xlsx_path)
    except PermissionError:
        raise RuntimeError(LOCKED_FILE_MESSAGE.format(path=xlsx_path))

    return actual_sheet_name
