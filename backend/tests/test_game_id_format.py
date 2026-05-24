#!/usr/bin/env python3
"""
Тест для проверки нового формата game_id (простые номера вместо test_game_001)
"""

import asyncio
import sys
import os
import pytest

# Добавляем путь к проекту
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from bin.core import MatchState, GameEngine
from bin.file_storage import FileStorage

@pytest.mark.asyncio
async def test_new_game_id_format():
    """Тестируем новый формат game_id с простыми номерами раздач"""

    print("🧪 Тестирование нового формата game_id")
    print("=" * 50)

    # Создаем хранилище
    storage = FileStorage()
    await storage.init_database()

    # Создаем состояние игры
    match_state = MatchState()
    match_state.set_current_game(1)  # Первая раздача

    # Создаем тестовые руки
    from bin.core import Card
    hands = {
        11: [Card('hearts', 'A', 11), Card('clubs', '7', 0)],
        12: [Card('diamonds', 'K', 4), Card('spades', '10', 10)],
        21: [Card('hearts', 'Q', 3), Card('clubs', '8', 0)],
        22: [Card('diamonds', 'J', 2), Card('spades', '9', 0)]
    }

    # Сохраняем первую раздачу
    match_id = "test_simple_game"
    game_id = match_state.current_game  # Просто 1

    print(f"💾 Сохраняем раздачу:")
    print(f"   Match ID: {match_id}")
    print(f"   Game ID: {game_id} (простой номер)")
    print(f"   Trump: hearts")
    print(f"   Shama player: 11")

    await storage.create_game(match_id, game_id, 'hearts', 11, hands)

    # Сохраняем вторую раздачу
    match_state.set_current_game()  # Увеличиваем до 2
    game_id = match_state.current_game

    print(f"\n💾 Сохраняем вторую раздачу:")
    print(f"   Match ID: {match_id}")
    print(f"   Game ID: {game_id} (простой номер)")
    print(f"   Trump: spades")
    print(f"   Shama player: 12")

    await storage.create_game(match_id, game_id, 'spades', 12, hands)

    print("\n✅ Тест завершен! Проверьте файл games.csv для подтверждения")

    # Показываем содержимое файла
    print("\n📊 Содержимое games.csv:")
    games_file = os.path.join('bin', 'storage', 'games', 'games.csv')
    if os.path.exists(games_file):
        with open(games_file, 'r') as f:
            lines = f.readlines()
            for line in lines[-3:]:  # Последние 3 строки
                print(f"   {line.strip()}")
    else:
        print("   Файл не найден")

if __name__ == "__main__":
    asyncio.run(test_new_game_id_format())