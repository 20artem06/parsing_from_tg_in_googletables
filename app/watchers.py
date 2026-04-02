from __future__ import annotations

import logging

from telethon import events

from app.config import AppConfig
from app.telegram_client import TelegramSourceClient
from app.utils.locks import AsyncSingleFlightRunner


class TelegramWatchers:
    def __init__(
        self,
        config: AppConfig,
        source_client: TelegramSourceClient,
        runner: AsyncSingleFlightRunner,
    ) -> None:
        self.config = config
        self.source_client = source_client
        self.runner = runner
        self.logger = logging.getLogger(__name__)

    async def start(self) -> None:
        client = self.source_client.client
        client.add_event_handler(
            self._on_best_message_edited,
            events.MessageEdited(chats=self.source_client.best_entity),
        )
        client.add_event_handler(
            self._on_sonic_new_message,
            events.NewMessage(chats=self.source_client.sonic_entity),
        )
        client.add_event_handler(
            self._on_sonic_message_edited,
            events.MessageEdited(chats=self.source_client.sonic_entity),
        )

    async def _on_best_message_edited(self, event) -> None:
        if event.message.id != self.config.telegram.best_message_id:
            return
        self.logger.info("Caught BEST edit event for message_id=%s", event.message.id)
        await self.runner.request(f"BEST edited:{event.message.id}")

    async def _on_sonic_new_message(self, event) -> None:
        self.logger.info("Rebuild triggered by SONIC new message_id=%s", event.message.id)
        await self.runner.request(f"SONIC new:{event.message.id}")

    async def _on_sonic_message_edited(self, event) -> None:
        self.logger.info("Rebuild triggered by SONIC edited message_id=%s", event.message.id)
        await self.runner.request(f"SONIC edited:{event.message.id}")
