# Шама - Карточная игра для Telegram

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Официальная реализация карточной игры "Шама" в формате Telegram Mini App.

## Особенности игры
- Классические правила игры в "Шаму" с 36 картами
- Реализована single-device игра через CLI

## В планах
- Мультиплеер на 4 игрока (2 команды по 2 человека)
    - через TelegramBotApi
    - через TelegramWebApp
- Интеграция с Telegram (WebApp, Bot, Payments)
- Система чата и реакций (эмодзи, звуковые фразы)
- Внутриигровые покупки

## Технологический стек
- **Фронтенд**: React, TypeScript, Vite
- **Бэкенд**: Python (FastAPI), WebSockets
- **База данных**: PostgreSQL
- **Инфраструктура**: Docker, Nginx

## Быстрый старт
1. Клонируйте репозиторий:
```bash
git clone https://github.com/Arroch/ShamaCardGame
cd shama-game
```

2. Запустите проект (инструкции будут дополнены):
```bash
backend/game_cli.py
```

## Документация
- [Техническое задание](TECHNICAL_SPEC.md) (будет добавлена)
- [API документация](docs/API.md) (будет добавлена)
- [Архитектура системы](docs/ARCHITECTURE.md) (будет добавлена)

## Лицензия
Проект распространяется под лицензией MIT. Подробнее см. [LICENSE](LICENSE).
