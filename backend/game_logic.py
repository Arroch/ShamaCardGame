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
        """Раздача карт игрокам"""
        # TODO: Реализовать логику раздачи
        pass
    
    def start_game(self):
        """Начало новой игры"""
        # TODO: Определить игрока с шестеркой крести
        # TODO: Установить козырь
        # TODO: Начать первый кон
        pass
    
    def play_turn(self, player_id: int, card_index: int):
        """Обработка хода игрока"""
        # TODO: Валидация хода
        # TODO: Обновление состояния игры
        # TODO: Проверка завершения кона/игры
        pass

# Пример использования
if __name__ == "__main__":
    engine = GameEngine()
    # Создаем тестовую карту для демонстрации символов
    test_card = Card('hearts', 'A', 11)
    print(f"Тестовая карта: {test_card}")  # Должно вывести: A♥
