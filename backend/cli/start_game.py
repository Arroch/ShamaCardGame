"""
Интерфейс командной строки для карточной игры "Шама".

Предоставляет текстовый интерфейс для игры в карты "Шама" через терминал.
Поддерживает локальную игру для 4 игроков.

Автор: ShamaVibe Team
"""

from bin.core import MatchState, GameEngine, Player, Card, InvalidPlayerAction
from bin.constants import GameConstants

def show_rules():
    print(
        """
    ПРАВИЛА ИГРЫ
Играются классические 36 игральных карт (карты: 6, 7, 8, 9, 10, валет, дама, король, туз и у каждой карты есть 4 масти: крести, пики, черви, бубны, в итоге 4 x 9 = 36 карт). В игре принимает участие 2 команды по 2 игрока, игроки ходят фиксированно друг за другом по кругу, начало хода может начаться с любого игрока в зависимости от ситуации в игре (1.1 -> 2.1 -> 1.2 -> 2.2 или 2.2 -> 1.1 -> 2.1 -> 1.2). 

Самая старшая карта – это шесть крести, дальше по убыванию – валет крести, валет пики, валет черви, валет бубны, козырный туз, козырная десять, козырный король, козырная дама, козырная девять, козырная восемь, козырная семь, козырная шесть, туз, десять, король, дама, девять, восемь, семь, шесть. Козырем может быть любая масть, она объявляется в начале каждой раздачи. Пять карт всегда имеют статус козырной в независимости от объявленного козыря в текущей раздаче – это шесть крести, валет крести, валет пики, валет черви, валет бубны.

В начале игры всем случайно раздается по 9 карт. После раздачи, игрок у которого на руках шести крести, должен объявить козырь, он сам выбирает, какая масть будет козырной в текущей раздаче. После объявления козыря этот игрок ходит первый и кидает любую карту из своей руки на стол. Остальные игроки должны в порядке очереди (противник, союзник, противник) выбросить по одной карте, но они должны бросать карты по следующим правилам:
1. Игроки обязаны кинуть карту такой же масти, с которой походил первый игрок, если такой масти у игрока нет, то он должен кинуть козырную карту, если козырной карты нет, то он должен кинуть любую карту из своей руки
2. Если первый игрок пошел с козырной карты, то и все остальные должны кидать козырные карты, если козырной карты нет, то можно кинуть любую карты из своей руки

После того, когда на столе оказывается 4 карты, то кон заканчивается и карты со стола (эти карты называют взяткой) забирает команда, чей участник кинул самую старшую карту. Игрок, чья карта была самой старшей, начинает следующий кон. Хода продолжаются до тех пор, пока у всех не закончатся карты на руках.

После завершения раздачи (у всех закончились карты) идет подсчет взяток команд.

Стоимость карт следующая:
1. туз – 11 очков
2. десять – 10 очков
3. король – 4 очка
4. дама – 3 очка
5. валет – 2 очка
6. все остальные карты – 0 очков

После подсчета взяток идет начисление очков:
- Для команды, у которой была шесть крести на руках:
  - 0 взяток - 12 очков
  - меньше 30 взяток – 6 очков
  - меньше 60 взяток – 3 очка
  - ровно 60 взяток – 2 очка
- Для команды, у которой не было шесть крести на руках:
  - 0 взяток - 6 очков
  - меньше 30 взяток – 3 очка
  - меньше 60 взяток – 1 очко

Игра идет до тех пор, пока какая-либо команда не наберет 12 очков и больше, команда, которая набрала 12 очков и больше, считается проигравшей.

Игрок может нарушать правила бросания карт, но если это заметит противник, то команде игрока начисляется 3 очка
        """
    )

def show_menu():
    """Отображает главное меню игры и обрабатывает выбор пользователя.
    
    Выводит основные опции меню:
    1. Новая игра - создание новой игры
    2. Правила - просмотр правил игры
    3. Выход - завершение работы приложения
    
    Returns:
        int: Код выбранной опции меню (1, 2, 3) или 0 при некорректном вводе
    """
    print("""Карточная игра Шама (6♣)
    МЕНЮ
    1. Новая игра
    2. Правила
    3. Выход
            """)
    try:
        input_comand = input("Введите число для выбора действия меню\n")
        return int(input_comand)
    except ValueError:
        print("Нужно ввести число")
        return 0

def show_hand(hand):
    """Отображает карты в руке игрока.
    
    Выводит карты с нумерацией для удобства выбора,
    форматируя вывод по 3 карты в строку.
    
    Args:
        hand: Список карт в руке игрока
    """
    card_iter = iter(hand)
    i = 0
    while True:
        i += 1
        p_end = ' || ' if i % 3 else '\n'
        try:
            print(f"{i}: {next(card_iter)}", end=p_end)
        except StopIteration:
            print()
            break

def show_state(state):
    """Отображает текущее состояние игры.
    
    Выводит информацию о счете команд, текущем козыре,
    игроке с шамой, номере хода и картах на столе.
    
    Args:
        state: Текущее состояние игры (объект MatchState)
    """
    print(f"""
Статус игры:
{state.players[GameConstants.PLAYER_1_1]} и {state.players[GameConstants.PLAYER_1_2]} - счет: {state.match_scores[GameConstants.TEAM_1]}
{state.players[GameConstants.PLAYER_2_1]} и {state.players[GameConstants.PLAYER_2_2]} - счет: {state.match_scores[GameConstants.TEAM_2]}
""")
    print(f"Козырь: {GameConstants.SUIT_SYMBOLS[state.trump]}, хвалил {state.players[state.first_player_index]}")
    print(f"Номер хода: {state.current_turn}")
    print(f"Карты на столе:", end=' ')
    print(state.show_table())
    print(f"Сейчас ходит: {state.players[state.current_player_index]}", end=' ')

def create_match():
    """Создает новый матч игры.
    
    Запрашивает имена четырех игроков и создает новый матч с ними.
    
    Returns:
        tuple: (status, state) - статус состояния, объект состояния игры
    """
    player_name_11 = input("Введите имя первого игрока первой команды\n")
    player_name_12 = input("Введите имя второго игрока первой команды\n")
    player_name_21 = input("Введите имя первого игрока второй команды\n")
    player_name_22 = input("Введите имя второго игрока второй команды\n")
    state = MatchState()
    try:
        state.add_player(GameConstants.PLAYER_1_1, Player(1, player_name_11))
        state.add_player(GameConstants.PLAYER_1_2, Player(2, player_name_12))
        state.add_player(GameConstants.PLAYER_2_1, Player(3, player_name_21))
        state.add_player(GameConstants.PLAYER_2_2, Player(4, player_name_22))
        if state.status == GameConstants.Status.PLAYERS_ADDED:
            print(f"""
Игроки в игре:
Команда 1 - {state.players[GameConstants.PLAYER_1_1]} и {state.players[GameConstants.PLAYER_1_2]}
Команда 2 - {state.players[GameConstants.PLAYER_2_1]} и {state.players[GameConstants.PLAYER_2_2]}
Чтобы начать игру введите `s`, чтобы вернуться в меню - `m`
            """)
        return state.status, state
    except Exception as e:
        print(e)
        return state.status, state

def handle_menu_selection(state):
    """Обрабатывает выбор пункта меню.

    Args:
        state: Объект состояния игры или None

    Returns:
        tuple: (GameConstants.Status | None, state) - новый статус или None при выходе
    """
    menu_choice = show_menu()

    if menu_choice == 3:
        return None, state
    elif menu_choice == 2:
        show_rules()
        return GameConstants.Status.WAITING_PLAYERS, state
    elif menu_choice == 1:
        status, state = create_match()
        return status, state
    return GameConstants.Status.WAITING_PLAYERS, state

def handle_trump_selection(engine, state, first_player):
    """Обрабатывает выбор козыря игроком с шамой.
    
    Args:
        engine: Игровой движок
        state: Объект состояния игры
        first_player: Игрок с шамой
        
    Returns:
        GameConstants.Status: Обновленный статус
    """
    print(f"Игрок с шамой: {first_player}")
    input_command = input(
        f"Показать карты игрока {first_player}\n"
        f"y - да, re - перераздача, f - завершить игру и выйти в меню\n"
    ).lower()

    if input_command == 'y':
        print(first_player.get_hand())
        suit_choice = int(input("Выберите козырь:\n1 - '♣', 2 - '♠', 3 - '♥', 4 - '♦'\n"))
        suits = [GameConstants.CLUBS, GameConstants.SPADES, GameConstants.HEARTS, GameConstants.DIAMONDS]
        try:
            suit = suits[suit_choice - 1]
            status, player_name, trump = engine.set_trump_by_player(state.first_player_index, suit)
            print("\033c\033[3J", end="")
            print(f"Игрок: {player_name} выбрал козырь: {GameConstants.SUIT_SYMBOLS[trump]}")
            return status
        except ValueError as e:
            print(f"Статус: {state.status_code}, Ошибка: {e}")
            return state.status
        except IndexError:
            print("Некорректный выбор масти")
            return state.status
    elif input_command == 're':
        state.set_status(GameConstants.Status.PLAYERS_ADDED)
        return state.status
    elif input_command == 'f':
        state.set_status(GameConstants.Status.GAME_FINISHED)
        return state.status
    
    return state.status

def handle_player_turn(engine, state):
    """Обрабатывает ход игрока.
    
    Args:
        engine: Игровой движок
        state: Объект состояния игры
        
    Returns:
        GameConstants.Status: Обновленный статус
    """
    print(f"Ходит игрок: {state.players[state.current_player_index]}")
    input_command = input(
        f"Показать карты игрока {state.players[state.current_player_index]}\n"
        f"y - да, f - завершить игру и выйти в меню\n"
    ).lower()
    
    if input_command == 'y':
        show_state(state)
        print('Ваши карты:')
        show_hand(state.players[state.current_player_index].get_hand())
        try:
            card_choice = int(input("Выберите номер карты для хода\n"))
            try:
                status, player, card = engine.play_turn(state.current_player_index, card_choice - 1)
                print("\033c\033[3J", end="")
                print(f"Игрок {player} сыграл: {card}")
                return status
            except InvalidPlayerAction as e:
                print(e)
                return state.status
        except ValueError:
            print("Нужно ввести число")
            return state.status
    elif input_command == 'f':
        state.set_status(GameConstants.Status.GAME_FINISHED)
        return GameConstants.Status.GAME_FINISHED
        
    return state.status

def handle_new_deal(engine, state):
    """Обрабатывает начало новой раздачи.
    
    Args:
        engine: Игровой движок
        state: Объект состояния игры
        
    Returns:
        GameConstants.Status: Обновленный статус
        int: Обновленный код состояния
    """
    input_command = input(f"Начать новую раздачу\ny - да, f - завершить игру и выйти в меню\n").lower()
    
    if input_command == 'y':
        print(f"Новая раздача!")
        team1_players = f"{state.players[GameConstants.PLAYER_1_1]} и {state.players[GameConstants.PLAYER_1_2]}"
        team2_players = f"{state.players[GameConstants.PLAYER_2_1]} и {state.players[GameConstants.PLAYER_2_2]}"
        team1_score = state.match_scores[GameConstants.TEAM_1]
        team2_score = state.match_scores[GameConstants.TEAM_2]
        print(f"Счет: {team1_players} | {team1_score}-{team2_score} | {team2_players}")
        status = engine.start_game()
        return status
    elif input_command == 'f':
        state.set_status(GameConstants.Status.GAME_FINISHED)
        return state.status
    
    return state.status

def run_game(engine, state):
    """Основной игровой цикл.

    Args:
        engine: Игровой движок
        state: Объект состояния игры
    """
    losing_team = None

    while state.status not in (GameConstants.Status.MATCH_COMPLETED, GameConstants.Status.GAME_FINISHED):
        if state.status == GameConstants.Status.PLAYERS_ADDED:
            engine.start_game()

        elif state.status == GameConstants.Status.WAITING_TRUMP:
            handle_trump_selection(engine, state, state.players[state.first_player_index])

        elif state.status == GameConstants.Status.NEW_DEAL_READY:
            handle_new_deal(engine, state)

        elif state.status in (
            GameConstants.Status.TRUMP_SELECTED,
            GameConstants.Status.PLAYING_CARDS,
            GameConstants.Status.PLAYED_CARD_1,
            GameConstants.Status.PLAYED_CARD_2,
            GameConstants.Status.PLAYED_CARD_3,
        ):
            handle_player_turn(engine, state)

        elif state.status == GameConstants.Status.TRICK_COMPLETED:
            print("Карты на столе:", state.show_table())
            _, winning_card, winning_player_index, trick_points = engine.complete_turn()
            print(f"Взятку забрал игрок {state.players[winning_player_index]} "
                  f"картой {winning_card}! Начислили: {trick_points}")

        elif state.status == GameConstants.Status.GAME_COMPLETED:
            _, scores, losing_team, losing_points, _ = engine.complete_game()
            team1_players = f"{state.players[GameConstants.PLAYER_1_1]} и {state.players[GameConstants.PLAYER_1_2]}"
            team2_players = f"{state.players[GameConstants.PLAYER_2_1]} и {state.players[GameConstants.PLAYER_2_2]}"
            losing_players = f"{state.players[losing_team + 1]} и {state.players[losing_team + 2]}"
            print(f"Раздача завершилась!")
            print(f"Хвалил {state.players[state.first_player_index]}, "
                  f"счет: {team1_players} | {scores[GameConstants.TEAM_1]}-{scores[GameConstants.TEAM_2]} | {team2_players}")
            print(f"Начислили {losing_points} очков для {losing_players}")

    if state.status == GameConstants.Status.MATCH_COMPLETED:
        engine.complete_match()
        losing_players = f"{state.players[losing_team + 1]} и {state.players[losing_team + 2]}" if losing_team else "неизвестная команда"
        print(f"\nИгра закончилась!")
        print(f"{losing_players} — проиграли(")
        print(f"Счет: {state.match_scores[GameConstants.TEAM_1]}-{state.match_scores[GameConstants.TEAM_2]}\n")


def main(state):
    """Обрабатывает один цикл главного меню.

    Args:
        state: Объект состояния игры или None

    Returns:
        tuple: (running, state) — False если нужно выйти из программы
    """
    if state is not None and state.status == GameConstants.Status.PLAYERS_ADDED:
        input_command = input()
        if input_command == 's':
            engine = GameEngine(state)
            run_game(engine, state)
            return True, None
        elif input_command == 'm':
            return True, None
        else:
            print("Чтобы начать игру введите `s`, чтобы вернуться в меню — `m`\n")
            return True, state

    status, state = handle_menu_selection(state)
    if status is None:
        return False, None
    return True, state


if __name__ == "__main__":
    try:
        state = None
        running = True
        while running:
            running, state = main(state)
    except KeyboardInterrupt:
        print("\nИгра прервана пользователем. До свидания!")
