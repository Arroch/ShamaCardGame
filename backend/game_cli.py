from game_api import GameAPI

def main():
    print("Запуск тестового CLI для игры Шама")
    api = GameAPI()
    session_id = "cli_session"
    
    # Создаем игроков
    players = ["Player1", "Player2", "Player3", "Player4"]
    api.start_new_game(session_id, players)
    
    # Получаем начальное состояние
    state = api.get_game_state(session_id)
    
    # Установка козыря
    print(f"\nИгрок {state['first_player']}, у вас шестерка треф - установите козырь")
    print("Доступные масти:")
    suits = ['♠', '♥', '♦', '♣']
    for i, suit in enumerate(suits, 1):
        print(f"{i}. {suit}")
    
    try:
        choice = int(input("Введите номер масти для козыря: "))
        if 1 <= choice <= 4:
            # Используем системный вызов для установки козыря
            api.make_move(session_id, "system", choice-1)
        else:
            print("Недопустимый выбор, устанавливаем ♣ по умолчанию")
            api.make_move(session_id, "system", 2)  # ♣
    except ValueError:
        print("Ошибка ввода, устанавливаем ♣ по умолчанию")
        api.make_move(session_id, "system", 2)  # ♣
    
    # Обновляем состояние после установки козыря
    state = api.get_game_state(session_id)
    
    # Основной игровой цикл
    while state['status'] != 'completed':
        current_player_id = state['current_player_id']
        current_player = next(p for p in state['players'] if p['id'] == current_player_id)
        
        print(f"\nХод игрока {current_player['name']} (ID: {current_player_id})")
        
        # Выводим текущие карты на столе
        if state['current_trick']:
            print(f"Карты на столе: {' '.join(state['current_trick'])}")
        else:
            print("Ваш ход первый!")
        
        # Выводим карты игрока с индексами
        print("\nВаши карты:")
        for i, card in enumerate(current_player['hand']):
            print(f"{i}: {card}")
        
        try:
            card_index = int(input("Выберите индекс карты для хода: "))
            # Совершаем ход через API
            state = api.make_move(session_id, current_player_id, card_index)
            
            # Выводим обновленное состояние стола
            if state['current_trick']:
                print(f"\nОбновленные карты на столе: {' '.join(state['current_trick'])}")
        except Exception as e:
            print(f"Ошибка: {e}")
            state = api.get_game_state(session_id)
    
    # Игра завершена
    print("\nИгра завершена!")
    print(f"Команда 1: {state['scores']['1']} очков")
    print(f"Команда 2: {state['scores']['2']} очков")
    
    # Определение победителя
    if state['scores']['1'] > state['scores']['2']:
        print("Победила команда 1!")
    elif state['scores']['2'] > state['scores']['1']:
        print("Победила команда 2!")
    else:
        print("Ничья!")

if __name__ == "__main__":
    main()
