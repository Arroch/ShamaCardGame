from game_logic import GameEngine

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
    
    # Создаем колоду и устанавливаем козырь
    engine.deck = engine.create_deck()
    engine.state.set_trump("clubs")
    
    print(f"Колода создана: {len(engine.deck)} карт")
    print(f"Козырь: {engine.state.trump}")
    
    # Тестовая карта
    test_card = engine.deck[0]
    players[0].add_card(test_card)
    print(f"Игрок 1 получил карту: {test_card}")

if __name__ == "__main__":
    main()
