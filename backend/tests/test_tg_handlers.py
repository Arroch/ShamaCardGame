"""Тесты для обработчиков Telegram бота"""

import unittest
import sys
import os
from unittest.mock import AsyncMock, MagicMock, patch

# Добавляем родительский каталог в путь для абсолютных импортов
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from client_tg_bot.handlers import (
    start_command, create_game_command,
    help_command, ping_command, status_command, stats_command,
    fill_bots_command, callback_handler
)
# Закомментируем leave_game_command, так как она еще не в проде
# from client_tg_bot.handlers import leave_game_command
from client_tg_bot.handlers import S  # Глобальное состояние
from bin.constants import GameConstants

class TestTelegramHandlers(unittest.TestCase):
    """Тесты для обработчиков команд Telegram бота"""

    def setUp(self):
        """Подготовка тестового окружения"""
        # Очищаем глобальное состояние перед каждым тестом
        S.WAITING_MATCHES.clear()
        S.ACTIVE_MATCHES.clear()
        S.PLAYER_TO_GAME.clear()
        S.MATCH_ENGINES.clear()

        # Создаем моки для Telegram объектов
        self.mock_update = MagicMock()
        self.mock_context = MagicMock()
        self.mock_user = MagicMock()
        self.mock_message = AsyncMock()

        # Настраиваем моки
        self.mock_user.id = 12345
        self.mock_user.first_name = "TestUser"
        self.mock_user.username = "testuser"
        self.mock_update.effective_user = self.mock_user
        self.mock_update.message = self.mock_message
        self.mock_context.bot = AsyncMock()
        self.mock_context.bot.get_me = AsyncMock(return_value=MagicMock(username="TestBot"))

        # Мок для хранилища
        self.mock_storage = AsyncMock()
        S.storage = self.mock_storage

    def tearDown(self):
        """Очистка после теста"""
        S.WAITING_MATCHES.clear()
        S.ACTIVE_MATCHES.clear()
        S.PLAYER_TO_GAME.clear()
        S.MATCH_ENGINES.clear()

    async def test_ping_command(self):
        """Тест команды /ping"""
        await ping_command(self.mock_update, self.mock_context)
        self.mock_message.reply_text.assert_called_once_with("Понг! Бот работает.")

    async def test_help_command(self):
        """Тест команды /help"""
        await help_command(self.mock_update, self.mock_context)
        # Проверяем, что сообщение отправлено
        self.mock_message.reply_text.assert_called_once()
        help_text = self.mock_message.reply_text.call_args[0][0]
        # Проверяем наличие ключевых команд
        self.assertIn("/start", help_text)
        self.assertIn("/help", help_text)
        self.assertIn("/ping", help_text)
        self.assertIn("/create_game", help_text)
        # Закомментируем проверку /leave_game, так как она еще не в проде
        # self.assertIn("/leave_game", help_text)
        self.assertIn("/fill_bots", help_text)

    async def test_create_game_command_new_game(self):
        """Тест создания новой игры командой /create_game"""
        # Игрок не в игре
        S.PLAYER_TO_GAME.clear()

        # Мок для создания игрока
        self.mock_storage.get_or_create_player.return_value = {
            'id': 12345,
            'username': 'testuser',
            'name': 'TestUser'
        }

        await create_game_command(self.mock_update, self.mock_context)

        # Проверяем, что игра создана
        self.assertEqual(len(S.WAITING_MATCHES), 1)
        self.assertEqual(len(S.PLAYER_TO_GAME), 1)
        self.assertIn(12345, S.PLAYER_TO_GAME)

        # Проверяем, что сообщение отправлено
        self.mock_message.reply_text.assert_called_once()
        reply_text = self.mock_message.reply_text.call_args[0][0]
        self.assertIn("создал(а) новую игру", reply_text)
        # Закомментируем проверку /leave_game в сообщении, так как она еще не в проде
        # self.assertIn("/leave_game", reply_text)

    async def test_create_game_command_already_in_game(self):
        """Тест создания игры, когда игрок уже в игре"""
        # Игрок уже в игре
        S.PLAYER_TO_GAME[12345] = {
            'id': 'test_match_001',
            'status': 'waiting',
            'position': 11
        }
        S.WAITING_MATCHES['test_match_001'] = {
            'creator_id': 12345,
            'players': {12345: {'id': 12345, 'name': 'TestUser', 'username': 'testuser'}},
            'team_1': ['TestUser (testuser)'],
            'team_2': [],
            'timestamp': 0
        }

        await create_game_command(self.mock_update, self.mock_context)

        # Проверяем сообщение об ошибке
        self.mock_message.reply_text.assert_called()
        reply_text = self.mock_message.reply_text.call_args_list[0][0][0]
        self.assertIn("Вы уже состоите в игре", reply_text)

    # Закомментируем тест leave_game, так как команда еще не в проде
    # async def test_leave_game_command_not_in_game(self):
    #     """Тест выхода из игры, когда игрок не в игре"""
    #     # Игрок не в игре
    #     S.PLAYER_TO_GAME.clear()
    #
    #     await leave_game_command(self.mock_update, self.mock_context)
    #
    #     # Проверяем сообщение об ошибке
    #     self.mock_message.reply_text.assert_called_once_with("Вы не состоите в ожидающей игре.")

    async def test_fill_bots_command_not_in_game(self):
        """Тест команды /fill_bots, когда игрок не в игре"""
        # Игрок не в игре
        S.PLAYER_TO_GAME.clear()

        await fill_bots_command(self.mock_update, self.mock_context)

        # Проверяем сообщение об ошибке
        self.mock_message.reply_text.assert_called_once_with("Вы не состоите в ожидающей игре.")

    async def test_fill_bots_command_success(self):
        """Тест успешного заполнения игры ботами"""
        # Создаем тестовую игру с одним игроком
        match_id = "test_match_001"
        S.WAITING_MATCHES[match_id] = {
            'creator_id': 12345,
            'players': {12345: {'id': 12345, 'name': 'TestUser', 'username': 'testuser'}},
            'team_1': ['TestUser (testuser)'],
            'team_2': [],
            'timestamp': 0
        }
        S.PLAYER_TO_GAME[12345] = {
            'id': match_id,
            'status': 'waiting',
            'position': 11
        }

        await fill_bots_command(self.mock_update, self.mock_context)

        # Проверяем, что добавлены боты
        # После fill_bots игра может автоматически начаться, проверяем общее количество игроков
        total_players = 0
        for match_id in S.WAITING_MATCHES:
            total_players += len(S.WAITING_MATCHES[match_id]['players'])
        for match_id in S.ACTIVE_MATCHES:
            total_players += len(S.ACTIVE_MATCHES[match_id].players)

        self.assertEqual(total_players, 4)
        self.assertEqual(len(S.PLAYER_TO_GAME), 4)

        # Проверяем сообщение
        self.mock_message.reply_text.assert_called_once()
        reply_text = self.mock_message.reply_text.call_args[0][0]
        self.assertIn("Добавлено ботов", reply_text)
        self.assertIn("Участников: 4/4", reply_text)

    async def test_status_command_not_in_game(self):
        """Тест команды /status, когда игрок не в игре"""
        # Игрок не в игре
        S.PLAYER_TO_GAME.clear()

        await status_command(self.mock_update, self.mock_context)

        # Проверяем сообщение
        self.mock_message.reply_text.assert_called_once_with(
            "Вы не состоите в игре.\n"
            "/create_game — создать, инвайт-ссылка — присоединиться."
        )

    async def test_stats_command_success(self):
        """Тест команды /stats с данными"""
        # Мок для статистики игрока
        player_stats = {
            'name': 'TestUser',
            'games': 5,
            'wins': 3,
            'win_rate': 60,
            'total_tricks': 25,
            'total_shama_calls': 2
        }
        self.mock_storage.get_player_stats.return_value = player_stats

        await stats_command(self.mock_update, self.mock_context)

        # Проверяем сообщение
        self.mock_message.reply_text.assert_called_once()
        reply_text = self.mock_message.reply_text.call_args[0][0]
        self.assertIn("Статистика TestUser", reply_text)
        self.assertIn("Игр: 5", reply_text)
        self.assertIn("Побед: 3", reply_text)
        self.assertIn("Процент побед: 60%", reply_text)

    async def test_stats_command_no_stats(self):
        """Тест команды /stats без данных"""
        # Мок для отсутствия статистики
        self.mock_storage.get_player_stats.return_value = None

        await stats_command(self.mock_update, self.mock_context)

        # Проверяем сообщение
        self.mock_message.reply_text.assert_called_once_with(
            "Статистики нет. Сыграйте несколько партий!"
        )


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
import asyncio
for attr_name in dir(TestTelegramHandlers):
    attr = getattr(TestTelegramHandlers, attr_name)
    if callable(attr) and attr_name.startswith('test_'):
        setattr(TestTelegramHandlers, attr_name, run_async_test(attr))


if __name__ == '__main__':
    unittest.main()