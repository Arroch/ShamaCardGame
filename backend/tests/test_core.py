import unittest
import sys
import os
import random

# Add parent directory to path to allow absolute imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core import Card, Player, MatchState, GameEngine

class TestCard(unittest.TestCase):
    def test_card_creation(self):
        card = Card('hearts', 'A', 11)
        self.assertEqual(card.suit, 'hearts')
        self.assertEqual(card.rank, 'A')
        self.assertEqual(card.value, 11)
        
    def test_card_repr(self):
        card = Card('diamonds', '10', 10)
        self.assertEqual(repr(card), '10♦')

class TestPlayer(unittest.TestCase):
    def setUp(self):
        self.player = Player(1, 'Test Player')
        
    def test_add_card(self):
        card = Card('spades', 'K', 4)
        self.player.add_card(card)
        self.assertEqual(len(self.player.hand), 1)
        self.assertEqual(self.player.hand[0], card)
        
    def test_play_card(self):
        card = Card('clubs', '6', 0)
        self.player.add_card(card)
        played = self.player.play_card(0)
        self.assertEqual(played, card)
        self.assertEqual(len(self.player.hand), 0)

class TestGameEngine(unittest.TestCase):
    def setUp(self):
        self.state = MatchState()
        self.state.add_player(11, Player(1, 'Player 1'))
        self.state.add_player(12, Player(2, 'Player 2'))
        self.state.add_player(21, Player(3, 'Player 3'))
        self.state.add_player(22, Player(4, 'Player 4'))
        self.engine = GameEngine(self.state)
        
    def test_create_deck(self):
        deck = self.engine.create_deck()
        self.assertEqual(len(deck), 36)
        self.assertTrue(all(isinstance(card, Card) for card in deck))
        
    def test_deal_cards(self):
        self.engine.deal_cards()
        for player in self.state.players.values():
            self.assertEqual(len(player.hand), 9)
            
    def test_start_game(self):
        self.engine.deal_cards()
        status, player = self.engine.start_game()
        self.assertIsNotNone(self.state.first_player_index)
        self.assertEqual(self.state.current_player_index, self.state.first_player_index)

    def test_full_game_cycle(self):
        """Тест полного цикла игры до достижения одной из команд 12 очков"""
        # Фиксируем seed для воспроизводимости
        random.seed(42)
        
        # Играем матчи, пока одна из команд не наберет 12 очков
        while max(self.state.match_scores.values()) < 12:
            # Начало игры
            self.engine.deal_cards()
            status, player = self.engine.start_game()
            # Установка козыря (предполагаем, что первый игрок имеет 6 треф и устанавливает козырь трефы)
            self.engine.set_trump_by_player(self.state.first_player_index, 'clubs')

            # Симуляция 9 взяток (каждая взятка состоит из 4 ходов)
            for trick in range(9):
                for turn in range(4):
                    current_player_index = self.state.current_player_index
                    try:
                        # Играем первую карту (индекс 0) из руки текущего игрока
                        self.engine.play_turn(current_player_index, 0)
                    except Exception as e:
                        self.fail(f"Ошибка при выполнении хода: {e}")

                # Завершаем взятку
                self.engine.complete_turn()

            # Завершаем игру (обновляем очки)
            self.engine.complete_game()
            # Завершаем матч (проверяем, есть ли команда с >=12 очками)
            self.engine.complete_match()

        # Проверяем состояние игры: status_code должен быть 700 (игра завершена)
        self.assertEqual(self.state.status_code, 700)
        # Проверяем, что одна из команд набрала 12 или более очков
        self.assertTrue(max(self.state.match_scores.values()) >= 12)

if __name__ == '__main__':
    unittest.main()
