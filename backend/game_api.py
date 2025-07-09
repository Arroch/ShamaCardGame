"""
Центральный API слой для игры в Шаму
Обеспечивает единый интерфейс для всех клиентов (Telegram, CLI, Web)
"""

import json
from datetime import datetime
from .game_logic import GameEngine, GameState

class GameAPI:
    def __init__(self):
        self.active_games = {}  # session_id -> GameEngine
    
    def start_new_game(self, session_id, players):
        """Создать новую игровую сессию"""
        game = GameEngine(players)
        self.active_games[session_id] = game
        self._log_event(session_id, "game_started", game.get_state())
        return game.get_state()
    
    def make_move(self, session_id, player_name, move):
        """Обработать ход игрока"""
        game = self.active_games.get(session_id)
        if not game:
            raise ValueError(f"Игровая сессия {session_id} не найдена")
        
        game.make_move(player_name, move)
        new_state = game.get_state()
        self._log_event(session_id, "move_made", new_state, player=player_name, move=move)
        return new_state
    
    def get_game_state(self, session_id):
        """Получить текущее состояние игры"""
        game = self.active_games.get(session_id)
        if not game:
            raise ValueError(f"Игровая сессия {session_id} не найдена")
        return game.get_state()
    
    def _log_event(self, session_id, event_type, game_state, **kwargs):
        """Унифицированное логгирование событий в JSON формате"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "session_id": session_id,
            "event_type": event_type,
            "game_state": game_state.to_dict(),
            **kwargs
        }
        # Добавляем запись в лог-файл
        with open("game_logs.json", "a") as log_file:
            log_file.write(json.dumps(log_entry) + "\n")

# Пример использования:
# api = GameAPI()
# api.start_new_game("session123", ["Player1", "Player2"])
