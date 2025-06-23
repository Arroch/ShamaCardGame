import unittest
from game_logic import Card, Player

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

if __name__ == "__main__":
    unittest.main()
