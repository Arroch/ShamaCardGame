from core import MatchState, GameEngine, Player, Card
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
    print("""Карточная игра Шама (6♣)
    МЕНЮ
    1. Новая игра
    2. Правила
    3. Выход
            """)
    try:
        input_comand = input("Введите число для выбора действия меню\n")
        return int(input_comand) if input_comand != '3' else -1
    except ValueError:
        print("Нужно ввести число")
        return 0

def show_hand(hand):
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
    print(f"""
Статус игры:
{state.players[11]} и {state.players[12]} - счет: {state.match_scores[10]}
{state.players[21]} и {state.players[22]} - счет: {state.match_scores[20]}
""")
    print(f"Козырь: {Card.SUIT_SYMBOLS[state.trump]}")
    print(f"Номер хода: {state.current_turn}")
    print(f"Карты на столе:", end=' ')
    state.show_table()

def create_match():
    player_name_11 = input("Введите имя первого игрока первой команды\n")
    player_name_12 = input("Введите имя второго игрока первой команды\n")
    player_name_21 = input("Введите имя первого игрока второй команды\n")
    player_name_22 = input("Введите имя второго игрока второй команды\n")
    state = MatchState()
    try:
        state.add_player(11, Player(1, player_name_11))
        state.add_player(12, Player(2, player_name_12))
        state.add_player(21, Player(3, player_name_21))
        state.add_player(22, Player(4, player_name_22))
    except Exception as e:
        return state, e

    return state.status_code, state, "Good"

def main(status_code, state):
    SUITS = ['clubs', 'spades', 'hearts', 'diamonds']
    status_code = show_menu() if status_code != 104 else status_code
    if status_code == 3:
        return -100
    elif status_code == 2:
        show_rules()
    elif status_code == 1:
        status_code, state, e = create_match()
        print(state.status_code, state.players, e)
        
        if status_code == 104:
            print(f"""
    Игроки в игре:
    Команад 1 - {state.players[11]} и {state.players[12]}
    Команад 2 - {state.players[21]} и {state.players[22]}
    Чтобы начать игру введите `s`, чтобы вернуться в меню - `m`
            """)
    if status_code == 104:
        input_comand = input()
        if input_comand == 's':
            engine = GameEngine(state)
            while status_code < 600:
                if state.status_code == 104:
                    status_code, f_player = engine.start_game()
                elif state.status_code == 500:
                    input_comand = input(f"Начать новую раздачу\ny - да, f - завершить игру и выйти в меню\n").lower()
                    if input_comand == 'y':
                        print(f"Новая раздача!")
                        print(f"Cчет: {state.players[11]} и {state.players[12]} | {state.match_scores[10]}-{state.match_scores[20]} | {state.players[21]} и {state.players[22]}")
                        status_code, f_player = engine.start_game()
                    elif input_comand == 'f':
                        state.set_status_code(700)
                        status_code = state.status_code

                if status_code == 202:
                    print(f"Игрок с шамой: {f_player}")
                    input_comand = input(
                        f"Показать карты игрока {f_player}\ny - да, re - перераздача, f - завершить игру и выйти в меню\n"
                    ).lower()

                    match input_comand:
                        case 'y':
                            print(state.players[state.first_player_index].get_hand())
                            suit = SUITS[int(input("Выебрите козырь:\n1 - '♣', 2 - '♠', 3 - '♥', 4 - '♦'\n")) - 1]
                            try:
                                status_code, player_name, trump = engine.set_trump_by_player(state.first_player_index, suit)
                                print("\033c\033[3J", end="")
                                print(f"Игрок: {player_name} выбрал козырь: {Card.SUIT_SYMBOLS[trump]}")
                            except ValueError as e:
                                print(f"Статус: {status_code}, Ошибка: {e}", )
                        case 're':
                            state.set_status_code(104)
                            status_code = state.status_code
                        case 'f':
                            state.set_status_code(700)
                            status_code = 700
                if 409 > status_code >= 203:
                    while state.status_code < 304:
                        print(f"Ходит игрок: {state.players[state.current_player_index]}")
                        input_comand = input(
                            f"Показать карты игрока {state.players[state.current_player_index]}\ny - да, f - завершить игру и выйти в меню\n"
                        ).lower()
                        match input_comand:
                            case 'y':
                                show_state(state)
                                print('Выши карты:')
                                show_hand(state.players[state.current_player_index].get_hand())
                                try:
                                    input_comand = int(input(
                                        f"Выберите номер карты для хода\n"
                                    ))
                                    try:
                                        status_code, player, card = engine.play_turn(state.current_player_index, input_comand - 1)
                                        print("\033c\033[3J", end="")
                                        print(f"Игрок {player} сыграл: {card}")
                                    except IndexError:
                                        print("У вас нет такой карты!")
                                except ValueError:
                                    print("Нужно ввести число")
                            case 'f':
                                state.set_status_code(700)
                                status_code = 0
                if status_code == 304:
                    status_code, winning_card, winning_player_index, trick_points = engine.complete_turn()
                    print(f"Взятку забрал игрок {state.players[winning_player_index]} картой {winning_card}! Начислили: {trick_points}")

                if status_code == 409:
                    status_code, scores, losed_team, losed_points = engine.complete_game()
                    print(f"""Раздача завершилась!
    Хвалил игрок {state.players[state.first_player_index]}, счет: {state.players[11]} и {state.players[12]} | {scores[10]}-{scores[20]} | {state.players[21]} и {state.players[22]}
    Начислили очки ({losed_points}) для {state.players[losed_team + 1]} и {state.players[losed_team + 2]}""")
        elif input_comand == 'm':
            state.set_status_code(700)
            status_code = state.status_code
        else:
            print("Чтобы начать игру введите `s`, чтобы вернуться в меню - `m`\n")

        if status_code == 600:
            status_code = engine.complete_match()
            print(f"""Игра закочилась!
    {state.players[losed_team + 1]} и {state.players[losed_team + 2]} - проиграли(
    Cчет: {state.match_scores[10]}-{state.match_scores[20]}\n""")
    return status_code, state


if __name__ == "__main__":
    status_code = 0
    state = None
    while status_code >= 0:
        status_code, state = main(status_code, state)

