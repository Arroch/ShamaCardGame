"""
Модуль с ядром игры Шама.

Содержит основные классы и логику для реализации правил
карточной игры Шама.

Автор: ShamaVibe Team
"""

from game_constants import GameConstants

class GameException(Exception):
    """Базовое исключение для игровых ошибок.
    
    Служит родительским классом для всех игровых исключений.
    """
    pass

class InvalidPlayerAction(GameException):
    """Недопустимое действие игрока"""
    pass

class Card:
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

    def get_order(self, trump=None):

        if self.rank == '6' and self.suit == 'clubs':
            first_rank = 3
        elif self.rank == 'J':
            first_rank = 2
        elif self.suit == trump:
            first_rank = 1
        else:
            first_rank = 0
        return (first_rank, GameConstants.SUIT_ORDER.get(self.suit, 0), GameConstants.RANK_ORDER.get(self.rank, 0))
        
    def __repr__(self):
        """Строковое представление карты с символами мастей"""
        symbol = GameConstants.SUIT_SYMBOLS.get(self.suit, '?')
        return f"{self.rank:>2}{symbol}"
    
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
    
    def sort_hand(self, trump=None):
        """Соритирует карты по убыванию силы, после козыря одномастные стоят рядом
        6♣, J♣,  J♠, J♥, J♦, A/10/K/Q♣, A/10/K/Q♠, A/10/K/Q♥, A/10/K/Q♦
        """
        self.hand.sort(reverse=True, key=lambda item: item.get_order(trump))

    def get_hand(self) -> list:
        """Показать карты на руке у игрока"""
        return self.hand
        
    def clear_hand(self) -> list:
        """Убрать карты на руке у игрока"""
        self.hand = []
    
    def __repr__(self):
        """Строковое представление игрока"""
        return f"{self.name}"

class MatchState:
    """Класс для хранения состояния матча в игре Шама.
    
    Атрибуты:
        status (GameConstants.Status): Перечисление статуса игры
        players (dict): Словарь игроков формата {id: Player}
        match_scores (dict): Очки команд за игры (ключи: 10, 20)
        game_scores (dict): Очки команд за взятки (ключи: 10, 20)
        first_player_index (int): ID игрока с шестеркой треф (шамой)
        trump (str): Текущий козырь (масть)
        current_player_index (int): ID текущего игрока
        current_table (list): Карты, выложенные на стол в текущем коны
        current_turn (int): Номер текущего хода (1-9)
    """
    
    def __init__(self):
        """Инициализация состояния игры"""
        self.status = GameConstants.Status.WAITING_PLAYERS
        self.players = {
            GameConstants.PLAYER_1_1: None, 
            GameConstants.PLAYER_1_2: None, 
            GameConstants.PLAYER_2_1: None, 
            GameConstants.PLAYER_2_2: None
        }  # Список игроков
        self.match_scores = {
            GameConstants.TEAM_1: 0, 
            GameConstants.TEAM_2: 0
        }  # Очки команд за игры
        self.game_scores = {
            GameConstants.TEAM_1: 0, 
            GameConstants.TEAM_2: 0
        }  # Очки команд за взятки
        self.first_player_index = 0  # Индекс игрока с шамой
        self.trump = None  # Текущий козырь
        self.current_player_index = 0  # Индекс текущего игрока
        self.current_table = []  # Карты на столе
        self.current_turn = 1  # Номер хода
                
    def set_status(self, status: GameConstants.Status):
        """Устанавливает состояние игры через перечисление.
        
        Args:
            status: Статус игры из GameConstants.Status
        """
        self.status = status
        
    def set_current_player_index(self, p_index: int):
        self.current_player_index = p_index
        
    def set_current_turn(self, new_turn=None):
        if new_turn:
            self.current_turn = new_turn
        else:
            self.current_turn += 1
        
    def set_trump(self, suit: str) -> tuple:
        self.trump = suit
        self.set_status(GameConstants.Status.TRUMP_SELECTED)
        
    def add_player(self, player_index: int, player: Player):
        """Добавление игрока в игру.
        
        Args:
            player_index: Индекс игрока (11, 12, 21, 22) GameConstants.PLAYER_*
            player: Объект Player для добавления
            
        Returns:
            GameConstants.Status: Текущий статус
            
        Raises:
            InvalidPlayerAction: Если игра не в состоянии ожидания игроков
                или все места уже заняты
        """
        # Проверяем, что игра в состоянии ожидания игроков и валидный индекс
        if self.status == GameConstants.Status.WAITING_PLAYERS:
            self.players[player_index] = player
            
            # Если добавлены все 4 игрока, обновляем состояние
            if sum(1 for p in self.players.values() if p is not None) == 4:
                self.set_status(GameConstants.Status.PLAYERS_ADDED)
        else:
            raise InvalidPlayerAction("Игра не создана или стол полон")
        
    def put_card(self, player_index: int, card: Card):
        """Выложить карту на стол"""
        self.current_table.append({'player_index': player_index, 'player': self.players[player_index], 'card': card})

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

    def clear_score(self, score_type: str):
        """Очистить счет матча/игры у команд"""
        if score_type == 'match':
            self.match_scores[10] = 0
            self.match_scores[20] = 0
        elif score_type == 'game':
            self.game_scores[10] = 0
            self.game_scores[20] = 0
        else:
            raise ValueError("Неверный тип счета")
        
    def show_table(self):
        card_iter = iter(self.current_table)
        while True:
            try:
                card = next(card_iter)
                print(f"{card['player']}: {card['card']}", end=", ")
            except StopIteration:
                print()
                break
        
class GameEngine:
    """Игровой движок, реализующий логику игры Шама.
    
    Отвечает за:
    - Создание и раздачу колоды
    - Управление ходом игры
    - Определение победителя кона
    - Подсчет очков
    - Определение победителя матча
    """

    def __init__(self, state):
        """Инициализация игрового движка"""
        self.state = state
        
    @staticmethod
    def create_deck() -> list[Card]:
        """Создание колоды из 36 карт"""
        suits = ['hearts', 'diamonds', 'clubs', 'spades']
        ranks = ['6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
        values = [0, 0, 0, 0, 10, 2, 3, 4, 11]  # Значения карт
        
        return [Card(suit, rank, values[i]) for suit in suits for i, rank in enumerate(ranks)]
    
    def deal_cards(self):
        """Раздача карт игрокам (по 9 карт каждому).
        
        Создаёт колоду, перемешивает и раздаёт карты игрокам.
        Также определяет, у какого игрока шама (6♣).
        """
        import random
        deck = self.create_deck()
        random.shuffle(deck)
        # Очищаем руки каждого игрока перед раздачей
        for player in self.state.players.values():
            player.clear_hand()

        # Оптимизированная раздача карт: один цикл вместо вложенных
        player_ids = list(self.state.players.keys())
        for i, card in enumerate(deck):
            player_index = player_ids[i % len(player_ids)]
            self.state.players[player_index].add_card(card)
            
            # Проверяем, является ли карта шестеркой треф (шамой)
            if card.rank == '6' and card.suit == GameConstants.CLUBS:
                self.state.first_player_index = player_index
    
    def start_game(self) -> tuple:
        """Запускает новую игру (раздачу).
        
        Раздает карты, находит игрока с шамой, сортирует карты в руках
        и устанавливает первого игрока.
        
        Returns:
            status - статус игры
            
        Raises:
            ValueError: Если шама не найдена ни у одного из игроков
        """
        # Раздаем карты
        self.deal_cards()
        self.state.set_status(GameConstants.Status.CARDS_DEALT)
        # Сортируем карты первого игрока для удобного отображения
        self.state.players[self.state.first_player_index].sort_hand()
                
        # Устанавливаем первого игрока (с шестеркой треф)
        if self.state.first_player_index:
            self.state.set_status(GameConstants.Status.WAITING_TRUMP)
            self.state.set_current_player_index(self.state.first_player_index)
            return self.state.status
        else:
            raise ValueError("Ни у кого нет шамы! Проверьте логику раздачи карт.")
        
    def set_trump_by_player(self, player_index: int, suit: str):
        """Установка козыря игроком"""
        if player_index != self.state.first_player_index:
            raise InvalidPlayerAction("Только игрок с шестеркой треф может устанавливать козырь")
        
        if suit not in GameConstants.SUIT_SYMBOLS.keys():
            raise InvalidPlayerAction("Недопустимая масть для козыря")
        self.state.set_trump(suit)

        if self.state.status == GameConstants.Status.TRUMP_SELECTED:
                    # Сортируем карты всех игроков с учетом козыря
            for p in self.state.players:
                    self.state.players[p].sort_hand(suit)

            return self.state.status, self.state.players[player_index].name, self.state.trump
        else:
            raise ValueError("Неудалось назначить козырь")
    
    def validate_card_play(self, player_index: int, card_index: int) -> bool:
        """Проверяет допустимость хода по правилам игры.
        
        Проверяет, соблюдает ли игрок правила хода:
        1. Если это первый ход в коне - можно ходить любой картой
        2. Если нет - нужно ходить в масть, если есть карты этой масти
        3. Если нет карт в масть - нужно ходить козырем, если есть козыри
        4. Если нет карт в масть и козырей - можно ходить любой картой
        
        Args:
            player_index: Индекс игрока
            card_index: Индекс карты в руке игрока
            
        Returns:
            bool: True если ход допустим, False иначе
        """
        player = self.state.players[player_index]
        
        # Проверяем, что индекс карты в допустимых пределах
        if card_index < 0 or card_index >= len(player.hand):
            return False
            
        card = player.hand[card_index]
        
        # Если это первый ход в коне, любая карта допустима
        if len(self.state.current_table) == 0:
            return True
            
        # Получаем карту первого хода в коне
        first_card = self.state.current_table[0]['card']
        first_suit = first_card.suit
        
        # Проверяем наличие карт нужной масти у игрока
        has_same_suit = any(c.suit == first_suit for c in player.hand)
        
        # Если карта той же масти или у игрока нет карт этой масти
        if card.suit == first_suit or not has_same_suit:
            return True
            
        # Проверяем, есть ли у игрока козыри
        has_trump = any(c.suit == self.state.trump for c in player.hand)
        
        # Если первая карта козырная, игрок должен ответить козырем, если может
        if first_suit == self.state.trump:
            return card.suit == self.state.trump or not has_trump
            
        # Если игрок не пошел в масть, должен ходить козырем, если он есть
        return card.suit == self.state.trump or not has_trump
    
    def play_turn(self, player_index: int, card_index: int):
        """Обработка хода игрока.
        
        Проверяет валидность хода, выбрасывает карту на стол и обновляет состояние игры.
        
        Args:
            player_index: Индекс игрока, делающего ход
            card_index: Индекс карты в руке игрока
            
        Returns:
            tuple: (status, player, card) - новый код состояния,
                   игрок, сделавший ход и сыгранная карта
                   
        Raises:
            InvalidPlayerAction: Если ход недопустим
        """
        player = self.state.players[player_index]
        
        # Проверяем, что ход делает правильный игрок
        if player_index != self.state.current_player_index:
            raise InvalidPlayerAction("Сейчас не ваш ход!")
        
        # Проверяем, что у игрока есть карты
        if len(player.hand) == 0:
            raise InvalidPlayerAction("У Вас нет больше карт!")
        
        # Проверяем, что у игрока есть эта карта
        if len(player.hand) <= card_index:
            raise InvalidPlayerAction("У вас нет такой карты!")
        
        # Проверяем, что сделали меньше 9-ти ходов
        if self.state.current_turn >= 10:
            raise InvalidPlayerAction("Уже сделали 9 ходов!")
        
        # Проверяем, что на столе меньше 4-х карт
        if len(self.state.current_table) >= 4:
            raise InvalidPlayerAction("На столе уже 4 карты!")
        
        # Выставляем номер хода
        if len(self.state.current_table) == 3:
            self.state.set_current_turn()
        
        # Проверяем, соответствует ли ход правилам игры
        # TODO: раскомментировать для включения проверки правил
        # if not self.validate_card_play(player_index, card_index):
        #     raise InvalidPlayerAction("Недопустимый ход! Вы должны ходить в масть или козырем.")
        
        # Играем карту
        card = player.play_card(card_index)
        self.state.put_card(player_index, card)
        card_count = len(self.state.current_table)
        
        # Устанавливаем новый статус в зависимости от количества карт на столе
        if card_count == 1:
            self.state.set_status(GameConstants.Status.PLAYED_CARD_1)
        elif card_count == 2:
            self.state.set_status(GameConstants.Status.PLAYED_CARD_2)
        elif card_count == 3:
            self.state.set_status(GameConstants.Status.PLAYED_CARD_3)
        elif card_count == 4:
            self.state.set_status(GameConstants.Status.TRICK_COMPLETED)

        if GameConstants.Status.PLAYING_CARDS.value < self.state.status.value < GameConstants.Status.TRICK_COMPLETED.value:
            next_player_index = GameConstants.PLAYERS_QUEUE[self.state.current_player_index]
            self.state.set_current_player_index(next_player_index)

        return self.state.status, player, card
    
    def calculate_card_power(self, card: Card, first_suit: str, trump: str) -> tuple:
        """Рассчитывает силу карты по правилам игры Шама.
        
        Иерархия карт (от сильнейшей к слабейшей):
        1. Шестерка треф (шама)
        2. Валеты (в порядке: ♣ > ♠ > ♥ > ♦)
        3. Козырные карты (кроме валетов и шамы)
        4. Карты масти первого хода
        5. Все остальные карты
            
        Args:
            card: Карта, силу которой нужно определить
            first_suit: Масть первой карты в коне
            trump: Текущий козырь
            
        Returns:
            tuple: (приоритет_группы, приоритет_внутри_группы)
                  для сравнения карт между собой
        """
        # Шестерка треф - самая сильная карта в игре
        if card.suit == GameConstants.CLUBS and card.rank == '6':
            return (4, 0)  # Максимальный приоритет
        
        # Валеты (всегда козыри, независимо от козырной масти)
        if card.rank == 'J':
            # Порядок валетов: ♣ > ♠ > ♥ > ♦
            return (3, GameConstants.SUIT_ORDER.get(card.suit, 0))
        
        # Козырные карты (кроме валетов и шестерки треф)
        if card.suit == trump:
            # Порядок козырных: A > 10 > K > Q > 9 > 8 > 7 > 6
            return (2, GameConstants.RANK_ORDER.get(card.rank, 0))
        
        # Карты масти первого хода
        if card.suit == first_suit:
            return (1, GameConstants.RANK_ORDER.get(card.rank, 0))
        
        # Остальные карты (младше всех)
        return (0, 0)
    
    def complete_turn(self):
        """Завершение кона и определение победителя.
        
        Определяет победителя взятки, подсчитывает очки за взятку,
        обновляет состояние игры и подготавливает к следующему кону.
        
        Returns:
            tuple: (status, winning_card, winning_player_index, trick_points)
                  - новый код состояния, выигрышная карта, 
                  индекс игрока-победителя и очки за взятку
                  
        Raises:
            IndexError: Если на столе меньше 4 карт
        """
             
        # Проверяем завершение кона (4 хода)
        if self.state.status == GameConstants.Status.TRICK_COMPLETED:
            # Определяем победителя взятки по правилам Шамы
            first_suit = self.state.current_table[0]['card'].suit
            trump = self.state.trump
            # Находим карту с максимальной силой
            strongest_card = max(
                self.state.current_table, 
                key=lambda x: self.calculate_card_power(x['card'], first_suit, trump)
            )
            winning_player_index = strongest_card['player_index']
            winning_card = strongest_card['card']
            winning_team_index = winning_player_index // 10 * 10
            
            # Подсчитываем очки за взятку
            trick_points = sum(c['card'].value for c in self.state.current_table)
            self.state.increase_score(winning_team_index, trick_points, 'game')
            
            self.state.current_player_index = winning_player_index
            print(f"Карты на столе:", end=' ')
            self.state.show_table()
            self.state.clear_table()
            if self.state.current_turn <= 9:
                self.state.set_status(GameConstants.Status.PLAYING_CARDS)
            else:
                self.state.set_status(GameConstants.Status.GAME_COMPLETED)
            return self.state.status, winning_card, winning_player_index, trick_points
        else:
            raise IndexError("На столе меньше 4х карт")
        
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
                    game_results = scores, losed_team, 12
                elif scores[losed_team] < 30:
                    game_results = scores, losed_team, 6
                elif scores[losed_team] < 60:
                    game_results = scores, losed_team, 3
                else:
                    game_results = scores, losed_team, 2
            else:
                if scores[losed_team] == 0:
                    game_results = scores, losed_team, 6
                elif scores[losed_team] < 30:
                    game_results = scores, losed_team, 3
                else:
                    game_results = scores, losed_team, 1
            return game_results

        # Проверка завершения игры (9 взяток)
        if self.state.current_turn > 9:
            scores, losed_team, losed_points = get_points(self.state.first_player_index, self.state.game_scores.copy())
            self.state.increase_score(losed_team, losed_points, 'match')
            self.state.clear_score('game')
            if self.state.match_scores[losed_team] < 12:
                self.state.set_status(GameConstants.Status.NEW_DEAL_READY)
                self.state.set_current_turn(1)
            else:
                self.state.set_status(GameConstants.Status.MATCH_COMPLETED)
            return self.state.status, scores, losed_team, losed_points
        
    def complete_match(self):  
        self.state.set_status(GameConstants.Status.GAME_FINISHED)
        return self.state.status
    
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
