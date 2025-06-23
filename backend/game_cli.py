from game_logic import GameEngine, Player

def main():
    print("Запуск тестового CLI для игры Шама")
    engine = GameEngine()
    
    # Создаем игроков
    players = [
        Player(1, 1),
        Player(2, 2),
        Player(3, 1),
        Player(4, 2)
    ]
    
    for player in players:
        engine.state.add_player(player)
    
    # Начинаем игру (раздача карт, определение первого игрока)
    engine.start_game()
    
    # Установка козыря игроком с шестеркой треф
    if engine.first_player_id:
        suits = ['hearts', 'diamonds', 'clubs', 'spades']
        print(f"\nИгрок {engine.first_player_id}, у вас шестерка треф - установите козырь")
        print("Доступные масти:")
        for i, suit in enumerate(suits, 1):
            print(f"{i}. {suit}")
        
        try:
            choice = int(input("Введите номер масти для козыря: "))
            if 1 <= choice <= 4:
                trump_suit = suits[choice-1]
                engine.set_trump_by_player(engine.first_player_id, trump_suit)
            else:
                print("Недопустимый выбор, устанавливаем clubs по умолчанию")
                engine.state.set_trump("clubs")
        except ValueError:
            print("Ошибка ввода, устанавливаем clubs по умолчанию")
            engine.state.set_trump("clubs")
    else:
        print("Шестерка треф не найдена, устанавливаем козырь автоматически")
        engine.state.set_trump("clubs")
    
    # Основной игровой цикл
    game_over = False
    while not game_over:
        current_player = engine.state.players[engine.state.current_player_index]
        print(f"\nХод игрока {current_player.id} (Команда {current_player.team})")
        
        # Выводим карты с индексами
        print("Ваши карты:")
        for i, card in enumerate(current_player.hand):
            print(f"{i}: {card}")
        
        try:
            card_index = int(input("Выберите индекс карты для хода: "))
            engine.play_turn(current_player.id, card_index)
            
            # Проверка завершения игры (9 взяток)
            if len(engine.state.tricks[1]) + len(engine.state.tricks[2]) == 9:
                game_over = True
                print("\nИгра завершена!")
                
                # Подсчет финальных очков по правилам Шамы
                team1_score = engine.state.scores.get(1, 0)
                team2_score = engine.state.scores.get(2, 0)
                
                # Определение команды с шестеркой треф
                six_clubs_team = engine.state.six_clubs_team
                
                # Расчет финальных очков
                final_scores = {1: 0, 2: 0}
                for team in [1, 2]:
                    points = team1_score if team == 1 else team2_score
                    
                    if team == six_clubs_team:
                        if points == 0:
                            final_scores[team] = 12
                        elif points < 30:
                            final_scores[team] = 6
                        elif points < 60:
                            final_scores[team] = 3
                        elif points == 60:
                            final_scores[team] = 2
                        else:
                            final_scores[team] = 0
                    else:
                        if points == 0:
                            final_scores[team] = 6
                        elif points < 30:
                            final_scores[team] = 3
                        elif points < 60:
                            final_scores[team] = 1
                        else:
                            final_scores[team] = 0
                
                print(f"Команда 1: {final_scores[1]} очков")
                print(f"Команда 2: {final_scores[2]} очков")
                
                # Определение победителя
                if final_scores[1] > final_scores[2]:
                    print("Победила команда 1!")
                elif final_scores[2] > final_scores[1]:
                    print("Победила команда 2!")
                else:
                    print("Ничья!")
        except Exception as e:
            print(f"Ошибка: {e}")

if __name__ == "__main__":
    main()
