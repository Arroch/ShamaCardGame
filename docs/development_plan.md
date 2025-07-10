# План разработки игры "Шама"

## Обзор проекта
- Карточная игра "Шама" для 4 игроков (2 команды по 2 игрока)
- Особенности игры:
  - Используется колода из 36 карт
  - Игра ведется на 9 кругов (раздач)
  - Командная стратегия и тактика
  - Специальные правила подсчета очков
- Интеграция с Telegram через WebApp
- Мультиплеерная онлайн-игра
- Система логирования и статистики

## Архитектура системы
```mermaid
graph LR
    A[Telegram Client] -->|WebApp| B[Frontend: React]
    B -->|REST API| C[Backend: FastAPI]
    C -->|WebSockets| B
    C -->|Data| D[(PostgreSQL)]
    C -->|Payments| E[Telegram Payments API]
```

## Этапы разработки

### 1. Игровое ядро (5 дней)
- Реализация логики карт и ходов по правилам "Шамы"
- CLI-интерфейс для тестирования
- Юнит-тесты

### 2. Фронтенд (3 дня)
- Адаптивный интерфейс для мобильных устройств
- Базовые компоненты игры (игровой стол, карты игрока)

### 3. Telegram интеграция (2 дня)
- WebApp для single-device игры
- Базовое взаимодействие с ботом

### 4. База данных (4 дня)
- Настройка PostgreSQL
- Система логирования матчей и раздач

### 5. Мультиплеер (5 дней)
- WebSockets для реального времени
- Система комнат и приглашений
- Рейтинговая система

## Схема базы данных
```mermaid
erDiagram
    EVENTS ||--o{ PLAYERS : contains
    MATCHES ||--o{ PLAYERS : contains
    MATCHES ||--o{ GAMES : contains
    MATCHES ||--o{ TURNS : contains
    GAMES ||--o{ TURNS : contains
    EVENTS {
        int user_id FK
        timestamp timestamp
        varchar event
        data data
        type else
    }
    MATCHES {
        int id PK 
        timestamp start_time
        timestamp end_time
        int player_11
        int player_12
        int player_21
        int player_22
        int winning_team
        int total_score_1
        int total_score_2
    }
    GAMES {
        int id
        int match_id FK
        varchar trump
        int shama
        list hand_11
        list hand_12
        list hand_21
        list hand_22
    }
    TURNS {
        int id
        int match_id FK
        int game_id FK
        int first_turn
        varchar card_11
        varchar card_12
        varchar card_21
        varchar card_22
        int loot_value
        int lootting_team
    }
    PLAYERS {
        int id PK
        varchar name
        int games
        int wins
        type else
    }
```

## Система логирования
- **MatchesLog**: Хранит данные матчей
- **GamesLog**: Хранит данные раздач (9 кругов)
- **TurnsLog**: Хранит данные ходов
- **PlayersLog**: Хранит данные игроков
- **EventsLog**: Хранит данные событий (регистрация, создание игры, подключение к игре и тд)

## Необходимые ресурсы
1. Сервер PostgreSQL
2. Python 3.10+ для бэкенда
3. Node.js 18+ для фронтенда
4. Telegram Bot API

---
_План актуален на 23 июня 2025 г._
