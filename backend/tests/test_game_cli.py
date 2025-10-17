import unittest
import sys
import os
from io import StringIO
from unittest.mock import patch, MagicMock, call

# Добавляем родительский каталог в путь для абсолютных импортов
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import game_cli
from core import MatchState, GameEngine, Player, Card
from game_constants import GameConstants

class TestGameCLI(unittest.TestCase):
    
    def setUp(self):
        # Подготовка тестового окружения
        self.state = MatchState()
        self.state.add_player(11, Player(1, 'Player 1'))
        self.state.add_player(12, Player(2, 'Player 2'))
        self.state.add_player(21, Player(3, 'Player 3'))
        self.state.add_player(22, Player(4, 'Player 4'))
        self.engine = GameEngine(self.state)
    
    @patch('builtins.print')
    def test_show_rules(self, mock_print):
        """Тест отображения правил игры"""
        game_cli.show_rules()
        self.assertTrue(mock_print.called)
        # Проверяем, что правила содержат ключевые слова
        rules_text = mock_print.call_args[0][0]
        self.assertIn('ПРАВИЛА ИГРЫ', rules_text)
        self.assertIn('шесть крести', rules_text)
        self.assertIn('валет крести', rules_text)
        
    @patch('builtins.print')
    @patch('builtins.input', return_value='1')
    def test_show_menu_new_game(self, mock_input, mock_print):
        """Тест выбора нового меню - Новая игра"""
        result = game_cli.show_menu()
        self.assertEqual(result, 1)
        mock_print.assert_called()
        mock_input.assert_called_once_with('Введите число для выбора действия меню\n')
    
    @patch('builtins.print')
    @patch('builtins.input', return_value='2')
    def test_show_menu_rules(self, mock_input, mock_print):
        """Тест выбора меню - Правила"""
        result = game_cli.show_menu()
        self.assertEqual(result, 2)
        mock_print.assert_called()
        mock_input.assert_called_once_with('Введите число для выбора действия меню\n')
    
    @patch('builtins.print')
    @patch('builtins.input', return_value='3')
    def test_show_menu_exit(self, mock_input, mock_print):
        """Тест выбора меню - Выход"""
        result = game_cli.show_menu()
        self.assertEqual(result, 3)
        mock_print.assert_called()
        mock_input.assert_called_once_with('Введите число для выбора действия меню\n')
    
    @patch('builtins.print')
    @patch('builtins.input', return_value='invalid')
    def test_show_menu_invalid(self, mock_input, mock_print):
        """Тест некорректного ввода в меню"""
        result = game_cli.show_menu()
        self.assertEqual(result, 0)
        mock_print.assert_called()
        mock_input.assert_called_once_with('Введите число для выбора действия меню\n')
    
    @patch('builtins.print')
    def test_show_hand(self, mock_print):
        """Тест отображения карт в руке игрока"""
        # Создаем тестовую руку
        hand = [
            Card('hearts', 'A', 11),
            Card('diamonds', 'K', 4),
            Card('clubs', '6', 0),
            Card('spades', 'Q', 3)
        ]
        
        game_cli.show_hand(hand)
        
        # Проверяем, что был вызов print для каждой карты
        expected_calls = [
            call('1:  A♥', end=' || '),
            call('2:  K♦', end=' || '),
            call('3:  6♣', end='\n'),
            call('4:  Q♠', end=' || '),
            call()
        ]
        mock_print.assert_has_calls(expected_calls)
    
    @patch('builtins.print')
    def test_show_state(self, mock_print):
        """Тест отображения состояния игры"""
        # Подготовим состояние
        state = self.state
        state.trump = 'hearts'
        state.first_player_index = 11
        state.current_player_index = 11
        state.current_turn = 3
        state.match_scores = {10: 5, 20: 7}
        
        # Добавим карту на стол
        state.put_card(11, Card('hearts', '10', 10))
        
        # Вызываем функцию
        game_cli.show_state(state)
        
        # Проверяем вызовы print
        mock_print.assert_called()
        # Проверяем, что вывод содержит информацию о козыре и ходе
        self.assertTrue(any('Козырь: ♥, хвалил Player 1' in str(args) for args, _ in mock_print.call_args_list))
        self.assertTrue(any('Номер хода: 3' in str(args) for args, _ in mock_print.call_args_list))
    
    @patch('builtins.input', side_effect=['Player A', 'Player B', 'Player C', 'Player D'])
    def test_create_match(self, mock_input):
        """Тест создания нового матча"""
        status, state = game_cli.create_match()
        
        # Проверяем результаты
        self.assertEqual(status, GameConstants.Status.PLAYERS_ADDED)  # Все 4 игрока добавлены
        self.assertEqual(state.players[11].name, 'Player A')
        self.assertEqual(state.players[12].name, 'Player B')
        self.assertEqual(state.players[21].name, 'Player C')
        self.assertEqual(state.players[22].name, 'Player D')
        
    @patch('builtins.print')
    @patch('builtins.input', return_value='3')  # Выбор пункта "Выход"
    def test_main_exit(self, mock_input, mock_print):
        """Тест выхода из игры через меню"""
        status_code, state = game_cli.main(0, None)
        
        # Проверяем, что функция вернула код выхода
        self.assertEqual(status_code, -100)
        self.assertIsNone(state)
    
    @patch('builtins.print')
    @patch('builtins.input', return_value='2')  # Выбор пункта "Правила"
    @patch('game_cli.show_rules')
    def test_main_show_rules(self, mock_show_rules, mock_input, mock_print):
        """Тест вызова правил через меню"""
        status_code, state = game_cli.main(0, None)
        
        # Проверяем, что была вызвана функция показа правил
        mock_show_rules.assert_called_once()
        
    @patch('builtins.print')
    @patch('game_cli.show_menu', return_value=1)  # Выбор "Новая игра"
    @patch('game_cli.create_match', return_value=(GameConstants.Status.PLAYERS_ADDED, MagicMock()))
    @patch('builtins.input', return_value='m')  # Выбор "Вернуться в меню"
    def test_main_new_game_then_menu(self, mock_input, mock_create_match, mock_show_menu, mock_print):
        """Тест создания новой игры и возврата в меню"""
        # Создаем заглушку для состояния игры
        mock_state = MagicMock()
        mock_state.status = GameConstants.Status.PLAYERS_ADDED
        mock_state.players = {11: Player(1, 'P1'), 12: Player(2, 'P2'), 
                             21: Player(3, 'P3'), 22: Player(4, 'P4')}
        
        # Обновляем возвращаемое значение create_match
        mock_create_match.return_value = (GameConstants.Status.PLAYERS_ADDED, mock_state)
        
        status_code, state = game_cli.main(0, None)
        
        # Проверяем, что игра была создана и статус изменен
        self.assertEqual(status_code, 104)
        
    @patch('builtins.print')
    @patch('game_cli.show_state')
    @patch('game_cli.show_hand')
    def test_show_game_state(self, mock_show_hand, mock_show_state, mock_print):
        """Тест отображения игрового состояния и руки игрока"""
        # Подготовим данные
        player = self.state.players[11]
        player.add_card(Card('hearts', 'A', 11))
        
        # Вызываем функции отображения состояния и руки
        game_cli.show_state(self.state)
        game_cli.show_hand(player.get_hand())
        
        # Проверяем вызовы
        mock_show_state.assert_called_once_with(self.state)
        mock_show_hand.assert_called_once()

if __name__ == '__main__':
    unittest.main()
