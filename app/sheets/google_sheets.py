from __future__ import annotations

import asyncio
from pathlib import Path

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

from app.config import GoogleSheetsConfig
from app.storage.models import MergedItem


class GoogleSheetsWriter:
    def __init__(self, config: GoogleSheetsConfig) -> None:
        self.config = config
        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        credentials = Credentials.from_service_account_file(
            Path(config.service_account_file),
            scopes=scopes,
        )
        self.service = build("sheets", "v4", credentials=credentials, cache_discovery=False)

    async def write_snapshot(self, items: list[MergedItem]) -> None:
        await asyncio.to_thread(self._write_snapshot_sync, items)

    def _write_snapshot_sync(self, items: list[MergedItem]) -> None:
        sheet_id = self._ensure_worksheet()
        rows = [MergedItem.sheet_columns()] + [item.to_sheet_row() for item in items]
        quoted_name = self._quote_sheet_name(self.config.worksheet_name)
        self.service.spreadsheets().values().clear(
            spreadsheetId=self.config.spreadsheet_id,
            range=f"{quoted_name}!A:ZZ",
        ).execute()
        self.service.spreadsheets().values().update(
            spreadsheetId=self.config.spreadsheet_id,
            range=f"{quoted_name}!A1",
            valueInputOption="RAW",
            body={"values": rows},
        ).execute()
        self.service.spreadsheets().batchUpdate(
            spreadsheetId=self.config.spreadsheet_id,
            body={
                "requests": [
                    {
                        "updateSheetProperties": {
                            "properties": {
                                "sheetId": sheet_id,
                                "gridProperties": {
                                    "frozenRowCount": 1,
                                },
                            },
                            "fields": "gridProperties.frozenRowCount",
                        }
                    },
                    {
                        "autoResizeDimensions": {
                            "dimensions": {
                                "sheetId": sheet_id,
                                "dimension": "COLUMNS",
                                "startIndex": 0,
                                "endIndex": len(MergedItem.sheet_columns()),
                            }
                        }
                    },
                ]
            },
        ).execute()

    def _ensure_worksheet(self) -> int:
        spreadsheet = self.service.spreadsheets().get(
            spreadsheetId=self.config.spreadsheet_id
        ).execute()
        for sheet in spreadsheet.get("sheets", []):
            properties = sheet.get("properties", {})
            if properties.get("title") == self.config.worksheet_name:
                return int(properties["sheetId"])

        response = self.service.spreadsheets().batchUpdate(
            spreadsheetId=self.config.spreadsheet_id,
            body={
                "requests": [
                    {
                        "addSheet": {
                            "properties": {
                                "title": self.config.worksheet_name,
                            }
                        }
                    }
                ]
            },
        ).execute()
        created = response["replies"][0]["addSheet"]["properties"]["sheetId"]
        return int(created)

    def _quote_sheet_name(self, value: str) -> str:
        escaped = value.replace("'", "''")
        return f"'{escaped}'"
