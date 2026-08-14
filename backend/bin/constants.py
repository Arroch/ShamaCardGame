"""
Модуль с константами для игры "Шама".

Содержит все константы, используемые в игре, включая коды статусов,
идентификаторы команд и игроков, а также названия мастей.
"""

from enum import Enum

class GameConstants:
    """Класс с константами для игры Шама."""
    
    # Константы для идентификации команд
    TEAM_1 = 10
    TEAM_2 = 20
    
    # Константы для идентификации игроков
    PLAYER_1_1 = 11  # Первый игрок первой команды
    PLAYER_1_2 = 12  # Второй игрок первой команды
    PLAYER_2_1 = 21  # Первый игрок второй команды
    PLAYER_2_2 = 22  # Второй игрок второй команды
    
    # Перечисление состояний игры
    class Status(Enum):
        """Статусы игры.
        
        Заменяет числовые коды для улучшения читаемости и надежности.
        """
        WAITING_PLAYERS = 100  # Ожидание регистрации игроков
        PLAYERS_ADDED = 104    # Все 4 игрока добавлены
        CARDS_DEALT = 201      # Карты розданы
        WAITING_TRUMP = 202    # Ожидание выбора козыря
        TRUMP_SELECTED = 203   # Козырь выбран, можно начинать игру
        PLAYING_CARDS = 300    # Процесс игры, ход картами
        PLAYED_CARD_1 = 301    # Процесс игры (1 карта на столе)
        PLAYED_CARD_2 = 302    # Процесс игры (2 карты на столе)
        PLAYED_CARD_3 = 303    # Процесс игры (3 карты на столе)
        TRICK_COMPLETED = 304  # Завершен кон (4 карты на столе)
        GAME_COMPLETED = 409   # Игра завершена (все 9 конов сыграны)
        NEW_DEAL_READY = 500   # Готово к новой раздаче
        MATCH_COMPLETED = 600  # Матч завершен (одна из команд набрала 12+ очков)
        GAME_FINISHED = 700    # Игра полностью завершена
    
    # Порядок хода игроков
    PLAYERS_QUEUE = {
        PLAYER_1_1: PLAYER_2_1,  # После 1-го игрока 1-й команды ходит 1-й игрок 2-й команды
        PLAYER_2_1: PLAYER_1_2,  # После 1-го игрока 2-й команды ходит 2-й игрок 1-й команды
        PLAYER_1_2: PLAYER_2_2,  # После 2-го игрока 1-й команды ходит 2-й игрок 2-й команды
        PLAYER_2_2: PLAYER_1_1,  # После 2-го игрока 2-й команды ходит 1-й игрок 1-й команды
    }

    # Константы для мастей
    HEARTS = 'hearts'       # Червы
    DIAMONDS = 'diamonds'   # Бубны
    CLUBS = 'clubs'         # Трефы
    SPADES = 'spades'       # Пики

    # Маппинг мастей на символы
    SUIT_SYMBOLS = {
        HEARTS: '♥',
        DIAMONDS: '♦',
        CLUBS: '♣',
        SPADES: '♠'
    }

    CARDS_DECK = [
        {'rank': '6', 'suit': DIAMONDS, 'value': 0,     'mask': 0},
        {'rank': '7', 'suit': DIAMONDS, 'value': 0,     'mask': 1},
        {'rank': '8', 'suit': DIAMONDS, 'value': 0,     'mask': 2},
        {'rank': '9', 'suit': DIAMONDS, 'value': 0,     'mask': 3},
        {'rank': 'Q', 'suit': DIAMONDS, 'value': 3,     'mask': 4},
        {'rank': 'K', 'suit': DIAMONDS, 'value': 4,     'mask': 5},
        {'rank': 'T', 'suit': DIAMONDS, 'value': 10,    'mask': 6},
        {'rank': 'A', 'suit': DIAMONDS, 'value': 11,    'mask': 7},
        {'rank': '6', 'suit': HEARTS,   'value': 0,     'mask': 8},
        {'rank': '7', 'suit': HEARTS,   'value': 0,     'mask': 9},
        {'rank': '8', 'suit': HEARTS,   'value': 0,     'mask': 10},
        {'rank': '9', 'suit': HEARTS,   'value': 0,     'mask': 11},
        {'rank': 'Q', 'suit': HEARTS,   'value': 3,     'mask': 12},
        {'rank': 'K', 'suit': HEARTS,   'value': 4,     'mask': 13},
        {'rank': 'T', 'suit': HEARTS,   'value': 10,    'mask': 14},
        {'rank': 'A', 'suit': HEARTS,   'value': 11,    'mask': 15},
        {'rank': '6', 'suit': SPADES,   'value': 0,     'mask': 16},
        {'rank': '7', 'suit': SPADES,   'value': 0,     'mask': 17},
        {'rank': '8', 'suit': SPADES,   'value': 0,     'mask': 18},
        {'rank': '9', 'suit': SPADES,   'value': 0,     'mask': 19},
        {'rank': 'Q', 'suit': SPADES,   'value': 3,     'mask': 20},
        {'rank': 'K', 'suit': SPADES,   'value': 4,     'mask': 21},
        {'rank': 'T', 'suit': SPADES,   'value': 10,    'mask': 22},
        {'rank': 'A', 'suit': SPADES,   'value': 11,    'mask': 23},
        {'rank': '7', 'suit': CLUBS,    'value': 0,     'mask': 24},
        {'rank': '8', 'suit': CLUBS,    'value': 0,     'mask': 25},
        {'rank': '9', 'suit': CLUBS,    'value': 0,     'mask': 26},
        {'rank': 'Q', 'suit': CLUBS,    'value': 3,     'mask': 27},
        {'rank': 'K', 'suit': CLUBS,    'value': 4,     'mask': 28},
        {'rank': 'T', 'suit': CLUBS,    'value': 10,    'mask': 29},
        {'rank': 'A', 'suit': CLUBS,    'value': 11,    'mask': 30},
        {'rank': 'J', 'suit': DIAMONDS, 'value': 2,     'mask': 31},
        {'rank': 'J', 'suit': HEARTS,   'value': 2,     'mask': 32},
        {'rank': 'J', 'suit': SPADES,   'value': 2,     'mask': 33},
        {'rank': 'J', 'suit': CLUBS,    'value': 2,     'mask': 34},
        {'rank': '6', 'suit': CLUBS,    'value': 0,     'mask': 35},
    ]
