import logging
from functools import cached_property

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

log = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


class SheetsClient:
    def __init__(self, creds_path: str, spreadsheet_id: str):
        self.creds_path = creds_path
        self.spreadsheet_id = spreadsheet_id

    @cached_property
    def service(self):
        creds = Credentials.from_service_account_file(self.creds_path, scopes=SCOPES)
        return build("sheets", "v4", credentials=creds, cache_discovery=False)

    def fetch_tab(self, tab_name: str, optional: bool = False) -> list[dict]:
        """
        Returns list of rows for the given tab. Each row is a dict:
        { 'row_index': 1-based, 'cells': { 'A': {'value': str|None, 'bg': (r,g,b) | None}, ... } }
        Includes both values and background colors in one API call.
        If optional=True and the tab is missing, returns [] and logs a warning.
        """
        try:
            resp = self.service.spreadsheets().get(
                spreadsheetId=self.spreadsheet_id,
                ranges=[tab_name],
                fields="sheets(data(rowData(values(formattedValue,effectiveFormat(backgroundColor)))))",
            ).execute()
        except HttpError as e:
            if optional and e.resp.status == 400 and b"Unable to parse range" in (e.content or b""):
                log.warning("optional tab %r not found — treating as empty", tab_name)
                return []
            raise

        sheets = resp.get("sheets", [])
        if not sheets:
            return []
        rows_out: list[dict] = []
        data = sheets[0].get("data", [])
        if not data:
            return []
        row_data = data[0].get("rowData", [])
        for idx, row in enumerate(row_data, start=1):
            cells_src = row.get("values", [])
            cells_out: dict[str, dict] = {}
            for i, cell in enumerate(cells_src):
                letter = _col_letter(i)
                value = cell.get("formattedValue")
                bg = None
                fmt = cell.get("effectiveFormat") or {}
                bg_raw = fmt.get("backgroundColor")
                if bg_raw:
                    bg = (
                        bg_raw.get("red", 0.0),
                        bg_raw.get("green", 0.0),
                        bg_raw.get("blue", 0.0),
                    )
                cells_out[letter] = {"value": value, "bg": bg}
            rows_out.append({"row_index": idx, "cells": cells_out})
        return rows_out


    def append_log_cell(self, tab_name: str, col_letter: str, row_index: int, note: str) -> None:
        """Append a new line to cell (col, row) without overwriting history."""
        a1 = f"{tab_name}!{col_letter}{row_index}"
        current = ""
        resp = self.service.spreadsheets().values().get(
            spreadsheetId=self.spreadsheet_id, range=a1,
        ).execute()
        values = resp.get("values") or [[]]
        if values and values[0]:
            current = str(values[0][0])
        new_value = f"{current}\n{note}" if current else note
        self.service.spreadsheets().values().update(
            spreadsheetId=self.spreadsheet_id,
            range=a1,
            valueInputOption="RAW",
            body={"values": [[new_value]]},
        ).execute()


def _col_letter(i: int) -> str:
    letters = ""
    n = i
    while True:
        letters = chr(ord("A") + n % 26) + letters
        n = n // 26 - 1
        if n < 0:
            break
    return letters


def is_default_white(bg: tuple[float, float, float] | None) -> bool:
    """Google returns None for empty, and (1,1,1) for explicit white. Both = 'no fill'."""
    if bg is None:
        return True
    r, g, b = bg
    return r >= 0.98 and g >= 0.98 and b >= 0.98
