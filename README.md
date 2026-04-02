# Apple Telegram Price Watcher

Рабочий Python-модуль для:

- отслеживания двух Telegram-источников через userbot на `Telethon`
- парсинга Apple-прайсов из Excel-сообщения `BEST` и текстовых сообщений `SONIC`
- нормализации Apple-товаров в канонические сущности
- слияния базового слоя `BEST` с приоритетными ценами `SONIC`
- записи итогового снапшота в один лист Google Sheets

## Архитектура

Пайплайн специально сделан детерминированным и прозрачным:

1. загрузить актуальный `BEST` из Telegram
2. распарсить Excel `BEST`
3. нормализовать позиции `BEST`
4. загрузить `SONIC` из Telegram
5. распарсить `SONIC`
6. нормализовать позиции `SONIC`
7. наложить `SONIC` поверх `BEST`
8. полностью перезаписать один лист Google Sheets
9. сохранить локальный кэш и статистику rebuild

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

## Логика источников

### BEST

- отслеживается одно фиксированное Telegram-сообщение в одном канале
- внутри сообщения ожидается Excel-файл
- при редактировании этого сообщения файл скачивается заново и запускается rebuild
- обрабатываются только Apple-листы:
  - `Аксессуары Apple`
  - `AirPods`
  - `Apple Watch`
  - `iPhone`
  - `iPad`
  - `MacBook`
  - `iMac`

### SONIC

SONIC теперь работает через **полный перескан канала**, а не через tracked `message_id` и не через batch по времени.

Это означает:

- watcher слушает **все новые и редактируемые сообщения** канала SONIC
- при любом таком событии запускается rebuild
- во время rebuild проект читает **все сообщения канала SONIC**
- среди них автоматически отбираются только **прайс-сообщения**
- из этих сообщений собирается единый SONIC snapshot

Что считается прайс-сообщением:

- большое сообщение с несколькими секциями и строками товаров
- сообщение с одной секцией и несколькими товарами
- сообщение из **одной-единственной товарной строки**
- сообщение-продолжение, где нет заголовка секции, но есть валидная строка вида `название - цена [флаг]`

Примеры валидных строк:

- `iPad 11 128 Silver Wi-Fi - 27.900 🇺🇸`
- `Magic Keyboard Air 11 Black (MGYX4) - 25.500 🇺🇸`

Служебные посты без валидных товарных строк в SONIC snapshot не попадают.

## Установка

Windows:

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
4. Создай Telegram API application.
5. Сохрани `api_id` и `api_hash`.

Важно:

- это не Bot API и не `BotFather`
- проект использует именно userbot session через `Telethon`

### 2. Первый вход Telethon

При первом запуске Telethon попросит:

- номер телефона
- код подтверждения
- пароль 2FA, если он включен

После успешного входа session-файл будет сохранен по пути `sessions/apple_prices.session` или по пути из `TELEGRAM_SESSION_NAME`.

### 3. Как указать канал и сообщение BEST

Для `BEST` нужны:

- `BEST_CHANNEL`
- `BEST_MESSAGE_ID`

Если ссылка на сообщение выглядит так:

```text
https://t.me/c/1887497207/6131
```

Тогда значения будут такими:

```env
BEST_CHANNEL=-1001887497207
BEST_MESSAGE_ID=6131
```

### 4. Как указать канал SONIC

Для `SONIC` достаточно указать:

- `SONIC_CHANNEL`

Пример:

```env
SONIC_CHANNEL=-1001234567890
```

Дополнительно можно ограничить глубину перескана:

```env
SONIC_SCAN_LIMIT=200
```

Для маленького канала этого более чем достаточно.

## Настройка Google Sheets

### 1. Создание service account

1. Открой Google Cloud Console.
2. Создай проект или выбери существующий.
3. Включи `Google Sheets API`.
4. Создай `service account`.
5. Сгенерируй JSON-ключ.
6. Сохрани его локально, например как `service-account.json`.

### 2. Расшаривание таблицы

1. Создай Google Sheet.
2. Скопируй `spreadsheet id` из URL таблицы.
3. Открой JSON service account и возьми поле `client_email`.
4. Расшарь таблицу на этот email.
5. Дай права `Редактор`.

## Конфигурация

Можно использовать `.env`, `config.yaml` или оба варианта сразу. Переменные окружения имеют приоритет над YAML.

### Пример `.env`

```env
TELEGRAM_API_ID=123456
TELEGRAM_API_HASH=your_api_hash
TELEGRAM_SESSION_NAME=sessions/apple_prices

BEST_CHANNEL=@best_channel_or_numeric_id
BEST_MESSAGE_ID=12345

SONIC_CHANNEL=@sonic_channel_or_numeric_id
SONIC_SCAN_LIMIT=200

# Legacy / optional:
SONIC_MESSAGE_IDS=
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
- процесс остается жить и реагирует на Telegram-события

## Что записывается в Google Sheets

Проект пишет данные в один worksheet и полностью перезаписывает его при каждом rebuild.

Основные колонки:

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

Проект хранит fallback-данные в `cache/`:

- `latest_best.xlsx`
- `latest_best_parsed.json`
- `latest_sonic_parsed.json`
- `latest_sonic_batch.txt`
- `latest_merged.json`
- `latest_rebuild_stats.json`

Поведение при сбоях:

- если не скачался `BEST`, используется кэшированный Excel
- если не распарсился `BEST`, используется кэшированный parsed `BEST`
- если не удалось получить или распарсить `SONIC`, используется кэшированный parsed `SONIC`
- если оба источника временно недоступны, может быть возвращен последний merged snapshot
- если упал апдейт Google Sheets, ошибка логируется, но процесс продолжает работать

## Логи

Используется стандартный Python logging с уровнями:

- `DEBUG`
- `INFO`
- `WARNING`
- `ERROR`

Типовые SONIC-события в логах:

- `Rebuild triggered by SONIC new message_id=...`
- `Rebuild triggered by SONIC edited message_id=...`
- `Scanned SONIC channel messages = N`
- `Detected SONIC price messages = M`
- `Parsed SONIC rows = X`

## Где подстраивать нормализацию и matching

Основные места для донастройки:

- `app/normalization/aliases.py`
  - ключевые слова категорий
  - алиасы цветов
  - алиасы connectivity
  - семейства аксессуаров
- `app/normalization/patterns.py`
  - regex для year, storage, chip, screen size и family
- `app/normalization/normalizer.py`
  - предобработка, извлечение полей, сборка `canonical_name` и `canonical_key`
- `app/normalization/matcher.py`
  - hard constraints, scoring и thresholds
- `app/parsers/sonic_text_parser.py`
  - эвристики определения прайс-сообщений SONIC
  - правила разбора одиночных строк и секций

## Тесты

Запуск:

```bash
pytest
```

Базово покрыто:

- парсинг цен
- парсинг строк `SONIC`
- парсинг `BEST` Excel
- detection прайс-сообщений SONIC
- single-line SONIC messages
- fallback SONIC через кэш
- нормализация
- matching
- merge logic

## Запуск на VPS

Типовой сценарий:

1. скопировать проект на сервер
2. создать `.env` или `config.yaml`
3. загрузить `service-account.json`
4. один раз запустить приложение интерактивно, чтобы создать Telethon session
5. после создания session-файла запускать процесс через `systemd`, `supervisor`, `tmux` или Docker

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

## Что, скорее всего, придется подправить под реальные данные

- эвристики секций Excel в `app/parsers/best_excel_parser.py`
- regex и детектор SONIC в `app/parsers/sonic_text_parser.py`
- словари аксессуаров и naming aliases
- алиасы цветов и connectivity
- состав `canonical_key`
- пороги и веса matching

Текущая реализация нарочно сделана прямолинейной и модульной, чтобы эти изменения оставались локальными и управляемыми.
