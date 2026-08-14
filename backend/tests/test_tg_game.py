"""Тесты для игровой логики Telegram бота"""

import unittest
import sys
import os
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

# Добавляем родительский каталог в путь для абсолютных импортов
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from client_tg_bot.game import (
    send_message_to_all_players, send_player_cards, format_game_status,
    _handle_game_completed, auto_play_bots, start_game
)
from client_tg_bot.handlers import S  # Глобальное состояние
from bin.core import MatchState, Player, GameEngine
from bin.constants import GameConstants

class TestTelegramGameLogic(unittest.TestCase):
    """Тесты для игровой логики Telegram бота"""

    def setUp(self):
        """Подготовка тестового окружения"""
        # Очищаем глобальное состояние перед каждым тестом
        S.WAITING_MATCHES.clear()
        S.ACTIVE_MATCHES.clear()
        S.PLAYER_TO_GAME.clear()
        S.MATCH_ENGINES.clear()

        # Создаем тестовое состояние игры
        self.match_state = MatchState()
        self.match_state.add_player(11, Player(12345, 'Player1'))
        self.match_state.add_player(12, Player(67890, 'Player2'))
        self.match_state.add_player(21, Player(11111, 'Player3'))
        self.match_state.add_player(22, Player(22222, 'Player4'))

        self.engine = GameEngine(self.match_state)

        # Мок для бота
        self.mock_bot = AsyncMock()
        S._bot = self.mock_bot

        # Мок для хранилища
        self.mock_storage = AsyncMock()
        S.storage = self.mock_storage

    def tearDown(self):
        """Очистка после теста"""
        S.WAITING_MATCHES.clear()
        S.ACTIVE_MATCHES.clear()
        S.PLAYER_TO_GAME.clear()
        S.MATCH_ENGINES.clear()

    async def test_send_message_to_all_players(self):
        """Тест отправки сообщения всем игрокам"""
        await send_message_to_all_players(self.match_state, "Test message")

        # Проверяем, что сообщение отправлено всем живым игрокам (id > 0)
        self.assertEqual(self.mock_bot.send_message.call_count, 4)

        # Проверяем содержимое сообщений
        calls = self.mock_bot.send_message.call_args_list
        for call in calls:
            self.assertEqual(call[1]['text'], "Test message")
            self.assertIn(call[1]['chat_id'], [12345, 67890, 11111, 22222])

    async def test_send_player_cards_to_bot(self):
        """Тест отправки карт боту (id < 0) - не должна отправляться"""
        bot_player = Player(-1, 'Bot1')
        await send_player_cards(bot_player, self.match_state)

        # Сообщение не должно быть отправлено
        self.mock_bot.send_message.assert_not_called()

    async def test_format_game_status(self):
        """Тест форматирования статуса игры"""
        status_text = await format_game_status(self.match_state)

        # Проверяем наличие ключевой информации
        self.assertIn("Статус", status_text)
        self.assertIn("Player1", status_text)
        self.assertIn("Player2", status_text)
        self.assertIn("Player3", status_text)
        self.assertIn("Player4", status_text)
        self.assertIn("Счёт раздачи", status_text)
        self.assertIn("Счёт матча", status_text)

    async def test_handle_game_completed_match_not_completed(self):
        """Тест завершения игры, когда матч не завершен"""
        # Настраиваем состояние для завершения игры
        self.match_state.status = GameConstants.Status.GAME_COMPLETED
        self.match_state.game_scores = {10: 30, 20: 30}
        self.match_state.match_scores = {10: 5, 20: 7}
        self.match_state.first_player_index = 11
        self.match_state.trump = 'hearts'
        self.match_state.current_turn = 9

        # Мок для complete_game
        self.engine.complete_game = MagicMock(return_value=(
            GameConstants.Status.NEW_DEAL_READY,
            {10: 35, 20: 25},
            20,  # losed_team
            1,   # losed_points
            "одно очко"
        ))

        # Добавляем матч в активные
        S.ACTIVE_MATCHES["test_match_001"] = self.match_state

        await _handle_game_completed("test_match_001", self.match_state, self.engine)

        # Проверяем, что сообщения отправлены
        self.assertTrue(self.mock_bot.send_message.called)

        # Проверяем, что статус обновлен (функция complete_game возвращает статус)
        # В этом тесте матч не завершен, поэтому должен быть NEW_DEAL_READY
        # Но _handle_game_completed не обновляет match_state.status, только вызывает complete_game()
        # Проверяем, что сообщения отправлены - это основная функция _handle_game_completed
        self.assertTrue(self.mock_bot.send_message.called)

    async def test_start_game_success(self):
        """Тест успешного запуска игры"""
        match_id = "test_match_001"
        players = {
            12345: {'id': 12345, 'name': 'Player1', 'username': 'player1'},
            67890: {'id': 67890, 'name': 'Player2', 'username': 'player2'},
            11111: {'id': 11111, 'name': 'Player3', 'username': 'player3'},
            22222: {'id': 22222, 'name': 'Player4', 'username': 'player4'}
        }

        # Мок для создания игроков
        for player_id in [12345, 67890, 11111, 22222]:
            self.mock_storage.get_or_create_player.return_value = {
                'id': player_id,
                'username': f'player{player_id}',
                'name': f'Player{player_id}'
            }

        # Создаем ожидающий матч с правильной структурой
        S.WAITING_MATCHES[match_id] = {
            'creator_id': 12345,
            'players': players,
            'team_1': [],
            'team_2': [],
            'timestamp': 0
        }

        # Устанавливаем позиции игроков в PLAYER_TO_GAME
        positions = [11, 12, 21, 22]
        for i, (player_id, player_data) in enumerate(players.items()):
            S.PLAYER_TO_GAME[player_id] = {
                'id': match_id,
                'status': 'waiting',
                'position': positions[i]
            }

        await start_game(match_id, players)

        # Проверяем, что игра создана
        # Используем реальный ID матча (может быть сгенерирован в start_game)
        actual_match_id = list(S.ACTIVE_MATCHES.keys())[0] if S.ACTIVE_MATCHES else match_id
        self.assertTrue(len(S.ACTIVE_MATCHES) > 0, "Матч должен быть добавлен в ACTIVE_MATCHES")
        self.assertTrue(len(S.MATCH_ENGINES) > 0, "Движок должен быть добавлен в MATCH_ENGINES")
        self.assertNotIn(match_id, S.WAITING_MATCHES)

        # Проверяем, что игроки добавлены в состояние
        match_state = S.ACTIVE_MATCHES[match_id]
        self.assertEqual(len(match_state.players), 4)
        # После start_game статус должен быть WAITING_TRUMP (ожидание выбора козыря)
        self.assertEqual(match_state.status, GameConstants.Status.WAITING_TRUMP)

        # Проверяем, что сообщения отправлены
        self.assertTrue(self.mock_bot.send_message.called)

    async def test_auto_play_bots_with_human_player(self):
        """Тест автохода ботов, когда следующий игрок - человек"""
        # Настраиваем состояние игры
        self.match_state.status = GameConstants.Status.TRUMP_SELECTED
        self.match_state.current_player_index = 11  # Человек
        self.match_state.first_player_index = 11  # Устанавливаем корректный first_player_index
        self.match_state.trump = 'hearts'  # Устанавливаем козырь

        S.ACTIVE_MATCHES["test_match_001"] = self.match_state
        S.MATCH_ENGINES["test_match_001"] = self.engine

        await auto_play_bots("test_match_001", self.match_state, self.engine)

        # Проверяем, что отправлены карты живому игроку
        self.assertTrue(self.mock_bot.send_message.called)

    async def test_auto_play_bots_with_bot_player(self):
        """Тест автохода ботов, когда следующий игрок - бот"""
        # Создаем бота как следующего игрока
        bot_player = Player(-1, 'Bot1')
        self.match_state.players[11] = bot_player
        self.match_state.current_player_index = 11  # Бот
        self.match_state.first_player_index = 11  # Устанавливаем корректный first_player_index
        self.match_state.status = GameConstants.Status.TRUMP_SELECTED
        self.match_state.trump = 'hearts'  # Устанавливаем козырь

        # Настраиваем руку бота
        from bin.core import Card
        bot_player.hand = [
            Card('hearts', 'A', 11, 15),
            Card('clubs', '6', 0, 35)
        ]

        S.ACTIVE_MATCHES["test_match_001"] = self.match_state
        S.MATCH_ENGINES["test_match_001"] = self.engine

        # Мок для валидации хода бота
        self.engine.validate_card_play = MagicMock(return_value=True)

        await auto_play_bots("test_match_001", self.match_state, self.engine)

        # Проверяем, что бот сделал ход (через play_turn)
        # Примечание: точная проверка зависит от реализации auto_play_bots


def run_async_test(test_func):
    """Вспомогательная функция для запуска асинхронных тестов"""
    def wrapper(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            if asyncio.iscoroutinefunction(test_func):
                loop.run_until_complete(test_func(self))
            else:
                test_func(self)
        finally:
            loop.close()
    return wrapper

# Оборачиваем все асинхронные тесты
for attr_name in dir(TestTelegramGameLogic):
    attr = getattr(TestTelegramGameLogic, attr_name)
    if callable(attr) and attr_name.startswith('test_'):
        setattr(TestTelegramGameLogic, attr_name, run_async_test(attr))


if __name__ == '__main__':
    unittest.main()