# Шама — Карточная игра

Реализация классической карточной игры «Шама» с тремя клиентами: CLI, Telegram-бот и (в будущем) Telegram WebApp.

## Структура проекта

```
ShamaCardGame/
├── backend/
│   ├── bin/                        # Общая игровая логика
│   │   ├── core.py                 # Движок (Card, Player, MatchState, GameEngine)
│   │   ├── constants.py            # Константы (масти, статусы, порядок ходов)
│   │   ├── storage_factory.py      # Фабрика хранилища (file / postgres)
│   │   ├── file_storage.py         # Файловое хранилище (CSV + JSON-события)
│   │   └── database_manager.py     # PostgreSQL (опционально)
│   ├── client_cli/
│   │   └── start_game.py           # CLI-клиент (4 игрока на одном устройстве)
│   ├── client_tg_bot/
│   │   ├── start_game.py           # Точка входа бота (run_bot, main)
│   │   ├── state.py                # Глобальное in-memory состояние
│   │   ├── game.py                 # Игровые хелперы (start_game, send_player_cards, …)
│   │   └── handlers.py             # Обработчики команд и callback-кнопок
│   ├── client_web/
│   │   └── start_game.py           # WebApp-клиент (в разработке)
│   ├── tests/
│   │   ├── test_core.py            # Тесты игрового движка
│   │   └── test_game_cli.py        # Тесты CLI-клиента
│   └── requirements.txt
├── README.md
└── TECHNICAL_SPEC.md
```

## Быстрый старт

### Требования

- Python 3.9+
- Telegram Bot API токен (только для TG-бота)

### Установка

```bash
git clone https://github.com/Arroch/ShamaCardGame
cd ShamaCardGame

python -m venv venv
source venv/bin/activate          # macOS/Linux
# venv\Scripts\activate           # Windows

pip install -r backend/requirements.txt
```

### Переменные окружения

Создайте файл `backend/.env` или задайте переменные вручную:

```bash
TELEGRAM_BOT_TOKEN=ваш_токен          # обязательно для TG-бота
STORAGE_TYPE=file                      # file (по умолчанию) или postgres
PROXY_URL=socks5://host:port           # SOCKS5-прокси (опционально)
# PROXY_URL=socks5://user:pass@host:port  # с авторизацией
```

При `STORAGE_TYPE=postgres` дополнительно:

```bash
DB_HOST=localhost
DB_PORT=5432
DB_NAME=shama_game
DB_USER=ваш_пользователь
DB_PASSWORD=ваш_пароль
```

### Запуск

**Telegram-бот:**
```bash
cd backend
python -m client_tg_bot.start_game
```

**CLI (локальная игра на одном устройстве):**
```bash
cd backend
python -m client_cli.start_game
```

**Тесты:**
```bash
cd backend
pytest
```

## Telegram-бот: команды

| Команда | Описание |
|---|---|
| `/start` | Регистрация / присоединение по инвайт-ссылке |
| `/help` | Список команд |
| `/rules` | Правила игры |
| `/create_game` | Создать новую игровую комнату |
| `/start_game` | Принудительно запустить игру (только создатель) |
| `/status` | Текущее состояние игры |
| `/stats` | Ваша статистика |
| `/ping` | Проверить работу бота |
| `/info` | Информация о боте |
| `/fill_bots` | Заполнить свободные места ботами (только создатель, для тестирования) |

## Процесс онлайн-игры

1. Один игрок создаёт комнату командой `/create_game`
2. Полученная инвайт-ссылка отправляется трём другим игрокам
3. Каждый переходит по ссылке и выбирает команду (1 или 2)
4. При 4 игроках игра стартует автоматически — карты раздаются, каждый получает их в личку
5. Игрок с шамой (6♣) выбирает козырь через кнопки
6. Игроки ходят картами по очереди, выбирая карту из инлайн-клавиатуры
7. После 9 ходов подсчитываются взятки и начисляются очки
8. Матч продолжается до тех пор, пока одна из команд не наберёт 12+ очков

## Хранилище данных

По умолчанию используется **файловое хранилище** (CSV + JSON):

| Файл | Содержимое |
|---|---|
| `backend/storage/players/players.csv` | Профили и статистика игроков |
| `backend/storage/matches/matches.csv` | Завершённые матчи |
| `backend/storage/games/games.csv` | Раздачи (руки, козырь, шама) |
| `backend/storage/turns/turns.csv` | Ходы (карты, взятки) |
| `backend/storage/events/*.json` | Лог всех событий |

**PostgreSQL** доступен как опция через `STORAGE_TYPE=postgres` (требует psycopg2).

## Автозапуск на Linux (systemd)

```bash
# 1. Отредактируйте deploy/shama-bot.service — укажите User, пути и токен
# 2. Установите сервис:
sudo bash deploy/install.sh

# Управление:
systemctl status shama-bot
sudo systemctl restart shama-bot
sudo systemctl stop shama-bot
journalctl -u shama-bot -f
```

## Правила игры

Подробные правила — в [TECHNICAL_SPEC.md](TECHNICAL_SPEC.md).

## Статус разработки

| Компонент | Статус |
|---|---|
| Игровой движок (`bin/core.py`) | ✅ Реализован, покрыт тестами |
| CLI-клиент (`client_cli/`) | ✅ Реализован |
| Telegram-бот (`client_tg_bot/`) | ✅ Реализован |
| Файловое хранилище | ✅ Реализовано |
| PostgreSQL хранилище | ⚠️ Реализовано, не тестировалось |
| Telegram WebApp (`client_web/`) | 🚧 В разработке |
| Восстановление игры после рестарта бота | 🚧 В разработке |
