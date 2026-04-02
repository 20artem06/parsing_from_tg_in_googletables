from __future__ import annotations

import logging
from pathlib import Path

from telethon import TelegramClient

from app.config import TelegramConfig
from app.parsers.sonic_text_parser import SonicTextParser
from app.storage.models import SonicBatch, TelegramTextMessage


class TelegramSourceClient:
    def __init__(self, config: TelegramConfig) -> None:
        self.config = config
        self._client: TelegramClient | None = None
        self.best_entity = None
        self.sonic_entity = None
        self.logger = logging.getLogger(__name__)
        self.sonic_text_parser = SonicTextParser()

    @property
    def client(self) -> TelegramClient:
        if self._client is None:
            raise RuntimeError("Telegram client is not started")
        return self._client

    async def start(self) -> None:
        session_path = Path(self.config.session_name)
        session_path.parent.mkdir(parents=True, exist_ok=True)
        self._client = TelegramClient(
            str(session_path),
            self.config.api_id,
            self.config.api_hash,
        )
        await self._client.start()
        self.best_entity = await self._client.get_input_entity(self.config.best_channel)
        self.sonic_entity = await self._client.get_input_entity(self.config.sonic_channel)

    async def stop(self) -> None:
        if self._client is not None:
            await self._client.disconnect()

    async def download_best_excel_bytes(self) -> bytes:
        message = await self.client.get_messages(self.best_entity, ids=self.config.best_message_id)
        if message is None:
            raise RuntimeError(f"BEST message {self.config.best_message_id} not found")
        if not message.media:
            raise RuntimeError("BEST message does not contain media")
        payload = await self.client.download_media(message, file=bytes)
        if not isinstance(payload, (bytes, bytearray)):
            raise RuntimeError("BEST message media download returned no bytes")
        return bytes(payload)

    async def fetch_latest_sonic_batch(self) -> SonicBatch:
        history = [
            message
            async for message in self.client.iter_messages(
                self.sonic_entity,
                limit=self.config.sonic_scan_limit or None,
            )
        ]
        textual = [
            message
            for message in reversed(history)
            if message is not None and self._extract_text(message)
        ]
        if not textual:
            raise RuntimeError("No textual messages available in SONIC channel")

        self.logger.info("Scanned SONIC channel messages = %s", len(textual))

        messages = [
            TelegramTextMessage(
                message_id=message.id,
                date=message.date,
                text=self._extract_text(message),
            )
            for message in textual
        ]
        price_message_ids: list[int] = []
        closed_message_ids: list[int] = []
        non_price_message_ids: list[int] = []

        for message in messages:
            if self.sonic_text_parser._is_placeholder_message(message.text):
                closed_message_ids.append(message.message_id)
                continue
            if self.sonic_text_parser.is_price_message(message.text):
                price_message_ids.append(message.message_id)
                continue
            non_price_message_ids.append(message.message_id)

        return SonicBatch(
            requested_message_ids=[],
            scanned_message_count=len(textual),
            message_ids=price_message_ids,
            price_message_ids=price_message_ids,
            closed_message_ids=closed_message_ids,
            missing_message_ids=[],
            non_price_message_ids=non_price_message_ids,
            messages=messages,
            raw_text="\n\n".join(
                message.text for message in messages if message.message_id in price_message_ids
            ),
            started_at=messages[0].date,
            finished_at=messages[-1].date,
        )

    def _extract_text(self, message) -> str:
        return (message.message or message.raw_text or "").strip()
