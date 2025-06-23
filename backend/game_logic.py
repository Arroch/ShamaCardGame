class Card:
    # Маппинг мастей на символы
    SUIT_SYMBOLS = {
        'hearts': '♥',
        'diamonds': '♦',
        'clubs': '♣',
        'spades': '♠'
    }
    
    def __init__(self, suit: str, rank: str, value: int):
        """
        Инициализация карты.
        
        :param suit: масть ('hearts', 'diamonds', 'clubs', 'spades')
        :param rank: достоинство ('6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A')
        :param value: стоимость карты в очках
        """
        self.suit = suit
        self.rank = rank
        self.value = value
        
    def __repr__(self):
        """Строковое представление карты с символами мастей"""
        symbol = Card.SUIT_SYMBOLS.get(self.suit, '?')
        return f"{self.rank}{symbol}"

class Player:
    def __init__(self, player_id: int, team: int):
        """
        Инициализация игрока.
        
        :param player_id: уникальный ID игрока
        :param team: номер команды (1 или 2)
        """
        self.id = player_id
        self.team = team
        self.hand = []  # Карты на руках
        
    def add_card(self, card: Card):
        """Добавление карты в руку игрока"""
        self.hand.append(card)
        
    def play_card(self, card_index: int) -> Card:
        """Сыграть карту по индексу"""
        return self.hand.pop(card_index)
    
    def __repr__(self):
        """Строковое представление игрока"""
        return f"Player {self.id} (Team {self.team})"

class GameState:
    def __init__(self):
        """Инициализация состояния игры"""
        self.players = []  # Список игроков
        self.trump = None  # Текущий козырь
        self.current_trick = []  # Текущий кон (карты на столе)
        self.tricks = {1: [], 2: []}  # Взятки по командам
        self.current_player_index = 0  # Индекс текущего игрока
        self.move_history = []  # История ходов
        
    def add_player(self, player: Player):
        """Добавление игрока в игру"""
        self.players.append(player)
        
    def set_trump(self, suit: str):
        """Установка козыря"""
        self.trump = suit
        
    def start_new_trick(self):
        """Начало нового кона"""
        self.current_trick = []
        
    def record_move(self, player_id: int, card: Card):
        """Запись хода игрока"""
        self.current_trick.append((player_id, card))
        self.move_history.append({
            "player": player_id,
            "card": card.__dict__,
            "trick": len(self.tricks[1]) + len(self.tricks[2])
        })
        
    def complete_trick(self, winning_team: int):
        """Завершение кона с указанием победившей команды"""
        self.tricks[winning_team].append(self.current_trick.copy())
        self.current_trick = []

class GameEngine:
    def __init__(self):
        """Инициализация игрового движка"""
        self.state = GameState()
        self.deck = self.create_deck()
        self.first_player_id = None  # ID игрока с шестеркой треф
        
    @staticmethod
    def create_deck() -> list[Card]:
        """Создание колоды из 36 карт"""
        suits = ['hearts', 'diamonds', 'clubs', 'spades']
        ranks = ['6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
        values = [0, 0, 0, 0, 10, 2, 3, 4, 11]  # Значения карт
        
        deck = []
        for suit in suits:
            for i, rank in enumerate(ranks):
                deck.append(Card(suit, rank, values[i]))
        return deck
    
    def deal_cards(self):
        """Раздача карт игрокам (по 9 карт каждому)"""
        import random
        random.shuffle(self.deck)
        
        # Раздаем по одной карте по кругу, пока у всех не будет по 9 карт
        for i in range(9):
            for player in self.state.players:
                if self.deck:
                    card = self.deck.pop()
                    player.add_card(card)
                    
                    # Проверяем, является ли карта шестеркой треф
                    if card.suit == 'clubs' and card.rank == '6':
                        self.first_player_id = player.id
    
    def start_game(self):
        """Начало новой игры"""
        # Раздаем карты
        self.deal_cards()
        
        # Устанавливаем первого игрока (с шестеркой треф)
        if self.first_player_id:
            # Находим индекс игрока по ID
            for i, player in enumerate(self.state.players):
                if player.id == self.first_player_id:
                    self.state.current_player_index = i
                    break
        else:
            # Если шестерка треф не найдена, начинаем с первого игрока
            self.state.current_player_index = 0
        
        # Начинаем первый кон
        self.state.start_new_trick()
        print(f"Игра началась! Первый ход за игроком {self.state.players[self.state.current_player_index]}")
    
    def set_trump_by_player(self, player_id: int, suit: str):
        """Установка козыря игроком"""
        if player_id != self.first_player_id:
            raise ValueError("Только игрок с шестеркой треф может устанавливать козырь")
        
        if suit not in ['hearts', 'diamonds', 'clubs', 'spades']:
            raise ValueError("Недопустимая масть для козыря")
        
        self.state.set_trump(suit)
        print(f"Игрок {player_id} установил козырь: {suit}")
    
    def play_turn(self, player_id: int, card_index: int):
        """Обработка хода игрока"""
        player = self.state.players[player_id - 1]
        
        # Проверяем, что ход делает правильный игрок
        if player_id != self.state.players[self.state.current_player_index].id:
            raise ValueError("Сейчас не ваш ход!")
        
        # Играем карту
        card = player.play_card(card_index)
        self.state.record_move(player_id, card)
        print(f"Игрок {player_id} сыграл: {card}")
        
        # Проверяем завершение кона (4 хода)
        if len(self.state.current_trick) == 4:
            # Определяем победителя взятки (упрощенная логика)
            winning_card = max(self.state.current_trick, 
                              key=lambda x: (x[1].suit == self.state.trump, x[1].value))
            winning_player_id = winning_card[0]
            winning_team = self.state.players[winning_player_id - 1].team
            
            self.state.complete_trick(winning_team)
            self.state.current_player_index = winning_player_id - 1
            print(f"Взятку выиграла команда {winning_team} (игрок {winning_player_id})")
        else:
            # Переход к следующему игроку
            self.state.current_player_index = (self.state.current_player_index + 1) % 4
        
        # Проверка завершения игры (9 взяток)
        if len(self.state.tricks[1]) + len(self.state.tricks[2]) == 9:
            print("Игра завершена!")
            # TODO: Подсчет очков и определение победителя

# Пример использования
if __name__ == "__main__":
    engine = GameEngine()
    # Создаем тестовую карту для демонстрации символов
    test_card = Card('hearts', 'A', 11)
    print(f"Тестовая карта: {test_card}")  # Должно вывести: A♥
