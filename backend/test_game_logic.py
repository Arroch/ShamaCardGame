import unittest
from game_logic import Card, Player, GameEngine

class TestCard(unittest.TestCase):
    def test_card_representation(self):
        card = Card('hearts', 'A', 11)
        self.assertEqual(repr(card), "A♥")
        
    def test_card_values(self):
        card = Card('spades', '10', 10)
        self.assertEqual(card.suit, 'spades')
        self.assertEqual(card.rank, '10')
        self.assertEqual(card.value, 10)

class TestPlayer(unittest.TestCase):
    def test_player_hand(self):
        player = Player(1, 1)
        card = Card('diamonds', 'K', 4)
        player.add_card(card)
        self.assertEqual(len(player.hand), 1)
        played = player.play_card(0)
        self.assertEqual(repr(played), "K♦")
        self.assertEqual(len(player.hand), 0)

class TestGameEngine(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine()
        self.players = [
            Player(1, 1),
            Player(2, 2),
            Player(3, 1),
            Player(4, 2)
        ]
        for player in self.players:
            self.engine.state.add_player(player)
    
    def test_find_six_of_clubs(self):
        """Тест определения игрока с шестеркой треф"""
        # Создаем полную колоду
        full_deck = self.engine.create_deck()
        
        # Находим шестерку треф и перемещаем ее в начало
        six_clubs = None
        for i, card in enumerate(full_deck):
            if card.suit == 'clubs' and card.rank == '6':
                six_clubs = card
                full_deck.insert(0, full_deck.pop(i))
                break
        
        if not six_clubs:
            self.fail("Шестерка треф не найдена в колоде")
        
        self.engine.deck = full_deck
        
        # Раздаем карты
        self.engine.deal_cards()
        
        # Проверяем, что игрок 1 получил шестерку треф
        self.assertEqual(self.engine.first_player_id, 1)
        self.assertIn(six_clubs, self.players[0].hand)
    
    def test_set_trump(self):
        """Тест установки козыря"""
        self.engine.first_player_id = 1
        self.engine.set_trump_by_player(1, 'hearts')
        self.assertEqual(self.engine.state.trump, 'hearts')
        
        # Проверяем ошибку при неверном игроке
        with self.assertRaises(ValueError):
            self.engine.set_trump_by_player(2, 'spades')
        
        # Проверяем ошибку при неверной масти
        with self.assertRaises(ValueError):
            self.engine.set_trump_by_player(1, 'invalid')

if __name__ == "__main__":
    unittest.main()
