from __future__ import annotations

import asyncio
import logging

from app.config import load_config
from app.normalization.matcher import MatchingEngine
from app.normalization.normalizer import ItemNormalizer
from app.orchestrator import RebuildOrchestrator
from app.parsers.best_excel_parser import BestExcelParser
from app.parsers.sonic_text_parser import SonicTextParser
from app.sheets.google_sheets import GoogleSheetsWriter
from app.storage.cache import CacheStore
from app.telegram_client import TelegramSourceClient
from app.utils.locks import AsyncSingleFlightRunner
from app.utils.logging import setup_logging
from app.watchers import TelegramWatchers


async def async_main() -> None:
    config = load_config()
    setup_logging(config.log_level)
    logger = logging.getLogger(__name__)

    cache = CacheStore(config.cache_dir)
    telegram_client = TelegramSourceClient(config.telegram)
    await telegram_client.start()

    sheets_writer: GoogleSheetsWriter | None = None
    if config.google_sheets.enabled and config.google_sheets.spreadsheet_id:
        sheets_writer = GoogleSheetsWriter(config.google_sheets)
    else:
        logger.warning("Google Sheets writer disabled because spreadsheet_id is empty")

    orchestrator = RebuildOrchestrator(
        telegram_client=telegram_client,
        cache=cache,
        best_parser=BestExcelParser(),
        sonic_parser=SonicTextParser(),
        normalizer=ItemNormalizer(currency=config.currency),
        matcher=MatchingEngine(config.matching),
        sheets_writer=sheets_writer,
    )

    runner = AsyncSingleFlightRunner(
        orchestrator.rebuild,
        logger=logging.getLogger("app.rebuild_runner"),
        debounce_seconds=config.rebuild_debounce_seconds,
    )

    if config.initial_rebuild:
        await orchestrator.rebuild("startup")

    watchers = TelegramWatchers(config, telegram_client, runner)
    await watchers.start()
    logger.info("Watchers are running. Waiting for Telegram events.")
    try:
        await telegram_client.client.run_until_disconnected()
    finally:
        await telegram_client.stop()


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
