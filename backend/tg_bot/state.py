"""Глобальное in-memory состояние бота."""

WAITING_MATCHES: dict = {}   # {match_id: {creator_id, players, team_1, team_2, timestamp}}
ACTIVE_MATCHES: dict = {}    # {match_id: MatchState}
HOLDING_MATCHES: dict = {}   # {match_id: MatchState}
MATCH_ENGINES: dict = {}     # {match_id: GameEngine}
PLAYER_TO_GAME: dict = {}    # {player_id: {id, status, position}}

storage = None   # FileStorage / DatabaseManager
_bot = None      # Shared telegram Bot, устанавливается в run_bot()
