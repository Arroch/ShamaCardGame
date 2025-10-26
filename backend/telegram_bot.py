"""
Модуль реализации Telegram бота для игры Шама.

Обеспечивает взаимодействие с пользователями через Telegram Bot API
и управление игровыми сессиями.

Автор: ShamaVibe Team
"""

import asyncio
import logging
import os
import json
import uuid
from typing import Dict, List, Optional, Tuple, Any, Set
from dotenv import load_dotenv

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)

from core import GameEngine, MatchState, Player, Card, InvalidPlayerAction, GameException
from game_constants import GameConstants
from storage_factory import StorageFactory

# Загружаем переменные окружения из .env файла
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class GameSession:
    """Класс, представляющий игровую сессию в Telegram.
    
    Инкапсулирует логику игры и взаимодействия с игроками через Telegram.
    """
    
    def __init__(self, game_id: str, creator_id: int, creator_name: str, bot: 'TelegramBotHandler'):
        """
        Инициализация игровой сессии.
        
        :param game_id: Уникальный идентификатор игровой сессии
        :param creator_id: ID создателя игры в Telegram
        :param creator_name: Имя создателя
        :param bot: Экземпляр обработчика Telegram бота
        """
        self.game_id = game_id
        self.invite_code = self._generate_invite_code()
        self.state = MatchState()
        self.state.add_player(GameConstants.PLAYER_1_1, Player(creator_id, creator_name))
        self.engine = GameEngine(self.state)
        self.bot = bot
        self.player_positions: Dict[int, int] = {creator_id: GameConstants.PLAYER_1_1}
        self.message_ids: Dict[int, List[int]] = {}  # chat_id -> list of message IDs
        self.game_state_messages: Dict[int, int] = {}  # player_id -> message_id
        self.waiting_for_trump: bool = False
        self.db_match_id: Optional[int] = None
        self.db_game_id: Optional[int] = None
        
    def _generate_invite_code(self) -> str:
        """Генерирует уникальный код приглашения для игры"""
        import random
        import string
        return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

    def get_invite_link(self) -> str:
        """Создание инвайт-ссылки для присоединения к игре"""
        return f"https://t.me/{self.bot.bot_username}?start=join_{self.invite_code}"
    
    def get_available_positions(self) -> List[int]:
        """Возвращает список доступных позиций для новых игроков"""
        all_positions = [
            GameConstants.PLAYER_1_1, GameConstants.PLAYER_1_2,
            GameConstants.PLAYER_2_1, GameConstants.PLAYER_2_2
        ]
        return [pos for pos in all_positions if self.state.players[pos] is None]
    
    def add_player(self, player_id: int, player_name: str, position: Optional[int] = None) -> bool:
        """
        Добавление игрока в сессию.
        
        :param player_id: ID игрока в Telegram
        :param player_name: Имя игрока
        :param position: Позиция (если None, выбирается первая свободная)
        :return: True если игрок успешно добавлен, иначе False
        """
        available_positions = self.get_available_positions()
        if not available_positions:
            return False
        
        if position is None:
            position = available_positions[0]
        elif position not in available_positions:
            return False
        
        try:
            self.state.add_player(position, Player(player_id, player_name))
            self.player_positions[player_id] = position
            return True
        except GameException:
            return False

    def get_player_position(self, player_id: int) -> Optional[int]:
        """Возвращает позицию игрока в игре по его Telegram ID"""
        return self.player_positions.get(player_id)
    
    def is_player_turn(self, player_id: int) -> bool:
        """Проверяет, ход ли данного игрока сейчас"""
        position = self.get_player_position(player_id)
        if position is None:
            return False
        return position == self.state.current_player_index

    def get_all_players_info(self) -> Dict[int, Dict[str, Any]]:
        """Возвращает информацию обо всех игроках в игре"""
        result = {}
        for position, player in self.state.players.items():
            if player is not None:
                team = position // 10 * 10
                result[player.id] = {
                    'position': position,
                    'name': player.name,
                    'team': team,
                    'is_current': position == self.state.current_player_index,
                    'is_shama_holder': position == self.state.first_player_index,
                    'hand': player.hand
                }
        return result

    async def start_game(self) -> bool:
        """
        Запуск игры.
        
        :return: True если игра успешно запущена, иначе False
        """
        # Проверяем, что есть все 4 игрока
        if self.state.status != GameConstants.Status.PLAYERS_ADDED:
            return False
        
        try:
            # Логируем начало матча в БД
            player_db_ids = {}
            for position, player in self.state.players.items():
                if player is not None:
                    db_player = await self.bot.db_manager.get_or_create_player(player.id, player.name)
                    if db_player:
                        player_db_ids[position] = db_player['id']
            
            # Создаем запись матча в БД
            self.db_match_id = await self.bot.db_manager.create_match(player_db_ids)
            
            # Запускаем игровой движок
            self.engine.start_game()
            
            # Ищем игрока с шамой
            shama_position = self.state.first_player_index
            shama_player = self.state.players[shama_position]
            
            # Отправляем всем сообщение о начале игры и текущем состоянии
            await self.notify_all_players("Игра началась! Раздача карт завершена.")
            
            # Логируем событие начала игры
            await self.bot.db_manager.log_event(
                None,
                "game_started",
                {
                    "game_id": self.game_id,
                    "db_match_id": self.db_match_id,
                    "players": {
                        str(pos): {
                            "id": player.id,
                            "name": player.name
                        } for pos, player in self.state.players.items() if player is not None
                    },
                    "shama_player": shama_position
                }
            )
            
            # Отправляем отдельное сообщение игроку с шамой
            shama_id = shama_player.id
            await self.bot.send_message(
                shama_id,
                f"У вас на руках шестерка треф (шама)! Выберите козырь:",
                reply_markup=self._create_trump_selection_keyboard()
            )
            self.waiting_for_trump = True
            
            # Отправляем текущее состояние всем игрокам
            await self.send_game_state_to_all()
            
            return True
        except Exception as e:
            logger.error(f"Ошибка при запуске игры: {e}")
            return False
    
    def _create_trump_selection_keyboard(self) -> InlineKeyboardMarkup:
        """Создает клавиатуру для выбора козыря"""
        keyboard = [
            [
                InlineKeyboardButton("♥️ Червы", callback_data=f"trump_{self.game_id}_hearts"),
                InlineKeyboardButton("♦️ Бубны", callback_data=f"trump_{self.game_id}_diamonds")
            ],
            [
                InlineKeyboardButton("♣️ Трефы", callback_data=f"trump_{self.game_id}_clubs"),
                InlineKeyboardButton("♠️ Пики", callback_data=f"trump_{self.game_id}_spades")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    def _create_hand_keyboard(self, player_id: int) -> InlineKeyboardMarkup:
        """
        Создает клавиатуру с картами в руке игрока
        
        :param player_id: Telegram ID игрока
        :return: Клавиатура с картами
        """
        position = self.get_player_position(player_id)
        if position is None:
            return InlineKeyboardMarkup([])
        
        player = self.state.players[position]
        hand = player.hand
        
        keyboard = []
        row = []
        for i, card in enumerate(hand):
            card_text = self._format_card(card)
            row.append(InlineKeyboardButton(
                card_text, 
                callback_data=f"card_{self.game_id}_{i}"
            ))
            if len(row) == 4 or i == len(hand) - 1:
                keyboard.append(row)
                row = []
        
        return InlineKeyboardMarkup(keyboard)
    
    def _format_card(self, card: Card) -> str:
        """Форматирует карту для отображения в Telegram"""
        suit_emoji = {
            'hearts': '♥️',
            'diamonds': '♦️',
            'clubs': '♣️',
            'spades': '♠️'
        }
        return f"{card.rank}{suit_emoji[card.suit]}"

    async def set_trump(self, player_id: int, suit: str) -> Tuple[bool, Optional[str]]:
        """
        Установка козыря игроком.
        
        :param player_id: ID игрока в Telegram
        :param suit: Масть козыря ('hearts', 'diamonds', 'clubs', 'spades')
        :return: (успех, сообщение)
        """
        position = self.get_player_position(player_id)
        if position is None or position != self.state.first_player_index:
            return False, "Только игрок с шестеркой треф может выбирать козырь"
        
        try:
            status, player_name, trump = self.engine.set_trump_by_player(position, suit)
            suit_name = {
                'hearts': 'Червы',
                'diamonds': 'Бубны',
                'clubs': 'Трефы',
                'spades': 'Пики'
            }.get(trump, trump)
            
            # Уведомляем всех игроков о выбранном козыре
            await self.notify_all_players(
                f"Игрок {player_name} объявил козырем: {suit_name} {GameConstants.SUIT_SYMBOLS[suit]}"
            )
            
            # Сохраняем данные о раздаче в БД
            if self.db_match_id:
                hands = {}
                for pos, player in self.state.players.items():
                    if player is not None:
                        hands[pos] = [
                            {"rank": card.rank, "suit": card.suit, "value": card.value} 
                            for card in player.hand
                        ]
                
                self.db_game_id = await self.bot.db_manager.create_game(
                    self.db_match_id,
                    suit,
                    position,
                    hands
                )
                
                # Логируем событие выбора козыря
                await self.bot.db_manager.log_event(
                    player_id,
                    "trump_selected",
                    {
                        "game_id": self.game_id,
                        "db_match_id": self.db_match_id,
                        "db_game_id": self.db_game_id,
                        "trump": suit,
                        "player": {"id": player_id, "name": player_name, "position": position}
                    }
                )
            
            self.waiting_for_trump = False
            # Обновляем состояние игры для всех
            await self.send_game_state_to_all()
            
            return True, None
        except GameException as e:
            return False, str(e)
    
    async def play_card(self, player_id: int, card_index: int) -> Tuple[bool, Optional[str]]:
        """
        Обработка хода игрока.
        
        :param player_id: ID игрока в Telegram
        :param card_index: Индекс карты в руке игрока
        :return: (успех, сообщение об ошибке или None)
        """
        position = self.get_player_position(player_id)
        if position is None:
            return False, "Вы не участвуете в этой игре"
        
        if not self.is_player_turn(player_id):
            return False, "Сейчас не ваш ход"
        
        try:
            status, player, card = self.engine.play_turn(position, card_index)
            
            # Уведомляем всех о сделанном ходе
            card_text = self._format_card(card)
            await self.notify_all_players(f"Игрок {player.name} сыграл карту: {card_text}")
            
            # Логируем ход в базу данных
            if self.db_match_id and self.db_game_id:
                await self.bot.db_manager.log_event(
                    player_id,
                    "card_played",
                    {
                        "game_id": self.game_id,
                        "db_match_id": self.db_match_id,
                        "db_game_id": self.db_game_id,
                        "player": {"id": player_id, "name": player.name, "position": position},
                        "card": {"rank": card.rank, "suit": card.suit, "value": card.value},
                        "turn_number": self.state.current_turn,
                        "cards_on_table": len(self.state.current_table)
                    }
                )
            
            # Если на столе 4 карты, подсчитываем результат кона
            if status == GameConstants.Status.TRICK_COMPLETED:
                await self.complete_turn()
            else:
                # Иначе обновляем состояние для всех
                await self.send_game_state_to_all()
            
            return True, None
        except GameException as e:
            return False, str(e)
    
    async def complete_turn(self) -> None:
        """Обработка завершения кона (4 карты на столе)"""
        try:
            status, winning_card, winning_player_index, trick_points = self.engine.complete_turn()
            
            winning_player = self.state.players[winning_player_index]
            winning_team = winning_player_index // 10 * 10
            
            card_text = self._format_card(winning_card)
            
            # Уведомляем о результатах кона
            team_name = "Команда 1" if winning_team == GameConstants.TEAM_1 else "Команда 2"
            await self.notify_all_players(
                f"Взятку забирает {winning_player.name} ({team_name}) "
                f"с картой {card_text}. Очки за взятку: {trick_points}"
            )
            
            # Сохраняем данные о коне в БД
            if self.db_match_id and self.db_game_id:
                cards = {}
                for item in self.state.current_table:
                    cards[item['player_index']] = f"{item['card'].rank}{GameConstants.SUIT_SYMBOLS[item['card'].suit]}"
                
                # Сохраняем ход в БД
                await self.bot.db_manager.create_turn(
                    self.db_game_id,
                    self.db_match_id,
                    self.state.current_player_index,
                    cards,
                    trick_points,
                    winning_team
                )
                
                # Логируем завершение кона
                await self.bot.db_manager.log_event(
                    None,
                    "turn_completed",
                    {
                        "game_id": self.game_id,
                        "db_match_id": self.db_match_id,
                        "db_game_id": self.db_game_id,
                        "turn_number": self.state.current_turn - 1,  # -1 т.к. уже увеличили
                        "winner": {
                            "id": winning_player.id,
                            "name": winning_player.name,
                            "position": winning_player_index,
                            "team": winning_team
                        },
                        "trick_points": trick_points,
                        "winning_card": {"rank": winning_card.rank, "suit": winning_card.suit}
                    }
                )
            
            # Если игра завершена (9 конов сыграны)
            if status == GameConstants.Status.GAME_COMPLETED:
                await self.complete_game()
            else:
                # Иначе продолжаем игру
                await self.send_game_state_to_all()
        except Exception as e:
            logger.error(f"Ошибка при завершении кона: {e}")
    
    async def complete_game(self) -> None:
        """Обработка завершения игры (все 9 конов сыграны)"""
        try:
            status, scores, losing_team, losing_points = self.engine.complete_game()
            
            # Форматируем счет команд
            team1_score = scores[GameConstants.TEAM_1]
            team2_score = scores[GameConstants.TEAM_2]
            
            # Определяем, какая команда проиграла и сколько очков получила
            losing_team_name = "Команда 1" if losing_team == GameConstants.TEAM_1 else "Команда 2"
            
            # Отправляем результаты раздачи
            await self.notify_all_players(
                f"Раздача завершена!\n\n"
                f"Счет взяток в раздаче:\n"
                f"Команда 1: {team1_score} очков\n"
                f"Команда 2: {team2_score} очков\n\n"
                f"{losing_team_name} получает {losing_points} штрафных очков."
            )
            
            # Логируем завершение раздачи в БД
            if self.db_match_id:
                await self.bot.db_manager.log_event(
                    None,
                    "game_completed",
                    {
                        "game_id": self.game_id,
                        "db_match_id": self.db_match_id,
                        "db_game_id": self.db_game_id,
                        "scores": {
                            "team1": team1_score,
                            "team2": team2_score
                        },
                        "losing_team": losing_team,
                        "losing_points": losing_points,
                        "match_scores": {
                            "team1": self.state.match_scores[GameConstants.TEAM_1],
                            "team2": self.state.match_scores[GameConstants.TEAM_2]
                        }
                    }
                )
            
            # Если матч завершен (одна из команд набрала 12+ очков)
            if status == GameConstants.Status.MATCH_COMPLETED:
                await self.complete_match()
            else:
                # Иначе начинаем новую раздачу
                await self.start_new_deal()
        except Exception as e:
            logger.error(f"Ошибка при завершении игры: {e}")
    
    async def complete_match(self) -> None:
        """Обработка завершения матча (одна из команд набрала 12+ очков)"""
        try:
            status = self.engine.complete_match()
            
            # Определяем проигравшую команду (у которой 12+ очков)
            losing_team = GameConstants.TEAM_1 if self.state.match_scores[GameConstants.TEAM_1] >= 12 else GameConstants.TEAM_2
            winning_team = GameConstants.TEAM_2 if losing_team == GameConstants.TEAM_1 else GameConstants.TEAM_1
            
            losing_team_name = "Команда 1" if losing_team == GameConstants.TEAM_1 else "Команда 2"
            winning_team_name = "Команда 2" if losing_team == GameConstants.TEAM_1 else "Команда 1"
            
            # Отправляем результаты матча
            message = (
                f"🎮 Матч завершен! 🎮\n\n"
                f"{losing_team_name} набрала {self.state.match_scores[losing_team]} очков (≥12) и проигрывает!\n"
                f"{winning_team_name} побеждает с {self.state.match_scores[winning_team]} очками!\n\n"
                f"Спасибо за игру! Используйте /start для начала новой игры."
            )
            
            await self.notify_all_players(message)
            
            # Обновляем информацию о матче в БД
            if self.db_match_id:
                await self.bot.db_manager.update_match(
                    self.db_match_id,
                    winning_team,
                    self.state.match_scores[GameConstants.TEAM_1],
                    self.state.match_scores[GameConstants.TEAM_2]
                )
                
                # Логируем завершение матча
                await self.bot.db_manager.log_event(
                    None,
                    "match_completed",
                    {
                        "game_id": self.game_id,
                        "db_match_id": self.db_match_id,
                        "winning_team": winning_team,
                        "losing_team": losing_team,
                        "scores": {
                            "team1": self.state.match_scores[GameConstants.TEAM_1],
                            "team2": self.state.match_scores[GameConstants.TEAM_2]
                        }
                    }
                )
                
                # Обновляем статистику игроков
                for position, player in self.state.players.items():
                    if player is not None:
                        player_team = position // 10 * 10
                        db_player = await self.bot.db_manager.get_player_by_tg_id(player.id)
                        if db_player:
                            # Определяем, выиграл ли игрок
                            won = player_team == winning_team
                            
                            # Считаем взятки (примерно)
                            tricks = 0  # TODO: Реализовать подсчет взяток для игрока
                            
                            # Считаем, сколько раз игрок объявлял козырь
                            shama_calls = 1 if position == self.state.first_player_index else 0
                            
                            await self.bot.db_manager.update_player_stats(
                                db_player['id'],
                                won,
                                tricks,
                                shama_calls
                            )
            
            # Удаляем игру из менеджера сессий
            self.bot.game_sessions.remove_game(self.game_id)
        except Exception as e:
            logger.error(f"Ошибка при завершении матча: {e}")
    
    async def start_new_deal(self) -> None:
        """Начало новой раздачи"""
        try:
            # Сбрасываем все руки игроков и начинаем новую раздачу
            for player in self.state.players.values():
                if player is not None:
                    player.clear_hand()
            
            # Запускаем новую игру
            self.engine.start_game()
            
            # Ищем игрока с шамой
            shama_position = self.state.first_player_index
            shama_player = self.state.players[shama_position]
            
            # Отправляем всем сообщение о начале новой раздачи
            await self.notify_all_players("Начинается новая раздача! Карты розданы.")
            
            # Отправляем отдельное сообщение игроку с шамой
            shama_id = shama_player.id
            await self.bot.send_message(
                shama_id,
                f"У вас на руках шестерка треф (шама)! Выберите козырь:",
                reply_markup=self._create_trump_selection_keyboard()
            )
            self.waiting_for_trump = True
            
            # Отправляем текущее состояние всем игрокам
            await self.send_game_state_to_all()
            
            # Логируем начало новой раздачи
            if self.db_match_id:
                await self.bot.db_manager.log_event(
                    None,
                    "new_deal_started",
                    {
                        "game_id": self.game_id,
                        "db_match_id": self.db_match_id,
                        "shama_player": {
                            "id": shama_player.id,
                            "name": shama_player.name,
                            "position": shama_position
                        },
                        "current_match_scores": {
                            "team1": self.state.match_scores[GameConstants.TEAM_1],
                            "team2": self.state.match_scores[GameConstants.TEAM_2]
                        }
                    }
                )
        except Exception as e:
            logger.error(f"Ошибка при начале новой раздачи: {e}")
    
    async def notify_all_players(self, message: str) -> None:
        """
        Отправляет сообщение всем игрокам в игре.
        
        :param message: Текст сообщения
        """
        for player_id in self.player_positions.keys():
            try:
                await self.bot.send_message(player_id, message)
            except Exception as e:
                logger.error(f"Ошибка при отправке сообщения игроку {player_id}: {e}")
    
    async def send_game_state_to_all(self) -> None:
        """Отправляет текущее состояние игры всем игрокам"""
        player_info = self.get_all_players_info()
        
        for player_id, info in player_info.items():
            try:
                # Формируем сообщение для игрока
                message = self._format_game_state_message(player_id, player_info)
                
                # Добавляем информацию о картах игрока
                message += "\n\nВаши карты:"
                
                # Определяем, может ли игрок сейчас ходить
                can_play = self.is_player_turn(player_id) and not self.waiting_for_trump
                keyboard = None
                
                if can_play:
                    keyboard = self._create_hand_keyboard(player_id)
                
                # Если у игрока уже есть сообщение с состоянием игры, обновляем его
                if player_id in self.game_state_messages:
                    try:
                        await self.bot.edit_message_text(
                            message,
                            player_id,
                            self.game_state_messages[player_id],
                            reply_markup=keyboard
                        )
                    except Exception:
                        # Если не удалось отредактировать, отправляем новое
                        msg = await self.bot.send_message(player_id, message, reply_markup=keyboard)
                        self.game_state_messages[player_id] = msg.message_id
                else:
                    # Иначе отправляем новое сообщение
                    msg = await self.bot.send_message(player_id, message, reply_markup=keyboard)
                    self.game_state_messages[player_id] = msg.message_id
            except Exception as e:
                logger.error(f"Ошибка при отправке состояния игры игроку {player_id}: {e}")
    
    def _format_game_state_message(self, player_id: int, player_info: Dict[int, Dict[str, Any]]) -> str:
        """
        Форматирует сообщение с текущим состоянием игры для игрока.
        
        :param player_id: ID игрока, которому отправляется сообщение
        :param player_info: Информация обо всех игроках
        :return: Отформатированное сообщение
        """
        # Получаем информацию об игроке
        info = player_info[player_id]
        position = info['position']
        team = info['team']
        
        # Определяем союзников и противников
        teammates = []
        opponents = []
        for p_id, p_info in player_info.items():
            if p_id != player_id:
                if p_info['team'] == team:
                    teammates.append(p_info)
                else:
                    opponents.append(p_info)
        
        # Получаем текущий козырь
        trump = self.state.trump or "не выбран"
        trump_text = {
            'hearts': 'Червы ♥️',
            'diamonds': 'Бубны ♦️',
            'clubs': 'Трефы ♣️',
            'spades': 'Пики ♠️',
            'не выбран': 'не выбран'
        }.get(trump, trump)
        
        # Форматируем сообщение с информацией о текущем состоянии игры
        message = (
            f"🎮 Игра: {self.game_id} | 🎯 Козырь: {trump_text}\n\n"
            f"📊 Счет матча:\n"
            f"Команда 1: {self.state.match_scores[GameConstants.TEAM_1]} очков\n"
            f"Команда 2: {self.state.match_scores[GameConstants.TEAM_2]} очков\n\n"
            f"📋 Ход {self.state.current_turn}/9\n"
        )
        
        # Добавляем информацию о текущем игроке
        current_player_pos = self.state.current_player_index
        current_player = self.state.players[current_player_pos]
        if current_player:
            current_player_team = "1" if current_player_pos // 10 == 1 else "2"
            message += f"🎲 Текущий ход: {current_player.name} (Команда {current_player_team})\n\n"
        
        # Добавляем информацию о картах на столе
        if self.state.current_table:
            message += "🃏 Карты на столе:\n"
            for item in self.state.current_table:
                player_name = item['player'].name
                card_text = self._format_card(item['card'])
                message += f"- {player_name}: {card_text}\n"
            message += "\n"
        
        # Добавляем информацию о союзниках и противниках
        message += "👥 Игроки:\n"
        message += f"- ВЫ: {info['name']} (Команда {team//10})\n"
        
        for teammate in teammates:
            message += f"- Союзник: {teammate['name']}\n"
        
        for opponent in opponents:
            message += f"- Противник: {opponent['name']}\n"
            
        return message


class GameSessionManager:
    """Класс для управления игровыми сессиями."""
    
    def __init__(self):
        """Инициализация менеджера игровых сессий."""
        self.sessions: Dict[str, GameSession] = {}  # id -> GameSession
        self.invite_codes: Dict[str, str] = {}      # invite_code -> game_id
        self.player_sessions: Dict[int, str] = {}   # player_id -> game_id
    
    def create_game(self, creator_id: int, creator_name: str, bot: 'TelegramBotHandler') -> GameSession:
        """
        Создает новую игровую сессию.
        
        :param creator_id: ID создателя игры в Telegram
        :param creator_name: Имя создателя
        :param bot: Экземпляр обработчика Telegram бота
        :return: Созданная игровая сессия
        """
        # Генерируем уникальный ID для игры
        game_id = str(uuid.uuid4())[:8]
        
        # Создаем игровую сессию
        session = GameSession(game_id, creator_id, creator_name, bot)
        
        # Добавляем сессию в хранилище
        self.sessions[game_id] = session
        self.invite_codes[session.invite_code] = game_id
        self.player_sessions[creator_id] = game_id
        
        return session
    
    def get_session_by_id(self, game_id: str) -> Optional[GameSession]:
        """
        Получает игровую сессию по ID.
        
        :param game_id: ID игровой сессии
        :return: Игровая сессия или None
        """
        return self.sessions.get(game_id)
    
    def get_session_by_invite_code(self, invite_code: str) -> Optional[GameSession]:
        """
        Получает игровую сессию по коду приглашения.
        
        :param invite_code: Код приглашения
        :return: Игровая сессия или None
        """
        game_id = self.invite_codes.get(invite_code)
        if game_id:
            return self.sessions.get(game_id)
        return None
    
    def get_player_session(self, player_id: int) -> Optional[GameSession]:
        """
        Получает игровую сессию, в которой участвует игрок.
        
        :param player_id: ID игрока в Telegram
        :return: Игровая сессия или None
        """
        game_id = self.player_sessions.get(player_id)
        if game_id:
            return self.sessions.get(game_id)
        return None
    
    def add_player_to_session(self, player_id: int, session: GameSession) -> None:
        """
        Добавляет игрока в список игроков сессии.
        
        :param player_id: ID игрока в Telegram
        :param session: Игровая сессия
        """
        self.player_sessions[player_id] = session.game_id
    
    def remove_game(self, game_id: str) -> None:
        """
        Удаляет игровую сессию.
        
        :param game_id: ID игровой сессии
        """
        if game_id in self.sessions:
            session = self.sessions[game_id]
            # Удаляем код приглашения
            if session.invite_code in self.invite_codes:
                del self.invite_codes[session.invite_code]
            
            # Удаляем игроков из сессии
            for player_id in list(self.player_sessions.keys()):
                if self.player_sessions[player_id] == game_id:
                    del self.player_sessions[player_id]
            
            # Удаляем саму сессию
            del self.sessions[game_id]
    
    def remove_player_from_sessions(self, player_id: int) -> None:
        """
        Удаляет игрока из сессии, в которой он участвует.
        
        :param player_id: ID игрока в Telegram
        """
        if player_id in self.player_sessions:
            del self.player_sessions[player_id]


class TelegramBotHandler:
    """Основной класс для обработки взаимодействий с Telegram Bot API."""
    
    def __init__(self, token: str, storage_type: Optional[str] = None):
        """
        Инициализация обработчика Telegram бота.
        
        :param token: Токен бота
        :param storage_type: Тип хранилища ('postgres' или 'file')
        """
        self.token = token
        self.bot_username = ""
        self.application = Application.builder().token(token).build()
        self.game_sessions = GameSessionManager()
        self.storage_type = storage_type
        self.db_manager = None  # Будет инициализировано позже
        self.setup_handlers()
    
    def setup_handlers(self) -> None:
        """Регистрирует обработчики команд и сообщений."""
        # Обработчики команд
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("rules", self.rules_command))
        self.application.add_handler(CommandHandler("create_game", self.create_game_command))
        self.application.add_handler(CommandHandler("join_game", self.join_game_command))
        self.application.add_handler(CommandHandler("stats", self.stats_command))
        
        # Обработчик callback-запросов (для inline клавиатур)
        self.application.add_handler(CallbackQueryHandler(self.button_callback))
        
        # Обработчик обычных текстовых сообщений
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.text_message))
        
        # Обработчик ошибок
        self.application.add_error_handler(self.error_handler)
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Обработчик команды /start.
        
        Приветствует пользователя и предлагает создать игру или присоединиться к существующей.
        Также обрабатывает Deep Linking для присоединения к игре по ссылке.
        """
        logger.info(f"Получена команда /start от пользователя {update.effective_user.id}")
        user = update.effective_user
        user_id = user.id
        chat_id = update.effective_chat.id
        
        # Получаем информацию о пользователе для БД
        user_name = user.username or user.first_name
        
        # Если в команде есть аргументы (например, код приглашения)
        if context.args:
            arg = context.args[0]
            
            # Проверяем, это присоединение к игре
            if arg.startswith("join_"):
                invite_code = arg[5:]  # Отрезаем 'join_'
                session = self.game_sessions.get_session_by_invite_code(invite_code)
                
                if session:
                    # Проверяем, не участвует ли пользователь уже в игре
                    if user_id in session.player_positions:
                        await self.send_message(
                            chat_id,
                            "Вы уже участвуете в этой игре!"
                        )
                        return
                    
                    # Проверяем, есть ли свободные места
                    available_positions = session.get_available_positions()
                    if not available_positions:
                        await self.send_message(
                            chat_id,
                            "Извините, в игре уже нет свободных мест."
                        )
                        return
                    
                    # Добавляем игрока в игру
                    success = session.add_player(user_id, user_name)
                    
                    if success:
                        self.game_sessions.add_player_to_session(user_id, session)
                        
                        # Логируем присоединение к игре
                        await self.db_manager.log_event(
                            user_id,
                            "player_joined_game",
                            {
                                "game_id": session.game_id,
                                "player": {"id": user_id, "name": user_name},
                                "position": session.get_player_position(user_id)
                            }
                        )
                        
                        # Уведомляем всех игроков о новом участнике
                        await session.notify_all_players(
                            f"Игрок {user_name} присоединился к игре!"
                        )
                        
                        # Отправляем сообщение игроку
                        await self.send_message(
                            chat_id,
                            f"Вы успешно присоединились к игре!\n"
                            f"Дождитесь, когда присоединятся все игроки."
                        )
                        
                        # Если все места заняты, можно начинать игру
                        if not session.get_available_positions():
                            # Запускаем игру
                            success = await session.start_game()
                            if not success:
                                await session.notify_all_players(
                                    "Не удалось начать игру. Пожалуйста, создайте новую игру."
                                )
                    else:
                        await self.send_message(
                            chat_id,
                            "Не удалось присоединиться к игре. Попробуйте еще раз."
                        )
                else:
                    await self.send_message(
                        chat_id,
                        "Игра не найдена или уже завершена."
                    )
                return
        
        # Обычная команда /start без аргументов
        keyboard = [
            [InlineKeyboardButton("Создать игру", callback_data="create_game")],
            [InlineKeyboardButton("Правила игры", callback_data="rules")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await self.send_message(
            chat_id,
            f"Привет, {user_name}! Добро пожаловать в игру «Шама».\n\n"
            f"Вы можете создать новую игру или присоединиться к существующей по ссылке-приглашению.",
            reply_markup=reply_markup
        )
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик команды /help."""
        chat_id = update.effective_chat.id
        
        help_text = (
            "Доступные команды:\n"
            "/start - Начать использование бота\n"
            "/create_game - Создать новую игру\n"
            "/join_game - Присоединиться к игре по коду (если у вас нет ссылки)\n"
            "/rules - Показать правила игры\n"
            "/stats - Показать вашу статистику\n"
            "/help - Показать это сообщение"
        )
        
        await self.send_message(chat_id, help_text)
    
    async def rules_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик команды /rules."""
        chat_id = update.effective_chat.id
        
        rules_text = (
            "🎮 Правила игры «Шама» 🎮\n\n"
            "Играются классические 36 игральных карт. Участвуют 2 команды по 2 игрока.\n\n"
            "Самая старшая карта – шесть треф (♣6), затем валеты (♣J > ♠J > ♥J > ♦J).\n"
            "Козырные карты бьют все некозырные. Козырь объявляет игрок с шамой (♣6).\n\n"
            "Как играть:\n"
            "1. Всем раздается по 9 карт\n"
            "2. Игрок с шамой объявляет козырь\n"
            "3. Игроки ходят по очереди, выкладывая карты\n"
            "4. Игроки обязаны ходить в масть или козырем\n"
            "5. Взятку забирает команда с самой сильной картой\n"
            "6. После 9 ходов подсчитываются очки\n\n"
            "Матч играется до 12 очков, команда с 12+ очками проигрывает.\n\n"
            "Используйте /create_game чтобы начать играть!"
        )
        
        await self.send_message(chat_id, rules_text)
    
    async def create_game_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик команды /create_game."""
        user = update.effective_user
        user_id = user.id
        chat_id = update.effective_chat.id
        
        # Получаем информацию о пользователе для БД
        user_name = user.username or user.first_name
        
        # Проверяем, не участвует ли пользователь уже в игре
        existing_session = self.game_sessions.get_player_session(user_id)
        if existing_session:
            await self.send_message(
                chat_id,
                "Вы уже участвуете в игре!\n"
                "Завершите текущую игру, прежде чем создавать новую."
            )
            return
        
        # Создаем новую игру
        session = self.game_sessions.create_game(user_id, user_name, self)
        
        # Логируем создание игры
        await self.db_manager.log_event(
            user_id,
            "game_created",
            {"game_id": session.game_id, "creator": {"id": user_id, "name": user_name}}
        )
        
        # Создаем инвайт-ссылку
        invite_link = session.get_invite_link()
        
        # Отправляем сообщение с инвайт-ссылкой
        await self.send_message(
            chat_id,
            f"Игра создана!\n\n"
            f"Поделитесь этой ссылкой с друзьями, чтобы пригласить их в игру:\n"
            f"{invite_link}\n\n"
            f"Игра начнется автоматически, когда присоединятся все 4 игрока."
        )
    
    async def join_game_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик команды /join_game."""
        user = update.effective_user
        user_id = user.id
        chat_id = update.effective_chat.id
        
        # Проверяем наличие аргументов (код приглашения)
        if not context.args:
            await self.send_message(
                chat_id,
                "Пожалуйста, укажите код приглашения после команды. Например:\n"
                "/join_game ABC123"
            )
            return
        
        invite_code = context.args[0]
        
        # Перенаправляем на команду start с аргументом
        await self.start_command(update, ContextTypes.DEFAULT_TYPE())
    
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик команды /stats."""
        user = update.effective_user
        user_id = user.id
        chat_id = update.effective_chat.id
        
        # Получаем статистику игрока из БД
        stats = await self.db_manager.get_player_stats(user_id)
        
        if stats:
            stats_text = (
                f"📊 Статистика игрока {stats['name']} 📊\n\n"
                f"Сыгранных матчей: {stats['games']}\n"
                f"Побед: {stats['wins']} ({stats['win_rate']}%)\n"
                f"Всего взяток: {stats['total_tricks']}\n"
                f"Объявлено козырей: {stats['total_shama_calls']}"
            )
        else:
            stats_text = "У вас пока нет статистики. Сыграйте несколько игр!"
        
        await self.send_message(chat_id, stats_text)
    
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Обработчик нажатий на inline-кнопки.
        
        Обрабатывает действия игроков в игре: выбор козыря, ход картами и т.д.
        """
        query = update.callback_query
        await query.answer()  # Отвечаем на запрос, чтобы убрать "часики" у кнопки
        
        user_id = query.from_user.id
        data = query.data
        
        # Обрабатываем нажатие на кнопку в зависимости от данных
        if data == "create_game":
            # Создаем новую игру (как если бы пользователь вызвал /create_game)
            new_update = Update(
                update_id=update.update_id,
                message=query.message
            )
            await self.create_game_command(new_update, context)
            return
        
        if data == "rules":
            # Показываем правила игры
            new_update = Update(
                update_id=update.update_id,
                message=query.message
            )
            await self.rules_command(new_update, context)
            return
        
        # Проверяем, не выбор ли это козыря
        if data.startswith("trump_"):
            parts = data.split("_")
            if len(parts) == 3:
                game_id = parts[1]
                suit = parts[2]
                
                # Получаем сессию игры
                session = self.game_sessions.get_session_by_id(game_id)
                if session:
                    # Проверяем, может ли игрок выбирать козырь
                    success, error_msg = await session.set_trump(user_id, suit)
                    if not success and error_msg:
                        await self.send_message(
                            user_id,
                            f"Ошибка: {error_msg}"
                        )
            return
        
        # Проверяем, не ход ли это картой
        if data.startswith("card_"):
            parts = data.split("_")
            if len(parts) == 3:
                game_id = parts[1]
                try:
                    card_index = int(parts[2])
                    
                    # Получаем сессию игры
                    session = self.game_sessions.get_session_by_id(game_id)
                    if session:
                        # Проверяем, может ли игрок ходить
                        success, error_msg = await session.play_card(user_id, card_index)
                        if not success and error_msg:
                            await self.send_message(
                                user_id,
                                f"Ошибка: {error_msg}"
                            )
                except ValueError:
                    pass
            return
    
    async def text_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Обработчик обычных текстовых сообщений.
        
        Отвечает пользователю помощью, если он отправил текст, который не является командой.
        """
        chat_id = update.effective_chat.id
        
        await self.send_message(
            chat_id,
            "Я понимаю только команды, начинающиеся с /\n"
            "Отправьте /help чтобы увидеть список доступных команд."
        )
    
    async def error_handler(self, update, context) -> None:
        """Обработчик ошибок."""
        logger.error(f"Ошибка при обработке обновления {update}: {context.error}")
        
        # Более подробное логирование
        import traceback
        traceback_str = ''.join(traceback.format_tb(context.error.__traceback__))
        logger.error(f"Трассировка ошибки:\n{traceback_str}")
        
        # Если сообщение от пользователя доступно, отправляем ему уведомление об ошибке
        if update and update.effective_chat:
            chat_id = update.effective_chat.id
            await self.send_message(
                chat_id,
                "Произошла ошибка при обработке вашего запроса. "
                "Пожалуйста, попробуйте еще раз позже."
            )
    
    async def send_message(self, chat_id: int, text: str, reply_markup=None) -> Any:
        """
        Отправляет сообщение в чат.
        
        :param chat_id: ID чата
        :param text: Текст сообщения
        :param reply_markup: Клавиатура (опционально)
        :return: Отправленное сообщение
        """
        try:
            return await self.application.bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
        except Exception as e:
            logger.error(f"Ошибка при отправке сообщения пользователю {chat_id}: {e}")
            return None
    
    async def edit_message_text(self, text: str, chat_id: int, message_id: int, reply_markup=None) -> Any:
        """
        Редактирует существующее сообщение.
        
        :param text: Новый текст сообщения
        :param chat_id: ID чата
        :param message_id: ID сообщения
        :param reply_markup: Новая клавиатура (опционально)
        :return: Отредактированное сообщение
        """
        try:
            return await self.application.bot.edit_message_text(
                text=text,
                chat_id=chat_id,
                message_id=message_id,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
        except Exception as e:
            logger.error(f"Ошибка при редактировании сообщения: {e}")
            return None
    
    async def init_bot(self) -> None:
        """Инициализирует бота и хранилище данных."""
        try:
            # Получаем информацию о боте
            bot_info = await self.application.bot.get_me()
            self.bot_username = bot_info.username
            
            # Инициализируем хранилище данных
            self.db_manager = await StorageFactory.create_storage(self.storage_type)
            
            logger.info(f"Бот @{self.bot_username} запущен и готов к работе")
        except Exception as e:
            logger.error(f"Ошибка при инициализации бота: {e}")
            raise
    
    def run(self) -> None:
        """Запускает бота."""
        # Создаем новый цикл событий
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Инициализируем бота и базу данных
            loop.run_until_complete(self.init_bot())
            
            logger.info("Запуск обработки обновлений...")
            
            # Настройка логгера для более детального вывода
            logging.getLogger('telegram').setLevel(logging.INFO)
            logging.getLogger('telegram.ext').setLevel(logging.INFO)
            
            # Запускаем бота с более подробными настройками
            self.application.run_polling(
                allowed_updates=["message", "callback_query", "inline_query"],
                drop_pending_updates=True,
                poll_interval=1.0
            )
        except Exception as e:
            logger.error(f"Критическая ошибка при запуске бота: {e}")
            raise
        finally:
            logger.info("Закрытие событийного цикла...")
            loop.close()


if __name__ == "__main__":
    try:
        # Настраиваем более подробное логирование
        logger.setLevel(logging.DEBUG)
        
        # Получаем токен бота из переменных окружения
        token = os.environ.get("TELEGRAM_BOT_TOKEN")
        
        if not token:
            logger.error("Не указан токен бота! Установите переменную окружения TELEGRAM_BOT_TOKEN")
            exit(1)
        
        logger.info(f"Использую токен: {token[:5]}...{token[-5:]}")
        
        # Получаем тип хранилища из переменных окружения (по умолчанию файловое)
        storage_type = os.environ.get("STORAGE_TYPE", "file")
        logger.info(f"Используемый тип хранилища: {storage_type}")
        
        # Создаем обработчик бота и запускаем его
        logger.info("Инициализация обработчика бота...")
        bot_handler = TelegramBotHandler(token, storage_type)
        
        logger.info("Запуск бота...")
        bot_handler.run()
    except Exception as e:
        logger.critical(f"Критическая ошибка в основном блоке: {e}", exc_info=True)
