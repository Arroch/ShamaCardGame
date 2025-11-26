"""
TG bot для карточной игры "Шама".

Предоставляет интерфейс для игры в карты "Шама" через сообщения телеграм.
Поддерживает онлайн игру.

Автор: ShamaVibe Team
"""

import os
import sys
from datetime import datetime
import logging
import asyncio

from telegram import Bot, Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    filters, ContextTypes
)
from telegram.error import TelegramError
from dotenv import load_dotenv

# Импорт модулей игры
from core import GameEngine, MatchState, Player, GameException, InvalidPlayerAction
from constants import GameConstants
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
WAITING_MATCHES = {}  # Хранит ожидающие игры {match_id: {creator_id, players: {}, timestamp, game_id}}
ACTIVE_MATCHES = {}  # Хранит активные игры {match_id: MatchState}
HOLDING_MATCHES = {}  # Хранит приостановленные игры {match_id: MatchState}
MATCH_ENGINES = {}  # Игровые движки {match_id: GameEngine}
PLAYER_TO_GAME = {} # Хранит игроков в игре{player_id: match_id}

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
    logger.info(f"Получена команда /start от пользователя {update.effective_user.username}")
    player_id = update.effective_user.id
    first_name = update.effective_user.first_name
    username = update.effective_user.username
    
    # Сохраняем или обновляем данные игрока
    player_data = await storage.get_or_create_player(
        player_id, 
        username,
        first_name,
    )
    
    if player_data:
        logger.info(f"Игрок {player_data['name']} (ID: {player_data['id']}) зарегистрирован")
    else:
        logger.warning(f"Не удалось зарегистрировать игрока {player_id}-{username}")
    
    # Проверяем, не является ли это присоединением к игре через инвайт-ссылку
    if context.args and context.args[0].startswith('join_'):
        match_id = context.args[0][5:]  # Получаем ID матча из аргумента
            
        # Проверяем, активна ли еще игра
        if match_id in WAITING_MATCHES:
            # Проверяем, не присоединился ли игрок уже
            if player_id in WAITING_MATCHES[match_id]['players']:
                await update.message.reply_text(
                    f"Привет, {first_name}! Вы уже присоединились к этой игре.\n"
                    f"Ожидайте начала игры."
                )
            # Проверяем, не заполнен ли стол (4 игрока)
            elif len(WAITING_MATCHES[match_id]['players']) >= 4:
                await update.message.reply_text(
                    f"Привет, {first_name}!\n"
                    f"К сожалению, в игре уже набралось максимальное количество игроков (4)."
                )
            else:
                # Добавляем игрока
                WAITING_MATCHES[match_id]['players'][player_id] = player_data.copy()
                PLAYER_TO_GAME[player_data['id']] = {
                    'id':match_id,
                    'status': 'waiting',
                    'position': None
                }
                # Логируем присоединение к игре
                await storage.log_event(
                    player_id, 
                    username,
                    "join_match", 
                    match_id
                )
                # Отправляем сообщение о выборе комамнды, если есть не полные команды
                if len(WAITING_MATCHES[match_id]['team_1']) < 2 and len(WAITING_MATCHES[match_id]['team_2']) < 2:
                    message_text = (f"Выберите команду:\n"
                    f"Команда 1: {WAITING_MATCHES[match_id]['team_1']}\n"
                    f"Команда 2: {WAITING_MATCHES[match_id]['team_2']}\n\n")
                    keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("Команда 1", callback_data="team_1"),
                    InlineKeyboardButton("Команда 2", callback_data="team_2")
                ]
            ])
                    await context.bot.send_message(
                        chat_id=player_id, 
                        text=message_text,
                        reply_markup=keyboard
                    )
                else:
                    match_id = PLAYER_TO_GAME[player_id]['id']
                    team = 1 if len(WAITING_MATCHES[match_id]['team_1']) < 2 else 2
                    players_cnt = len(WAITING_MATCHES[match_id][f"team_{team}"])
                    position = int(f"{team}{players_cnt + 1}")
                    
                    WAITING_MATCHES[match_id][f"team_{team}"].append(f'{first_name} ({username})')
                    PLAYER_TO_GAME[player_id]['position'] = position

                    # Получаем обновленный список игроков
                    players = WAITING_MATCHES[match_id]['players']
                    
                    # Отправляем сообщения другим игрокам
                    for chat_id in players:
                        if chat_id > 0:
                            await context.bot.send_message(
                                chat_id=chat_id,
                                text=f"🎮 {first_name} присоединился к игре!\n\n"
                                        f"Текущие участники ({len(players)}/4):\n"
                                        f"Команда 1: {WAITING_MATCHES[match_id]['team_1']}\n"
                                        f"Команда 2: {WAITING_MATCHES[match_id]['team_2']}\n\n"
                            )
                    
                    # Если набралось 4 игрока, начинаем игру
                    if len(players) == 4:
                        message = await context.bot.send_message(
                            chat_id=chat_id,
                            text="Набралось 4 игрока! Игра начинается..."
                        )
                        await start_game(message, match_id, players)

            return
        elif match_id in ACTIVE_MATCHES:
            if player_id in PLAYER_TO_GAME and PLAYER_TO_GAME[player_id]['id'] == match_id:
                await update.message.reply_text(
                f"Привет, {first_name}!\n"
                f"Вы уже состоите в этой игре и она уже идет.\n"
            )
            else:
                await update.message.reply_text(
                    f"Привет, {first_name}!\n"
                    f"К сожалению, игра по этой ссылке уже идет.\n"
                    f"Вы можете создать новую игру командой /create_game."
                )
            return
        else:
            await update.message.reply_text(
                f"Привет, {first_name}!\n"
                f"К сожалению, игра по этой ссылке уже не активна или завершена.\n"
                f"Вы можете создать новую игру командой /create_game."
            )
            return
    
    # Обычный старт бота
    await update.message.reply_text(
        f"Привет, {first_name}! Добро пожаловать в игру «Шама».\n\n"
        f"Используйте /help для получения списка команд."
    )

async def create_game_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /create_game."""
    logger.info(f"Получена команда /create_game от пользователя {update.effective_user.username}")
    
    player_id = update.effective_user.id
    first_name = update.effective_user.first_name
    username = update.effective_user.username
    bot_username = (await context.bot.get_me()).username
    
    # Проверяем, состоит ли игрок в активной или ожидающей игре игре
    if player_id in PLAYER_TO_GAME:
        await update.message.reply_text(f"Вы уже состоите в игре. \n"
                                        f"Покиньте или завершите ее, для создания новой игры")
        

        # Выводим инфу по активной игре
        game_id = PLAYER_TO_GAME[player_id]['id']
        game_status = PLAYER_TO_GAME[player_id]['status']
        if game_status == 'waiting':
            players = WAITING_MATCHES[game_id]['players']
            player_list = "\n".join([f"• {p_data['name']}" for p_data in players.values()])
            invite_link = f"https://t.me/{bot_username}?start=join_{game_id}"
            await update.message.reply_text(
                f"Ваша игра в ожидании игроков!\n\n"
                f"Текущие участники:\n{player_list}\n\n"
                f"Игра начнется, когда присоединятся 4 игрока.\n"
                f"Для присоединения к игре отправьте эту ссылку друзьям:\n"
                f"{invite_link}\n"
                f"/start join_{game_id}"
            )
            return
        else:
            match_state = ACTIVE_MATCHES[game_id]
            await update.message.reply_text(
                f"Ваша игра уже идет!\n\n"
                f"Статус игры:\n"
                f"{match_state.players[GameConstants.PLAYER_1_1]} и "
                f"{match_state.players[GameConstants.PLAYER_1_2]} - счет: "
                f"{match_state.match_scores[GameConstants.TEAM_1]}\n"
                f"{match_state.players[GameConstants.PLAYER_2_1]} и "
                f"{match_state.players[GameConstants.PLAYER_2_2]} - счет: "
                f"{match_state.match_scores[GameConstants.TEAM_2]}\n"
                f"Козырь: {GameConstants.SUIT_SYMBOLS[match_state.trump]}, хвалил: "
                f"{match_state.players[match_state.first_player_index]}\n"
                f"Номер хода: {match_state.current_turn}\n"
                f"Карты на столе: {match_state.show_table()}\n"
            )
            return
    
    # Получаем данные игрока из хранилища
    player_data = await storage.get_or_create_player(player_id, username, first_name)
    if not player_data:
        await update.message.reply_text("Произошла ошибка при создании игрока. Попробуйте еще раз.")
        return
    
    # Генерируем уникальный ID для игры
    import uuid
    match_id = str(int(datetime.now().timestamp())) + str(uuid.uuid4())[:8]
    
    # Создаем новую игру в ожидании игроков
    WAITING_MATCHES[match_id] = {
        'creator_id': player_id,
        'players': {
            player_id: player_data.copy()
        },
        'team_1': [f"{player_data['name']} ({player_data['username']})"],
        'team_2': [],
        'timestamp': asyncio.get_event_loop().time(),
    }
    PLAYER_TO_GAME[player_id] = {
        'id': match_id,
        'status': 'waiting',
        'position': GameConstants.PLAYER_1_1
    }
    

    # Создаем инвайт-ссылку
    invite_link = f"https://t.me/{bot_username}?start=join_{match_id}"
    
    # Логируем создание игры
    await storage.log_event(
        player_id, 
        username,
        "create_game", 
        match_id, 
    )
    
    # Отправляем сообщение о создании игры
    await update.message.reply_text(
        f"🎮 {first_name} создал(а) новую игру!\n\n"
        f"Текущие участники:\n• {first_name}\n\n"
        f"Игра начнется, когда присоединятся 4 игрока.\n\n"
        f"Пригласите друзей по этой ссылке:\n"
        f"{invite_link}\n\n"
        f"/start join_{match_id}"
    )
            
async def start_game(message, match_id, players):
    """Начинает новую игру после того, как собрались 4 игрока."""
    logger.info(f"Начинаем новую игру {match_id}")
    
    try:
        # Создаем состояние матча
        match_state = MatchState()
        players_data = list(players.values())
        
        # Добавляем игроков в состояние матча
        for player_data in players_data:
            player = Player(player_data['id'], player_data['name'])
            match_state.add_player(PLAYER_TO_GAME[player_data['id']]['position'], player)
            PLAYER_TO_GAME[player_data['id']]['status'] = 'active'
            
        # Создаем игровой движок
        engine = GameEngine(match_state)
        
        # Запускаем игру (раздаем карты и т.д.)
        engine.start_game()
        
        # Добавляем игру в активные
        ACTIVE_MATCHES[match_id] = match_state
        MATCH_ENGINES[match_id] = engine
        
        # Удаляем игру из ожидающих
        del WAITING_MATCHES[match_id]
        
        # Отправляем сообщение о начале игры
        team1 = [match_state.players[GameConstants.PLAYER_1_1].name, match_state.players[GameConstants.PLAYER_1_2].name]
        team2 = [match_state.players[GameConstants.PLAYER_2_1].name, match_state.players[GameConstants.PLAYER_2_2].name]
        
        await message.reply_text(
            f"🎮 Игра начинается!\n\n"
            f"Команда 1: {', '.join(team1)}\n"
            f"Команда 2: {', '.join(team2)}\n\n"
            f"Карты розданы. Ожидаем выбор козыря."
        )
        
        # Отправляем всем игрокам их карты
        for player_position, player in match_state.players.items():
            await send_player_cards(player, match_state, is_first=(player_position == match_state.first_player_index))
        
    except Exception as e:
        logger.error(f"Ошибка при начале игры: {e}")
        await message.reply_text(f"Произошла ошибка при начале игры: {e}")

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик callback-запросов от инлайн-клавиатуры."""
    query = update.callback_query
    await query.answer()  # Отвечаем на запрос, чтобы убрать часы загрузки
    
    logger.info(f"Получен callback {query.data} от пользователя {query.from_user.id}")
    
    player_id = query.from_user.id
    username = query.from_user.username
    first_name = query.from_user.first_name
    data = query.data

    if data.startswith('card_'):
        # Обработка выбора карты
        try:
            card_index = int(data.split('_')[1])
            
            # Находим состояние игры для этого игрока
            match_id = PLAYER_TO_GAME[player_id]['id']
            match_state = ACTIVE_MATCHES[match_id]
            match_engine = MATCH_ENGINES[match_id]
            player_position = PLAYER_TO_GAME[player_id]['position']
            
            # Делаем ход
            try:
                status, player, card = match_engine.play_turn(player_position, card_index)
                
                # Обновляем сообщение чтобы показать выбор карты
                await query.edit_message_text(
                    text=f"{query.message.text}\n\nВы выбрали карту: {card}",
                    reply_markup=None  # Удаляем клавиатуру после выбора
                )
                
                # Логируем ход
                await storage.log_event(
                    player_id,
                    username,
                    "play_card", 
                    str(card)
                )
                
                # Отправляем сообщение всем игрокам о ходе
                await send_message_to_all_players(
                    match_state,
                    f"🃏 Игрок {player.name} сыграл картой: {card}"
                )
                
                # Проверяем, завершен ли кон (4 карты на столе)
                if status == GameConstants.Status.TRICK_COMPLETED:
                    # Завершаем кон и определяем победителя
                    trick_result = match_engine.complete_turn()
                    status, winning_card, winning_player_index, trick_points = trick_result
                    
                    # Находим имя победителя
                    winning_player = match_state.players[winning_player_index]
                    winning_team = winning_player_index // 10 * 10
                    
                    # Отправляем сообщение о результате кона
                    await send_message_to_all_players(
                        match_state,
                        f"👑 Игрок {winning_player.name} забирает взятку с {winning_card}!\n"
                        f"Очки за взятку: {trick_points}\n\n"
                    )
                    
                    # Проверяем, завершена ли игра (9 конов)
                    if status == GameConstants.Status.GAME_COMPLETED:
                        # Завершаем игру
                        game_result = match_engine.complete_game()
                        status, scores, losed_team, _, losed_points_text = game_result
                        
                        # Отправляем сообщение о результатах игры
                        winning_team = 10 if losed_team == 20 else 20
                        
                        await send_message_to_all_players(
                            match_state,
                            f"🏆 Игра завершена!\n\n"
                            f"Результаты раздачи:\n"
                            f"Козырь хвалил: "
                            f"{match_state.players[match_state.first_player_index]}\n"
                            f"Команда 1: {match_state.players[GameConstants.PLAYER_1_1]} и "
                            f"{match_state.players[GameConstants.PLAYER_1_2]}: "
                            f"{scores[10]}\n"
                            f"Команда 2: {match_state.players[GameConstants.PLAYER_2_1]} и "
                            f"{match_state.players[GameConstants.PLAYER_2_2]}: "
                            f"{scores[20]}\n\n"
                            f"Команда {losed_team//10} получает {losed_points_text}\n\n"
                            f"Общий счет матча:\n"
                            f"Команда 1: {match_state.match_scores[10]}\n"
                            f"Команда 2: {match_state.match_scores[20]}"
                        )
                        
                        # Проверяем, завершен ли матч (одна из команд набрала 12+ очков)
                        if status == GameConstants.Status.MATCH_COMPLETED:
                            # Завершаем матч
                            match_engine.complete_match()
                            
                            # Определяем победителя матча
                            losing_team = 10 if match_state.match_scores[10] >= 12 else 20
                            winning_team = 20 if losing_team == 10 else 10
                            
                            # Отправляем сообщение о результате матча
                            await send_message_to_all_players(
                                match_state,
                                f"🎉 Матч завершен!\n\n"
                                f"Победила Команда {winning_team//10}: "
                                f"{match_state.players[winning_team + 1]} и "
                                f"{match_state.players[winning_team + 2]}\n"
                                f"Финальный счет:\n"
                                f"Команда 1: {match_state.match_scores[10]}\n"
                                f"Команда 2: {match_state.match_scores[20]}\n\n"
                                f"Спасибо за игру! Используйте /create_game для новой игры."
                            )
                            
                            # Удаляем игру из активных
                            del ACTIVE_MATCHES[match_id]
                            del MATCH_ENGINES[match_id]
                            
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
                            match_engine.start_game()

                            # Отправляем всем игрокам их карты
                            for player_position, player in match_state.players.items():
                                await send_player_cards(player, match_state, is_first=(player_position == match_state.first_player_index))
                            return
                    
                    # Если игра продолжается, переходим к следующему ходу
                    if status == GameConstants.Status.PLAYING_CARDS:
                        # Отправляем следующему игроку его карты и приглашение сделать ход
                        next_player = match_state.players[match_state.current_player_index]
                        await send_player_cards(next_player, match_state)
                
                else:
                    # Отправляем следующему игроку его карты и приглашение сделать ход
                    next_player = match_state.players[match_state.current_player_index]
                    await send_player_cards(next_player, match_state)
            
            except InvalidPlayerAction as e:
                logger.warning(f"Недопустимый ход: {e}")
                await query.message.reply_text(f"Недопустимый ход: {e}")
                await send_player_cards(match_state.players[player_position], match_state)
            
            except Exception as e:
                logger.error(f"Ошибка при выполнении хода: {e}")
                await query.message.reply_text(f"Произошла ошибка при выполнении хода: {e}")
                
        except Exception as e:
            logger.error(f"Ошибка при обработке выбора карты: {e}")
            await query.message.reply_text(f"Произошла ошибка: {e}")
    
    elif data.startswith('trump_'):
        # Обработка выбора козыря
        try:
            suit = data.split('_')[1]
            match_id = PLAYER_TO_GAME[player_id]['id']
            match_state = ACTIVE_MATCHES[match_id]
            match_engine = MATCH_ENGINES[match_id]
            # player_position = PLAYER_TO_GAME[player_id]['position']
            
            try:
                match_engine = MATCH_ENGINES[match_id]
                status, player_name, trump = match_engine.set_trump_by_player(match_state.first_player_index, suit)
                
                # Обновляем сообщение чтобы показать выбор масти
                suit_symbol = GameConstants.SUIT_SYMBOLS.get(suit, '?')
                suit_text = {
                    'clubs': 'трефы',
                    'diamonds': 'бубны',
                    'hearts': 'червы',
                    'spades': 'пики'
                }.get(suit, '?')
                
                await query.edit_message_text(
                    text=f"{query.message.text}\n\nВы выбрали козырь: {suit_symbol} ({suit_text})",
                    reply_markup=None  # Удаляем клавиатуру после выбора
                )

                # Логируем выбор козыря
                await storage.log_event(
                    player_id,
                    username,
                    "set_trump", 
                    trump
                )
                
                # Отправляем сообщение всем игрокам
                await send_message_to_all_players(
                    match_state,
                    f"🃏 Игрок {player_name} выбрал козырь: {suit_symbol} ({suit_text})\n\n"
                    f"Начинаем игру! Ходит игрок с шамой."
                )

                # Подготавливаем ход первого игрока
                player = match_state.players[match_state.current_player_index]
                
                # Отправляем первому игроку его карты и приглашение сделать ход
                await send_player_cards(player, match_state)
                
            except Exception as e:
                logger.error(f"Ошибка при установке козыря: {e}")
                await query.message.reply_text(f"Произошла ошибка: {e}")
                
        except Exception as e:
            logger.error(f"Ошибка при обработке выбора козыря: {e}")
            await query.message.reply_text(f"Произошла ошибка: {e}")

    elif data.startswith('team_'):
        match_id = PLAYER_TO_GAME[player_id]['id']
        team = data.split('_')[1]
        if len(WAITING_MATCHES[match_id][data]) < 2:
            position = int(f"{team}{len(WAITING_MATCHES[match_id][data]) + 1}")
            await query.edit_message_text(
                text=f"{query.message.text}\n\nВы выбрали: Команду {team} ({WAITING_MATCHES[match_id][data]})",
                reply_markup=None  # Удаляем клавиатуру после выбора
            )
        else:
            team = 1 if team == 2 else 2
            position = int(f"{team}{len(WAITING_MATCHES[match_id][f'team_{team}']) + 1}")
            await query.edit_message_text(
                text=f"{query.message.text}\n\nВыбранная комнда заполнена, добавили Вас в Команду {team} ({WAITING_MATCHES[match_id][f'team_{team}']})",
                reply_markup=None  # Удаляем клавиатуру после выбора
            )

        
        WAITING_MATCHES[match_id][data].append(f'{first_name} ({username})')
        PLAYER_TO_GAME[player_id]['position'] = position

        # Получаем обновленный список игроков
        players = WAITING_MATCHES[match_id]['players']
        
        # Отправляем сообщения другим игрокам
        for chat_id in players:
            if chat_id > 0:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"🎮 {first_name} присоединился к игре!\n\n"
                            f"Текущие участники ({len(players)}/4):\n"
                            f"Команда 1: {WAITING_MATCHES[match_id]['team_1']}\n"
                            f"Команда 2: {WAITING_MATCHES[match_id]['team_2']}\n\n"
                )
        
        # Если набралось 4 игрока, начинаем игру
        if len(players) == 4:
            message = await context.bot.send_message(
                chat_id=chat_id,
                text="Набралось 4 игрока! Игра начинается..."
            )
            await start_game(message, match_id, players)

async def send_player_cards(player, match_state, is_first=False):
    """Отправляет игроку его карты и инструкции для хода."""
    if player.id < 0:  # Фиктивный игрок (бот)
        return
        
    # Форматируем карты игрока
    hand = player.get_hand()
    cards_text = " ".join([f"{card}" for card in hand])
    
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
        if match_state.current_player_index and player.id == match_state.players[match_state.current_player_index].id:
            # Если сейчас ход этого игрока
            message_text = (f"🃏 Ваши карты:\n{cards_text}\n\n"
                            f"Статус игры:\n"
                            f"{match_state.players[GameConstants.PLAYER_1_1]} и "
                            f"{match_state.players[GameConstants.PLAYER_1_2]} - счет: "
                            f"{match_state.match_scores[GameConstants.TEAM_1]}\n"
                            f"{match_state.players[GameConstants.PLAYER_2_1]} и "
                            f"{match_state.players[GameConstants.PLAYER_2_2]} - счет: "
                            f"{match_state.match_scores[GameConstants.TEAM_2]}\n"
                            f"Козырь: {GameConstants.SUIT_SYMBOLS[match_state.trump]}, хвалил: "
                            f"{match_state.players[match_state.first_player_index]}\n"
                            f"Номер хода: {match_state.current_turn}\n"
                            f"Карты на столе: {match_state.show_table()}\n"
                            f"Сейчас ваш ход! Выберите карту:"
            )
            
            # Создаем кнопки для выбора карт (максимум 3 карты в ряду)
            buttons = []
            current_row = []
            
            for i, card in enumerate(hand):
                current_row.append(InlineKeyboardButton(
                    text=f"{card}", 
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
                f"Сейчас ход игрока {current_player_name}."
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
        logger.error(f"Ошибка при отправке карт игроку {player.name} (ID: {player.id}): {e}")

async def send_message_to_all_players(match_state, message_text):
    """Отправляет сообщение всем игрокам в личку."""
    bot = Bot(BOT_TOKEN)
    for player_position, player in match_state.players.items():
        if player.id > 0:  # Только реальным игрокам
            try:
                await bot.send_message(chat_id=player.id, text=message_text)
            except Exception as e:
                logger.error(f"Ошибка при отправке сообщения игроку {player.name} (ID: {player.id}): {e}")

async def start_game_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /help."""
    logger.info(f"Получена команда /start_game от пользователя {update.effective_user.username}")
    
    player_id = update.effective_user.id
    match_id = PLAYER_TO_GAME[player_id]['id']
    players = WAITING_MATCHES[match_id]['players']

    await start_game(update.message, match_id, players)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /help."""
    logger.info(f"Получена команда /help от пользователя {update.effective_user.username}")
    
    help_text = (
        "Доступные команды:\n"
        "/start - Начать использование бота\n"
        "/help - Показать это сообщение\n"
        "/ping - Проверить работу бота\n"
        "/info - Показать информацию о боте\n"
        "/create_game - Создать новую игру\n"
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

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /status для отображения статуса игры."""
    logger.info(f"Получена команда /status от пользователя {update.effective_user.id}")
    
    player_id = update.effective_user.id
    
    # Проверяем, есть ли активная игра в чате
    if player_id in PLAYER_TO_GAME and PLAYER_TO_GAME[player_id]['status'] == 'active':
        match_state = ACTIVE_MATCHES[PLAYER_TO_GAME[player_id]['id']]
        
        # Определяем статус игры и формируем сообщение
        status_text = await format_game_status(match_state)
        
        await update.message.reply_text(status_text)
    elif player_id in PLAYER_TO_GAME and PLAYER_TO_GAME[player_id]['status'] == 'waiting':
        # Есть игра в ожидании
        players = WAITING_MATCHES[PLAYER_TO_GAME[player_id]['id']]['players']
        player_list = "\n".join([f"• {p_data['name']}" for p_data in players.values()])
        
        await update.message.reply_text(
            f"🎮 Игра ожидает игроков.\n\n"
            f"Текущие участники ({len(players)}/4):\n{player_list}\n\n"
            f"Игра начнется, когда присоединятся 4 игрока."
        )
    else:
        # Нет игры в этом чате
        await update.message.reply_text(
            "Вы не состоите в игре.\n"
            "Используйте /create_game - для создания новой игры"
            "Используйте инвайт ссылку - для присоединения к игре"
        )

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /stats для отображения статистики игрока."""
    logger.info(f"Получена команда /stats от пользователя {update.effective_user.id}")
    
    player_id = update.effective_user.id
    
    # Получаем статистику игрока из хранилища
    player_stats = await storage.get_player_stats(player_id)
    
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

async def add_bot(update: Update) -> None:
    """Обработчик команды /add_bot для добавления бота в игру."""
    logger.info(f"Получена команда /add_bot от пользователя {update.effective_user.id}")
    
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик текстовых сообщений."""
    logger.info(f"Получено текстовое сообщение от пользователя {update.effective_user.id}: {update.message.text[:30]}...")
    await update.message.reply_text(
        "Я понимаю только команды, начинающиеся с /\n"
        "Отправьте /help чтобы увидеть список доступных команд."
    )

async def format_game_status(match_state):
    """Форматирует текущий статус игры для отображения."""
    status_codes = {
        GameConstants.Status.WAITING_PLAYERS: "Ожидание игроков",
        GameConstants.Status.PLAYERS_ADDED: "Все игроки добавлены",
        GameConstants.Status.CARDS_DEALT: "Карты розданы",
        GameConstants.Status.WAITING_TRUMP: "Ожидание выбора козыря",
        GameConstants.Status.TRUMP_SELECTED: "Козырь выбран",
        GameConstants.Status.PLAYING_CARDS: "Игра идет",
        GameConstants.Status.PLAYED_CARD_1: "1 карта на столе",
        GameConstants.Status.PLAYED_CARD_2: "2 карты на столе",
        GameConstants.Status.PLAYED_CARD_3: "3 карты на столе",
        GameConstants.Status.TRICK_COMPLETED: "Кон завершен",
        GameConstants.Status.GAME_COMPLETED: "Игра завершена",
        GameConstants.Status.NEW_DEAL_READY: "Готовы к новой раздаче",
        GameConstants.Status.MATCH_COMPLETED: "Матч завершен",
        GameConstants.Status.GAME_FINISHED: "Игра полностью завершена"
    }
    
    status_text = f"🎮 Статус игры: {status_codes.get(match_state.status, 'Неизвестный')}\n\n"
    
    # Добавляем информацию об игроках
    status_text += "Игроки:\n"
    for pos, player in match_state.players.items():
        team = "1" if pos // 10 == 1 else "2"
        status_text += f"• Команда {team}: {player.name}"
        if pos == match_state.first_player_index:
            status_text += " (шама)"
        if pos == match_state.current_player_index:
            status_text += " (ходит)"
        status_text += "\n"
    
    # Добавляем информацию о козыре
    if match_state.trump:
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
        application.add_handler(CommandHandler("start_game", start_game_command))
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
        
        # Сначала очищаем все предыдущие сессии, ЗАЧЕМ?
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
