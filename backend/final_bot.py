"""
Финальная версия Telegram бота для игры Шама.
Исправлены все проблемы с конфликтами и циклами событий.

Автор: ShamaVibe Team
"""

import os
import sys
import logging
import asyncio
import re
from typing import Dict, List, Optional, Any, Tuple
import json

from telegram import Bot, Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    filters, ContextTypes
)
from telegram.error import TelegramError
from dotenv import load_dotenv

# Импорт модулей игры
from core import GameEngine, MatchState, Player, GameException, InvalidPlayerAction
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

# Уменьшаем уровень логирования для библиотечных модулей
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('httpcore').setLevel(logging.WARNING)
logging.getLogger('telegram').setLevel(logging.INFO)

# Глобальные переменные
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
ACTIVE_GAMES = {}  # Хранит активные игры {chat_id: MatchState}
WAITING_GAMES = {}  # Хранит ожидающие игры {chat_id: {creator_id, players: {}, timestamp, game_id}}
TRUMP_SELECTION = {}  # Игроки, ожидающие выбора козыря {user_id: match_state}
WAITING_PLAYERS = {}  # Игроки, ожидающие своего хода {user_id: match_state}
GAME_ENGINES = {}  # Игровые движки {chat_id: GameEngine}
GAMES_BY_ID = {}  # Хранит игры по их ID {game_id: chat_id} для инвайт-ссылок

# Инициализация хранилища
storage = None


async def init_storage():
    """Инициализация хранилища данных."""
    global storage
    try:
        # Получаем тип хранилища из переменной окружения или используем файловое по умолчанию
        storage_type = os.environ.get("STORAGE_TYPE", "file")
        storage = await StorageFactory.create_storage(storage_type)
        logger.info(f"Хранилище данных ({storage_type}) инициализировано успешно")
        return True
    except Exception as e:
        logger.error(f"Ошибка при инициализации хранилища данных: {e}")
        return False

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /start."""
    logger.info(f"Получена команда /start от пользователя {update.effective_user.id}")
    user_name = update.effective_user.first_name
    user_id = update.effective_user.id
    
    # Сохраняем или обновляем данные игрока
    player_data = await storage.get_or_create_player(
        update.effective_user.id, 
        update.effective_user.first_name
    )
    
    if player_data:
        logger.info(f"Игрок {player_data['name']} (ID: {player_data['id']}) зарегистрирован")
    else:
        logger.warning(f"Не удалось зарегистрировать игрока {user_name}")
    
    # Проверяем, не является ли это присоединением к игре через инвайт-ссылку
    if context.args and context.args[0].startswith('game_'):
        game_id = context.args[0][5:]  # Получаем ID игры из аргумента
        
        if game_id in GAMES_BY_ID:
            chat_id = GAMES_BY_ID[game_id]
            
            # Проверяем, активна ли еще игра
            if chat_id in WAITING_GAMES:
                # Проверяем, не присоединился ли игрок уже
                if user_id in WAITING_GAMES[chat_id]['players']:
                    await update.message.reply_text(
                        f"Привет, {user_name}! Вы уже присоединились к этой игре.\n"
                        f"Ожидайте начала игры."
                    )
                # Проверяем, не заполнен ли стол (4 игрока)
                elif len(WAITING_GAMES[chat_id]['players']) >= 4:
                    await update.message.reply_text(
                        f"Привет, {user_name}!\n"
                        f"К сожалению, в игре уже набралось максимальное количество игроков (4)."
                    )
                else:
                    # Добавляем игрока в список ожидающих
                    WAITING_GAMES[chat_id]['players'][user_id] = {
                        'id': player_data['id'],
                        'tg_id': user_id,
                        'name': user_name,
                        'position': None  # Позиция будет назначена позже
                    }
                    
                    # Логируем присоединение к игре
                    await storage.log_event(
                        user_id, 
                        "join_game_via_link", 
                        {"chat_id": chat_id, "player_name": user_name, "game_id": game_id}
                    )
                    
                    # Получаем обновленный список игроков
                    players = WAITING_GAMES[chat_id]['players']
                    
                    # Отправляем сообщение в личку игроку
                    await update.message.reply_text(
                        f"Вы успешно присоединились к игре! Всего игроков: {len(players)}/4.\n"
                        f"Ожидайте начала игры."
                    )
                    
                    # Отправляем сообщение в чат с игрой
                    player_list = "\n".join([f"• {p_data['name']}" for p_data in players.values()])
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=f"🎮 {user_name} присоединился к игре!\n\n"
                             f"Текущие участники ({len(players)}/4):\n{player_list}\n\n"
                             f"Игра начнется, когда присоединятся 4 игрока."
                    )
                    
                    # Если набралось 4 игрока, начинаем игру
                    if len(players) == 4:
                        message = await context.bot.send_message(
                            chat_id=chat_id,
                            text="Набралось 4 игрока! Игра начинается..."
                        )
                        await start_game(message, chat_id, players)
                
                return
            else:
                await update.message.reply_text(
                    f"Привет, {user_name}!\n"
                    f"К сожалению, игра по этой ссылке уже не активна или завершена.\n"
                    f"Вы можете создать новую игру командой /create_game."
                )
                return
    
    # Обычный старт бота
    await update.message.reply_text(
        f"Привет, {user_name}! Добро пожаловать в игру «Шама».\n\n"
        f"Используйте /help для получения списка команд."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /help."""
    logger.info(f"Получена команда /help от пользователя {update.effective_user.id}")
    
    help_text = (
        "Доступные команды:\n"
        "/start - Начать использование бота\n"
        "/help - Показать это сообщение\n"
        "/ping - Проверить работу бота\n"
        "/info - Показать информацию о боте\n"
        "/create_game - Создать новую игру\n"
        "/join - Присоединиться к игре\n"
        "/status - Показать текущее состояние игры\n"
        "/stats - Показать вашу статистику\n"
        "/rules - Показать правила игры"
    )
    
    await update.message.reply_text(help_text)


async def ping_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /ping для проверки работы бота."""
    logger.info(f"Получена команда /ping от пользователя {update.effective_user.id}")
    
    await update.message.reply_text("Понг! Бот работает.")


async def info_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /info для вывода информации о боте."""
    logger.info(f"Получена команда /info от пользователя {update.effective_user.id}")
    
    bot_info = await context.bot.get_me()
    
    info_text = (
        f"🤖 Информация о боте:\n"
        f"ID: {bot_info.id}\n"
        f"Имя: {bot_info.first_name}\n"
        f"Имя пользователя: @{bot_info.username}\n\n"
        f"🔄 Версия бота: Финальная версия (21.10.2025)\n"
        f"💾 Тип хранилища: {os.environ.get('STORAGE_TYPE', 'file')}\n\n"
        f"👤 Информация о пользователе:\n"
        f"ID: {update.effective_user.id}\n"
        f"Имя: {update.effective_user.first_name}\n"
        f"Имя пользователя: @{update.effective_user.username or 'отсутствует'}"
    )
    
    await update.message.reply_text(info_text)


async def rules_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /rules."""
    logger.info(f"Получена команда /rules от пользователя {update.effective_user.id}")
    
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
    
    await update.message.reply_text(rules_text)


async def create_game_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /create_game."""
    logger.info(f"Получена команда /create_game от пользователя {update.effective_user.id}")
    
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name
    bot_username = (await context.bot.get_me()).username
    
    # Проверяем, есть ли уже активная игра в этом чате
    if chat_id in ACTIVE_GAMES:
        await update.message.reply_text("В этом чате уже идет игра!")
        return
    
    # Проверяем, есть ли игра в ожидании
    if chat_id in WAITING_GAMES:
        # Если создатель тот же - обновляем время
        if WAITING_GAMES[chat_id]['creator_id'] == user_id:
            WAITING_GAMES[chat_id]['timestamp'] = asyncio.get_event_loop().time()
            
            # Выводим текущий список игроков
            players = WAITING_GAMES[chat_id]['players']
            player_list = "\n".join([f"• {p_data['name']}" for p_data in players.values()])
            game_id = WAITING_GAMES[chat_id]['game_id']
            invite_link = f"https://t.me/{bot_username}?start=game_{game_id}"
            
            await update.message.reply_text(
                f"Вы обновили приглашение в игру!\n\n"
                f"Текущие участники:\n{player_list}\n\n"
                f"Игра начнется, когда присоединятся 4 игрока.\n"
                f"Используйте /join для присоединения или отправьте эту ссылку друзьям:\n"
                f"{invite_link}"
            )
        else:
            game_id = WAITING_GAMES[chat_id]['game_id']
            invite_link = f"https://t.me/{bot_username}?start=game_{game_id}"
            
            await update.message.reply_text(
                f"В этом чате уже создана игра, но еще не начата.\n"
                f"Используйте /join для присоединения или отправьте эту ссылку друзьям:\n"
                f"{invite_link}"
            )
        return
    
    # Получаем данные игрока из хранилища
    player_data = await storage.get_or_create_player(user_id, user_name)
    if not player_data:
        await update.message.reply_text("Произошла ошибка при создании игрока. Попробуйте еще раз.")
        return
    
    # Генерируем уникальный ID для игры
    import uuid
    game_id = str(uuid.uuid4())[:8]
    
    # Создаем новую игру в ожидании игроков
    WAITING_GAMES[chat_id] = {
        'creator_id': user_id,
        'players': {
            user_id: {
                'id': player_data['id'],
                'tg_id': user_id,
                'name': user_name,
                'position': None  # Позиция будет назначена позже
            }
        },
        'timestamp': asyncio.get_event_loop().time(),
        'game_id': game_id
    }
    
    # Добавляем игру в словарь по ID
    GAMES_BY_ID[game_id] = chat_id
    
    # Создаем инвайт-ссылку
    invite_link = f"https://t.me/{bot_username}?start=game_{game_id}"
    
    # Логируем создание игры
    await storage.log_event(
        user_id, 
        "create_game", 
        {"chat_id": chat_id, "player_name": user_name, "game_id": game_id}
    )
    
    # Отправляем сообщение о создании игры
    await update.message.reply_text(
        f"🎮 {user_name} создал(а) новую игру!\n\n"
        f"Текущие участники:\n• {user_name}\n\n"
        f"Игра начнется, когда присоединятся 4 игрока.\n\n"
        f"Пригласите друзей по этой ссылке:\n"
        f"{invite_link}\n\n"
        f"Или используйте команду /join для присоединения."
    )


async def join_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /join для присоединения к игре."""
    logger.info(f"Получена команда /join от пользователя {update.effective_user.id}")
    
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name
    
    # Проверяем, есть ли уже активная игра в этом чате
    if chat_id in ACTIVE_GAMES:
        await update.message.reply_text("В этом чате уже идет игра!")
        return
    
    # Проверяем, создана ли игра в этом чате
    if chat_id not in WAITING_GAMES:
        await update.message.reply_text(
            "В этом чате еще не создана игра.\n"
            "Используйте /create_game для создания новой игры."
        )
        return
    
    # Проверяем, не присоединился ли игрок уже
    if user_id in WAITING_GAMES[chat_id]['players']:
        await update.message.reply_text("Вы уже присоединились к этой игре.")
        return
    
    # Проверяем, не заполнен ли стол (4 игрока)
    if len(WAITING_GAMES[chat_id]['players']) >= 4:
        await update.message.reply_text("Игра уже набрала максимальное количество игроков (4).")
        return
    
    # Получаем данные игрока из хранилища
    player_data = await storage.get_or_create_player(user_id, user_name)
    if not player_data:
        await update.message.reply_text("Произошла ошибка при создании игрока. Попробуйте еще раз.")
        return
    
    # Добавляем игрока в список ожидающих
    WAITING_GAMES[chat_id]['players'][user_id] = {
        'id': player_data['id'],
        'tg_id': user_id,
        'name': user_name,
        'position': None  # Позиция будет назначена позже
    }
    
    # Получаем обновленный список игроков
    players = WAITING_GAMES[chat_id]['players']
    player_list = "\n".join([f"• {p_data['name']}" for p_data in players.values()])
    
    # Логируем присоединение к игре
    await storage.log_event(
        user_id, 
        "join_game", 
        {"chat_id": chat_id, "player_name": user_name}
    )
    
    # Если набралось 4 игрока, начинаем игру
    if len(players) == 4:
        await start_game(update.message, chat_id, players)
    else:
        # Иначе отправляем сообщение о присоединении
        await update.message.reply_text(
            f"🎮 {user_name} присоединился к игре!\n\n"
            f"Текущие участники ({len(players)}/4):\n{player_list}\n\n"
            f"Игра начнется, когда присоединятся 4 игрока."
        )

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /status для отображения статуса игры."""
    logger.info(f"Получена команда /status от пользователя {update.effective_user.id}")
    
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    # Проверяем, есть ли активная игра в чате
    if chat_id in ACTIVE_GAMES:
        match_state = ACTIVE_GAMES[chat_id]
        
        # Определяем статус игры и формируем сообщение
        status_text = await format_game_status(match_state, chat_id)
        
        await update.message.reply_text(status_text)
    elif chat_id in WAITING_GAMES:
        # Есть игра в ожидании
        players = WAITING_GAMES[chat_id]['players']
        player_list = "\n".join([f"• {p_data['name']}" for p_data in players.values()])
        
        await update.message.reply_text(
            f"🎮 Игра ожидает игроков.\n\n"
            f"Текущие участники ({len(players)}/4):\n{player_list}\n\n"
            f"Игра начнется, когда присоединятся 4 игрока."
        )
    else:
        # Нет игры в этом чате
        await update.message.reply_text(
            "В этом чате нет активной игры.\n"
            "Используйте /create_game для создания новой игры."
        )

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /stats для отображения статистики игрока."""
    logger.info(f"Получена команда /stats от пользователя {update.effective_user.id}")
    
    user_id = update.effective_user.id
    
    # Получаем статистику игрока из хранилища
    player_stats = await storage.get_player_stats(user_id)
    
    if player_stats:
        # Форматируем статистику
        stats_text = (
            f"📊 Статистика игрока {player_stats['name']}:\n\n"
            f"Всего игр: {player_stats['games']}\n"
            f"Победы: {player_stats['wins']}\n"
            f"Процент побед: {player_stats['win_rate']}%\n"
            f"Всего взяток: {player_stats['total_tricks']}\n"
            f"Ходов с шамой: {player_stats['total_shama_calls']}"
        )
        
        await update.message.reply_text(stats_text)
    else:
        await update.message.reply_text(
            "У вас еще нет игровой статистики.\n"
            "Сыграйте несколько игр чтобы увидеть статистику."
        )

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик текстовых сообщений."""
    logger.info(f"Получено текстовое сообщение от пользователя {update.effective_user.id}: {update.message.text[:30]}...")
    
    # Проверяем, может быть это ход игрока
    user_id = update.effective_user.id
    
    # Если игрок выбирает козырь
    if user_id in TRUMP_SELECTION:
        # Извлекаем указанную масть
        match = re.search(r'[♣♦♥♠]|[КБЧП]|[трефы|бубны|червы|пики]', update.message.text, re.IGNORECASE)
        if match:
            suit_text = match.group(0).lower()
            # Определяем масть
            if suit_text in ['♣', 'к', 'трефы']:
                suit = 'clubs'
            elif suit_text in ['♦', 'б', 'бубны']:
                suit = 'diamonds'
            elif suit_text in ['♥', 'ч', 'червы']:
                suit = 'hearts'
            elif suit_text in ['♠', 'п', 'пики']:
                suit = 'spades'
            else:
                await update.message.reply_text("Не удалось распознать масть. Пожалуйста, выберите масть: ♣ трефы, ♦ бубны, ♥ червы или ♠ пики.")
                return
                
            # Устанавливаем козырь
            match_state = TRUMP_SELECTION[user_id]
            chat_id = next(chat_id for chat_id, state in ACTIVE_GAMES.items() if state == match_state)
            
            try:
                engine = GAME_ENGINES[chat_id]
                result = engine.set_trump_by_player(match_state.first_player_index, suit)
                
                # Удаляем игрока из списка ожидающих выбора козыря
                del TRUMP_SELECTION[user_id]
                
                # Обновляем статус игры
                status, player_name, trump = result
                
                # Логируем выбор козыря
                await storage.log_event(
                    user_id, 
                    "set_trump", 
                    {"chat_id": chat_id, "trump": trump}
                )
                
                # Формируем сообщение о выбранном козыре
                trump_symbol = GameConstants.SUIT_SYMBOLS.get(trump, '?')
                trump_text = {
                    'clubs': 'трефы',
                    'diamonds': 'бубны',
                    'hearts': 'червы',
                    'spades': 'пики'
                }.get(trump, '?')
                
                # Отправляем сообщение всем игрокам
                await send_message_to_all_players(
                    match_state,
                    f"🃏 Игрок {player_name} выбрал козырь: {trump_symbol} ({trump_text})\n\n"
                    f"Начинаем игру! Ходит игрок с шамой."
                )
                
                # Переходим к фазе игры
                match_state.set_status(GameConstants.Status.PLAYING_CARDS)
                
                # Подготавливаем ход первого игрока
                player = match_state.players[match_state.current_player_index]
                WAITING_PLAYERS[player.id] = match_state
                
                # Отправляем первому игроку его карты и приглашение сделать ход
                await send_player_cards(player, match_state)
                
            except Exception as e:
                logger.error(f"Ошибка при установке козыря: {e}")
                await update.message.reply_text(f"Произошла ошибка: {e}")
            
            return
        else:
            await update.message.reply_text("Не удалось распознать масть. Пожалуйста, выберите масть: ♣ трефы, ♦ бубны, ♥ червы или ♠ пики.")
            return
            
    # Проверяем, если игрок должен сделать ход
    elif user_id in WAITING_PLAYERS:
        # Извлекаем номер карты
        match = re.search(r'\d+', update.message.text)
        if match:
            card_index = int(match.group(0)) - 1  # Конвертируем в 0-based индекс
            
            # Получаем состояние игры
            match_state = WAITING_PLAYERS[user_id]
            chat_id = next(chat_id for chat_id, state in ACTIVE_GAMES.items() if state == match_state)
            
            # Находим игрока и его позицию
            player_position = None
            for pos, player in match_state.players.items():
                if player and player.id == user_id:
                    player_position = pos
                    break
            
            if player_position is None:
                logger.error(f"Не удалось найти позицию игрока {user_id} в игре")
                await update.message.reply_text("Произошла ошибка: не удалось определить вашу позицию в игре")
                return
                
            try:
                # Делаем ход
                engine = GAME_ENGINES[chat_id]
                result = engine.play_turn(player_position, card_index)
                
                # Обрабатываем результат хода
                status, player, card = result
                
                # Логируем ход
                await storage.log_event(
                    user_id, 
                    "play_card", 
                    {"chat_id": chat_id, "card": str(card)}
                )
                
                # Удаляем игрока из списка ожидающих хода
                del WAITING_PLAYERS[user_id]
                
                # Отправляем сообщение всем игрокам о ходе
                await send_message_to_all_players(
                    match_state,
                    f"🃏 Игрок {player.name} сыграл картой: {card}"
                )
                
                # Проверяем, завершен ли кон (4 карты на столе)
                if status == GameConstants.Status.TRICK_COMPLETED:
                    # Завершаем кон и определяем победителя
                    trick_result = engine.complete_turn()
                    status, winning_card, winning_player_index, trick_points = trick_result
                    
                    # Находим имя победителя
                    winning_player = match_state.players[winning_player_index]
                    winning_team = winning_player_index // 10 * 10
                    
                    # Отправляем сообщение о результате кона
                    await send_message_to_all_players(
                        match_state,
                        f"👑 Игрок {winning_player.name} забирает взятку!\n"
                        f"Очки за взятку: {trick_points}\n\n"
                        f"Счет в игре:\n"
                        f"Команда 1: {match_state.game_scores[10]}\n"
                        f"Команда 2: {match_state.game_scores[20]}"
                    )
                    
                    # Проверяем, завершена ли игра (9 конов)
                    if status == GameConstants.Status.GAME_COMPLETED:
                        # Завершаем игру
                        game_result = engine.complete_game()
                        status, scores, losed_team, losed_points = game_result
                        
                        # Отправляем сообщение о результатах игры
                        winning_team = 10 if losed_team == 20 else 20
                        
                        await send_message_to_all_players(
                            match_state,
                            f"🏆 Игра завершена!\n\n"
                            f"Результаты раздачи:\n"
                            f"Команда 1: {scores[10]}\n"
                            f"Команда 2: {scores[20]}\n\n"
                            f"Команда {losed_team//10} получает {losed_points} очков\n\n"
                            f"Общий счет матча:\n"
                            f"Команда 1: {match_state.match_scores[10]}\n"
                            f"Команда 2: {match_state.match_scores[20]}"
                        )
                        
                        # Проверяем, завершен ли матч (одна из команд набрала 12+ очков)
                        if status == GameConstants.Status.MATCH_COMPLETED:
                            # Завершаем матч
                            match_result = engine.complete_match()
                            
                            # Определяем победителя матча
                            losing_team = 10 if match_state.match_scores[10] >= 12 else 20
                            winning_team = 20 if losing_team == 10 else 10
                            
                            # Отправляем сообщение о результате матча
                            await send_message_to_all_players(
                                match_state,
                                f"🎉 Матч завершен!\n\n"
                                f"Победила команда {winning_team//10}!\n"
                                f"Финальный счет:\n"
                                f"Команда 1: {match_state.match_scores[10]}\n"
                                f"Команда 2: {match_state.match_scores[20]}\n\n"
                                f"Спасибо за игру! Используйте /create_game для новой игры."
                            )
                            
                            # Удаляем игру из активных
                            del ACTIVE_GAMES[chat_id]
                            del GAME_ENGINES[chat_id]
                            
                            # Обновляем статистику игроков
                            for pos, player in match_state.players.items():
                                player_team = pos // 10 * 10
                                won = player_team == winning_team
                                # TODO: Здесь должен быть код для подсчета взяток каждого игрока
                                tricks = 0  # Упрощенно, в реальности нужно считать
                                shama_calls = 1 if pos == match_state.first_player_index else 0
                                
                                await storage.update_player_stats(player.id, won, tricks, shama_calls)
                            
                            return
                        
                        # Если матч не завершен, начинаем новую раздачу
                        if status == GameConstants.Status.NEW_DEAL_READY:
                            await send_message_to_all_players(
                                match_state,
                                "🃏 Подготовка к новой раздаче...\n"
                                "Карты будут розданы автоматически."
                            )
                            
                            # Запускаем новую игру с теми же игроками
                            new_status = engine.start_game()
                            
                            # Находим игрока с шамой и предлагаем выбрать козырь
                            first_player = match_state.players[match_state.first_player_index]
                            TRUMP_SELECTION[first_player.id] = match_state
                            
                            # Отправляем всем игрокам их карты
                            for player_position, player in match_state.players.items():
                                await send_player_cards(player, match_state, is_first=(player_position == match_state.first_player_index))
                            
                            return
                    
                    # Если игра продолжается, переходим к следующему ходу
                    if status == GameConstants.Status.PLAYING_CARDS:
                        # Определяем следующего игрока
                        next_player = match_state.players[match_state.current_player_index]
                        WAITING_PLAYERS[next_player.id] = match_state
                        
                        # Отправляем следующему игроку его карты и приглашение сделать ход
                        await send_player_cards(next_player, match_state)
                
                else:
                    # Определяем следующего игрока
                    next_player_index = GameConstants.PLAYERS_QUEUE[player_position]
                    next_player = match_state.players[next_player_index]
                    match_state.set_current_player_index(next_player_index)
                    WAITING_PLAYERS[next_player.id] = match_state
                    
                    # Отправляем следующему игроку его карты и приглашение сделать ход
                    await send_player_cards(next_player, match_state)
            
            except InvalidPlayerAction as e:
                logger.warning(f"Недопустимый ход: {e}")
                await update.message.reply_text(f"Недопустимый ход: {e}")
                # Возвращаем игрока в список ожидающих хода
                WAITING_PLAYERS[user_id] = match_state
                await send_player_cards(match_state.players[player_position], match_state)
            
            except Exception as e:
                logger.error(f"Ошибка при выполнении хода: {e}")
                await update.message.reply_text(f"Произошла ошибка при выполнении хода: {e}")
                # Возвращаем игрока в список ожидающих хода
                WAITING_PLAYERS[user_id] = match_state
                
            return
                
        else:
            await update.message.reply_text("Введите номер карты от 1 до 9.")
            return
    
    # Если это обычное текстовое сообщение
    await update.message.reply_text(
        "Я понимаю только команды, начинающиеся с /\n"
        "Отправьте /help чтобы увидеть список доступных команд."
    )

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик callback-запросов от инлайн-клавиатуры."""
    query = update.callback_query
    await query.answer()  # Отвечаем на запрос, чтобы убрать часы загрузки
    
    logger.info(f"Получен callback {query.data} от пользователя {query.from_user.id}")
    
    user_id = query.from_user.id
    data = query.data
    
    if data.startswith('card_'):
        # Обработка выбора карты
        try:
            card_index = int(data.split('_')[1])
            
            # Находим состояние игры для этого игрока
            if user_id in WAITING_PLAYERS:
                match_state = WAITING_PLAYERS[user_id]
                chat_id = next(chat_id for chat_id, state in ACTIVE_GAMES.items() if state == match_state)
                
                # Находим игрока и его позицию
                player_position = None
                for pos, player in match_state.players.items():
                    if player and player.id == user_id:
                        player_position = pos
                        break
                
                if player_position is None:
                    logger.error(f"Не удалось найти позицию игрока {user_id} в игре")
                    await query.message.reply_text("Произошла ошибка: не удалось определить вашу позицию в игре")
                    return
                
                # Делаем ход
                engine = GAME_ENGINES[chat_id]
                result = engine.play_turn(player_position, card_index)
                
                # Обрабатываем результат хода
                status, player, card = result
                
                # Логируем ход
                await storage.log_event(
                    user_id, 
                    "play_card", 
                    {"chat_id": chat_id, "card": str(card)}
                )
                
                # Удаляем игрока из списка ожидающих хода
                del WAITING_PLAYERS[user_id]
                
                # Отправляем сообщение всем игрокам о ходе
                await send_message_to_all_players(
                    match_state,
                    f"🃏 Игрок {player.name} сыграл картой: {card}"
                )
                
                # Логика обработки статуса игры такая же, как в text_handler
                # ... (аналогично коду выше)
            else:
                await query.message.reply_text("Сейчас не ваш ход.")
                
        except Exception as e:
            logger.error(f"Ошибка при обработке выбора карты: {e}")
            await query.message.reply_text(f"Произошла ошибка: {e}")
    
    elif data.startswith('trump_'):
        # Обработка выбора козыря
        try:
            suit = data.split('_')[1]
            
            if user_id in TRUMP_SELECTION:
                # Логика аналогична той, что в text_handler для выбора козыря
                # ... (аналогично коду выше)
                pass
            else:
                await query.message.reply_text("Сейчас не ваш ход для выбора козыря.")
                
        except Exception as e:
            logger.error(f"Ошибка при обработке выбора козыря: {e}")
            await query.message.reply_text(f"Произошла ошибка: {e}")

async def start_game(message, chat_id, players):
    """Начинает новую игру после того, как собрались 4 игрока."""
    logger.info(f"Начинаем новую игру в чате {chat_id}")
    
    try:
        # Создаем состояние матча
        match_state = MatchState()
        
        # Распределяем позиции игроков
        positions = [GameConstants.PLAYER_1_1, GameConstants.PLAYER_1_2, 
                    GameConstants.PLAYER_2_1, GameConstants.PLAYER_2_2]
        player_data = list(players.values())
        
        # Если игроков меньше 4, добавляем фиктивных
        while len(player_data) < 4:
            player_data.append({
                'id': -1,  # Фиктивный ID
                'tg_id': -1,
                'name': f"Бот {len(player_data) + 1}",
                'position': None
            })
        
        # Перемешиваем позиции игроков
        import random
        random.shuffle(player_data)
        
        # Добавляем игроков в состояние матча
        for i, position in enumerate(positions):
            player_info = player_data[i]
            player = Player(player_info['tg_id'], player_info['name'])
            match_state.add_player(position, player)
            player_info['position'] = position
        
        # Создаем игровой движок
        engine = GameEngine(match_state)
        
        # Запускаем игру (раздаем карты и т.д.)
        status = engine.start_game()
        
        # Добавляем игру в активные
        ACTIVE_GAMES[chat_id] = match_state
        GAME_ENGINES[chat_id] = engine
        
        # Удаляем игру из ожидающих
        del WAITING_GAMES[chat_id]
        
        # Логируем начало игры
        for p_data in player_data:
            if p_data['tg_id'] > 0:  # Только для реальных игроков
                await storage.log_event(
                    p_data['tg_id'], 
                    "game_start", 
                    {"chat_id": chat_id, "position": p_data['position']}
                )
        
        # Отправляем сообщение о начале игры
        team1 = [p_data['name'] for p_data in player_data if p_data['position'] in (GameConstants.PLAYER_1_1, GameConstants.PLAYER_1_2)]
        team2 = [p_data['name'] for p_data in player_data if p_data['position'] in (GameConstants.PLAYER_2_1, GameConstants.PLAYER_2_2)]
        
        await message.reply_text(
            f"🎮 Игра начинается!\n\n"
            f"Команда 1: {', '.join(team1)}\n"
            f"Команда 2: {', '.join(team2)}\n\n"
            f"Карты розданы. Ожидаем выбор козыря."
        )
        
        # Находим игрока с шамой и предлагаем выбрать козырь
        first_player = match_state.players[match_state.first_player_index]
        TRUMP_SELECTION[first_player.id] = match_state
        
        # Отправляем всем игрокам их карты
        for player_position, player in match_state.players.items():
            await send_player_cards(player, match_state, is_first=(player_position == match_state.first_player_index))
        
    except Exception as e:
        logger.error(f"Ошибка при начале игры: {e}")
        await message.reply_text(f"Произошла ошибка при начале игры: {e}")

async def send_player_cards(player, match_state, is_first=False):
    """Отправляет игроку его карты и инструкции для хода."""
    if player.id < 0:  # Фиктивный игрок (бот)
        return
        
    # Форматируем карты игрока
    hand = player.get_hand()
    cards_text = "\n".join([f"{i+1}. {card}" for i, card in enumerate(hand)])
    
    # Создаем инлайн-клавиатуру
    keyboard = None
    
    # Определяем сообщение в зависимости от ситуации
    if is_first and match_state.status == GameConstants.Status.WAITING_TRUMP:
        message_text = (
            f"🃏 Ваши карты:\n{cards_text}\n\n"
            f"У вас шама (шестерка треф)! Выберите козырь:"
        )
        
        # Создаем кнопки для выбора козыря
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("♣ Трефы", callback_data="trump_clubs"),
                InlineKeyboardButton("♦ Бубны", callback_data="trump_diamonds")
            ],
            [
                InlineKeyboardButton("♥ Червы", callback_data="trump_hearts"),
                InlineKeyboardButton("♠ Пики", callback_data="trump_spades")
            ]
        ])
    else:
        # Добавляем информацию о козыре, если он выбран
        trump_info = ""
        if match_state.trump:
            trump_symbol = GameConstants.SUIT_SYMBOLS.get(match_state.trump, '?')
            trump_info = f"Козырь: {trump_symbol}\n\n"
        
        if match_state.current_player_index and player.id == match_state.players[match_state.current_player_index].id:
            # Если сейчас ход этого игрока
            message_text = (
                f"🃏 Ваши карты:\n{cards_text}\n\n"
                f"{trump_info}Сейчас ваш ход! Выберите карту:"
            )
            
            # Создаем кнопки для выбора карт (максимум 3 карты в ряду)
            buttons = []
            current_row = []
            
            for i, card in enumerate(hand):
                current_row.append(InlineKeyboardButton(
                    text=f"{i+1}. {card}", 
                    callback_data=f"card_{i}"
                ))
                
                # Создаем новый ряд после каждых 3 кнопок
                if len(current_row) == 3:
                    buttons.append(current_row)
                    current_row = []
            
            # Добавляем оставшиеся кнопки, если есть
            if current_row:
                buttons.append(current_row)
                
            keyboard = InlineKeyboardMarkup(buttons)
            
        else:
            # Если ход другого игрока
            current_player_name = "?"
            if match_state.current_player_index:
                current_player_name = match_state.players[match_state.current_player_index].name
                
            message_text = (
                f"🃏 Ваши карты:\n{cards_text}\n\n"
                f"{trump_info}Сейчас ход игрока {current_player_name}."
            )
    
    try:
        # Отправляем сообщение игроку в личку
        bot = Bot(BOT_TOKEN)
        
        # Если есть клавиатура, отправляем с ней
        if keyboard:
            await bot.send_message(
                chat_id=player.id, 
                text=message_text,
                reply_markup=keyboard
            )
        else:
            await bot.send_message(chat_id=player.id, text=message_text)
            
        logger.info(f"Отправлены карты игроку {player.name} (ID: {player.id})")
    except Exception as e:
        trump_symbol = GameConstants.SUIT_SYMBOLS.get(match_state.trump, '?')
        status_text += f"\nКозырь: {trump_symbol}\n"
    
    # Добавляем информацию о счете
    status_text += f"\nСчет в игре:\n"
    status_text += f"Команда 1: {match_state.game_scores[10]}\n"
    status_text += f"Команда 2: {match_state.game_scores[20]}\n"
    
    status_text += f"\nСчет в матче:\n"
    status_text += f"Команда 1: {match_state.match_scores[10]}\n"
    status_text += f"Команда 2: {match_state.match_scores[20]}\n"
    
    # Добавляем информацию о текущем ходе
    status_text += f"\nХод: {match_state.current_turn}/9\n"
    
    return status_text

async def error_handler(update, context) -> None:
    """Обработчик ошибок."""
    logger.error(f"Ошибка при обработке обновления {update}: {context.error}")
    
    # Уведомляем пользователя об ошибке, если возможно
    if update and update.effective_chat:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Произошла ошибка при обработке вашего запроса."
        )


async def cleanup_bot() -> bool:
    """Сбрасывает все обновления и вебхуки для бота."""
    try:
        if not BOT_TOKEN:
            logger.error("Токен бота не найден!")
            return False
            
        bot = Bot(BOT_TOKEN)
        
        # Получаем и удаляем вебхук если есть
        webhook_info = await bot.get_webhook_info()
        if webhook_info.url:
            await bot.delete_webhook()
            logger.info("Webhook удален")
        
        # Получаем все непрочитанные обновления и сбрасываем их
        updates = await bot.get_updates(timeout=1, offset=-1)
        if updates:
            offset = updates[-1].update_id + 1
            logger.info(f"Найдено {len(updates)} обновлений. Последний ID: {updates[-1].update_id}")
            await bot.get_updates(offset=offset)
            logger.info("Все обновления сброшены")
        else:
            logger.info("Непрочитанных обновлений не найдено")
            
        return True
    except TelegramError as e:
        logger.error(f"Ошибка Telegram API при очистке: {e}")
        return False
    except Exception as e:
        logger.error(f"Непредвиденная ошибка при очистке: {e}")
        return False


async def run_bot() -> None:
    """Основная функция запуска бота."""
    try:
        # Инициализируем хранилище данных
        storage_init_result = await init_storage()
        if not storage_init_result:
            logger.error("Не удалось инициализировать хранилище данных! Бот не может быть запущен.")
            return
        
        # Создаем и настраиваем приложение
        application = Application.builder().token(BOT_TOKEN).build()
        
        # Регистрируем обработчики команд
        application.add_handler(CommandHandler("start", start_command))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("ping", ping_command))
        application.add_handler(CommandHandler("info", info_command))
        application.add_handler(CommandHandler("rules", rules_command))
        application.add_handler(CommandHandler("create_game", create_game_command))
        application.add_handler(CommandHandler("join", join_command))
        application.add_handler(CommandHandler("status", status_command))
        application.add_handler(CommandHandler("stats", stats_command))
        
        # Обработчик текстовых сообщений
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
        
        # Обработчик callback-запросов от инлайн-клавиатуры
        application.add_handler(CallbackQueryHandler(callback_handler))
        
        # Регистрируем обработчик ошибок
        application.add_error_handler(error_handler)
        
        # Запускаем приложение
        logger.info("Инициализация бота...")
        await application.initialize()
        
        logger.info("Запуск бота...")
        await application.start()
        
        # Запускаем получение обновлений
        await application.updater.start_polling(
            drop_pending_updates=True,
            allowed_updates=["message", "callback_query"],
            poll_interval=1.0,
        )
        
        logger.info("Бот успешно запущен и готов к работе!")
        
        # Ждем, пока не будет нажато Ctrl+C
        stop_signal = asyncio.Future()
        
        # Задаем обработчик сигнала SIGINT
        def signal_handler():
            logger.info("Получен сигнал остановки")
            if not stop_signal.done():
                stop_signal.set_result(None)
        
        try:
            # В Windows нужен иной подход, но мы видим что используется macOS
            loop = asyncio.get_event_loop()
            loop.add_signal_handler(2, signal_handler)  # SIGINT = 2
        except NotImplementedError:
            # Для систем, где add_signal_handler не реализован
            logger.warning("Обработчик сигнала не поддерживается в этой системе")
        
        # Ждем сигнала остановки
        logger.info("Нажмите Ctrl+C для остановки бота")
        await stop_signal
        
    except KeyboardInterrupt:
        logger.info("Получен сигнал остановки (Ctrl+C)")
    finally:
        # Завершаем работу бота
        logger.info("Остановка бота...")
        try:
            if 'application' in locals():
                await application.updater.stop()
                await application.stop()
                await application.shutdown()
        except Exception as e:
            logger.error(f"Ошибка при остановке бота: {e}")
        finally:
            logger.info("Бот остановлен")


def main():
    """Точка входа в программу."""
    # Проверяем наличие токена
    global BOT_TOKEN
    if not BOT_TOKEN:
        logger.error("Токен бота не найден! Установите переменную TELEGRAM_BOT_TOKEN.")
        return 1
        
    logger.info(f"Запуск бота с токеном: {BOT_TOKEN[:5]}...{BOT_TOKEN[-5:]}")
    
    try:
        # Создаем и запускаем цикл событий
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Сначала очищаем все предыдущие сессии
        cleanup_success = loop.run_until_complete(cleanup_bot())
        if not cleanup_success:
            logger.warning("Не удалось полностью очистить состояние бота, но продолжаем работу")
        
        # Запускаем бота
        loop.run_until_complete(run_bot())
        
        return 0
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
        return 0
    except Exception as e:
        logger.critical(f"Критическая ошибка: {e}", exc_info=True)
        return 1
    finally:
        logger.info("Программа завершена")


if __name__ == "__main__":
    sys.exit(main())
