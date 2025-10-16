import unittest
import sys
import os
import random
from unittest.mock import patch, MagicMock

# Добавляем родительский каталог в путь для абсолютных импортов
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core import Card, Player, MatchState, GameEngine, InvalidPlayerAction

class TestCard(unittest.TestCase):
    def test_card_creation(self):
        card = Card('hearts', 'A', 11)
        self.assertEqual(card.suit, 'hearts')
        self.assertEqual(card.rank, 'A')
        self.assertEqual(card.value, 11)
        
    def test_card_repr(self):
        card = Card('diamonds', '10', 10)
        self.assertEqual(repr(card), '10♦')
        
    def test_card_symbols(self):
        """Проверка корректного отображения символов мастей"""
        self.assertEqual(Card.SUIT_SYMBOLS['hearts'], '♥')
        self.assertEqual(Card.SUIT_SYMBOLS['diamonds'], '♦')
        self.assertEqual(Card.SUIT_SYMBOLS['clubs'], '♣')
        self.assertEqual(Card.SUIT_SYMBOLS['spades'], '♠')

class TestPlayer(unittest.TestCase):
    def setUp(self):
        self.player = Player(1, 'Test Player')
        
    def test_player_creation(self):
        """Проверка создания игрока с корректными атрибутами"""
        self.assertEqual(self.player.id, 1)
        self.assertEqual(self.player.name, 'Test Player')
        self.assertEqual(self.player.hand, [])
        
    def test_add_card(self):
        """Тест добавления карты в руку игрока"""
        card = Card('spades', 'K', 4)
        self.player.add_card(card)
        self.assertEqual(len(self.player.hand), 1)
        self.assertEqual(self.player.hand[0], card)
        
    def test_play_card(self):
        """Тест розыгрыша карты из руки игрока"""
        card = Card('clubs', '6', 0)
        self.player.add_card(card)
        played = self.player.play_card(0)
        self.assertEqual(played, card)
        self.assertEqual(len(self.player.hand), 0)
    
    def test_get_hand(self):
        """Тест получения списка карт в руке игрока"""
        card1 = Card('hearts', '9', 0)
        card2 = Card('diamonds', 'Q', 3)
        self.player.add_card(card1)
        self.player.add_card(card2)
        hand = self.player.get_hand()
        self.assertEqual(len(hand), 2)
        self.assertEqual(hand[0], card1)
        self.assertEqual(hand[1], card2)
        
    def test_clear_hand(self):
        """Тест очистки руки игрока"""
        self.player.add_card(Card('hearts', '9', 0))
        self.player.add_card(Card('diamonds', 'Q', 3))
        self.assertEqual(len(self.player.hand), 2)
        self.player.clear_hand()
        self.assertEqual(len(self.player.hand), 0)
        
    def test_player_repr(self):
        """Тест строкового представления игрока"""
        self.assertEqual(repr(self.player), 'Test Player')

class TestMatchState(unittest.TestCase):
    def setUp(self):
        self.state = MatchState()
        
    def test_match_state_init(self):
        """Тест инициализации состояния матча"""
        self.assertEqual(self.state.status_code, 100)
        self.assertEqual(self.state.match_scores, {10: 0, 20: 0})
        self.assertEqual(self.state.game_scores, {10: 0, 20: 0})
        self.assertEqual(self.state.first_player_index, 0)
        self.assertIsNone(self.state.trump)
        
    def test_set_status_code(self):
        """Тест установки кода состояния"""
        self.state.set_status_code(200)
        self.assertEqual(self.state.status_code, 200)
        
    def test_set_current_player_index(self):
        """Тест установки индекса текущего игрока"""
        self.state.set_current_player_index(11)
        self.assertEqual(self.state.current_player_index, 11)
        
    def test_set_current_turn(self):
        """Тест установки номера текущего хода"""
        # Тест с указанием номера хода
        self.state.set_current_turn(5)
        self.assertEqual(self.state.current_turn, 5)
        
        # Тест инкремента номера хода
        self.state.set_current_turn()
        self.assertEqual(self.state.current_turn, 6)
        
    def test_set_trump(self):
        """Тест установки козыря"""
        self.state.set_trump('hearts')
        self.assertEqual(self.state.trump, 'hearts')
        self.assertEqual(self.state.status_code, 203)
        
    def test_add_player(self):
        """Тест добавления игрока"""
        player = Player(1, 'Test Player')
        status = self.state.add_player(11, player)
        self.assertEqual(status, 101)
        self.assertEqual(self.state.players[11], player)
        
    def test_add_player_when_full(self):
        """Тест добавления игрока, когда стол заполнен"""
        # Добавляем 4 игрока
        self.state.add_player(11, Player(1, 'Player 1'))
        self.state.add_player(12, Player(2, 'Player 2'))
        self.state.add_player(21, Player(3, 'Player 3'))
        self.state.add_player(22, Player(4, 'Player 4'))
        
        # Пытаемся добавить еще одного игрока
        with self.assertRaises(InvalidPlayerAction):
            self.state.add_player(30, Player(5, 'Player 5'))
            
    def test_put_card(self):
        """Тест выкладывания карты на стол"""
        player = Player(1, 'Test Player')
        self.state.add_player(11, player)
        card = Card('hearts', 'A', 11)
        self.state.put_card(11, card)
        self.assertEqual(len(self.state.current_table), 1)
        self.assertEqual(self.state.current_table[0]['player_index'], 11)
        self.assertEqual(self.state.current_table[0]['player'], player)
        self.assertEqual(self.state.current_table[0]['card'], card)
        
    def test_clear_table(self):
        """Тест очистки стола"""
        player = Player(1, 'Test Player')
        self.state.add_player(11, player)
        card = Card('hearts', 'A', 11)
        self.state.put_card(11, card)
        self.assertEqual(len(self.state.current_table), 1)
        self.state.clear_table()
        self.assertEqual(len(self.state.current_table), 0)
        
    def test_increase_score_match(self):
        """Тест увеличения счета матча"""
        self.state.increase_score(10, 5, 'match')
        self.assertEqual(self.state.match_scores[10], 5)
        
    def test_increase_score_game(self):
        """Тест увеличения счета игры"""
        self.state.increase_score(20, 10, 'game')
        self.assertEqual(self.state.game_scores[20], 10)
        
    def test_increase_score_invalid_type(self):
        """Тест увеличения счета с неверным типом"""
        with self.assertRaises(ValueError):
            self.state.increase_score(10, 5, 'invalid')
            
    def test_clear_score_match(self):
        """Тест очистки счета матча"""
        self.state.increase_score(10, 5, 'match')
        self.state.increase_score(20, 7, 'match')
        self.state.clear_score('match')
        self.assertEqual(self.state.match_scores[10], 0)
        self.assertEqual(self.state.match_scores[20], 0)
        
    def test_clear_score_game(self):
        """Тест очистки счета игры"""
        self.state.increase_score(10, 5, 'game')
        self.state.increase_score(20, 7, 'game')
        self.state.clear_score('game')
        self.assertEqual(self.state.game_scores[10], 0)
        self.assertEqual(self.state.game_scores[20], 0)
        
    def test_clear_score_invalid_type(self):
        """Тест очистки счета с неверным типом"""
        with self.assertRaises(ValueError):
            self.state.clear_score('invalid')

class TestGameEngine(unittest.TestCase):
    def setUp(self):
        self.state = MatchState()
        self.state.add_player(11, Player(1, 'Player 1'))
        self.state.add_player(12, Player(2, 'Player 2'))
        self.state.add_player(21, Player(3, 'Player 3'))
        self.state.add_player(22, Player(4, 'Player 4'))
        self.engine = GameEngine(self.state)
        
    def test_create_deck(self):
        """Тест создания колоды"""
        deck = self.engine.create_deck()
        self.assertEqual(len(deck), 36)
        self.assertTrue(all(isinstance(card, Card) for card in deck))
        
        # Проверяем, что все комбинации масть/ранг присутствуют
        suits = ['hearts', 'diamonds', 'clubs', 'spades']
        ranks = ['6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
        for suit in suits:
            for rank in ranks:
                self.assertTrue(any(card.suit == suit and card.rank == rank for card in deck))
                
    def test_deal_cards(self):
        """Тест раздачи карт"""
        self.engine.deal_cards()
        # Проверяем, что у каждого игрока по 9 карт
        for player in self.state.players.values():
            self.assertEqual(len(player.hand), 9)
            
    @patch('random.shuffle')
    def test_deal_cards_shama(self, mock_shuffle):
        """Тест раздачи карт с шамой (6 крести)"""
        # Мокаем shuffle, чтобы шама попала первому игроку
        def side_effect(deck):
            shama = None
            for card in deck:
                if card.rank == '6' and card.suit == 'clubs':
                    shama = card
                    break
            if shama:
                deck.remove(shama)
                deck.insert(0, shama)
            
        mock_shuffle.side_effect = side_effect
        
        self.engine.deal_cards()
        # Проверяем, что first_player_index указывает на игрока с шамой
        self.assertEqual(self.state.first_player_index, 11)
        # Проверяем, что у игрока действительно есть шама
        has_shama = False
        for card in self.state.players[11].hand:
            if card.rank == '6' and card.suit == 'clubs':
                has_shama = True
                break
        self.assertTrue(has_shama)
            
    def test_start_game(self):
        """Тест начала игры"""
        # Подготовим состояние, чтобы шама была у определенного игрока
        self.state.first_player_index = 11
        status, player = self.engine.start_game()
        
        self.assertEqual(status, 202)
        self.assertEqual(player, self.state.players[11])
        self.assertEqual(self.state.current_player_index, 11)
        
    def test_start_game_no_shama(self):
        """Тест начала игры без шамы"""
        # Подготовим состояние без шамы
        self.state.first_player_index = 0
        
        with patch.object(self.engine, 'deal_cards'):
            with self.assertRaises(ValueError):
                self.engine.start_game()
                
    def test_set_trump_by_player(self):
        """Тест установки козыря игроком"""
        # Подготовим состояние
        self.state.first_player_index = 11
        self.state.current_player_index = 11
        self.state.status_code = 202
        
        status, player_name, trump = self.engine.set_trump_by_player(11, 'hearts')
        
        self.assertEqual(status, 203)
        self.assertEqual(player_name, self.state.players[11].name)
        self.assertEqual(trump, 'hearts')
        
    def test_set_trump_by_wrong_player(self):
        """Тест установки козыря не тем игроком"""
        # Подготовим состояние
        self.state.first_player_index = 11
        
        with self.assertRaises(InvalidPlayerAction):
            self.engine.set_trump_by_player(12, 'hearts')
            
    def test_set_trump_invalid_suit(self):
        """Тест установки некорректной масти в качестве козыря"""
        # Подготовим состояние
        self.state.first_player_index = 11
        
        with self.assertRaises(InvalidPlayerAction):
            self.engine.set_trump_by_player(11, 'invalid')
            
    def test_play_turn(self):
        """Тест хода игрока"""
        # Подготовим состояние
        self.state.status_code = 203
        self.state.current_player_index = 11
        self.state.trump = 'hearts'
        
        # Добавим карту игроку
        card = Card('hearts', 'A', 11)
        self.state.players[11].add_card(card)
        
        status, player, played_card = self.engine.play_turn(11, 0)
        
        self.assertEqual(status, 301)  # 300 + 1 (одна карта на столе)
        self.assertEqual(player, self.state.players[11])
        self.assertEqual(played_card, card)
        self.assertEqual(self.state.current_player_index, 21)  # Следующий игрок
        
    def test_play_turn_wrong_player(self):
        """Тест хода не тем игроком"""
        # Подготовим состояние
        self.state.status_code = 203
        self.state.current_player_index = 11
        
        with self.assertRaises(InvalidPlayerAction):
            self.engine.play_turn(12, 0)
            
    def test_play_turn_no_cards(self):
        """Тест хода, когда у игрока нет карт"""
        # Подготовим состояние
        self.state.status_code = 203
        self.state.current_player_index = 11
        
        with self.assertRaises(InvalidPlayerAction):
            self.engine.play_turn(11, 0)
            
    def test_play_turn_too_many_turns(self):
        """Тест хода, когда уже сделано 9 ходов"""
        # Подготовим состояние
        self.state.status_code = 203
        self.state.current_player_index = 11
        self.state.current_turn = 10
        
        # Добавим карту игроку
        self.state.players[11].add_card(Card('hearts', 'A', 11))
        
        with self.assertRaises(InvalidPlayerAction):
            self.engine.play_turn(11, 0)
            
    def test_play_turn_table_full(self):
        """Тест хода, когда на столе уже 4 карты"""
        # Подготовим состояние
        self.state.status_code = 203
        self.state.current_player_index = 11
        
        # Заполним стол
        for _ in range(4):
            self.state.current_table.append({})
            
        # Добавим карту игроку
        self.state.players[11].add_card(Card('hearts', 'A', 11))
        
        with self.assertRaises(InvalidPlayerAction):
            self.engine.play_turn(11, 0)

    @patch('builtins.print')
    def test_complete_turn(self, mock_print):
        """Тест завершения кона"""
        # Подготовим состояние
        self.state.status_code = 304  # 4 карты на столе
        self.state.trump = 'hearts'
        
        # Добавим карты на стол
        self.state.put_card(11, Card('spades', '9', 0))
        self.state.put_card(21, Card('spades', 'K', 4))
        self.state.put_card(12, Card('hearts', '7', 0))  # Козырь, сильнее всех
        self.state.put_card(22, Card('spades', 'Q', 3))
        
        status, winning_card, winning_player_index, trick_points = self.engine.complete_turn()
        
        self.assertEqual(status, 300)  # Готов к новому кону
        self.assertEqual(winning_card.suit, 'hearts')  # Козырь победил
        self.assertEqual(winning_card.rank, '7')
        self.assertEqual(winning_player_index, 12)
        self.assertEqual(trick_points, 7)  # 0 + 4 + 0 + 3
        self.assertEqual(self.state.game_scores[10], 7)  # Очки команде
        self.assertEqual(self.state.current_player_index, 12)  # Следующий ход начнет победитель
        
    def test_complete_turn_table_not_full(self):
        """Тест завершения кона, когда на столе меньше 4 карт"""
        # Подготовим состояние
        self.state.status_code = 303  # 3 карты на столе
        
        with self.assertRaises(IndexError):
            self.engine.complete_turn()
            
    def test_complete_game(self):
        """Тест завершения игры"""
        # Подготовим состояние
        self.state.current_turn = 10  # Все 9 ходов сделаны
        self.state.first_player_index = 11  # Шама у игрока 11
        self.state.game_scores = {10: 20, 20: 30}  # Команда 10 проиграла с меньшим счетом
        
        status, scores, losed_team, losed_points = self.engine.complete_game()
        
        self.assertEqual(status, 500)  # Готов к новой раздаче
        self.assertEqual(scores, {10: 20, 20: 30})
        self.assertEqual(losed_team, 10)  # Проигравшая команда
        self.assertEqual(losed_points, 6)  # Очки за проигрыш (меньше 30 очков, с шамой)
        self.assertEqual(self.state.match_scores[10], 6)  # Очки добавлены
        self.assertEqual(self.state.game_scores[10], 0)  # Счет игры обнулен
        self.assertEqual(self.state.game_scores[20], 0)
        
    def test_complete_match(self):
        """Тест завершения матча"""
        status = self.engine.complete_match()
        self.assertEqual(status, 700)
        self.assertEqual(self.state.status_code, 700)
        
    def test_full_game_cycle(self):
        """Тест полного цикла игры до достижения одной из команд 12 очков"""
        # Фиксируем seed для воспроизводимости
        random.seed(42)
        
        # Играем матчи, пока одна из команд не наберет 12 очков
        while max(self.state.match_scores.values()) < 12:
            # Начало игры
            self.engine.deal_cards()
            status, player = self.engine.start_game()
            # Установка козыря
            self.engine.set_trump_by_player(self.state.first_player_index, 'clubs')

            # Симуляция 9 взяток (каждая взятка состоит из 4 ходов)
            for trick in range(9):
                for turn in range(4):
                    current_player_index = self.state.current_player_index
                    try:
                        # Играем первую карту из руки текущего игрока
                        self.engine.play_turn(current_player_index, 0)
                    except Exception as e:
                        self.fail(f"Ошибка при выполнении хода: {e}")

                # Завершаем взятку
                self.engine.complete_turn()

            # Завершаем игру (обновляем очки)
            self.engine.complete_game()
            # Завершаем матч (проверяем, есть ли команда с >=12 очками)
            if max(self.state.match_scores.values()) >= 12:
                self.engine.complete_match()

        # Проверяем состояние игры: status_code должен быть 700 (игра завершена)
        self.assertEqual(self.state.status_code, 700)
        # Проверяем, что одна из команд набрала 12 или более очков
        self.assertTrue(max(self.state.match_scores.values()) >= 12)

if __name__ == '__main__':
    unittest.main()
