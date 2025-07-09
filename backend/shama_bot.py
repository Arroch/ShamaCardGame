import logging
import json
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler
)
from game_logic import GameEngine, Player

# Настройка логгирования
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Форматтер для файла
file_formatter = logging.Formatter('{"time": "%(asctime)s", "level": "%(levelname)s", "message": "%(message)s"}', datefmt='%Y-%m-%d %H:%M:%S')

# Форматтер для консоли
console_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%H:%M:%S')

# Обработчик для файла
file_handler = logging.FileHandler('game_logs.json')
file_handler.setFormatter(file_formatter)

# Обработчик для консоли
console_handler = logging.StreamHandler()
console_handler.setFormatter(console_formatter)

# Добавляем обработчики
logger.addHandler(file_handler)
logger.addHandler(console_handler)

# Состояния бота
LOBBY, CHOOSE_TEAM, CHOOSE_TRUMP, GAME = range(4)

# Хранилище игровых сессий
game_sessions = {}

import time

class GameSession:
    def __init__(self, creator_id):
        self.match_id = f"{int(time.time())}{creator_id}"
        self.creator_id = creator_id
        self.players = {}
        self.teams = {1: [], 2: []}
        self.engine = GameEngine()
        self.invite_link = f"https://t.me/ShamaGameBot?start={self.match_id}"
        self.state = "LOBBY"  # LOBBY, IN_GAME

    def add_player(self, user_id, username, team, private_chat_id):
        if user_id in self.players:
            return False
        
        if len(self.teams[team]) >= 2:
            return False  # В команде уже 2 игрока
        
        player_id = len(self.players) + 1
        player = Player(player_id, team)
        player.user_id = user_id
        player.username = username
        player.private_chat_id = private_chat_id
        
        self.players[user_id] = player
        self.teams[team].append(user_id)
        self.engine.state.add_player(player)
        return True

    def get_team_players(self, team):
        return [self.players[user_id].username for user_id in self.teams[team]]

    def start_game(self):
        if len(self.players) < 4:
            return False
        
        self.engine.start_game()
        self.state = "IN_GAME"
        return True

    def get_shama(self):
        return self.players[self.creator_id]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args
    private_chat_id = update.effective_chat.id
    logger.debug(f"start: user={user.id}, args={args}, private_chat_id={private_chat_id}")
    
    if args:
        # Присоединение к игре по ссылке
        match_id = args[0]
        if match_id in game_sessions:
            session = game_sessions[match_id]
            
            # Проверяем свободные команды
            available_teams = []
            if len(session.teams[1]) < 2:
                available_teams.append(1)
            if len(session.teams[2]) < 2:
                available_teams.append(2)
                
            if not available_teams:
                await update.message.reply_text("Все команды заполнены!")
                return ConversationHandler.END
                
            # Если доступна только одна команда - добавляем автоматически
            if len(available_teams) == 1:
                team = available_teams[0]
                if session.add_player(user.id, user.username, team, private_chat_id):
                    team_players = session.get_team_players(team)
                    await update.message.reply_text(
                        f"Вы присоединились к команде {team}! Игроки в команде: {', '.join(team_players)}\n"
                        f"Ожидаем начала игры. Игроков: {len(session.players)}/4"
                    )
                    return LOBBY
                else:
                    await update.message.reply_text("Ошибка присоединения к игре")
                    return ConversationHandler.END
            else:
                # Предлагаем выбрать команду
                keyboard = [
                    [InlineKeyboardButton("Команда 1", callback_data=f"team_1_{match_id}")],
                    [InlineKeyboardButton("Команда 2", callback_data=f"team_2_{match_id}")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                # Показываем состав команд
                team1_players = session.get_team_players(1)
                team2_players = session.get_team_players(2)
                
                await update.message.reply_text(
                    f"Выберите команду:\n\n"
                    f"Команда 1: {', '.join(team1_players) if team1_players else 'пусто'}\n"
                    f"Команда 2: {', '.join(team2_players) if team2_players else 'пусто'}",
                    reply_markup=reply_markup
                )
                context.user_data['match_id'] = match_id
                return CHOOSE_TEAM
        else:
            await update.message.reply_text("Игра не найдена")
            return ConversationHandler.END
    else:
        # Создание новой игры
        session = GameSession(user.id)
        game_sessions[session.match_id] = session
        if session.add_player(user.id, user.username, 1, private_chat_id):
            await update.message.reply_text(
                f"Игра создана! Пригласите друзей: {session.invite_link}\n"
                f"Вы в команде 1. Игроков: 1/4"
            )
            return LOBBY
        else:
            await update.message.reply_text("Ошибка создания игры")
            return ConversationHandler.END

async def play_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    logger.debug(f"play_card: query.data={query.data}, user={query.from_user.id}")
    
    user_id = query.from_user.id
    card_index = int(query.data.split("_")[1])
    
    # Найти игровую сессию по ID пользователя
    session = None
    for s in game_sessions.values():
        if user_id in s.players:
            session = s
            break
    logger.debug(f"Найдена сессия: {session.match_id if session else 'None'}")
    
    if not session:
        await query.edit_message_text(text="Игра не найдена!")
        return GAME
    
    player = session.players.get(user_id)
    if not player:
        await query.edit_message_text(text="Вы не участвуете в этой игре!")
        return GAME
    
    try:
        # Совершаем ход
        session.engine.play_turn(player.id, card_index)
        
        # Обновляем сообщение с картами
        keyboard = []
        for i, card in enumerate(player.hand):
            keyboard.append([InlineKeyboardButton(str(card), callback_data=f"play_{i}")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            text="Ваши карты:",
            reply_markup=reply_markup
        )
        
        # Обновляем состояние стола для всех игроков
        table_cards = session.engine.state.current_trick
        table_state = ", ".join(str(card) for card in table_cards) if table_cards else "пусто"
        for p in session.players.values():
            await context.bot.send_message(
                chat_id=p.private_chat_id,
                text=f"Козырь: {session.engine.state.get_trump_suit()}\nНа столе: {table_state}"
            )
        
        # Проверяем завершение игры
        if len(session.engine.state.tricks[1]) + len(session.engine.state.tricks[2]) == 9:
            # Подсчет и вывод результатов
            team1_score = session.engine.state.scores.get(1, 0)
            team2_score = session.engine.state.scores.get(2, 0)
            
            # Расчет финальных очков по правилам Шамы
            six_clubs_team = session.engine.state.six_clubs_team
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
            
            # Формируем результат
            result = (
                "Игра завершена!\n"
                f"Команда 1: {final_scores[1]} очков\n"
                f"Команда 2: {final_scores[2]} очков\n\n"
            )
            
            # Определение победителя
            if final_scores[1] > final_scores[2]:
                result += "Победила команда 1!"
            elif final_scores[2] > final_scores[1]:
                result += "Победила команда 2!"
            else:
                result += "Ничья!"
                
            # Рассылаем результаты всем игрокам
            for p in session.players.values():
                await context.bot.send_message(
                    chat_id=p.private_chat_id,
                    text=result
                )
            
            return ConversationHandler.END
        
        # Уведомляем о следующем ходе
        next_player_id = session.engine.state.players[session.engine.state.current_player_index].id
        next_player = next(p for p in session.players.values() if p.id == next_player_id)
        
        await context.bot.send_message(
            chat_id=next_player.private_chat_id,
            text="Ваш ход! Выберите карту:"
        )
        
    except Exception as e:
        await query.edit_message_text(text=f"Ошибка: {str(e)}")
    
    return GAME
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Игра отменена')
    return ConversationHandler.END

async def choose_team(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик выбора команды"""
    query = update.callback_query
    await query.answer()
    logger.debug(f"choose_team: query.data={query.data}, user={query.from_user.id}")
    
    data = query.data.split('_')
    team = int(data[1])
    match_id = data[2]
    user = query.from_user
    private_chat_id = query.message.chat_id
    
    if match_id not in game_sessions:
        await query.edit_message_text(text="Игра не найдена!")
        return ConversationHandler.END
        
    session = game_sessions[match_id]
    
    if session.add_player(user.id, user.username, team, private_chat_id):
        team_players = session.get_team_players(team)
        await query.edit_message_text(
            f"Вы присоединились к команде {team}! Игроки в команде: {', '.join(team_players)}\n"
            f"Ожидаем начала игры. Игроков: {len(session.players)}/4"
        )
        return LOBBY
    else:
        await query.edit_message_text("Не удалось присоединиться к команде. Возможно, команда уже заполнена.")
        return ConversationHandler.END

async def start_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик начала игры"""
    user = update.effective_user
    private_chat_id = update.effective_chat.id
    logger.debug(f"start_game: user={user.id}, private_chat_id={private_chat_id}")
    
    # Найти игру по ID создателя
    session = None
    for s in game_sessions.values():
        if s.creator_id == user.id:
            session = s
            break
    logger.debug(f"Найдена сессия для создателя: {session.match_id if session else 'None'}")
    
    if not session:
        await update.message.reply_text("Игра не найдена!")
        return LOBBY
    
    if len(session.players) < 4:
        await update.message.reply_text("Недостаточно игроков! Нужно 4 человека")
        return LOBBY
    
    if session.start_game():
        shama = session.get_shama()
        
        # Формируем информацию о командах
        team1_players = ", ".join(session.get_team_players(1))
        team2_players = ", ".join(session.get_team_players(2))
        match_info = (
            f"Игра №{session.match_id}\n"
            f"Команды: {team1_players} vs {team2_players}\n"
            f"Шама: {shama.username}"
        )
        
        # Рассылаем уведомление всем игрокам
        for player in session.players.values():
            await context.bot.send_message(
                chat_id=player.private_chat_id,
                text=f"{match_info}\nИгра началась! Шама выбирает козырь..."
            )
        
        # Шама выбирает козырь
        keyboard = [
            [InlineKeyboardButton("♠", callback_data="trump_0")],
            [InlineKeyboardButton("♥", callback_data="trump_1")],
            [InlineKeyboardButton("♦", callback_data="trump_2")],
            [InlineKeyboardButton("♣", callback_data="trump_3")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await context.bot.send_message(
            chat_id=shama.private_chat_id,
            text="Выберите козырь:",
            reply_markup=reply_markup
        )
        
        context.user_data['match_id'] = session.match_id
        return CHOOSE_TRUMP
    else:
        await update.message.reply_text("Ошибка начала игры")
        return LOBBY

async def choose_trump(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик выбора козыря"""
    query = update.callback_query
    await query.answer()
    logger.debug(f"choose_trump: query.data={query.data}, match_id={context.user_data.get('match_id')}")
    
    trump_index = int(query.data.split("_")[1])
    match_id = context.user_data['match_id']
    
    if match_id not in game_sessions:
        await query.edit_message_text(text="Игра не найдена!")
        return ConversationHandler.END
        
    session = game_sessions[match_id]
    session.engine.state.trump_suit = trump_index
    
    # Уведомляем всех игроков о козыре
    suits = ["♠", "♥", "♦", "♣"]
    for player in session.players.values():
        await context.bot.send_message(
            chat_id=player.private_chat_id,
            text=f"Козырь: {suits[trump_index]}\nНа столе: пусто"
        )
    
    # Рассылаем карты игрокам
    for player in session.players.values():
        keyboard = []
        for i, card in enumerate(player.hand):
            keyboard.append([InlineKeyboardButton(str(card), callback_data=f"play_{i}")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(
            chat_id=player.private_chat_id,
            text="Ваши карты:",
            reply_markup=reply_markup
        )
    
    await query.edit_message_text(text=f"Выбран козырь: {suits[trump_index]}")
    return GAME

def main():
    token = os.environ.get("BOT_TOKEN")
    if not token:
        print("Ошибка: переменная окружения BOT_TOKEN не установлена")
        print("Пожалуйста, установите токен бота командой:")
        print("export BOT_TOKEN='ваш_токен'")
        return
    
    application = Application.builder().token(token).build()
    
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            LOBBY: [
                CommandHandler('start', start),
                CommandHandler('startgame', start_game),
                CommandHandler('cancel', cancel)
            ],
            CHOOSE_TEAM: [
                CallbackQueryHandler(choose_team, pattern="^team_")
            ],
            CHOOSE_TRUMP: [
                CallbackQueryHandler(choose_trump, pattern="^trump_")
            ],
            GAME: [
                CallbackQueryHandler(play_card),
                CommandHandler('cancel', cancel)
            ]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    
    application.add_handler(conv_handler)
    application.run_polling()

if __name__ == '__main__':
    main()
