"""
Модуль для работы с базой данных для игры Шама.

Обеспечивает взаимодействие с PostgreSQL для хранения
информации об играх, игроках, матчах и логирования событий.

Автор: ShamaVibe Team
"""

import logging
import os
from typing import Dict, List, Optional, Any, Tuple

import psycopg2
from psycopg2 import pool
from psycopg2.extras import DictCursor, Json

from constants import GameConstants

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class DatabaseManager:
    """Класс для работы с базой данных PostgreSQL."""
    
    def __init__(self, connection_params: Optional[Dict[str, Any]] = None):
        """
        Инициализация менеджера базы данных.
        
        :param connection_params: Параметры подключения к базе данных
                                 (если None, используются переменные окружения)
        """
        if connection_params is None:
            # Получаем параметры из переменных окружения
            self.connection_params = {
                'host': os.environ.get('DB_HOST', 'localhost'),
                'port': os.environ.get('DB_PORT', '5432'),
                'database': os.environ.get('DB_NAME', 'shama_game'),
                'user': os.environ.get('DB_USER', 'postgres'),
                'password': os.environ.get('DB_PASSWORD', '')
            }
        else:
            self.connection_params = connection_params
        
        # Создаем пул соединений
        try:
            self.connection_pool = psycopg2.pool.SimpleConnectionPool(
                1, 10, **self.connection_params
            )
            logger.info("Пул соединений с базой данных создан успешно")
        except Exception as e:
            logger.error(f"Ошибка при создании пула соединений с БД: {e}")
            self.connection_pool = None
    
    def get_connection(self):
        """Получает соединение из пула."""
        if self.connection_pool:
            return self.connection_pool.getconn()
        return None
    
    def return_connection(self, conn):
        """Возвращает соединение в пул."""
        if self.connection_pool:
            self.connection_pool.putconn(conn)
    
    def init_database(self):
        """Инициализирует структуру базы данных, если она не существует."""
        conn = self.get_connection()
        if not conn:
            logger.error("Не удалось получить соединение с БД для инициализации")
            return
        
        try:
            with conn.cursor() as cur:
                # Создаем таблицы, если их нет
                
                # Таблица PLAYERS
                cur.execute("""
                CREATE TABLE IF NOT EXISTS players (
                    id SERIAL PRIMARY KEY,
                    tg_id BIGINT UNIQUE NOT NULL,
                    name VARCHAR(255) NOT NULL,
                    games INTEGER DEFAULT 0,
                    wins INTEGER DEFAULT 0,
                    total_tricks INTEGER DEFAULT 0,
                    total_shama_calls INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """)
                
                # Таблица MATCHES
                cur.execute("""
                CREATE TABLE IF NOT EXISTS matches (
                    id SERIAL PRIMARY KEY,
                    start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    end_time TIMESTAMP,
                    player_11 INTEGER REFERENCES players(id),
                    player_12 INTEGER REFERENCES players(id),
                    player_21 INTEGER REFERENCES players(id),
                    player_22 INTEGER REFERENCES players(id),
                    winning_team INTEGER,
                    total_score_1 INTEGER DEFAULT 0,
                    total_score_2 INTEGER DEFAULT 0
                );
                """)
                
                # Таблица GAMES (раздачи)
                cur.execute("""
                CREATE TABLE IF NOT EXISTS games (
                    id SERIAL PRIMARY KEY,
                    match_id INTEGER REFERENCES matches(id),
                    trump VARCHAR(10),
                    shama_player INTEGER,
                    hand_11 JSONB,
                    hand_12 JSONB,
                    hand_21 JSONB,
                    hand_22 JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """)
                
                # Таблица TURNS (ходы)
                cur.execute("""
                CREATE TABLE IF NOT EXISTS turns (
                    id SERIAL PRIMARY KEY,
                    game_id INTEGER REFERENCES games(id),
                    match_id INTEGER REFERENCES matches(id),
                    first_player INTEGER,
                    card_11 VARCHAR(10),
                    card_12 VARCHAR(10),
                    card_21 VARCHAR(10),
                    card_22 VARCHAR(10),
                    loot_value INTEGER,
                    looting_team INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """)
                
                # Таблица EVENTS (события)
                cur.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id SERIAL PRIMARY KEY,
                    tg_id BIGINT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    event_type VARCHAR(50),
                    event_data JSONB
                );
                """)
                
                conn.commit()
                logger.info("Структура базы данных инициализирована успешно")
        except Exception as e:
            conn.rollback()
            logger.error(f"Ошибка при инициализации базы данных: {e}")
        finally:
            self.return_connection(conn)
    
    def get_player_by_tg_id(self, tg_id: int) -> Optional[Dict[str, Any]]:
        """
        Получает информацию об игроке по его Telegram ID.
        
        :param tg_id: Telegram ID игрока
        :return: Информация об игроке или None, если игрок не найден
        """
        conn = self.get_connection()
        if not conn:
            return None
        
        try:
            with conn.cursor(cursor_factory=DictCursor) as cur:
                cur.execute(
                    "SELECT * FROM players WHERE tg_id = %s",
                    (tg_id,)
                )
                result = cur.fetchone()
                if result:
                    return dict(result)
                return None
        except Exception as e:
            logger.error(f"Ошибка при получении информации об игроке: {e}")
            return None
        finally:
            self.return_connection(conn)
    
    def create_player(self, tg_id: int, name: str) -> Optional[int]:
        """
        Создает нового игрока в базе данных.
        
        :param tg_id: Telegram ID игрока
        :param name: Имя игрока
        :return: ID игрока в базе данных или None в случае ошибки
        """
        conn = self.get_connection()
        if not conn:
            return None
        
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO players (tg_id, name) VALUES (%s, %s) RETURNING id",
                    (tg_id, name)
                )
                player_id = cur.fetchone()[0]
                conn.commit()
                logger.info(f"Создан новый игрок: {name} (ID: {player_id})")
                return player_id
        except Exception as e:
            conn.rollback()
            logger.error(f"Ошибка при создании игрока: {e}")
            return None
        finally:
            self.return_connection(conn)
    
    def get_or_create_player(self, tg_id: int, name: str) -> Optional[Dict[str, Any]]:
        """
        Получает информацию об игроке или создает нового, если не существует.
        
        :param tg_id: Telegram ID игрока
        :param name: Имя игрока
        :return: Информация об игроке или None в случае ошибки
        """
        player = self.get_player_by_tg_id(tg_id)
        if player:
            return player
        
        player_id = self.create_player(tg_id, name)
        if player_id:
            return self.get_player_by_tg_id(tg_id)
        return None
    
    def create_match(self, player_ids: Dict[int, int]) -> Optional[int]:
        """
        Создает новый матч в базе данных.
        
        :param player_ids: Словарь {позиция игрока: ID игрока в БД}
        :return: ID матча в базе данных или None в случае ошибки
        """
        conn = self.get_connection()
        if not conn:
            return None
        
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO matches (
                        player_11, player_12, player_21, player_22
                    ) VALUES (%s, %s, %s, %s) RETURNING id
                    """,
                    (
                        player_ids.get(GameConstants.PLAYER_1_1),
                        player_ids.get(GameConstants.PLAYER_1_2),
                        player_ids.get(GameConstants.PLAYER_2_1),
                        player_ids.get(GameConstants.PLAYER_2_2)
                    )
                )
                match_id = cur.fetchone()[0]
                conn.commit()
                logger.info(f"Создан новый матч (ID: {match_id})")
                return match_id
        except Exception as e:
            conn.rollback()
            logger.error(f"Ошибка при создании матча: {e}")
            return None
        finally:
            self.return_connection(conn)
    
    def create_game(self, match_id: int, trump: str, shama_player: int,
                   hands: Dict[int, List[Dict[str, str]]]) -> Optional[int]:
        """
        Создает новую раздачу в базе данных.
        
        :param match_id: ID матча
        :param trump: Козырь
        :param shama_player: Позиция игрока с шамой
        :param hands: Словарь {позиция игрока: список карт}
        :return: ID раздачи в базе данных или None в случае ошибки
        """
        conn = self.get_connection()
        if not conn:
            return None
        
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO games (
                        match_id, trump, shama_player,
                        hand_11, hand_12, hand_21, hand_22
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id
                    """,
                    (
                        match_id, trump, shama_player,
                        Json(hands.get(GameConstants.PLAYER_1_1, [])),
                        Json(hands.get(GameConstants.PLAYER_1_2, [])),
                        Json(hands.get(GameConstants.PLAYER_2_1, [])),
                        Json(hands.get(GameConstants.PLAYER_2_2, []))
                    )
                )
                game_id = cur.fetchone()[0]
                conn.commit()
                logger.info(f"Создана новая раздача (ID: {game_id}) в матче {match_id}")
                return game_id
        except Exception as e:
            conn.rollback()
            logger.error(f"Ошибка при создании раздачи: {e}")
            return None
        finally:
            self.return_connection(conn)
    
    def create_turn(self, game_id: int, match_id: int, first_player: int,
                   cards: Dict[int, str], loot_value: int, looting_team: int) -> Optional[int]:
        """
        Сохраняет ход в базе данных.
        
        :param game_id: ID раздачи
        :param match_id: ID матча
        :param first_player: Позиция игрока, который ходил первым
        :param cards: Словарь {позиция игрока: карта}
        :param loot_value: Стоимость взятки
        :param looting_team: Команда, забравшая взятку
        :return: ID хода в базе данных или None в случае ошибки
        """
        conn = self.get_connection()
        if not conn:
            return None
        
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO turns (
                        game_id, match_id, first_player,
                        card_11, card_12, card_21, card_22,
                        loot_value, looting_team
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
                    """,
                    (
                        game_id, match_id, first_player,
                        cards.get(GameConstants.PLAYER_1_1, ""),
                        cards.get(GameConstants.PLAYER_1_2, ""),
                        cards.get(GameConstants.PLAYER_2_1, ""),
                        cards.get(GameConstants.PLAYER_2_2, ""),
                        loot_value, looting_team
                    )
                )
                turn_id = cur.fetchone()[0]
                conn.commit()
                logger.info(f"Сохранен ход (ID: {turn_id}) в раздаче {game_id}")
                return turn_id
        except Exception as e:
            conn.rollback()
            logger.error(f"Ошибка при сохранении хода: {e}")
            return None
        finally:
            self.return_connection(conn)
    
    def update_match(self, match_id: int, winning_team: int, team1_score: int, team2_score: int) -> bool:
        """
        Обновляет информацию о матче после его завершения.
        
        :param match_id: ID матча
        :param winning_team: Команда-победитель
        :param team1_score: Счет первой команды
        :param team2_score: Счет второй команды
        :return: True в случае успеха, False в случае ошибки
        """
        conn = self.get_connection()
        if not conn:
            return False
        
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE matches SET
                        end_time = CURRENT_TIMESTAMP,
                        winning_team = %s,
                        total_score_1 = %s,
                        total_score_2 = %s
                    WHERE id = %s
                    """,
                    (winning_team, team1_score, team2_score, match_id)
                )
                conn.commit()
                logger.info(f"Обновлена информация о матче (ID: {match_id})")
                return True
        except Exception as e:
            conn.rollback()
            logger.error(f"Ошибка при обновлении информации о матче: {e}")
            return False
        finally:
            self.return_connection(conn)
    
    def update_player_stats(self, player_id: int, won: bool, tricks: int, shama_calls: int = 0) -> bool:
        """
        Обновляет статистику игрока.
        
        :param player_id: ID игрока в базе данных
        :param won: True если игрок выиграл матч
        :param tricks: Количество взяток, взятых игроком
        :param shama_calls: Количество раз, когда игрок объявлял козырь
        :return: True в случае успеха, False в случае ошибки
        """
        conn = self.get_connection()
        if not conn:
            return False
        
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE players SET
                        games = games + 1,
                        wins = wins + %s,
                        total_tricks = total_tricks + %s,
                        total_shama_calls = total_shama_calls + %s
                    WHERE id = %s
                    """,
                    (1 if won else 0, tricks, shama_calls, player_id)
                )
                conn.commit()
                logger.info(f"Обновлена статистика игрока (ID: {player_id})")
                return True
        except Exception as e:
            conn.rollback()
            logger.error(f"Ошибка при обновлении статистики игрока: {e}")
            return False
        finally:
            self.return_connection(conn)
    
    def log_event(self, tg_id: Optional[int], event_type: str, event_data: Dict[str, Any]) -> Optional[int]:
        """
        Логирует событие в базе данных.
        
        :param tg_id: Telegram ID игрока (может быть None)
        :param event_type: Тип события
        :param event_data: Данные события
        :return: ID события в базе данных или None в случае ошибки
        """
        conn = self.get_connection()
        if not conn:
            return None
        
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO events (tg_id, event_type, event_data)
                    VALUES (%s, %s, %s) RETURNING id
                    """,
                    (tg_id, event_type, Json(event_data))
                )
                event_id = cur.fetchone()[0]
                conn.commit()
                logger.info(f"Событие {event_type} залогировано (ID: {event_id})")
                return event_id
        except Exception as e:
            conn.rollback()
            logger.error(f"Ошибка при логировании события: {e}")
            return None
        finally:
            self.return_connection(conn)
    
    def get_player_stats(self, tg_id: int) -> Optional[Dict[str, Any]]:
        """
        Получает расширенную статистику игрока.
        
        :param tg_id: Telegram ID игрока
        :return: Статистика игрока или None в случае ошибки
        """
        conn = self.get_connection()
        if not conn:
            return None
        
        try:
            with conn.cursor(cursor_factory=DictCursor) as cur:
                cur.execute(
                    """
                    SELECT 
                        name, games, wins, total_tricks, total_shama_calls,
                        CASE WHEN games > 0 THEN ROUND(wins::float / games * 100, 1) ELSE 0 END AS win_rate
                    FROM players
                    WHERE tg_id = %s
                    """,
                    (tg_id,)
                )
                result = cur.fetchone()
                if result:
                    return dict(result)
                return None
        except Exception as e:
            logger.error(f"Ошибка при получении статистики игрока: {e}")
            return None
        finally:
            self.return_connection(conn)
    
    def close(self):
        """Закрывает пул соединений с базой данных."""
        if self.connection_pool:
            self.connection_pool.closeall()
            logger.info("Пул соединений с базой данных закрыт")
