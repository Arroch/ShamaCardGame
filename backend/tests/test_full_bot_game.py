#!/usr/bin/env python3
"""
Тест для проверки полной игры с ботами и сохранения всех ходов
"""

import asyncio
import sys
import os
import json
from datetime import datetime

# Добавляем путь к проекту
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from bin.core import MatchState, GameEngine, Card, Player
from bin.constants import GameConstants
from bin.file_storage import FileStorage
import client_tg_bot.state as S

async def test_full_bot_game():
    """Тестируем полную игру с ботами и сохранение всех ходов"""

    print("🧪 Тестирование полной игры с ботами")
    print("=" * 50)

    # Создаем хранилище
    S.storage = FileStorage()
    await S.storage.init_database()

    # Создаем состояние игры
    match_state = MatchState()
    match_state.set_current_game(1)

    # Добавляем игроков (включая ботов)
    match_state.add_player(11, Player(12345, 'Игрок1'))  # Живой игрок
    match_state.add_player(12, Player(-12, 'Бот Маша'))  # Бот
    match_state.add_player(21, Player(67890, 'Игрок2'))  # Живой игрок
    match_state.add_player(22, Player(-22, 'Бот Коля'))  # Бот

    # Создаем движок игры
    engine = GameEngine(match_state)
    engine.start_game()

    # Сохраняем матч
    match_id = "test_full_bot_game"
    player_ids = {11: 12345, 12: -12, 21: 67890, 22: -22}
    await S.storage.create_match(match_id, player_ids)
    print(f"✅ Матч сохранен: {match_id}")

    # Раздаем тестовые карты для полной игры
    # Создаем реалистичные руки для 4 игроков (по 8 карт каждый)
    cards = [
        # Команда 1
        Card('hearts', 'A', 11), Card('clubs', '7', 0), Card('diamonds', 'K', 4), Card('spades', '10', 10),
        Card('hearts', 'Q', 3), Card('clubs', '8', 0), Card('diamonds', 'J', 2), Card('spades', '9', 0),

        # Команда 2
        Card('hearts', 'K', 4), Card('clubs', '9', 0), Card('diamonds', 'A', 11), Card('spades', 'J', 2),
        Card('hearts', '10', 10), Card('clubs', 'Q', 3), Card('diamonds', '8', 0), Card('spades', '7', 0),

        # Команда 1
        Card('hearts', '9', 0), Card('clubs', '10', 10), Card('diamonds', 'Q', 3), Card('spades', 'K', 4),
        Card('hearts', '8', 0), Card('clubs', 'J', 2), Card('diamonds', '7', 0), Card('spades', 'A', 11),

        # Команда 2
        Card('hearts', '7', 0), Card('clubs', 'K', 4), Card('diamonds', '9', 0), Card('spades', 'Q', 3),
        Card('hearts', 'J', 2), Card('clubs', 'A', 11), Card('diamonds', '10', 10), Card('spades', '8', 0)
    ]

    # Распределяем карты по игрокам
    for i, player_pos in enumerate([11, 12, 21, 22]):
        start_idx = i * 8
        match_state.players[player_pos].hand = cards[start_idx:start_idx + 8]

    # Сохраняем первую раздачу
    hands = {}
    for position, player in match_state.players.items():
        hands[position] = player.hand

    await S.storage.create_game(match_id, 1, 'hearts', 11, hands)
    print("✅ Первая раздача сохранена")

    # Устанавливаем козырь
    match_state.trump = 'hearts'
    match_state.set_status(GameConstants.Status.TRUMP_SELECTED)

    print("\n🎮 Начинаем игру с ботами...")

    # Имитируем несколько ходов
    turn_count = 0
    max_turns = 36  # Максимум 9 ходов * 4 игрока

    while turn_count < max_turns and match_state.status not in [
        GameConstants.Status.GAME_COMPLETED,
        GameConstants.Status.MATCH_COMPLETED,
        GameConstants.Status.GAME_FINISHED
    ]:
        current_player_idx = match_state.current_player_index
        current_player = match_state.players[current_player_idx]

        print(f"\n🃏 Ход {turn_count + 1}: {current_player.name} (ID: {current_player.id})")

        # Если это бот - автоматически выбираем карту
        if current_player.id < 0:
            # Ищем допустимую карту
            valid_idx = None
            for i in range(len(current_player.hand)):
                if engine.validate_card_play(current_player_idx, i):
                    valid_idx = i
                    break

            if valid_idx is not None:
                # Имитируем задержку бота
                await asyncio.sleep(0.5)

                # Бот делает ход
                status, player, card = engine.play_turn(current_player_idx, valid_idx)
                print(f"   🤖 {player.name} сыграл: {card}")

                # Логируем ход бота
                await S.storage.log_event(player.id, player.name, "play_card", {"card": str(card)})

                # Если кон завершен (4 карты на столе)
                if match_state.status == GameConstants.Status.TRICK_COMPLETED:
                    # Сохраняем карты до очистки стола
                    cards_data = {}
                    for card_data in match_state.current_table:
                        player_pos = card_data['player_index']
                        card = card_data['card']
                        cards_data[player_pos] = str(card)

                    _, winning_card, winning_player_idx, trick_points = engine.complete_turn()
                    winning_player = match_state.players[winning_player_idx]
                    print(f"   👑 {winning_player.name} забирает взятку ({winning_card}, {trick_points} очков)")

                    # Сохраняем ход
                    game_id = match_state.current_game
                    turn_id = match_state.current_turn - 1  # complete_turn увеличивает номер хода

                    # Получаем первого игрока в этом коне
                    first_player_idx = match_state.current_table[0]['player_index'] if match_state.current_table else current_player_idx

                    await S.storage.create_turn(match_id, game_id, turn_id,
                                              first_player_idx, cards_data,
                                              trick_points, winning_player_idx // 10 * 10)

                    print(f"   💾 Ход {turn_id} сохранен")

                    # Если игра завершена
                    if match_state.status == GameConstants.Status.GAME_COMPLETED:
                        print("\n🏆 Раздача завершена!")

                        # Подсчитываем очки
                        status, scores, losed_team, losed_points, losed_points_text = engine.complete_game()
                        print(f"   Счёт: Команда 1 - {scores[10]}, Команда 2 - {scores[20]}")
                        print(f"   Команда {losed_team // 10} получает {losed_points_text}")

                        # Сохраняем завершенную игру
                        game_id = match_state.current_game
                        hands = {}
                        for position, player in match_state.players.items():
                            hands[position] = player.hand

                        await S.storage.create_game(match_id, game_id, match_state.trump,
                                                   match_state.first_player_index, hands)

                        # Если матч завершен
                        if match_state.status == GameConstants.Status.MATCH_COMPLETED:
                            print("🎉 Матч завершён!")
                            engine.complete_match()
                            break
                        else:
                            # Начинаем новую раздачу
                            print("🃏 Начинаем новую раздачу...")
                            engine.start_game()
                            match_state.set_current_game()

                            # Сохраняем новую раздачу
                            game_id = match_state.current_game
                            hands = {}
                            for position, player in match_state.players.items():
                                hands[position] = player.hand

                            await S.storage.create_game(match_id, game_id, match_state.trump,
                                                       match_state.first_player_index, hands)
                            print(f"   Новая раздача {game_id} сохранена")

            turn_count += 1
        else:
            # Живой игрок - пропускаем для теста
            print(f"   ⏭️  Пропускаем ход живого игрока для теста")
            # Переходим к следующему игроку
            next_player_idx = GameConstants.PLAYERS_QUEUE[current_player_idx]
            match_state.set_current_player_index(next_player_idx)
            turn_count += 1

    print("\n📊 Проверяем сохраненные данные:")

    # Проверяем матчи
    print("\n🔍 Матчи:")
    with open('backend/bin/storage/matches/matches.csv', 'r') as f:
        lines = f.readlines()
        for line in lines[-3:]:
            print(f"   {line.strip()}")

    # Проверяем раздачи
    print("\n🔍 Раздачи:")
    with open('backend/bin/storage/games/games.csv', 'r') as f:
        lines = f.readlines()
        for line in lines[-3:]:
            print(f"   {line.strip()}")

    # Проверяем ходы
    print("\n🔍 Ходы:")
    with open('backend/bin/storage/turns/turns.csv', 'r') as f:
        lines = f.readlines()
        for line in lines[-5:]:
            print(f"   {line.strip()}")

    # Проверяем события
    print("\n🔍 События:")
    import glob
    event_files = glob.glob('backend/bin/storage/events/*.json')
    if event_files:
        print(f"   Событий: {len(event_files)} файлов")
        # Покажем последние 3 события
        for event_file in event_files[-3:]:
            with open(event_file, 'r') as f:
                event = json.load(f)
                print(f"   {event['player_username']}: {event['event_type']} - {event.get('data', {})}")

    print("\n✅ Тест завершен!")
    print(f"\n📈 Статистика:")
    print(f"   • Сыграно ходов: {turn_count}")
    print(f"   • Сохранено раздач: {match_state.current_game}")
    print(f"   • Сохранено событий: {len(event_files) if event_files else 0}")

if __name__ == "__main__":
    asyncio.run(test_full_bot_game())