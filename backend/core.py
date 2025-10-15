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
    def __init__(self, player_id: int, player_name: str):
        """
        Инициализация игрока.
        
        :param player_id: уникальный ID игрока = tg_chat_id с ботом
        :param player_name: тг логин игрока или имя введенное руками
        """
        self.id = player_id
        self.name = player_name
        self.hand = []  # Карты на руках
        
    def add_card(self, card: Card):
        """Добавление карты в руку игрока"""
        self.hand.append(card)
        
    def play_card(self, card_index: int) -> Card:
        """Сыграть карту по индексу"""
        return self.hand.pop(card_index)
        
    def get_hand(self) -> list:
        """Показать карты на руке у игрока"""
        return self.hand
    
    def __repr__(self):
        """Строковое представление игрока"""
        return f"{self.name}"

class MatchState:
    def __init__(self):
        """Инициализация состояния игры"""
        self.status_code = 100
        self.players = {11: None, 12: None, 21: None, 22: None}  # Список игроков
        self.match_scores = {10: 0, 20: 0}  # Очки команд за игры
        self.game_scores = {10: 0, 20: 0}  # Очки команд за взятки
        self.first_player_index = 0  # Индекс игрока с шамой
        self.trump = None  # Текущий козырь
        self.current_player_index = 0  # Индекс текущего игрока
        self.current_table = []  # Карты на столе
        self.current_turn = 0  # Номер хода
        # self.tricks = {10: [], 20: []}  # Взятки по командам
        # self.six_clubs_team = None  # Команда с шестеркой треф
        # self.move_history = []  # История ходов
        
    def set_status_code(self, status_code: int):
        self.status_code = status_code
        
    def set_current_player_index(self, p_index: int):
        self.current_player_index = p_index
        
    def set_current_turn(self):
        self.current_turn += 1
        
    def set_trump(self, suit: str) -> tuple:
        """Возвращает кортеж (индекс игрока кто установил козырь, и козырь)"""
        self.trump = suit
        self.status_code = 203
        
    def add_player(self, p_index: int, player: Player):
        """Добавление игрока в игру"""
        if 100 <= self.status_code < 104:
            self.players[p_index] = player
            self.status_code += 1
        else:
            raise IndexError("Игра не создана или стол полон")
        
    def put_card(self, player_index: int, card: Card):
        """Выложить карту на стол"""
        self.current_table.append((player_index, card))

    def clear_table(self):
        """Очистка стола"""
        self.current_table = []

    def increase_score(self, team_index: int, incr: int, score_type: str):
        """Увеличить счет матча/игры у команды"""
        if score_type == 'match':
            self.match_scores[team_index] += incr
        elif score_type == 'game':
            self.game_scores[team_index] += incr
        else:
            raise ValueError("Неверный тип счета")
        
class GameEngine:
    PLAYERS_QUEUE = {
        11: 21,
        21: 12,
        12: 22,
        22: 11,
    }

    def __init__(self, state):
        """Инициализация игрового движка"""
        self.state = state
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
        """Раздача карт игрокам (по 9 карт каждому)"""
        import random
        random.shuffle(self.deck)
        
        # Раздаем по одной карте по кругу, пока у всех не будет по 9 карт
        for i in range(9):
            for p_index in self.state.players:
                if self.deck:
                    card = self.deck.pop()
                    self.state.players[p_index].add_card(card)
                    
                    # Проверяем, является ли карта шестеркой треф
                    if card.rank == '6' and card.suit == 'clubs':
                        self.state.first_player_index = p_index
    
    def start_game(self) -> str:
        """Возвращает имя игрока с шамой"""
        # Раздаем карты
        self.deal_cards()
        self.state.set_status_code(201)
        # Сортируем карты
        for player_num in self.state.players:
                self.state.players[player_num].hand.sort(reverse=True, key=lambda item: (item.suit, item.value))
                
        # Устанавливаем первого игрока (с шестеркой треф)
        if self.state.first_player_index:
            self.state.set_status_code(202)
            self.state.set_current_player_index(self.state.first_player_index)
            return self.state.status_code, self.state.players[self.state.first_player_index]
        else:
            raise ValueError("Ни у кого нет шамы???")
        
    def set_trump_by_player(self, player_index: int, suit: str):
        """Установка козыря игроком"""
        if player_index != self.first_player_index:
            raise ValueError("Только игрок с шестеркой треф может устанавливать козырь")
        
        if suit not in ['hearts', 'diamonds', 'clubs', 'spades']:
            raise ValueError("Недопустимая масть для козыря")
        self.trump = suit

        if self.status_code == 203:
            return self.state.status_code, self.players[player_index].name, self.trump
        else:
            raise ValueError("Неудалось назначить козырь")
    
    def play_turn(self, player_index: int, card_index: int):
        """Обработка хода игрока"""
        player = self.state.players[player_index]
        
        # Проверяем, что ход делает правильный игрок
        if player_index != self.state.current_player_index:
            raise ValueError("Сейчас не ваш ход!")
        
        # Проверяем, что у игрока есть карты
        if len(player.hand) == 0:
            raise ValueError("У Вас нет больше карт!")
        
        # Проверяем, что сделали меньше 9-ти ходов
        if self.state.current_turn >= 9:
            raise ValueError("Уже сделали 9 ходов!")
        
        # Проверяем, что на столе меньше 4-х карт
        if len(self.state.current_table) >= 4:
            raise ValueError("На столе уже 4 карты!")
        
        # Выставляем номер хода
        if len(self.state.current_table) == 0:
            self.set_current_turn()
        
        # Играем карту
        card = player.play_card(card_index)
        self.state.put_card(player_index, card)
        card_count = len(self.state.current_table)
        self.state.set_status_code(300 + card_count)

        if 300 < self.state.status_code < 304:
            next_player_index = self.PLAYERS_QUEUE[self.state.current_player_index]
            self.state.set_current_player_index(next_player_index)
        else:
            self.state.set_current_player_index(100)

        # print(f"Игрок {player} сыграл: {card}, селдующий ходит {current_player_index}")
        return self.state.status_code, player, card, self.state.current_player_index
    
    def complete_turn(self):
        # Функция для определения силы карты
        def card_power(card):
            # Шестерка треф - самая сильная
            if card.suit == 'clubs' and card.rank == '6':
                return (4, 0)  # Максимальный приоритет
            
            # Валеты (всегда козыри)
            if card.rank == 'J':
                # Порядок валетов: ♣ > ♠ > ♥ > ♦
                suit_order = {'clubs': 3, 'spades': 2, 'hearts': 1, 'diamonds': 0}
                return (3, suit_order.get(card.suit, 0))
            
            # Козырные карты (кроме валетов и шестерки треф)
            if card.suit == trump:
                # Порядок козырных: A > 10 > K > Q > 9 > 8 > 7 > 6
                rank_order = {'A': 7, '10': 6, 'K': 5, 'Q': 4, '9': 3, '8': 2, '7': 1, '6': 0}
                return (2, rank_order.get(card.rank, 0))
            
            # Карты масти первого хода
            if card.suit == first_suit:
                rank_order = {'A': 7, '10': 6, 'K': 5, 'Q': 4, '9': 3, '8': 2, '7': 1, '6': 0}
                return (1, rank_order.get(card.rank, 0))
            
            # Остальные карты (младше всех)
            return (0, 0)
             
        # Проверяем завершение кона (4 хода)
        if self.state.status_code == 304:
            # Определяем победителя взятки по правилам Шамы
            first_suit = self.state.current_table[0][1].suit
            trump = self.state.trump
            # Находим карту с максимальной силой
            strongest_card = max(self.state.current_table, key=lambda x: card_power(x[1]))
            winning_player_index = strongest_card[0]
            winning_card = strongest_card[1]
            winning_team_index = winning_player_index // 10 * 10
            
            # Подсчитываем очки за взятку
            trick_points = sum(card.value for _, card in self.state.current_table)
            self.state.increase_score(winning_team_index, trick_points, 'game')
            
            self.state.current_player_index = winning_player_index
            self.clear_table()
            self.state.set_status_code(400 + self.state.current_turn)
            # print(f"Взятку выиграла команда {winning_team} (игрок {winning_team_index})! Очки: {trick_points}")
            return self.state.status_code, winning_card, winning_player_index, winning_team_index, trick_points
        else:
            raise IndexError("На столе меньше 4х карт (satus_code != 304)")
        
    def complete_game(self):
        """ Подсчет очков и определение победителя"""

        # Функция для подсчета очков
        def get_points(first_player_index, scores):
            """
            - Для команды, у которой была шесть крести на руках:
            - 0 взяток - 12 очков
            - меньше 30 взяток – 6 очков
            - меньше 60 взяток – 3 очка
            - ровно 60 взяток – 2 очка
            - Для команды, у которой не было шесть крести на руках:
            - 0 взяток - 6 очков
            - меньше 30 взяток – 3 очка
            - меньше 60 взяток – 1 очко
            """
            shama_team = first_player_index // 10 * 10
            losed_team = 10 if scores[10] < scores[20] or scores[10] == 60 and shama_team == 10 else 20
            if shama_team == losed_team:
                if scores[losed_team] == 0:
                    return losed_team, 12
                elif scores[losed_team] < 30:
                    return losed_team, 6
                elif scores[losed_team] < 60:
                    return losed_team, 3
                else:
                    return losed_team, 2
            else:
                if scores[losed_team] == 0:
                    return losed_team, 6
                elif scores[losed_team] < 30:
                    return losed_team, 3
                else:
                    return losed_team, 1

        # Проверка завершения игры (9 взяток)
        if self.state.status_code == 409:
            print("Игра завершена!")
            losed_team, losed_points = get_points(self.state.first_player_index, self.state.game_scores)
            self.state.increase_score(losed_team, losed_points, 'match')
            if self.state.match_scores[losed_team] < 12:
                self.state.set_status_code(500)
            else:
                self.state.set_status_code(600)
            return self.state.status_code, losed_team, losed_points, self.state.match_scores
        
    def complete_match(self):  
        self.state.set_status_code(700)
        return self.state.status_code
# Пример использования
if __name__ == "__main__":
    state = MatchState()
    state.add_player(11, Player(1, 'Name_1'))
    state.add_player(12, Player(2, 'Name_2'))
    state.add_player(21, Player(3, 'Name_3'))
    state.add_player(22, Player(4, 'Name_4'))
    engine = GameEngine(state)
    s_code, f_player = engine.start_game()
    print(f'StatusCode: {s_code}, {f_player} has Shama')
    print(engine.state.players[11], engine.state.players[11].get_hand())
    print(engine.state.players[12], engine.state.players[12].get_hand())
    print(engine.state.players[21], engine.state.players[21].get_hand())
    print(engine.state.players[22], engine.state.players[22].get_hand())
