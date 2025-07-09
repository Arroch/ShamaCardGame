"""
Веб-интерфейс для игры в Шаму
Использует Flask для предоставления API и веб-страниц
"""

from flask import Flask, jsonify, render_template, request
from .game_api import GameAPI
import os

app = Flask(__name__)
api = GameAPI()

@app.route('/')
def index():
    """Главная страница с интерфейсом игры"""
    return render_template('index.html')

@app.route('/api/game/start', methods=['POST'])
def start_game():
    """Создать новую игровую сессию"""
    data = request.json
    session_id = data.get('session_id')
    players = data.get('players', [])
    
    if not session_id or not players:
        return jsonify({'error': 'Не указан session_id или players'}), 400
    
    try:
        state = api.start_new_game(session_id, players)
        return jsonify(state), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/game/<session_id>/state', methods=['GET'])
def get_state(session_id):
    """Получить текущее состояние игры"""
    try:
        state = api.get_game_state(session_id)
        return jsonify(state), 200
    except ValueError:
        return jsonify({'error': 'Игра не найдена'}), 404

@app.route('/api/game/<session_id>/move', methods=['POST'])
def make_move(session_id):
    """Совершить ход в игре"""
    data = request.json
    player_id = data.get('player_id')
    move = data.get('move')
    
    if not player_id or move is None:
        return jsonify({'error': 'Не указан player_id или move'}), 400
    
    try:
        state = api.make_move(session_id, player_id, move)
        return jsonify(state), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
