# Apple Telegram Price Watcher

Рабочий Python-модуль для:

- отслеживания двух Telegram-источников через userbot на `Telethon`
- парсинга Apple-прайсов из Excel-сообщения `BEST` и текстовых batch-обновлений `SONIC`
- нормализации названий Apple-товаров в канонические сущности
- сопоставления и объединения базового слоя `BEST` с приоритетными ценами `SONIC`
- записи одного детерминированного снапшота в один лист Google Sheets

## Архитектура

Пайплайн сделан намеренно явным и детерминированным:

1. Загрузить актуальный источник `BEST` из Telegram.
2. Распарсить Excel `BEST`.
3. Нормализовать позиции `BEST`.
4. Загрузить последний актуальный batch `SONIC` из Telegram.
5. Распарсить текст `SONIC`.
6. Нормализовать позиции `SONIC`.
7. Наложить `SONIC` поверх `BEST`.
8. Полностью перезаписать один лист Google Sheets.
9. Сохранить локальный кэш и статистику rebuild.

При любом событии источника выполняется полная пересборка, а не частичные патчи.

## Структура проекта

```text
app/
  main.py
  config.py
  telegram_client.py
  watchers.py
  orchestrator.py
  parsers/
    best_excel_parser.py
    sonic_text_parser.py
  normalization/
    aliases.py
    patterns.py
    normalizer.py
    matcher.py
  sheets/
    google_sheets.py
  storage/
    cache.py
    models.py
  utils/
    logging.py
    locks.py
tests/
.env.example
config.example.yaml
requirements.txt
README.md
```

## Поддерживаемые источники

### BEST

- Отслеживается одно фиксированное Telegram-сообщение в одном канале.
- Внутри сообщения ожидается Excel-файл.
- При редактировании сообщения файл скачивается заново и запускается rebuild.
- Обрабатываются только Apple-листы:
  - `Аксессуары Apple`
  - `AirPods`
  - `Apple Watch`
  - `iPhone`
  - `iPad`
  - `MacBook`
  - `iMac`

### SONIC

- Отслеживается Telegram-канал на новые сообщения и редактирования.
- Берется последнее сообщение, затем к нему добираются предыдущие подряд идущие сообщения в пределах настраиваемого временного окна.
- Сообщения склеиваются в один текстовый batch и парсятся единым проходом.

## Установка

```bash
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Linux / VPS:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Настройка Telegram

### 1. Получение Telegram API credentials

1. Открой `https://my.telegram.org`.
2. Войди под своим Telegram-аккаунтом.
3. Перейди в `API development tools`.
4. Создай приложение.
5. Сохрани `api_id` и `api_hash`.

### 2. Настройка Telethon user session

Проект использует именно userbot session, а не Bot API.

При первом запуске Telethon попросит:

- номер телефона
- код подтверждения
- пароль 2FA, если он включен

После успешного входа session-файл будет сохранен по пути `sessions/apple_prices.session` или по пути из `TELEGRAM_SESSION_NAME`.

### 3. Указание каналов

Можно использовать:

- публичный username вида `@channel_name`
- числовой `channel id`

Для `BEST` также нужен точный `message_id` сообщения, в котором лежит Excel-файл.

## Настройка Google Sheets

### 1. Создание service account

1. Открой Google Cloud Console.
2. Создай проект или выбери существующий.
3. Включи Google Sheets API.
4. Создай service account.
5. Сгенерируй JSON-ключ.
6. Сохрани его локально, например как `service-account.json`.

### 2. Расшаривание таблицы

1. Создай Google Sheet.
2. Скопируй `spreadsheet id` из URL таблицы.
3. Расшарь таблицу на email service account из JSON-ключа.
4. Дай права редактора.

## Конфигурация

Можно использовать `.env`, `config.yaml` или сразу оба варианта. Переменные окружения имеют приоритет над YAML.

### Пример `.env`

```env
TELEGRAM_API_ID=123456
TELEGRAM_API_HASH=your_api_hash
TELEGRAM_SESSION_NAME=sessions/apple_prices
BEST_CHANNEL=@best_channel_or_numeric_id
BEST_MESSAGE_ID=12345
SONIC_CHANNEL=@sonic_channel_or_numeric_id
SONIC_HISTORY_LIMIT=40
SONIC_BATCH_WINDOW_MINUTES=20
SONIC_BATCH_GAP_MINUTES=6

GOOGLE_SHEETS_ENABLED=true
GOOGLE_SPREADSHEET_ID=your_google_sheet_id
GOOGLE_WORKSHEET_NAME=Apple Prices
GOOGLE_SERVICE_ACCOUNT_FILE=service-account.json

MATCHING_SIMILARITY_THRESHOLD=0.74
MATCHING_STRONG_MATCH_THRESHOLD=0.86

CACHE_DIR=cache
LOG_LEVEL=INFO
CURRENCY=RUB
INITIAL_REBUILD=true
REBUILD_DEBOUNCE_SECONDS=2.0
```

### Пример `config.yaml`

Скопируй `config.example.yaml` в `config.yaml` и подставь свои значения.

## Запуск

```bash
python -m app.main
```

Что происходит при старте:

- Telethon поднимает user session
- выполняется стартовый rebuild, если `INITIAL_REBUILD=true`
- watcher-ы подписываются на `BEST` и `SONIC`
- процесс остается жить и реагирует на новые Telegram-события

## Что записывается в Google Sheets

Проект пишет данные в один worksheet и полностью перезаписывает его при каждом rebuild.

Текущие колонки:

- `category`
- `product_line`
- `family`
- `canonical_name`
- `canonical_key`
- `price`
- `currency`
- `price_source`
- `source_priority`
- `best_price`
- `sonic_price`
- `country_flag`
- `best_country_flag`
- `sonic_country_flag`
- `model_code`
- `color`
- `storage_gb`
- `ram_gb`
- `connectivity`
- `year`
- `chip`
- `screen_size`
- `size_label`
- `raw_best_name`
- `raw_sonic_name`
- `updated_at`
- `parsed_from_best`
- `parsed_from_sonic`
- `match_score`

## Локальный кэш

Модуль хранит локальные fallback-данные в `cache/`:

- `latest_best.xlsx`
- `latest_best_parsed.json`
- `latest_sonic_parsed.json`
- `latest_sonic_batch.txt`
- `latest_merged.json`
- `latest_rebuild_stats.json`

Поведение при сбоях:

- если не скачался `BEST`, используется кэшированный `BEST` Excel
- если не распарсился `BEST`, используется кэшированный parsed `BEST` JSON
- если не удалось получить или распарсить `SONIC`, используется кэшированный parsed `SONIC` JSON
- если оба источника временно недоступны, может быть возвращен последний merged snapshot
- если упал апдейт Google Sheets, ошибка логируется, но процесс продолжает работать

## Логирование

Используется стандартный Python logging с уровнями:

- `DEBUG`
- `INFO`
- `WARNING`
- `ERROR`

Типовые события:

- поймано Telegram-событие
- скачан `BEST` Excel
- распарсены строки `BEST`
- распарсен `SONIC` batch
- количество merged rows
- количество override из `SONIC`
- количество новых строк, добавленных из `SONIC`
- успешный или неуспешный апдейт Google Sheets

## Где подстраивать нормализацию и matching

Основные места для донастройки:

- `app/normalization/aliases.py`
  - ключевые слова категорий
  - алиасы цветов
  - алиасы connectivity
  - семейства аксессуаров
- `app/normalization/patterns.py`
  - regex для year, storage, chip, screen size и product family
- `app/normalization/normalizer.py`
  - правила предобработки
  - извлечение category
  - извлечение family и product_line
  - сборка `canonical_name` и `canonical_key`
- `app/normalization/matcher.py`
  - hard constraints
  - веса strict scoring
  - weighted similarity
  - thresholds из конфига

## Тесты

Запуск:

```bash
pytest
```

Что покрыто базово:

- парсинг цены
- парсинг строки `SONIC`
- парсинг `BEST` Excel
- нормализация
- matching
- merge logic

## Запуск на VPS

Типовой сценарий:

1. Скопировать проект на сервер.
2. Создать `.env` или `config.yaml`.
3. Загрузить `service-account.json`.
4. Один раз запустить приложение интерактивно, чтобы создать Telethon session.
5. После создания session-файла запускать процесс через `systemd`, `supervisor`, `tmux` или Docker.

Минимальный пример `systemd`:

```ini
[Unit]
Description=Apple Telegram Price Watcher
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/apple-price-watcher
ExecStart=/opt/apple-price-watcher/.venv/bin/python -m app.main
Restart=always
RestartSec=5
Environment=APP_CONFIG_PATH=/opt/apple-price-watcher/config.yaml

[Install]
WantedBy=multi-user.target
```

## Какие места почти наверняка придется адаптировать под реальные данные

С высокой вероятностью ты захочешь донастроить следующие части под реальные каналы:

- эвристики секций Excel в `app/parsers/best_excel_parser.py`
- окно batch и допустимый gap для `SONIC`
- regex парсинга строк `SONIC`, если реальные строки отличаются
- словари аксессуаров и naming aliases
- алиасы цветов
- состав `canonical_key`
- пороги и веса matching

Текущая реализация уже runnable и сделана нарочно прямолинейной, чтобы эти изменения были локальными и предсказуемыми.
