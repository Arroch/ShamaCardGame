#!/usr/bin/env python3
"""
Тест для проверки логирования ходов ботов в хранилище
"""

import asyncio
import sys
import os
import pytest

# Добавляем путь к проекту
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from bin.core import MatchState, GameEngine, Card
from bin.file_storage import FileStorage
import client_tg_bot.state as S

@pytest.mark.asyncio
async def test_bot_logging():
    """Тестируем логирование ходов ботов"""

    print("🧪 Тестирование логирования ходов ботов")
    print("=" * 50)

    # Создаем хранилище
    S.storage = FileStorage()
    await S.storage.init_database()

    # Создаем состояние игры с ботами
    match_state = MatchState()
    match_state.set_current_game(1)

    # Добавляем игроков (включая ботов)
    from bin.core import Player
    match_state.add_player(11, Player(12345, 'Игрок1'))  # Живой игрок
    match_state.add_player(12, Player(-12, 'Бот Маша'))  # Бот
    match_state.add_player(21, Player(67890, 'Игрок2'))  # Живой игрок
    match_state.add_player(22, Player(-22, 'Бот Коля'))  # Бот

    # Создаем движок игры
    engine = GameEngine(match_state)
    engine.start_game()

    # Устанавливаем козырь
    match_state.trump = 'hearts'
    from bin.constants import GameConstants
    match_state.set_status(GameConstants.Status.TRUMP_SELECTED)

    # Раздаем тестовые карты
    cards = [
        Card('hearts', 'A', 11), Card('clubs', '7', 0),
        Card('diamonds', 'K', 4), Card('spades', '10', 10),
        Card('hearts', 'Q', 3), Card('clubs', '8', 0),
        Card('diamonds', 'J', 2), Card('spades', '9', 0)
    ]

    # Распределяем карты по игрокам
    for i, player_pos in enumerate([11, 12, 21, 22]):
        match_state.players[player_pos].hand = [cards[i*2], cards[i*2+1]]

    # Сохраняем матч и раздачу
    match_id = "test_bot_match"

    # Сохраняем матч (включая ботов)
    player_ids = {11: 12345, 12: -12, 21: 67890, 22: -22}
    await S.storage.create_match(match_id, player_ids)

    # Сохраняем раздачу
    hands = {}
    for position, player in match_state.players.items():
        hands[position] = player.hand

    await S.storage.create_game(match_id, 1, 'hearts', 11, hands)

    print("✅ Матч и раздача сохранены (включая ботов)")

    # Имитируем ход бота
    print("\n🤖 Имитируем ход бота...")

    # Устанавливаем бота как текущего игрока
    match_state.current_player_index = 12  # Бот Маша

    # Выбираем допустимую карту
    valid_idx = 0  # Первая карта в руке

    # Имитируем ход бота
    status, player, card = engine.play_turn(12, valid_idx)
    print(f"   Бот {player.name} сыграл: {card}")

    # Логируем ход бота
    await S.storage.log_event(player.id, player.name, "play_card", {"card": str(card)})
    print("✅ Ход бота залогирован")

    # Проверяем сохраненные данные
    print("\n📊 Проверяем сохраненные данные:")

    # Проверяем матчи
    matches_file = os.path.join('bin', 'storage', 'matches', 'matches.csv')
    if os.path.exists(matches_file):
        with open(matches_file, 'r') as f:
            lines = f.readlines()
            print("   Матчи:")
            for line in lines[-2:]:
                print(f"     {line.strip()}")
    else:
        print("   Матчи: файл не найден")

    # Проверяем раздачи
    games_file = os.path.join('bin', 'storage', 'games', 'games.csv')
    if os.path.exists(games_file):
        with open(games_file, 'r') as f:
            lines = f.readlines()
            print("\n   Раздачи:")
            for line in lines[-2:]:
                print(f"     {line.strip()}")
    else:
        print("   Раздачи: файл не найден")

    # Проверяем события
    import csv
    events_file = os.path.join('bin', 'storage', 'events', 'events.csv')
    if os.path.exists(events_file):
        with open(events_file, 'r') as f:
            reader = csv.DictReader(f)
            events = list(reader)
            print(f"\n   Событий: {len(events)} записей")
            if events:
                last_event = events[-1]
                print(f"     Последнее: {last_event['event_type']} от {last_event['player_username']}")
    else:
        print("   Событий: файл не найден")

    print("\n✅ Тест завершен!")

if __name__ == "__main__":
    asyncio.run(test_bot_logging())