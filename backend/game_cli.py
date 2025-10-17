"""
Интерфейс командной строки для карточной игры "Шама".

Предоставляет текстовый интерфейс для игры в карты "Шама" через терминал.
Поддерживает локальную игру для 4 игроков.

Автор: ShamaVibe Team
"""

from core import MatchState, GameEngine, Player, Card, InvalidPlayerAction
from game_constants import GameConstants
import os

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
    state.show_table()
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

def handle_menu_selection(status_code, state):
    """Обрабатывает выбор пункта меню.
    
    Args:
        status_code: Текущий код состояния
        state: Объект состояния игры
        
    Returns:
        tuple: (status_code, state) - обновленные код состояния и объект игры
    """
    menu_choice = show_menu() if status_code != GameConstants.Status.PLAYERS_ADDED.value else status_code
    
    if menu_choice == 3:  # Выход
        return -100, state
    elif menu_choice == 2:  # Правила
        show_rules()
        return menu_choice, state
    elif menu_choice == 1:  # Новая игра
        status, state = create_match()
        return status.value, state
    return status_code, state

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

def main(status_code, state):
    """Основная функция игрового процесса.
    
    Управляет потоком игры в зависимости от текущего состояния.
    
    Args:
        status_code: Текущий код состояния
        state: Объект состояния игры
        
    Returns:
        tuple: (status_code, state) - обновленные код состояния и объект игры
    """
    # Обрабатываем выбор в меню
    status_code, state = handle_menu_selection(status_code, state)
    if status_code == -100 or state is None:
        return status_code, state
    # Обработка начала игры
    if state.status == GameConstants.Status.PLAYERS_ADDED:
        input_command = input()
        if input_command == 's':  # Начать игру
            engine = GameEngine(state)
            status = state.status
            # game_finished = False
            # losing_team = None
            
            # Основной игровой цикл
            while state.status not in (GameConstants.Status.MATCH_COMPLETED, GameConstants.Status.GAME_FINISHED):
                # Обработка разных состояний игры
                if state.status == GameConstants.Status.PLAYERS_ADDED:
                    # Начало игры (раздача карт)
                    status = engine.start_game()
                    
                elif state.status == GameConstants.Status.WAITING_TRUMP:
                    # Выбор козыря
                    status = handle_trump_selection(engine, state, 
                                                        state.players[state.first_player_index])
                    
                elif state.status == GameConstants.Status.NEW_DEAL_READY:
                    # Новая раздача
                    status = handle_new_deal(engine, state)
                    
                # Игровой процесс
                elif GameConstants.Status.TRUMP_SELECTED.value <= status.value < GameConstants.Status.TRICK_COMPLETED.value:
                    # Обработка ходов игроков
                    while state.status != GameConstants.Status.TRICK_COMPLETED:
                        status = handle_player_turn(engine, state)
                        if status == GameConstants.Status.GAME_FINISHED:
                            # game_finished = True
                            break
                    
                # Завершение кона
                elif state.status == GameConstants.Status.TRICK_COMPLETED:
                    status, winning_card, winning_player_index, trick_points = engine.complete_turn()
                    print(f"Взятку забрал игрок {state.players[winning_player_index]} "
                          f"картой {winning_card}! Начислили: {trick_points}")
                
                # Завершение игры
                elif state.status == GameConstants.Status.GAME_COMPLETED:
                    status, scores, losing_team, losing_points = engine.complete_game()
                    team1_players = f"{state.players[GameConstants.PLAYER_1_1]} и {state.players[GameConstants.PLAYER_1_2]}"
                    team2_players = f"{state.players[GameConstants.PLAYER_2_1]} и {state.players[GameConstants.PLAYER_2_2]}"
                    
                    print(f"""Раздача завершилась!
    Хвалил игрок {state.players[state.first_player_index]}, счет: {team1_players} | {scores[GameConstants.TEAM_1]}-{scores[GameConstants.TEAM_2]} | {team2_players}
    Начислили очки ({losing_points}) для {state.players[losing_team + 1]} и {state.players[losing_team + 2]}""")
            
            # Завершение матча, если одна из команд набрала 12+ очков
            if status == GameConstants.Status.MATCH_COMPLETED:
                status = engine.complete_match()
                print(f"""Игра закончилась!
    {state.players[losing_team + 1]} и {state.players[losing_team + 2]} - проиграли(
    Счет: {state.match_scores[GameConstants.TEAM_1]}-{state.match_scores[GameConstants.TEAM_2]}\n""")
                return state.status.value, state
        
        elif input_command in ('m',):  # Вернуться в меню
            state.set_status(GameConstants.Status.GAME_FINISHED)
            return state.status.value, state
        else:
            print("Чтобы начать игру введите `s`, чтобы вернуться в меню - `m`\n")
    else:
        return state.status.value, state
    return status_code, state


if __name__ == "__main__":
    """Точка входа в программу при запуске скрипта напрямую."""
    try:
        status_code = 0
        state = None
        # Основной цикл программы
        while status_code >= 0:
            status_code, state = main(status_code, state)
            
    except KeyboardInterrupt:
        print("\nИгра прервана пользователем. До свидания!")
    # except Exception as e:
    #     print(f"\nПроизошла ошибка: {e}")
    #     print("Игра завершена.")
