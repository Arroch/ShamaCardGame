"""
Модуль для работы с файловым хранилищем для игры Шама.

Обеспечивает хранение данных в CSV-файлах без необходимости 
использования PostgreSQL.

Автор: ShamaVibe Team
"""

import os
import csv
import json
import logging
import uuid
import datetime
from typing import Dict, List, Optional, Any, Tuple

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class FileStorage:
    """Класс для работы с файловым хранилищем."""
    
    def __init__(self, storage_dir: Optional[str] = None):
        """
        Инициализация менеджера файлового хранилища.
        
        :param storage_dir: Директория для хранения файлов
                          (если None, используется './storage')
        """
        self.storage_dir = storage_dir or os.path.join(os.path.dirname(__file__), 'storage')
        
        # Создаем директории для хранения данных
        self.players_dir = os.path.join(self.storage_dir, 'players')
        self.matches_dir = os.path.join(self.storage_dir, 'matches')
        self.games_dir = os.path.join(self.storage_dir, 'games')
        self.turns_dir = os.path.join(self.storage_dir, 'turns')
        self.events_dir = os.path.join(self.storage_dir, 'events')
        
        # Создаем директории, если они не существуют
        for directory in [self.storage_dir, self.players_dir, self.matches_dir, 
                         self.games_dir, self.turns_dir, self.events_dir]:
            if not os.path.exists(directory):
                os.makedirs(directory)
        
        # Файлы с данными
        self.players_file = os.path.join(self.players_dir, 'players.csv')
        self.matches_file = os.path.join(self.matches_dir, 'matches.csv')
        self.games_file = os.path.join(self.games_dir, 'games.csv')
        self.turns_file = os.path.join(self.turns_dir, 'turns.csv')
        
        # Инициализируем файлы, если они не существуют
        self._init_files()
    
    def _init_files(self):
        """Инициализирует структуру файлов, если они не существуют."""
        # Игроки
        if not os.path.exists(self.players_file):
            with open(self.players_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['id', 'username', 'name', 'games', 'wins', 
                                'total_tricks', 'total_shama_calls', 'created_at'])
        
        # Матчи
        if not os.path.exists(self.matches_file):
            with open(self.matches_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['match_id', 'start_time', 'end_time', 'player_11', 'player_12', 
                                'player_21', 'player_22', 'winning_team', 'total_score_1', 
                                'total_score_2'])
        
        # Игры (раздачи)
        if not os.path.exists(self.games_file):
            with open(self.games_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['match_id', 'game_id', 'trump', 'shama_player', 
                                'hand_11', 'hand_12', 'hand_21', 'hand_22', 'created_at'])
        
        # Ходы
        if not os.path.exists(self.turns_file):
            with open(self.turns_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['match_id', 'game_id', 'turn_id', 'first_player', 
                                'card_11', 'card_12', 'card_21', 'card_22', 
                                'loot_value', 'looting_team', 'created_at'])
    
    async def init_database(self):
        """Инициализирует хранилище данных."""
        logger.info("Файловое хранилище инициализировано")
    
    async def create_player(self, tg_id: int, tg_username: str, tg_first_name: str) -> Optional[Dict[str, Any]]:
        """
        Создает нового игрока в хранилище.
        
        :param tg_id: Telegram ID игрока
        :param name: Имя игрока
        """
        p = {
            'id': tg_id,
            'username': tg_username,
            'name': tg_first_name,
            'games': 0,
            'wins': 0,
            'total_tricks': 0,
            'total_shama_calls': 0,
            'created_at': datetime.datetime.now().isoformat()
        }

        try:
            # Добавляем игрока в файл
            with open(self.players_file, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(list(p.values()))
            
            logger.info(f"Создан новый игрок: {tg_first_name} (ID: {tg_id} username: {tg_username})")
            return p
        except Exception as e:
            logger.error(f"Ошибка при создании игрока: {e}")
            return None
    
    async def get_or_create_player(self, id: int, username: str, first_name: str) -> Optional[Dict[str, Any]]:
        """
        Получает информацию об игроке.
        
        :param id: ID игрока = Telegram ID
        :return: Информация об игроке или None в случае ошибки
        """
        try:
            with open(self.players_file, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if int(row['id']) == id:
                        # Конвертируем строковые значения в числа
                        row['id'] = int(row['id'])
                        row['games'] = int(row['games'])
                        row['wins'] = int(row['wins'])
                        row['total_tricks'] = int(row['total_tricks'])
                        row['total_shama_calls'] = int(row['total_shama_calls'])
                        return row
            return await self.create_player(id, username, first_name)
        except Exception as e:
            logger.error(f"Ошибка при получении информации об игроке: {e}")
            return None
    
    async def create_match(self, match_id: int, player_ids: Dict[int, int]) -> Optional[int]:
        """
        Создает новый матч в хранилище.
        
        :param match_id: уникальный ID матча
        :param player_ids: Словарь {позиция игрока: ID игрока в хранилище}
        """
        try:
            # Добавляем матч в файл
            with open(self.matches_file, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    match_id, 
                    datetime.datetime.now().isoformat(),
                    '',  # end_time
                    player_ids.get(11, ''),
                    player_ids.get(12, ''),
                    player_ids.get(21, ''),
                    player_ids.get(22, ''),
                    '',  # winning_team
                    0,   # total_score_1
                    0    # total_score_2
                ])
            
            logger.info(f"Создан новый матч (ID: {match_id})")
        except Exception as e:
            logger.error(f"Ошибка при создании матча: {e}")
    
    async def create_game(self, match_id: int, game_id: int, trump: str, shama_player: int,
                   hands: Dict[int, List[Dict[str, str]]]) -> Optional[int]:
        """
        Создает новую раздачу в хранилище.
        
        :param match_id: ID матча
        :param game_id: ID раздачи
        :param trump: Козырь
        :param shama_player: Позиция игрока с шамой
        :param hands: Словарь {позиция игрока: список карт}
        """
        try:
            # Преобразуем руки в JSON строки
            hand_11 = json.dumps(hands.get(11, []))
            hand_12 = json.dumps(hands.get(12, []))
            hand_21 = json.dumps(hands.get(21, []))
            hand_22 = json.dumps(hands.get(22, []))
            
            # Добавляем игру в файл
            with open(self.games_file, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    game_id, 
                    match_id,
                    trump,
                    shama_player,
                    hand_11,
                    hand_12,
                    hand_21,
                    hand_22,
                    datetime.datetime.now().isoformat()
                ])
            
            logger.info(f"Создана новая раздача (ID: {game_id}) в матче {match_id}")
        except Exception as e:
            logger.error(f"Ошибка при создании раздачи: {e}")
    
    async def create_turn(self, match_id: int, game_id: int, turn_id: int, first_player: int,
                   cards: Dict[int, str], loot_value: int, looting_team: int) -> Optional[int]:
        """
        Сохраняет ход в хранилище.
        
        :param match_id: ID матча
        :param game_id: ID раздачи
        :param turn_id: ID хода
        :param first_player: Позиция игрока, который ходил первым
        :param cards: Словарь {позиция игрока: карта}
        :param loot_value: Стоимость взятки
        :param looting_team: Команда, забравшая взятку
        """
        try:
            # Добавляем ход в файл
            with open(self.turns_file, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    match_id,
                    game_id,
                    turn_id,
                    first_player,
                    cards.get(11, ''),
                    cards.get(12, ''),
                    cards.get(21, ''),
                    cards.get(22, ''),
                    loot_value,
                    looting_team,
                    datetime.datetime.now().isoformat()
                ])
            
            logger.info(f"Сохранен ход (ID: {turn_id}) в раздаче {game_id} в матче {match_id}")
        except Exception as e:
            logger.error(f"Ошибка при сохранении хода: {e}")
    
    async def update_match(self, match_id: int, winning_team: int, team1_score: int, team2_score: int) -> bool:
        """
        Обновляет информацию о матче после его завершения.
        
        :param match_id: ID матча
        :param winning_team: Команда-победитель
        :param team1_score: Счет первой команды
        :param team2_score: Счет второй команды
        :return: True в случае успеха, False в случае ошибки
        """
        try:
            # Читаем текущие данные о матчах
            matches = []
            with open(self.matches_file, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    matches.append(row)
            
            # Обновляем информацию о матче
            for match in matches:
                if match['match_id'] == match_id:
                    match['end_time'] = datetime.datetime.now().isoformat()
                    match['winning_team'] = winning_team
                    match['total_score_1'] = team1_score
                    match['total_score_2'] = team2_score
            
            # Перезаписываем файл с обновленными данными
            with open(self.matches_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=matches[0].keys())
                writer.writeheader()
                writer.writerows(matches)
            
            logger.info(f"Обновлена информация о матче (ID: {match_id})")
            return True
        except Exception as e:
            logger.error(f"Ошибка при обновлении информации о матче: {e}")
            return False
    
    async def update_player_stats(self, player_id: int, won: bool, tricks: int, shama_calls: int = 0) -> bool:
        """
        Обновляет статистику игрока.
        
        :param player_id: ID игрока в хранилище
        :param won: True если игрок выиграл матч
        :param tricks: Количество взяток, взятых игроком
        :param shama_calls: Количество раз, когда игрок объявлял козырь
        :return: True в случае успеха, False в случае ошибки
        """
        try:
            # Читаем текущие данные об игроках
            players = []
            with open(self.players_file, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    players.append(row)
            
            # Обновляем статистику игрока
            for player in players:
                if int(player['id']) == player_id:
                    player['games'] = int(player['games']) + 1
                    player['wins'] = int(player['wins']) + (1 if won else 0)
                    player['total_tricks'] = int(player['total_tricks']) + tricks
                    player['total_shama_calls'] = int(player['total_shama_calls']) + shama_calls
            
            # Перезаписываем файл с обновленными данными
            with open(self.players_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=players[0].keys())
                writer.writeheader()
                writer.writerows(players)
            
            logger.info(f"Обновлена статистика игрока (ID: {player_id})")
            return True
        except Exception as e:
            logger.error(f"Ошибка при обновлении статистики игрока: {e}")
            return False
    
    async def get_player_stats(self, id: int) -> Optional[Dict[str, Any]]:
        """
        Получает расширенную статистику игрока.
        
        :param id: Telegram ID игрока
        :return: Статистика игрока или None в случае ошибки
        """
        try:
            player = await self.get_or_create_player(id, '', '')
            if not player:
                return None
            
            # Рассчитываем процент побед
            games = int(player['games'])
            wins = int(player['wins'])
            win_rate = round(wins / games * 100, 2) if games > 0 else 0
            
            # Формируем статистику
            stats = {
                'name': player['name'],
                'games': games,
                'wins': wins,
                'win_rate': win_rate,
                'total_tricks': int(player['total_tricks']),
                'total_shama_calls': int(player['total_shama_calls']),
            }
            
            return stats
        except Exception as e:
            logger.error(f"Ошибка при получении статистики игрока: {e}")
            return None
    
    async def log_event(self, player_id: Optional[int], player_username: str, event_type: str, event_data: Dict[str, Any]) -> Optional[int]:
        """
        Логирует событие в файл.
        
        :param tg_id: Telegram ID игрока (может быть None)
        :param event_type: Тип события
        :param event_data: Данные события
        :return: ID события или None в случае ошибки
        """
        try:
            # Генерируем имя файла для события
            event_id = str(uuid.uuid4())
            event_file = os.path.join(self.events_dir, f"event_{event_id}.json")
            
            # Создаем структуру события
            event = {
                'id': event_id,
                'player_id': player_id,
                'player_username': player_username,
                'timestamp': datetime.datetime.now().isoformat(),
                'event_type': event_type,
                'event_data': event_data
            }
            
            # Записываем событие в файл
            with open(event_file, 'w', encoding='utf-8') as f:
                json.dump(event, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Событие {event_type} залогировано (ID: {event_id})")
            return event_id
        except Exception as e:
            logger.error(f"Ошибка при логировании события: {e}")
            return None
    
    def close(self):
        """Закрывает хранилище данных."""
        logger.info("Файловое хранилище закрыто")
