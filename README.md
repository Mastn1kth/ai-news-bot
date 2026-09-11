# ai-news-bot

Автоматизация для Telegram-канала с AI/IT-новостями. Система собирает новости из RSS/Atom, считает score по правилам, отсекает мусор и дубли, формирует пост на русском и отправляет его через Telegram Bot API.

Базовый режим работает без платных AI API. LLM/Ollama и Telethon вынесены в опциональные режимы.

## 1. Что делает проект

- Читает источники из `config/sources.yml`.
- Собирает новости из RSS/Atom.
- Очищает HTML и мусор.
- Считает score от 0 до 100.
- Отклоняет дубли, кликбейт, рекламу, вакансии и слишком слабые новости.
- Сохраняет новости и причины отклонения в SQLite.
- Формирует Telegram-пост.
- В режиме `run` публикует готовые посты в канал.
- В режиме `dry-run` ничего не отправляет.
- Проверяет источники командой `validate-sources`.

## 2. Что работает бесплатно

Бесплатно работают RSS, SQLite, rule-based фильтрация, дедупликация, Docker и Telegram Bot API. Для этого не нужны OpenAI, Claude, Gemini или другие платные API.

Telegram Bot API бесплатный, но нужен свой бот и канал, где бот добавлен администратором.

## 3. Ограничения бесплатных серверов

Полностью бесплатный вечный сервер без лимитов никто честно не гарантирует. Бесплатные тарифы могут засыпать, требовать карту, иметь лимиты времени или запрещать долгие фоновые задачи.

Практичные варианты:

- домашний ПК с cron/Task Scheduler, если он часто включен;
- VPS, если нужна стабильность;
- GitHub Actions по расписанию, если хватает лимитов и устраивает запуск раз в несколько часов;
- Docker на любом сервере.

Сам код не требует платных API. Надежность зависит от места запуска.

## 4. Как создать Telegram-бота через BotFather

1. Открой Telegram.
2. Найди `@BotFather`.
3. Отправь `/newbot`.
4. Задай имя и username бота.
5. BotFather выдаст `TELEGRAM_BOT_TOKEN`.

Токен нельзя писать в коде и отправлять в публичные места.

## 5. Как добавить бота администратором в канал

1. Открой настройки канала.
2. Перейди в администраторы.
3. Добавь созданного бота.
4. Дай право публиковать сообщения.

Без прав администратора Telegram вернет ошибку при публикации.

## 6. Как узнать `TELEGRAM_CHAT_ID`

Для публичного канала можно использовать username:

```env
TELEGRAM_CHAT_ID=@your_channel_name
```

Для приватного канала обычно нужен numeric id вида `-1001234567890`. Самый простой путь: временно сделать тестовый пост ботом или использовать сервисы/боты для получения chat id. Не публикуй токен в сторонние сервисы.

## 7. Как заполнить `.env`

Сделай файл `.env` рядом с `.env.example` и заполни:

```env
TELEGRAM_BOT_TOKEN=123456:secret
TELEGRAM_CHAT_ID=@your_channel_name
MIN_SCORE=65
MAX_POSTS_PER_RUN=3
DRY_RUN=true
REQUEST_TIMEOUT=15
FETCH_RETRIES=3
USE_LLM=false
USE_TELEGRAM_FETCHER=false
```

Пока `DRY_RUN=true`, команда `run` не отправляет сообщения. Для реальной публикации поставь:

```env
DRY_RUN=false
```

## 8. Как добавить RSS-источники

Открой `config/sources.yml` и добавь источник:

```yaml
- name: Example AI Blog
  type: rss
  url: https://example.com/feed.xml
  category: ai_lab
  tier: 2
  trust_score: 8
  language: en
  rewrite_policy: keep_detailed
  enabled: true
```

Нерабочие источники лучше не удалять, а выключать:

```yaml
enabled: false
disabled_reason: Feed returned 404 on check.
```

## 9. Как запустить локально

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m app.main init-db
python -m app.main list-sources
python -m app.main validate-sources
python -m app.main dry-run
```

Команды запускаются из папки `ai-news-bot`.

## 10. Как запустить через Docker

```powershell
docker compose build
docker compose run --rm ai-news-bot python -m app.main dry-run
docker compose run --rm ai-news-bot python -m app.main run
```

База лежит в `data/news.db`, потому что папка `data` проброшена volume.

## 11. Как настроить cron

Пример для Linux, запуск каждые 3 часа:

```cron
0 */3 * * * cd /path/to/ai-news-bot && /usr/bin/python3 -m app.main run >> logs/cron.log 2>&1
```

Создай папку `logs`, если хочешь писать cron-лог в файл.

## 12. Как запустить `dry-run`

```powershell
python -m app.main dry-run
```

`dry-run` собирает новости, считает score, сохраняет записи в SQLite и показывает preview готовых постов. В Telegram он ничего не отправляет.

## 13. Как проверить Telegram

После заполнения `.env`:

```powershell
python -m app.main test-telegram
```

Если команда упала, проверь:

- токен бота;
- `TELEGRAM_CHAT_ID`;
- добавлен ли бот администратором;
- есть ли у бота право публиковать.

## 14. Как включить Telegram-парсинг через Telethon

По умолчанию Telegram-парсинг выключен.

В `.env`:

```env
USE_TELEGRAM_FETCHER=true
TELETHON_API_ID=
TELETHON_API_HASH=
TELETHON_SESSION=ai_news_bot
```

Telethon должен читать только публичные каналы. Закрытые каналы, обход приватности и копирование чужих постов один в один не поддерживаются.

Все Telegram-источники должны иметь:

```yaml
rewrite_policy: rewrite_required
```

## 15. Как включить Ollama

Ollama нужен только для локального улучшения рерайта. Базовая система без него работает.

В `.env`:

```env
USE_LLM=true
LLM_PROVIDER=ollama
LLM_API_BASE=http://localhost:11434/api/generate
LLM_MODEL=llama3.1
```

Если Ollama недоступна, система пишет предупреждение и возвращается к rule-based посту.

Для OpenAI-compatible API:

```env
USE_LLM=true
LLM_PROVIDER=openai-compatible
LLM_API_BASE=https://example.com/v1
LLM_API_KEY=your_key
LLM_MODEL=your_model
```

Это опционально. Базовый режим не требует внешнего LLM API.

## 16. Как смотреть логи

Обычный запуск:

```powershell
python -m app.main dry-run
```

Подробный запуск:

```powershell
python -m app.main --verbose dry-run
```

В SQLite можно смотреть таблицы:

- `news_items`;
- `sources_state`;
- `publish_log`.

## 17. Как понять, почему новость не опубликована

Смотри поля в `news_items`:

- `status`;
- `reject_reason`;
- `score`;
- `error_message`.

Типовые причины:

- `low_score`;
- `duplicate`;
- `duplicate_similar_title`;
- `too_short_without_facts`;
- `clickbait`;
- `ad_or_partner_material`;
- `missing_source_url`.

## CLI-команды

```powershell
python -m app.main init-db
python -m app.main list-sources
python -m app.main validate-sources
python -m app.main dry-run
python -m app.main run
python -m app.main test-telegram
```

## Проверка источников

```powershell
python -m app.main validate-sources
```

Проверить даже выключенные источники:

```powershell
python -m app.main validate-sources --all
```

Автоматически выключить сломанные источники и записать причину:

```powershell
python -m app.main validate-sources --write
```

## Важная честная оговорка

Rule-based режим не является полноценным литературным переводчиком. Он формирует пост на русском и вытаскивает из источника названия, даты, версии, суммы и продукты, но не заменяет качественный LLM-рерайт. Для более естественного текста включи Ollama или OpenAI-compatible провайдера. Это не ломает базовое требование: без AI API система все равно работает.
